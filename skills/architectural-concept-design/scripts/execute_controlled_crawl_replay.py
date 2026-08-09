"""Run a local, offline replay of a validated controlled-crawl plan."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from check_source_access import load_json_object
from validate_controlled_crawl_plan import validate_controlled_crawl_plan

JsonObject = Mapping[str, Any]
DEFAULT_PLAN_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "controlled-crawl-plan.schema.json"
DEFAULT_REPLAY_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "controlled-crawl-replay.schema.json"
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "source-access-registry.json"
SUCCESS_STATUS = "offline_replay_unverified"
SOURCE_TEXT_TRUST = "untrusted_page_content"
INSTRUCTION_HANDLING = "data_only_ignore_instructions"
HTTP_DENIAL_STATUSES = {401, 403, 429}


class ReplayResult(TypedDict):
    """Safe deterministic outcome for one local replay."""

    contract_version: Literal["1.0.0"]
    ok: bool
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"]
    plan_id: str | None
    source_domain: str | None
    registry_version: str | None
    processed_page_count: int
    attempt_count: int
    retry_count: Literal[0]
    reason_codes: list[str]
    records: list[dict[str, object]]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _plan_identity(plan: JsonObject) -> tuple[str | None, str | None, str | None]:
    return _string(plan.get("plan_id")), _string(plan.get("source_domain")), _string(plan.get("registry_version"))


def _result(
    plan: JsonObject,
    *,
    ok: bool,
    outcome: Literal["completed", "insufficiency", "blocked", "dependency_unavailable"],
    reason_codes: Sequence[str] = (),
    processed_page_count: int = 0,
    attempt_count: int = 0,
    records: Sequence[dict[str, object]] = (),
) -> ReplayResult:
    """Build a privacy-minimized candidate output; validation happens at return."""

    plan_id, domain, registry_version = _plan_identity(plan)
    return {
        "contract_version": "1.0.0",
        "ok": ok,
        "outcome": outcome,
        "plan_id": plan_id,
        "source_domain": domain,
        "registry_version": registry_version,
        "processed_page_count": processed_page_count,
        "attempt_count": attempt_count,
        "retry_count": 0,
        "reason_codes": sorted(set(reason_codes)),
        "records": list(records),
    }


def _safe_result_schema_failure() -> ReplayResult:
    """Return the fixed safe fallback when plan identity cannot be emitted."""

    return {
        "contract_version": "1.0.0",
        "ok": False,
        "outcome": "blocked",
        "plan_id": None,
        "source_domain": None,
        "registry_version": None,
        "processed_page_count": 0,
        "attempt_count": 0,
        "retry_count": 0,
        "reason_codes": ["RESULT_SCHEMA_VALIDATION_FAILED"],
        "records": [],
    }


def _schema_codes(value: JsonObject, schema: JsonObject, definition: str) -> list[str]:
    schema_with_definitions: dict[str, object] = {"$ref": f"#/$defs/{definition}", "$defs": schema.get("$defs", {})}
    try:
        validator = Draft202012Validator(schema_with_definitions, format_checker=FormatChecker())
    except Exception:
        return ["REPLAY_SCHEMA_INVALID"]
    return ["REPLAY_SCHEMA_INVALID"] if any(validator.iter_errors(value)) else []


def _finalize(result: ReplayResult, replay_schema: JsonObject) -> ReplayResult:
    """Validate every adapter return and prevent invalid plan identifiers leaking."""

    if not _schema_codes(result, replay_schema, "ExecutionResult"):
        return result
    fallback = _safe_result_schema_failure()
    _schema_codes(fallback, replay_schema, "ExecutionResult")
    return fallback


def _controlled_source(registry: JsonObject, domain: str | None) -> Mapping[str, Any] | None:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        return None
    return next((item for item in sources if isinstance(item, Mapping) and item.get("domain") == domain), None)


def _safe_locator(value: object) -> str | None:
    raw = _string(value)
    if raw is None:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port is not None:
        return None
    if parsed.query or parsed.fragment:
        return None
    return f"https://{parsed.hostname}{parsed.path}"


def _redirect_code(value: object, domain: str, prefixes: object) -> str:
    locator = _safe_locator(value)
    if locator is None:
        return "MALFORMED_RESPONSE"
    parsed = urlsplit(locator)
    in_prefix = isinstance(prefixes, list) and any(
        isinstance(prefix, str) and (parsed.path.startswith(prefix) if prefix.endswith("/") else parsed.path == prefix)
        for prefix in prefixes
    )
    return "REDIRECT_FOLLOW_FORBIDDEN" if parsed.hostname == domain and in_prefix else "REDIRECT_OUT_OF_BOUNDARY"


def validate_controlled_crawl_replay(plan: JsonObject, replay: JsonObject, plan_schema: JsonObject, replay_schema: JsonObject, registry: JsonObject) -> ReplayResult:
    """Validate *plan* first, then process a synthetic replay without I/O or mutation."""

    def finish(result: ReplayResult) -> ReplayResult:
        return _finalize(result, replay_schema)

    plan_result = validate_controlled_crawl_plan(plan, plan_schema, registry)
    if not plan_result["ok"]:
        return finish(_result(plan, ok=False, outcome="blocked", reason_codes=[error["code"] for error in plan_result["errors"]]))
    replay_schema_codes = _schema_codes(replay, replay_schema, "ReplayInput")
    if replay_schema_codes:
        return finish(_result(plan, ok=False, outcome="blocked", reason_codes=[replay_schema_codes[0]]))
    if replay.get("execution_mode") != "offline_replay":
        return finish(_result(plan, ok=False, outcome="blocked", reason_codes=["LIVE_MODE_FORBIDDEN"]))
    runtime_state = replay.get("runtime_state")
    if runtime_state == "unavailable":
        return finish(_result(plan, ok=False, outcome="dependency_unavailable", reason_codes=["RUNTIME_UNAVAILABLE"]))
    if runtime_state != "receipt_lock_match":
        return finish(_result(plan, ok=False, outcome="dependency_unavailable", reason_codes=["RUNTIME_RECEIPT_LOCK_MISMATCH"]))

    source = _controlled_source(registry, _string(plan.get("source_domain")))
    contract = _mapping(source.get("controlled_crawl")) if source is not None else None
    pages = plan.get("requested_pages")
    events = replay.get("events")
    if source is None or contract is None or not isinstance(pages, list) or not isinstance(events, list):
        return finish(_result(plan, ok=False, outcome="blocked", reason_codes=["REPLAY_AUTHORITY_INVALID"]))

    page_by_id = {
        page.get("id"): page for page in pages
        if isinstance(page, Mapping) and isinstance(page.get("id"), str)
    }
    allowed_fields = set(contract.get("allowed_text_fields", []))
    prefixes = contract.get("allowed_path_prefixes")
    source_domain = _string(source.get("domain")) or ""
    accessed_at = _string(replay.get("accessed_at"))
    records: list[dict[str, object]] = []
    processed_page_ids: set[str] = set()
    next_page_index = 0

    def stop_at(event_index: int, code: str) -> ReplayResult:
        """Stop at the first failed event and reject tail events deterministically."""

        codes = [code]
        outcome: Literal["insufficiency", "blocked"] = "insufficiency"
        if event_index != len(events) - 1:
            codes.append("EVENT_AFTER_STOP_FORBIDDEN")
            outcome = "blocked"
        return finish(_result(
            plan,
            ok=False,
            outcome=outcome,
            reason_codes=codes,
            processed_page_count=len(records),
            attempt_count=len(records) + 1,
            records=records,
        ))

    for event_index, event_value in enumerate(events):
        event = _mapping(event_value)
        if event is None:
            return stop_at(event_index, "MALFORMED_RESPONSE")
        event_type = event.get("event_type")
        if event_type == "malformed":
            return stop_at(event_index, "MALFORMED_RESPONSE")
        if event_type == "denial":
            denial = _string(event.get("denial_reason"))
            code = {
                "robots_denied": "ROBOTS_DENIED",
                "login": "LOGIN_REQUIRED",
                "paywall": "PAYWALL_BLOCKED",
                "captcha": "CAPTCHA_BLOCKED",
                "cloudflare_challenge": "CLOUDFLARE_CHALLENGE",
                "explicit_refusal": "EXPLICIT_REFUSAL",
            }.get(denial or "", "MALFORMED_RESPONSE")
            return stop_at(event_index, code)
        if event_type == "redirect":
            return stop_at(event_index, _redirect_code(event.get("redirect_target"), source_domain, prefixes))
        if event_type != "response":
            return stop_at(event_index, "MALFORMED_RESPONSE")
        if next_page_index >= len(pages):
            return finish(_result(
                plan,
                ok=False,
                outcome="blocked",
                reason_codes=["EVENT_AFTER_COMPLETION_FORBIDDEN"],
                processed_page_count=len(records),
                attempt_count=len(records) + 1,
                records=records,
            ))

        page_id = _string(event.get("page_id"))
        if page_id not in page_by_id:
            return stop_at(event_index, "REPLAY_PAGE_NOT_REQUESTED")
        if page_id in processed_page_ids:
            return stop_at(event_index, "REPLAY_PAGE_DUPLICATE")
        expected_page = _mapping(pages[next_page_index])
        expected_page_id = _string(expected_page.get("id")) if expected_page is not None else None
        if page_id != expected_page_id:
            return stop_at(event_index, "REPLAY_PAGE_OUT_OF_ORDER")
        page = page_by_id[page_id]
        parent_page_id = _string(page.get("parent_page_id"))
        if page.get("depth") != 0 and parent_page_id not in processed_page_ids:
            return stop_at(event_index, "REPLAY_PARENT_NOT_PROCESSED")

        status = event.get("http_status")
        if status in HTTP_DENIAL_STATUSES:
            return stop_at(event_index, f"HTTP_{status}_BLOCKED")
        if status != 200:
            return stop_at(event_index, "MALFORMED_RESPONSE")
        locator = _safe_locator(event.get("observed_url"))
        if locator is None:
            return stop_at(event_index, "MALFORMED_RESPONSE")
        if locator != page.get("url"):
            return stop_at(event_index, "REDIRECT_OUT_OF_BOUNDARY")
        short_text = _mapping(event.get("extracted_text"))
        summary = _string(event.get("team_authored_summary"))
        if short_text is None or summary is None or accessed_at is None:
            return stop_at(event_index, "MALFORMED_RESPONSE")
        if not short_text or not set(short_text) <= allowed_fields:
            return stop_at(event_index, "REPLAY_FIELD_FORBIDDEN")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 280 for value in short_text.values()) or len(summary) > 280:
            return stop_at(event_index, "REPLAY_CONTENT_FORBIDDEN")
        records.append({
            "source_locator": locator,
            "accessed_at": accessed_at,
            "audit_status": SUCCESS_STATUS,
            "source_text_trust": SOURCE_TEXT_TRUST,
            "instruction_handling": INSTRUCTION_HANDLING,
            "short_text": dict(short_text),
            "team_authored_summary": summary,
        })
        processed_page_ids.add(page_id)
        next_page_index += 1

    if next_page_index != len(pages):
        return finish(_result(
            plan,
            ok=False,
            outcome="insufficiency",
            reason_codes=["REPLAY_PAGE_COUNT_MISMATCH"],
            processed_page_count=len(records),
            attempt_count=len(records),
            records=records,
        ))
    return finish(_result(
        plan,
        ok=True,
        outcome="completed",
        processed_page_count=len(records),
        attempt_count=len(records),
        records=records,
    ))


def _load_failure() -> ReplayResult:
    return _result({}, ok=False, outcome="blocked", reason_codes=["REPLAY_AUTHORITY_LOAD_FAILED"])


def main(argv: Sequence[str]) -> int:
    """Emit one deterministic replay result without launching an external runtime."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("replay", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        replay_schema = load_json_object(DEFAULT_REPLAY_SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        replay_schema = None
    try:
        plan = load_json_object(arguments.plan)
        replay = load_json_object(arguments.replay)
        plan_schema = load_json_object(DEFAULT_PLAN_SCHEMA_PATH)
        registry = load_json_object(DEFAULT_REGISTRY_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        result = _load_failure()
        if replay_schema is not None:
            result = _finalize(result, replay_schema)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    if replay_schema is None:
        result = _safe_result_schema_failure()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    result = validate_controlled_crawl_replay(plan, replay, plan_schema, replay_schema, registry)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
