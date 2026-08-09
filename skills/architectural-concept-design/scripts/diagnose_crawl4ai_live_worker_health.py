"""Classify one sanitized live-worker diagnostic and recheck local runtime health offline."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
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
DIAGNOSTIC_SCHEMA = REFERENCES / "crawl4ai-live-worker-health-diagnostic.schema.json"
REGISTRY = REFERENCES / "source-access-registry.json"
LOCK = REFERENCES / "external-dependency-lock.json"
RUNTIME_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")

# ARCH-061 reason codes whose diagnostics the launcher/gate builds outside
# ``_runtime_exception_result``; the pairs themselves still come from the gate.
# ARCH-066 adds the sanitized worker exit-envelope process codes.
# ARCH-067 adds the launch/supervision/exit-boundary attribution codes.
WORKER_PROCESS_REASON_CODES = (
    "RUNTIME_WORKER_TIMEOUT",
    "RUNTIME_WORKER_EXECUTION_FAILED",
    "RUNTIME_WORKER_REQUEST_LOAD_FAILED",
    "RUNTIME_WORKER_REQUEST_CONTRACT_INVALID",
    "RUNTIME_WORKER_LOCAL_FAILURE",
    "RUNTIME_WORKER_SPAWN_FAILED",
    "RUNTIME_WORKER_SUPERVISION_FAILED",
    "RUNTIME_WORKER_UNEXPECTED_EXIT_STATUS",
)
WORKER_OUTPUT_REASON_CODES = (
    "WORKER_OUTPUT_MALFORMED",
    "MALFORMED_WORKER_OBSERVATION",
    "RUNTIME_WORKER_EXIT_OUTPUT_INVALID",
)
RENDERER_NAVIGATION_REASON_CODES = ("BROWSER_NAVIGATION_TIMEOUT", "BROWSER_NAVIGATION_FAILED")
RENDERER_RUNTIME_STAGES: tuple[live_canary_gate.RuntimeDiagnosticStage, ...] = (
    "crawl4ai_import",
    "browser_configuration",
    "crawler_session",
    "page_render",
    "unclassified",
)


class HealthDiagnosticResult(TypedDict):
    """Fixed, sanitized offline health report; never a page-access conclusion."""

    contract_version: Literal["1.0.0"]
    ok: bool
    outcome: Literal["diagnosed_offline", "blocked", "dependency_unavailable"]
    plan_id: str | None
    source_domain: str | None
    registry_version: str | None
    runtime_id: str | None
    runtime_health: Literal["receipt_and_local_layout_validated_dry_run_only", "not_available_or_not_validated"]
    probe_status: Literal["local_probe_not_executed"]
    diagnostic_classification: live_canary_gate.RuntimeDiagnostic | None
    reason_codes: list[str]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def expected_reason_code_diagnostics() -> dict[str, live_canary_gate.RuntimeDiagnostic]:
    """Derive the fixed ARCH-061 reason-code/diagnostic audit map from the gate."""

    pairs: dict[str, live_canary_gate.RuntimeDiagnostic] = {}
    for code in WORKER_PROCESS_REASON_CODES:
        pairs[code] = live_canary_gate._runtime_diagnostic("worker_process", "worker_invocation")
    for code in WORKER_OUTPUT_REASON_CODES:
        pairs[code] = live_canary_gate._runtime_diagnostic("worker_output", "worker_result")
    for code in RENDERER_NAVIGATION_REASON_CODES:
        pairs[code] = live_canary_gate._runtime_diagnostic("renderer_navigation", "page_render")
    for stage in RENDERER_RUNTIME_STAGES:
        stage_code, diagnostic = live_canary_gate._runtime_exception_result(stage)
        pairs[stage_code] = diagnostic
    return pairs


def _result(
    plan: JsonObject,
    *,
    ok: bool,
    outcome: Literal["diagnosed_offline", "blocked", "dependency_unavailable"],
    codes: Sequence[str],
    runtime_id: str | None = None,
    healthy: bool = False,
    classification: live_canary_gate.RuntimeDiagnostic | None = None,
) -> HealthDiagnosticResult:
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
        "runtime_health": "receipt_and_local_layout_validated_dry_run_only" if healthy else "not_available_or_not_validated",
        "probe_status": "local_probe_not_executed",
        "diagnostic_classification": classification,
        "reason_codes": sorted(set(codes)),
    }


def _fallback_result() -> HealthDiagnosticResult:
    return _result({}, ok=False, outcome="blocked", codes=["DIAGNOSTIC_RESULT_SCHEMA_INVALID"])


def _finalize(result: HealthDiagnosticResult, diagnostic_schema: JsonObject) -> HealthDiagnosticResult:
    """Validate every emitted result against the diagnostic result schema."""

    if not _schema_codes(result, diagnostic_schema, "HealthDiagnosticResult"):
        return result
    fallback = _fallback_result()
    _schema_codes(fallback, diagnostic_schema, "HealthDiagnosticResult")
    return fallback


def _classification_result(
    payload: JsonObject,
    canary_schema: JsonObject,
) -> tuple[str | None, str | None, live_canary_gate.RuntimeDiagnostic | None]:
    """Map an observed code/pair to (blocking code, audit code, gate-built pair)."""

    observed_code = payload.get("observed_reason_code")
    observed = payload.get("observed_runtime_diagnostic")
    if observed_code is None and observed is None:
        return None, "DIAGNOSTIC_NOT_SUPPLIED", None
    if observed_code is None or observed is None:
        return "DIAGNOSTIC_OBSERVATION_INCOMPLETE", None, None
    if _mapping(observed) is None or _schema_codes(observed, canary_schema, "RuntimeDiagnostic"):
        return "DIAGNOSTIC_PAIR_NOT_ALLOWLISTED", None, None
    expected = expected_reason_code_diagnostics().get(observed_code) if isinstance(observed_code, str) else None
    if expected is None:
        return "DIAGNOSTIC_CODE_NOT_ALLOWLISTED", None, None
    if dict(observed) != dict(expected):
        return "DIAGNOSTIC_CODE_PAIR_MISMATCH", None, None
    return None, "DIAGNOSTIC_PAIR_CONSISTENT", expected


def diagnose_crawl4ai_live_worker_health(
    payload: JsonObject,
    plan_schema: JsonObject,
    dry_run_schema: JsonObject,
    canary_schema: JsonObject,
    diagnostic_schema: JsonObject,
    registry: JsonObject,
    lock: JsonObject,
    *,
    execute_local_probe: bool = False,
) -> HealthDiagnosticResult:
    """Report only offline, allowlisted health facts; never invoke a local probe."""

    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    plan = _mapping(runtime_input.get("plan")) or {}
    if execute_local_probe:
        return _finalize(_result(plan, ok=False, outcome="blocked", codes=["LOCAL_PROBE_EXECUTION_NOT_IMPLEMENTED"]), diagnostic_schema)
    if payload.get("execution_mode") != "local_health_diagnostic":
        return _finalize(_result(plan, ok=False, outcome="blocked", codes=["LOCAL_PROBE_EXECUTION_NOT_IMPLEMENTED"]), diagnostic_schema)
    if _schema_codes(payload, diagnostic_schema, "HealthDiagnosticInput"):
        return _finalize(_result(plan, ok=False, outcome="blocked", codes=["DIAGNOSTIC_INPUT_SCHEMA_INVALID"]), diagnostic_schema)
    blocking_code, audit_code, classification = _classification_result(payload, canary_schema)
    if blocking_code is not None:
        return _finalize(_result(plan, ok=False, outcome="blocked", codes=[blocking_code]), diagnostic_schema)
    assert audit_code is not None
    dry_run = prepare_controlled_crawl_runtime_dry_run(runtime_input, plan_schema, dry_run_schema, registry, lock)
    if not dry_run["ok"]:
        outcome: Literal["blocked", "dependency_unavailable"] = "dependency_unavailable" if dry_run["outcome"] == "dependency_unavailable" else "blocked"
        return _finalize(_result(plan, ok=False, outcome=outcome, codes=["RUNTIME_HEALTH_DRY_RUN_NOT_READY", *dry_run["reason_codes"], audit_code], classification=classification), diagnostic_schema)
    return _finalize(_result(
        plan,
        ok=True,
        outcome="diagnosed_offline",
        codes=["LOCAL_PROBE_NOT_EXECUTED", "RUNTIME_HEALTH_RECEIPT_AND_LAYOUT_VALIDATED", audit_code],
        runtime_id=dry_run["runtime_id"],
        healthy=True,
        classification=classification,
    ), diagnostic_schema)


def _authority_load_failure() -> HealthDiagnosticResult:
    return _result({}, ok=False, outcome="blocked", codes=["DIAGNOSTIC_AUTHORITY_LOAD_FAILED"])


def main(argv: Sequence[str]) -> int:
    """Print one deterministic offline health diagnostic from local JSON only."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--execute-local-probe", action="store_true")
    arguments = parser.parse_args(argv[1:])
    try:
        payload = load_json_object(arguments.input)
        result = diagnose_crawl4ai_live_worker_health(
            payload,
            load_json_object(PLAN_SCHEMA),
            load_json_object(DRY_RUN_SCHEMA),
            load_json_object(CANARY_SCHEMA),
            load_json_object(DIAGNOSTIC_SCHEMA),
            load_json_object(REGISTRY),
            load_json_object(LOCK),
            execute_local_probe=arguments.execute_local_probe,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        result = _authority_load_failure()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
