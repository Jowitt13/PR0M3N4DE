"""Enforce the explicitly gated, zero-webpage local health probe boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict

import execute_controlled_crawl_live_canary as live_canary_gate
from check_source_access import load_json_object
from execute_controlled_crawl_replay import _schema_codes
from prepare_controlled_crawl_runtime_dry_run import _identity, prepare_controlled_crawl_runtime_dry_run

JsonObject = Mapping[str, Any]
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
PLAN_SCHEMA = REFERENCES / "controlled-crawl-plan.schema.json"
DRY_RUN_SCHEMA = REFERENCES / "controlled-crawl-runtime-dry-run.schema.json"
CANARY_SCHEMA = REFERENCES / "controlled-crawl-live-canary.schema.json"
PROBE_SCHEMA = REFERENCES / "crawl4ai-local-health-probe.schema.json"
REGISTRY = REFERENCES / "source-access-registry.json"
LOCK = REFERENCES / "external-dependency-lock.json"
RUNTIME_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")

# The future supervised worker budget and its strict single-line output limit.
PROBE_TIMEOUT_SECONDS = 30
PROBE_OUTPUT_MAX_LENGTH = 512
PROBE_REQUEST_KEYS = frozenset({"runtime_root"})

ProbeRunner = Callable[[Mapping[str, object], int], str]

ProbeRuntimeStage = Literal["crawl4ai_import", "browser_configuration", "live_configuration", "crawler_session", "browser_launch", "robots_gate"]

# Local probe stages that also carry the merged ARCH-062 health classification.
# ARCH-071's live_configuration and robots_gate stages are probe-only stages
# (the live gate has no matching renderer_runtime stage), like browser_launch.
HEALTH_CLASSIFIED_STAGES: tuple[ProbeRuntimeStage, ...] = (
    "crawl4ai_import",
    "browser_configuration",
    "crawler_session",
)
PROBE_FAILURE_OUTCOMES: dict[str, tuple[str, ProbeRuntimeStage]] = {
    "crawl4ai_import_failed": ("PROBE_CRAWL4AI_IMPORT_FAILED", "crawl4ai_import"),
    "browser_configuration_failed": ("PROBE_BROWSER_CONFIGURATION_FAILED", "browser_configuration"),
    "live_configuration_failed": ("PROBE_LIVE_CONFIGURATION_FAILED", "live_configuration"),
    "live_configuration_cache_mode_incompatible": ("PROBE_LIVE_CONFIGURATION_CACHE_MODE_INCOMPATIBLE", "live_configuration"),
    "live_configuration_parameter_incompatible": ("PROBE_LIVE_CONFIGURATION_PARAMETER_INCOMPATIBLE", "live_configuration"),
    "live_configuration_combination_incompatible": ("PROBE_LIVE_CONFIGURATION_COMBINATION_INCOMPATIBLE", "live_configuration"),
    "crawler_session_failed": ("PROBE_CRAWLER_SESSION_FAILED", "crawler_session"),
    "browser_launch_failed": ("PROBE_BROWSER_LAUNCH_FAILED", "browser_launch"),
    "robots_gate_incompatible": ("PROBE_ROBOTS_GATE_INCOMPATIBLE", "robots_gate"),
}

# ARCH-072: the only worker outcome that may carry a ``parameter`` key, and the
# fixed, statically-defined allowlist of kwarg names that ``parameter`` may take.
# It mirrors the worker's ``LIVE_RUN_CONFIG_KWARGS`` in order and membership; an
# offline drift test binds this tuple, the worker mirror, and the schema enum
# together. A ``parameter`` value outside this allowlist, or present on any
# other outcome, fails closed as malformed output.
LIVE_CONFIGURATION_PARAMETER_OUTCOME = "live_configuration_parameter_incompatible"
LIVE_CONFIGURATION_PARAMETER_ALLOWLIST: tuple[str, ...] = (
    "only_text",
    "excluded_tags",
    "remove_forms",
    "check_robots_txt",
    "page_timeout",
    "wait_until",
    "wait_for_images",
    "screenshot",
    "pdf",
    "capture_mhtml",
    "capture_network_requests",
    "capture_console_messages",
    "process_iframes",
    "scan_full_page",
    "js_code",
    "js_code_before_wait",
    "c4a_script",
    "max_retries",
    "fallback_fetch_function",
)


class ProbeDiagnostic(TypedDict):
    """Allowlisted local probe stage; never an error message or local state."""

    category: Literal["probe_process", "probe_output", "probe_runtime"]
    stage: Literal["probe_invocation", "probe_result", "crawl4ai_import", "browser_configuration", "live_configuration", "crawler_session", "browser_launch", "robots_gate"]


class ProbeResult(TypedDict):
    """Fixed, sanitized probe boundary result; never a page-access claim."""

    contract_version: Literal["1.0.0"]
    ok: bool
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"]
    plan_id: str | None
    source_domain: str | None
    registry_version: str | None
    runtime_id: str | None
    probe_status: Literal["local_probe_not_executed", "local_probe_failed_local_stage", "local_probe_completed_local_stages_only"]
    attempt_count: int
    retry_count: Literal[0]
    probe_diagnostic: ProbeDiagnostic | None
    health_diagnostic_classification: live_canary_gate.RuntimeDiagnostic | None
    incompatible_parameter: str | None
    reason_codes: list[str]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _probe_diagnostic(
    category: Literal["probe_process", "probe_output", "probe_runtime"],
    stage: Literal["probe_invocation", "probe_result", "crawl4ai_import", "browser_configuration", "live_configuration", "crawler_session", "browser_launch", "robots_gate"],
) -> ProbeDiagnostic:
    """Build the only probe-health data that may leave the boundary."""

    return {"category": category, "stage": stage}


def _health_classification(stage: ProbeRuntimeStage) -> live_canary_gate.RuntimeDiagnostic | None:
    """Reuse the ARCH-061/062 gate pair for stages shared with the live worker."""

    if stage not in HEALTH_CLASSIFIED_STAGES:
        return None
    return live_canary_gate._runtime_diagnostic("renderer_runtime", stage)


def _result(
    plan: JsonObject,
    *,
    ok: bool,
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"],
    codes: Sequence[str],
    runtime_id: str | None = None,
    probe_status: Literal["local_probe_not_executed", "local_probe_failed_local_stage", "local_probe_completed_local_stages_only"] = "local_probe_not_executed",
    attempt_count: int = 0,
    probe_diagnostic: ProbeDiagnostic | None = None,
    health_diagnostic_classification: live_canary_gate.RuntimeDiagnostic | None = None,
    incompatible_parameter: str | None = None,
) -> ProbeResult:
    """Build a result carrying only safe identifiers and allowlisted codes."""

    plan_id, source_domain, registry_version = _identity(plan)
    return {
        "contract_version": "1.0.0",
        "ok": ok,
        "outcome": outcome,
        "plan_id": plan_id,
        "source_domain": source_domain,
        "registry_version": registry_version,
        "runtime_id": runtime_id if isinstance(runtime_id, str) and RUNTIME_ID_RE.fullmatch(runtime_id) else None,
        "probe_status": probe_status,
        "attempt_count": attempt_count,
        "retry_count": 0,
        "probe_diagnostic": probe_diagnostic,
        "health_diagnostic_classification": health_diagnostic_classification,
        "incompatible_parameter": incompatible_parameter if isinstance(incompatible_parameter, str) and incompatible_parameter in LIVE_CONFIGURATION_PARAMETER_ALLOWLIST else None,
        "reason_codes": sorted(set(codes)),
    }


def _fallback_result() -> ProbeResult:
    return _result({}, ok=False, outcome="blocked", codes=["PROBE_RESULT_SCHEMA_INVALID"])


def _finalize(result: ProbeResult, probe_schema: JsonObject) -> ProbeResult:
    """Validate every emitted result against the probe result schema."""

    if not _schema_codes(result, probe_schema, "ProbeResult"):
        return result
    fallback = _fallback_result()
    _schema_codes(fallback, probe_schema, "ProbeResult")
    return fallback


def _output_failure(code: str) -> dict[str, object]:
    """Bundle one invoked-probe output failure with its fixed diagnostic."""

    return {
        "ok": False,
        "outcome": "insufficiency",
        "codes": [code],
        "probe_status": "local_probe_failed_local_stage",
        "attempt_count": 1,
        "probe_diagnostic": _probe_diagnostic("probe_output", "probe_result"),
    }


def _invoked_probe_result(output: object) -> dict[str, object]:
    """Map one raw worker output to fixed codes only; never retain its content."""

    if not isinstance(output, str) or len(output) > PROBE_OUTPUT_MAX_LENGTH:
        return _output_failure("PROBE_OUTPUT_MALFORMED")
    if "http" in output.lower():
        return _output_failure("PROBE_NETWORK_INTENT_FORBIDDEN")
    try:
        observation = json.loads(output)
    except json.JSONDecodeError:
        return _output_failure("PROBE_OUTPUT_MALFORMED")
    if not isinstance(observation, Mapping):
        return _output_failure("PROBE_OUTPUT_MALFORMED")
    keys = set(observation)
    if keys == {"outcome"}:
        parameter: object = None
    elif keys == {"outcome", "parameter"}:
        parameter = observation.get("parameter")
    else:
        return _output_failure("PROBE_OUTPUT_MALFORMED")
    outcome = observation.get("outcome")
    if outcome == "completed":
        if parameter is not None:
            return _output_failure("PROBE_OUTPUT_MALFORMED")
        return {
            "ok": True,
            "outcome": "completed",
            "codes": ["PROBE_COMPLETED_LOCAL_STAGES_ONLY"],
            "probe_status": "local_probe_completed_local_stages_only",
            "attempt_count": 1,
        }
    if outcome == LIVE_CONFIGURATION_PARAMETER_OUTCOME:
        if not isinstance(parameter, str) or parameter not in LIVE_CONFIGURATION_PARAMETER_ALLOWLIST:
            return _output_failure("PROBE_OUTPUT_MALFORMED")
        code, stage = PROBE_FAILURE_OUTCOMES[outcome]
        return {
            "ok": False,
            "outcome": "insufficiency",
            "codes": [code],
            "probe_status": "local_probe_failed_local_stage",
            "attempt_count": 1,
            "probe_diagnostic": _probe_diagnostic("probe_runtime", stage),
            "health_diagnostic_classification": _health_classification(stage),
            "incompatible_parameter": parameter,
        }
    if isinstance(outcome, str) and outcome in PROBE_FAILURE_OUTCOMES:
        if parameter is not None:
            return _output_failure("PROBE_OUTPUT_MALFORMED")
        code, stage = PROBE_FAILURE_OUTCOMES[outcome]
        return {
            "ok": False,
            "outcome": "insufficiency",
            "codes": [code],
            "probe_status": "local_probe_failed_local_stage",
            "attempt_count": 1,
            "probe_diagnostic": _probe_diagnostic("probe_runtime", stage),
            "health_diagnostic_classification": _health_classification(stage),
        }
    return _output_failure("PROBE_STATUS_UNKNOWN")


def execute_crawl4ai_local_health_probe(
    payload: JsonObject,
    plan_schema: JsonObject,
    dry_run_schema: JsonObject,
    canary_schema: JsonObject,
    probe_schema: JsonObject,
    registry: JsonObject,
    lock: JsonObject,
    *,
    execute_local_probe: bool = False,
    probe_runner: ProbeRunner | None = None,
) -> ProbeResult:
    """Refuse by default; invoke at most one injected runner after every gate."""

    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    plan = _mapping(runtime_input.get("plan")) or {}
    finish = lambda result: _finalize(result, probe_schema)
    if not execute_local_probe:
        return finish(_result(plan, ok=False, outcome="blocked", codes=["PROBE_EXPLICIT_FLAG_REQUIRED"]))
    if payload.get("execution_mode") != "local_health_probe":
        return finish(_result(plan, ok=False, outcome="blocked", codes=["PROBE_EXECUTION_MODE_FORBIDDEN"]))
    if _schema_codes(payload, probe_schema, "ProbeInput"):
        return finish(_result(plan, ok=False, outcome="blocked", codes=["PROBE_INPUT_SCHEMA_INVALID"]))
    confirmation = _mapping(payload.get("human_confirmation"))
    if confirmation is None or _schema_codes(confirmation, canary_schema, "HumanConfirmation"):
        return finish(_result(plan, ok=False, outcome="blocked", codes=["PROBE_HUMAN_CONFIRMATION_REQUIRED"]))
    dry_run = prepare_controlled_crawl_runtime_dry_run(runtime_input, plan_schema, dry_run_schema, registry, lock)
    if not dry_run["ok"]:
        outcome: Literal["blocked", "dependency_unavailable"] = "dependency_unavailable" if dry_run["outcome"] == "dependency_unavailable" else "blocked"
        return finish(_result(plan, ok=False, outcome=outcome, codes=["PROBE_RUNTIME_DRY_RUN_NOT_READY", *dry_run["reason_codes"]]))
    if probe_runner is None:
        return finish(_result(plan, ok=False, outcome="blocked", codes=["PROBE_RUNNER_NOT_CONFIGURED"], runtime_id=dry_run["runtime_id"]))
    request = {"runtime_root": runtime_input.get("runtime_root")}
    assert set(request) == PROBE_REQUEST_KEYS
    try:
        output: object = probe_runner(request, PROBE_TIMEOUT_SECONDS)
    except TimeoutError:
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=["PROBE_WORKER_TIMEOUT"], runtime_id=dry_run["runtime_id"], probe_status="local_probe_failed_local_stage", attempt_count=1, probe_diagnostic=_probe_diagnostic("probe_process", "probe_invocation")))
    except Exception:
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=["PROBE_WORKER_EXECUTION_FAILED"], runtime_id=dry_run["runtime_id"], probe_status="local_probe_failed_local_stage", attempt_count=1, probe_diagnostic=_probe_diagnostic("probe_process", "probe_invocation")))
    fields = _invoked_probe_result(output)
    return finish(_result(plan, runtime_id=dry_run["runtime_id"], **fields))  # type: ignore[arg-type]


def _authority_load_failure() -> ProbeResult:
    return _result({}, ok=False, outcome="blocked", codes=["PROBE_AUTHORITY_LOAD_FAILED"])


def main(argv: Sequence[str]) -> int:
    """Run the gated boundary from local JSON; the CLI never supplies a runner."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--execute-local-probe", action="store_true")
    arguments = parser.parse_args(argv[1:])
    try:
        payload = load_json_object(arguments.input)
        result = execute_crawl4ai_local_health_probe(
            payload,
            load_json_object(PLAN_SCHEMA),
            load_json_object(DRY_RUN_SCHEMA),
            load_json_object(CANARY_SCHEMA),
            load_json_object(PROBE_SCHEMA),
            load_json_object(REGISTRY),
            load_json_object(LOCK),
            execute_local_probe=arguments.execute_local_probe,
            probe_runner=None,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        result = _authority_load_failure()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
