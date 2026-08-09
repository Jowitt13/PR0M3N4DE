"""Run only a contract-gated, injected single-page controlled live canary."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import urlsplit

from check_source_access import load_json_object
from execute_controlled_crawl_replay import _schema_codes
from prepare_controlled_crawl_runtime_dry_run import prepare_controlled_crawl_runtime_dry_run
from validate_controlled_crawl_plan import validate_controlled_crawl_plan

JsonObject = Mapping[str, Any]
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
PLAN_SCHEMA = REFERENCES / "controlled-crawl-plan.schema.json"
DRY_RUN_SCHEMA = REFERENCES / "controlled-crawl-runtime-dry-run.schema.json"
CANARY_SCHEMA = REFERENCES / "controlled-crawl-live-canary.schema.json"
REGISTRY = REFERENCES / "source-access-registry.json"
LOCK = REFERENCES / "external-dependency-lock.json"


class LiveCanaryResult(TypedDict):
    contract_version: Literal["1.0.0"]
    ok: bool
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"]
    plan_id: str | None
    source_domain: str | None
    registry_version: str | None
    attempt_count: int
    retry_count: Literal[0]
    reason_codes: list[str]
    runtime_diagnostic: RuntimeDiagnostic | None
    records: list[dict[str, object]]


LiveCanaryTransport = Callable[[Mapping[str, object]], Mapping[str, object]]
RuntimeDiagnosticCategory = Literal[
    "worker_process",
    "worker_output",
    "renderer_navigation",
    "renderer_runtime",
]
RuntimeDiagnosticStage = Literal[
    "worker_invocation",
    "worker_result",
    "crawl4ai_import",
    "browser_configuration",
    "crawler_session",
    "page_render",
    "unclassified",
]


class RuntimeDiagnostic(TypedDict):
    """Allowlisted local runtime state with no exception detail or page data."""

    category: RuntimeDiagnosticCategory
    stage: RuntimeDiagnosticStage


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _identity(plan: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    plan_id = plan.get("plan_id")
    domain = plan.get("source_domain")
    version = plan.get("registry_version")
    return (
        plan_id if isinstance(plan_id, str) and plan_id.startswith("CCP-") else None,
        domain if isinstance(domain, str) and domain.replace(".", "").replace("-", "").isalnum() else None,
        version if isinstance(version, str) and version.count(".") == 2 else None,
    )


def _result(
    plan: Mapping[str, Any],
    *,
    ok: bool,
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"],
    codes: Sequence[str],
    attempt_count: int = 0,
    runtime_diagnostic: RuntimeDiagnostic | None = None,
    records: Sequence[dict[str, object]] = (),
) -> LiveCanaryResult:
    plan_id, domain, version = _identity(plan)
    return {"contract_version": "1.0.0", "ok": ok, "outcome": outcome, "plan_id": plan_id, "source_domain": domain, "registry_version": version, "attempt_count": attempt_count, "retry_count": 0, "reason_codes": sorted(set(codes)), "runtime_diagnostic": runtime_diagnostic, "records": list(records)}


def _finalize(result: LiveCanaryResult, schema: JsonObject) -> LiveCanaryResult:
    if not _schema_codes(result, schema, "LiveCanaryResult"):
        return result
    return {"contract_version": "1.0.0", "ok": False, "outcome": "blocked", "plan_id": None, "source_domain": None, "registry_version": None, "attempt_count": 0, "retry_count": 0, "reason_codes": ["LIVE_CANARY_RESULT_SCHEMA_INVALID"], "runtime_diagnostic": None, "records": []}


def _runtime_diagnostic(category: RuntimeDiagnosticCategory, stage: RuntimeDiagnosticStage) -> RuntimeDiagnostic:
    """Build the only runtime-health data that may leave the worker boundary."""

    return {"category": category, "stage": stage}


def _runtime_exception_result(stage: object) -> tuple[str, RuntimeDiagnostic]:
    """Map a worker stage to an allowlisted, non-retaining result diagnostic."""

    if stage == "crawl4ai_import":
        return "RUNTIME_CRAWL4AI_IMPORT_FAILED", _runtime_diagnostic("renderer_runtime", "crawl4ai_import")
    if stage == "browser_configuration":
        return "RUNTIME_BROWSER_CONFIGURATION_FAILED", _runtime_diagnostic("renderer_runtime", "browser_configuration")
    if stage == "crawler_session":
        return "RUNTIME_CRAWLER_SESSION_FAILED", _runtime_diagnostic("renderer_runtime", "crawler_session")
    if stage == "page_render":
        return "RUNTIME_RENDER_FAILED", _runtime_diagnostic("renderer_runtime", "page_render")
    return "RUNTIME_EXCEPTION", _runtime_diagnostic("renderer_runtime", "unclassified")


# ARCH-066: fixed mapping for the worker's sanitized non-zero exit envelope.
# Stage tokens reuse the exact ARCH-060/061 renderer_runtime pairs above;
# process tokens stay in the allowlisted worker_process/worker_invocation pair.
WORKER_EXIT_STAGE_REASONS: dict[str, RuntimeDiagnosticStage] = {
    "crawl4ai_import_failed": "crawl4ai_import",
    "browser_configuration_failed": "browser_configuration",
    "crawler_session_failed": "crawler_session",
    "page_render_failed": "page_render",
}
WORKER_EXIT_PROCESS_CODES: dict[str, str] = {
    "request_load_failed": "RUNTIME_WORKER_REQUEST_LOAD_FAILED",
    "request_contract_invalid": "RUNTIME_WORKER_REQUEST_CONTRACT_INVALID",
    "worker_local_failure": "RUNTIME_WORKER_LOCAL_FAILURE",
}


def _worker_exit_envelope_result(reason: object) -> tuple[str, RuntimeDiagnostic]:
    """Map one validated exit-envelope token to allowlisted codes only.

    An unknown or non-string token keeps the existing conservative
    worker-execution result; the token itself is never echoed.
    """

    if isinstance(reason, str) and reason in WORKER_EXIT_STAGE_REASONS:
        return _runtime_exception_result(WORKER_EXIT_STAGE_REASONS[reason])
    if isinstance(reason, str) and reason in WORKER_EXIT_PROCESS_CODES:
        return WORKER_EXIT_PROCESS_CODES[reason], _runtime_diagnostic("worker_process", "worker_invocation")
    return "RUNTIME_WORKER_EXECUTION_FAILED", _runtime_diagnostic("worker_process", "worker_invocation")


def _https_host(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port or parts.fragment:
        return None
    return parts.hostname


def _controlled_source(registry: JsonObject, domain: object) -> Mapping[str, Any] | None:
    """Resolve the exact controlled_crawl_allowed registry record for a domain."""

    sources = registry.get("sources")
    if not isinstance(sources, list) or not isinstance(domain, str):
        return None
    for item in sources:
        if isinstance(item, Mapping) and item.get("domain") == domain and item.get("status") == "controlled_crawl_allowed":
            return item
    return None


class _CanaryTarget(TypedDict):
    seed_url: str
    terms_url: str
    robots_url: str
    allowed_fields: frozenset[str]
    minimum_delay_ms: int


def _canary_target(plan: Mapping[str, Any], source: Mapping[str, Any] | None) -> tuple[str | None, _CanaryTarget | None]:
    """Derive the one reviewed seed/terms/robots target strictly from the registry."""

    pages = plan.get("requested_pages")
    if source is None or not isinstance(pages, list) or len(pages) != 1:
        return "CANARY_SOURCE_OR_PAGE_BUDGET_FORBIDDEN", None
    contract = _mapping(source.get("controlled_crawl")) or {}
    seed_urls = contract.get("seed_urls")
    fields = contract.get("allowed_text_fields")
    delay = contract.get("minimum_delay_ms")
    terms_url = source.get("official_terms_url")
    robots_url = source.get("official_robots_url")
    if not isinstance(seed_urls, list) or not isinstance(fields, list) or not fields or not isinstance(terms_url, str) or not isinstance(robots_url, str) or isinstance(delay, bool) or not isinstance(delay, int):
        return "CANARY_SOURCE_OR_PAGE_BUDGET_FORBIDDEN", None
    if len(seed_urls) != 1:
        return "CANARY_SOURCE_SEED_CARDINALITY_FORBIDDEN", None
    page = _mapping(pages[0])
    seed = page.get("url") if page is not None else None
    if page is None or not isinstance(seed, str) or seed not in seed_urls:
        return "CANARY_SEED_NOT_APPROVED", None
    if page.get("depth") != 0 or page.get("parent_page_id") is not None:
        return "CANARY_DEPTH_OR_PARENT_FORBIDDEN", None
    if plan.get("minimum_delay_ms") != delay:
        return "CANARY_DELAY_MISMATCH", None
    host = _https_host(seed)
    if host is None or _https_host(terms_url) != host or _https_host(robots_url) != host or robots_url != f"https://{host}/robots.txt":
        return "CANARY_SOURCE_OR_PAGE_BUDGET_FORBIDDEN", None
    return None, {"seed_url": seed, "terms_url": terms_url, "robots_url": robots_url, "allowed_fields": frozenset(item for item in fields if isinstance(item, str)), "minimum_delay_ms": delay}


def _observation_result(plan: Mapping[str, Any], observation: Mapping[str, Any]) -> tuple[LiveCanaryResult | None, Mapping[str, Any] | None, str | None]:
    """Map only reviewed, non-retaining transport signals to safe outcomes."""

    transport_failure = observation.get("transport_failure")
    if transport_failure == "worker_exit_envelope":
        code, diagnostic = _worker_exit_envelope_result(observation.get("worker_exit_reason"))
        return _result(plan, ok=False, outcome="insufficiency", codes=[code], attempt_count=1, runtime_diagnostic=diagnostic), None, None
    transport_codes: dict[object, tuple[str, RuntimeDiagnostic]] = {
        "worker_timeout": ("RUNTIME_WORKER_TIMEOUT", _runtime_diagnostic("worker_process", "worker_invocation")),
        "worker_execution_failed": ("RUNTIME_WORKER_EXECUTION_FAILED", _runtime_diagnostic("worker_process", "worker_invocation")),
        "worker_output_malformed": ("WORKER_OUTPUT_MALFORMED", _runtime_diagnostic("worker_output", "worker_result")),
        # ARCH-067: fixed launch/supervision/exit-boundary attribution; the
        # signals stay allowlisted tokens and never carry local details.
        "worker_spawn_failed": ("RUNTIME_WORKER_SPAWN_FAILED", _runtime_diagnostic("worker_process", "worker_invocation")),
        "worker_supervision_failed": ("RUNTIME_WORKER_SUPERVISION_FAILED", _runtime_diagnostic("worker_process", "worker_invocation")),
        "worker_unexpected_exit_status": ("RUNTIME_WORKER_UNEXPECTED_EXIT_STATUS", _runtime_diagnostic("worker_process", "worker_invocation")),
        "worker_exit_output_invalid": ("RUNTIME_WORKER_EXIT_OUTPUT_INVALID", _runtime_diagnostic("worker_output", "worker_result")),
    }
    if transport_failure is not None:
        code, diagnostic = transport_codes.get(transport_failure, ("MALFORMED_WORKER_OBSERVATION", _runtime_diagnostic("worker_output", "worker_result")))
        return _result(plan, ok=False, outcome="insufficiency", codes=[code], attempt_count=1, runtime_diagnostic=diagnostic), None, None

    robots, terms, checked_at = observation.get("robots"), observation.get("terms"), observation.get("checked_at")
    if robots != "allowed":
        return _result(plan, ok=False, outcome="insufficiency", codes=["ROBOTS_DENIED" if robots == "denied" else "ROBOTS_CURRENT_CHECK_UNAVAILABLE"]), None, None
    if terms != "allowed":
        return _result(plan, ok=False, outcome="insufficiency", codes=["TERMS_DENIED" if terms == "denied" else "TERMS_CURRENT_CHECK_UNAVAILABLE"]), None, None
    page = _mapping(observation.get("page"))
    if not isinstance(checked_at, str) or page is None:
        return _result(plan, ok=False, outcome="insufficiency", codes=["MALFORMED_LIVE_OBSERVATION"]), None, None
    return None, page, checked_at


def execute_controlled_crawl_live_canary(payload: JsonObject, plan_schema: JsonObject, dry_run_schema: JsonObject, canary_schema: JsonObject, registry: JsonObject, lock: JsonObject, transport: LiveCanaryTransport | None = None) -> LiveCanaryResult:
    """Validate all local gates and invoke at most one explicitly injected transport."""

    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    plan = _mapping(runtime_input.get("plan")) or {}
    finish = lambda result: _finalize(result, canary_schema)
    plan_result = validate_controlled_crawl_plan(plan, plan_schema, registry)
    if not plan_result["ok"]:
        return finish(_result(plan, ok=False, outcome="blocked", codes=[error["code"] for error in plan_result["errors"]]))
    if payload.get("execution_mode") != "live_canary" or payload.get("live_enabled") is not True:
        return finish(_result(plan, ok=False, outcome="blocked", codes=["LIVE_CANARY_EXPLICIT_ENABLE_REQUIRED"]))
    if _schema_codes(payload, canary_schema, "LiveCanaryInput"):
        return finish(_result(plan, ok=False, outcome="blocked", codes=["LIVE_CANARY_INPUT_SCHEMA_INVALID"]))
    source = _controlled_source(registry, plan.get("source_domain"))
    code, target = _canary_target(plan, source)
    if code is not None or target is None:
        return finish(_result(plan, ok=False, outcome="blocked", codes=[code or "CANARY_SOURCE_OR_PAGE_BUDGET_FORBIDDEN"]))
    dry_run = prepare_controlled_crawl_runtime_dry_run(runtime_input, plan_schema, dry_run_schema, registry, lock)
    if not dry_run["ok"]:
        outcome: Literal["blocked", "dependency_unavailable"] = "dependency_unavailable" if dry_run["outcome"] == "dependency_unavailable" else "blocked"
        return finish(_result(plan, ok=False, outcome=outcome, codes=["RUNTIME_DRY_RUN_NOT_READY", *dry_run["reason_codes"]]))
    if transport is None:
        return finish(_result(plan, ok=False, outcome="blocked", codes=["LIVE_CANARY_TRANSPORT_NOT_CONFIGURED"]))
    try:
        observation = transport({"seed_url": target["seed_url"], "terms_url": target["terms_url"], "robots_url": target["robots_url"], "page_budget": 1, "depth": 0, "minimum_delay_ms": target["minimum_delay_ms"], "follow_redirects": False, "retry_count": 0})
    except Exception:
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=["RUNTIME_EXCEPTION"], attempt_count=0, runtime_diagnostic=_runtime_diagnostic("renderer_runtime", "unclassified")))
    blocked, page, checked_at = _observation_result(plan, observation)
    if blocked is not None:
        return finish(blocked)
    assert page is not None and checked_at is not None
    kind = page.get("kind")
    if kind != "response":
        codes = {
            "login": "LOGIN_REQUIRED",
            "paywall": "PAYWALL_BLOCKED",
            "captcha": "CAPTCHA_BLOCKED",
            "cloudflare": "CLOUDFLARE_CHALLENGE",
            "refusal": "EXPLICIT_REFUSAL",
            "redirect": "REDIRECT_FOLLOW_FORBIDDEN",
            "navigation_timeout": "BROWSER_NAVIGATION_TIMEOUT",
            "navigation_failure": "BROWSER_NAVIGATION_FAILED",
            "unexpected_response": "UNEXPECTED_PAGE_RESPONSE",
            "malformed_response": "MALFORMED_PAGE_RESPONSE",
        }
        if kind == "runtime_exception":
            code, diagnostic = _runtime_exception_result(page.get("runtime_stage"))
        elif kind in {"navigation_timeout", "navigation_failure"}:
            code = codes[kind]
            diagnostic = _runtime_diagnostic("renderer_navigation", "page_render")
        else:
            code = codes.get(kind, "MALFORMED_WORKER_OBSERVATION")
            diagnostic = None
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=[code], attempt_count=1, runtime_diagnostic=diagnostic))
    if page.get("http_status") in {401, 403, 429}:
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=[f"HTTP_{page['http_status']}_BLOCKED"], attempt_count=1))
    if page.get("http_status") != 200 or page.get("observed_url") != target["seed_url"]:
        return finish(_result(plan, ok=False, outcome="insufficiency", codes=["REDIRECT_FOLLOW_FORBIDDEN" if page.get("observed_url") != target["seed_url"] else "MALFORMED_LIVE_OBSERVATION"], attempt_count=1))
    short_text = _mapping(page.get("extracted_text"))
    if not short_text or not set(short_text) <= target["allowed_fields"]:
        return finish(_result(plan, ok=False, outcome="blocked", codes=["CANARY_FIELD_FORBIDDEN"], attempt_count=1))
    if any(not isinstance(value, str) or not value.strip() or len(value) > 280 for value in short_text.values()):
        return finish(_result(plan, ok=False, outcome="blocked", codes=["CANARY_CONTENT_FORBIDDEN"], attempt_count=1))
    record = {"source_locator": target["seed_url"], "accessed_at": checked_at, "audit_status": "live_canary_unverified", "source_text_trust": "untrusted_page_content", "instruction_handling": "data_only_ignore_instructions", "short_text": dict(short_text), "team_authored_summary": "Approved short fields were returned by the bounded canary."}
    return finish(_result(plan, ok=True, outcome="completed", codes=["LIVE_CANARY_COMPLETED_SOURCE_UNTRUSTED"], attempt_count=1, records=[record]))


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        payload = load_json_object(arguments.input)
        result = execute_controlled_crawl_live_canary(payload, load_json_object(PLAN_SCHEMA), load_json_object(DRY_RUN_SCHEMA), load_json_object(CANARY_SCHEMA), load_json_object(REGISTRY), load_json_object(LOCK))
    except (OSError, ValueError, json.JSONDecodeError):
        result = {"contract_version": "1.0.0", "ok": False, "outcome": "blocked", "plan_id": None, "source_domain": None, "registry_version": None, "attempt_count": 0, "retry_count": 0, "reason_codes": ["LIVE_CANARY_AUTHORITY_LOAD_FAILED"], "runtime_diagnostic": None, "records": []}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
