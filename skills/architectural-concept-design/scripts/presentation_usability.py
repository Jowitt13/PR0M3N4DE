"""Presentation usability, speaker notes, and human acceptance authority (ARCH-125).

Single shared implementation for the ARCH-125 contracts: the per-page usability
plan bound to the actual handoff, the independent human usability review, and
the real-rehearsal evidence receipt. Delivery verification recomputes every
binding from the actual handoff and deck bytes; speaker notes, internal trace,
error codes, and approval流水 never reach visible slides; estimated planning
time is never accepted as actual rehearsal time. No network, no clock reads,
no subprocesses, no in-place writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    SchemaError = Exception  # type: ignore[assignment,misc]

from _rfc3339 import is_rfc3339_datetime
from presentation_audience_copy import is_human_reviewer_label
from validate_state import JsonObject, compute_input_hash

SKILL_ROOT = Path(__file__).resolve().parents[1]
USABILITY_SCHEMA_PATH = SKILL_ROOT / "references" / "presentation-usability.schema.json"

USABILITY_CONTRACT_VERSION = "1.0.0"
REVIEW_RULES_VERSION = "1.0.0"

# Structural-leak patterns reused from the existing authorities: internal
# entity/task IDs and error-code-shaped tokens never belong in speaker notes,
# communication purposes, or visible copy.
_INTERNAL_ID_RE = re.compile(r"(?:^|[^A-Za-z0-9-])(?:RC|RCR|SRC|E|C|S|R|H|O|K|D)-[0-9]{3,}(?:$|[^A-Za-z0-9-])")
_ERROR_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}_(?:[A-Z0-9]+_){0,4}[A-Z][A-Z0-9]{1,}\b")

DELIVERY_CONCLUSION = "COMPLETED"


class UsabilityError(TypedDict):
    code: str
    path: str
    message: str
    related_ids: list[str]
    severity: str


def _error(code: str, path: str, message: str, related_ids: Sequence[str] = ()) -> UsabilityError:
    return {
        "code": code,
        "path": path,
        "message": message,
        "related_ids": list(related_ids),
        "severity": "ERROR",
    }


def _parse_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def load_json_object(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_parse_constant)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a top-level JSON object")
    return payload


def canonical_hash(value: Any) -> str:
    """Canonical SHA-256 (ADR-0001 canonicalization) of one JSON value."""
    return compute_input_hash({"value": value})


def _usability_schema() -> JsonObject:
    return load_json_object(USABILITY_SCHEMA_PATH)


def _def_schema(kind: str) -> JsonObject:
    """A standalone schema for one $defs entry that keeps sibling $refs resolvable."""
    full = _usability_schema()
    return {"$ref": f"#/$defs/{kind}", "$defs": full["$defs"]}


def _schema_errors(payload: JsonObject, schema: JsonObject) -> list[UsabilityError]:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema must be installed to validate presentation usability contracts")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors: list[UsabilityError] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        errors.append(_error(str(error.validator), path or "/", error.message))
    return errors


def _pages(handoff: JsonObject) -> list[JsonObject]:
    framework = handoff.get("deck_framework")
    return [page for page in framework if isinstance(page, Mapping)] if isinstance(framework, list) else []


def visible_copy_digest(handoff: JsonObject) -> str:
    """Canonical hash of the handoff's visible copy section."""
    copies = [page.get("visible_slide_copy") for page in _pages(handoff) if isinstance(page.get("visible_slide_copy"), Mapping)]
    return canonical_hash(copies)


def speaker_notes_digest(handoff: JsonObject) -> str:
    """Canonical hash of the handoff's speaker notes section."""
    notes = [page.get("speaker_notes") for page in _pages(handoff) if page.get("speaker_notes") is not None]
    return canonical_hash(notes)


def page_ids(handoff: JsonObject) -> list[str]:
    return [str(page.get("page_id", "")) for page in _pages(handoff)]


def _leak_errors(text: str, path: str) -> list[UsabilityError]:
    errors: list[UsabilityError] = []
    if _INTERNAL_ID_RE.search(text):
        errors.append(_error("INTERNAL_ID_IN_TEXT", path, "internal entity or task IDs must never enter notes, purposes, or copy", []))
    if _ERROR_CODE_RE.search(text):
        errors.append(_error("ERROR_CODE_IN_TEXT", path, "system error codes must never enter notes, purposes, or copy", []))
    return errors


def _notes_of(page: Mapping[str, Any]) -> JsonObject | None:
    notes = page.get("speaker_notes")
    return dict(notes) if isinstance(notes, Mapping) else None


def verify_plan(plan: JsonObject, handoff: JsonObject) -> tuple[bool, list[UsabilityError]]:
    """Verify the usability plan against the actual handoff object."""
    try:
        errors = _schema_errors(plan, _def_schema("UsabilityPlan"))
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return False, [_error("RUNTIME_ERROR", "", str(error))]
    if plan.get("handoff_sha256") != canonical_hash(handoff):
        errors.append(_error("PLAN_HANDOFF_MISMATCH", "/handoff_sha256", "the plan does not bind the current handoff", []))
        return False, errors
    actual_order = page_ids(handoff)
    if plan.get("page_order") != actual_order:
        errors.append(_error("PLAN_PAGE_ORDER_MISMATCH", "/page_order", "the plan page order does not match the actual handoff pages", []))
    pages = plan.get("pages", [])
    actual_pages = _pages(handoff)
    if not isinstance(pages, list) or len(pages) != len(actual_pages):
        errors.append(_error("PLAN_PAGES_INCOMPLETE", "/pages", "the plan must cover exactly the handoff pages", []))
        return (not errors), errors
    for position, (entry, page) in enumerate(zip(pages, actual_pages)):
        base = f"/pages/{position}"
        page_id = str(entry.get("page_id", position))
        if str(page.get("page_id", "")) != page_id:
            errors.append(_error("PLAN_PAGE_ORDER_MISMATCH", f"{base}/page_id", f"plan page {page_id} does not line up with the handoff", [page_id]))
        notes = _notes_of(page)
        if notes is None:
            errors.append(_error("PLAN_NOTES_MISSING", f"{base}/notes_sha256", f"page {page_id} has no speaker notes to bind", [page_id]))
        else:
            if canonical_hash(notes) != entry.get("notes_sha256"):
                errors.append(_error("PLAN_NOTES_MISMATCH", f"{base}/notes_sha256", f"speaker notes for {page_id} changed after the plan was written", [page_id]))
            notes_text = json.dumps(notes, ensure_ascii=False)
            errors.extend(_leak_errors(notes_text, f"{base}/notes_sha256"))
            headline = page.get("visible_slide_copy", {}).get("headline") if isinstance(page.get("visible_slide_copy"), Mapping) else None
            if isinstance(headline, str) and notes.get("delivery_hint") == headline:
                errors.append(_error("NOTES_REPEAT_COPY", f"{base}/notes_sha256", f"speaker notes for {page_id} repeat the visible headline verbatim instead of supporting the talk", [page_id]))
        purpose = str(entry.get("communication_purpose", ""))
        errors.extend(_leak_errors(purpose, f"{base}/communication_purpose"))
        for field in ("key_message", "sequence_hint", "visual_reference", "evidence_note", "transition_hint"):
            errors.extend(_leak_errors(str(entry.get(field, "")), f"{base}/{field}"))
    return (not errors), errors


def verify_review(
    review: JsonObject | None,
    plan: JsonObject,
    handoff: JsonObject,
    *,
    expected_deck_sha256: str | None = None,
) -> tuple[bool, list[UsabilityError], str]:
    """Verify the independent human usability review against the current state."""
    errors: list[UsabilityError] = []
    if review is None:
        return False, [_error("USABILITY_REVIEW_REQUIRED", "/usability_review", "delivery requires an independent human usability review")], ""
    try:
        errors.extend(_schema_errors(review, _def_schema("UsabilityReview")))
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return False, [_error("RUNTIME_ERROR", "", str(error))], ""
    review_digest = hashlib.sha256(
        json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    if review.get("status") != "APPROVED":
        errors.append(_error("USABILITY_REVIEW_NOT_APPROVED", "/status", f"usability review status {review.get('status')!r} cannot enter delivery", []))
    if not is_human_reviewer_label(review.get("reviewed_by")):
        errors.append(_error("USABILITY_REVIEWER_LABEL_REJECTED", "/reviewed_by", "reviewed_by must identify a human, not an agent, model, or system label", []))
    if review.get("plan_sha256") != canonical_hash(plan):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/plan_sha256", "the review does not cover the current usability plan", []))
    if review.get("handoff_sha256") != canonical_hash(handoff):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/handoff_sha256", "the handoff changed after the review", []))
    if review.get("visible_copy_sha256") != visible_copy_digest(handoff):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/visible_copy_sha256", "visible copy changed after the review", []))
    if review.get("speaker_notes_sha256") != speaker_notes_digest(handoff):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/speaker_notes_sha256", "speaker notes changed after the review", []))
    if review.get("page_order") != page_ids(handoff):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/page_order", "the page order changed after the review", []))
    if expected_deck_sha256 is not None and review.get("deck_sha256") != expected_deck_sha256:
        errors.append(_error("REVIEW_HASH_MISMATCH", "/deck_sha256", "the deck bytes changed after the review", []))
    findings_payload = {"page_findings": review.get("page_findings", []), "findings_resolutions": review.get("findings_resolutions", [])}
    if review.get("findings_sha256") != canonical_hash(findings_payload):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/findings_sha256", "findings hash does not bind the findings record", []))
    return (not errors), errors, review_digest


def _parse_rfc3339(value: object) -> datetime | None:
    if not isinstance(value, str) or not is_rfc3339_datetime(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rehearsal_evidence_digest(rehearsal: Mapping[str, Any]) -> str:
    """Canonical SHA-256 over the complete rehearsal record minus the digest itself.

    The payload is the whole object with ``rehearsal_evidence_sha256`` removed:
    sorted keys, stable separators, array order preserved. No caller-supplied
    field list and no request field (such as ``protected_inputs``) can shrink
    the covered surface; any future schema-accepted semantic field enters the
    digest automatically.
    """

    payload = {key: value for key, value in rehearsal.items() if key != "rehearsal_evidence_sha256"}
    return canonical_hash(payload)


def verify_rehearsal(
    rehearsal: JsonObject | None,
    plan: JsonObject,
    review: JsonObject | None,
    handoff: JsonObject,
    *,
    expected_deck_sha256: str | None = None,
) -> tuple[bool, list[UsabilityError], str | None]:
    """Verify real-rehearsal evidence; estimated planning time is never accepted.

    Returns the recomputed canonical rehearsal digest (the value the record's
    ``rehearsal_evidence_sha256`` must carry) so verdicts bind the exact
    record; it is ``None`` only when the record could not be read at all.
    """
    errors: list[UsabilityError] = []
    if rehearsal is None:
        return False, [_error("REHEARSAL_REQUIRED", "/rehearsal", "delivery requires real rehearsal evidence; planning estimates never substitute for it")], None
    try:
        errors.extend(_schema_errors(rehearsal, _def_schema("RehearsalEvidence")))
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return False, [_error("RUNTIME_ERROR", "", str(error))], None
    recomputed_digest = rehearsal_evidence_digest(rehearsal)
    if rehearsal.get("rehearsal_evidence_sha256") != recomputed_digest:
        errors.append(_error(
            "PRESENTATION_REHEARSAL_EVIDENCE_HASH_MISMATCH",
            "/rehearsal_evidence_sha256",
            "the rehearsal evidence self-binding digest does not match the recomputed canonical hash of the complete record",
            [],
        ))
    if not is_human_reviewer_label(rehearsal.get("presenter")):
        errors.append(_error("REHEARSAL_PRESENTER_LABEL_REJECTED", "/presenter", "presenter must identify a human, not an agent, model, or system label", []))
    if rehearsal.get("conclusion") != DELIVERY_CONCLUSION:
        errors.append(_error("REHEARSAL_NOT_COMPLETED", "/conclusion", f"rehearsal conclusion {rehearsal.get('conclusion')!r} cannot enter delivery", []))
    started = _parse_rfc3339(rehearsal.get("started_at"))
    ended = _parse_rfc3339(rehearsal.get("ended_at"))
    if started is None or ended is None:
        errors.append(_error("REHEARSAL_TIME_INVALID", "/started_at", "started_at and ended_at must be explicit RFC 3339 timestamps", []))
    elif int((ended - started).total_seconds()) != rehearsal.get("actual_total_seconds"):
        errors.append(_error("REHEARSAL_TIME_INVALID", "/actual_total_seconds", "actual_total_seconds must equal ended_at minus started_at", []))
    if rehearsal.get("target_seconds") != plan.get("target_seconds"):
        errors.append(_error("REHEARSAL_TARGET_MISMATCH", "/target_seconds", "the rehearsal target does not match the plan target", []))
    if rehearsal.get("plan_sha256") != canonical_hash(plan):
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/plan_sha256", "the usability plan changed after the rehearsal", []))
    if rehearsal.get("handoff_sha256") != canonical_hash(handoff):
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/handoff_sha256", "the handoff changed after the rehearsal", []))
    if rehearsal.get("visible_copy_sha256") != visible_copy_digest(handoff):
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/visible_copy_sha256", "visible copy changed after the rehearsal", []))
    if rehearsal.get("speaker_notes_sha256") != speaker_notes_digest(handoff):
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/speaker_notes_sha256", "speaker notes changed after the rehearsal", []))
    if rehearsal.get("page_order") != page_ids(handoff):
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/page_order", "the page order changed after the rehearsal", []))
    if expected_deck_sha256 is not None and rehearsal.get("deck_sha256") != expected_deck_sha256:
        errors.append(_error("REHEARSAL_HASH_MISMATCH", "/deck_sha256", "the deck bytes changed after the rehearsal", []))
    if review is not None:
        if rehearsal.get("usability_review_sha256") != canonical_hash(review):
            errors.append(_error("REHEARSAL_HASH_MISMATCH", "/usability_review_sha256", "the usability review changed after the rehearsal", []))
        if review.get("status") != "APPROVED":
            errors.append(_error("USABILITY_REVIEW_NOT_APPROVED", "/usability_review_sha256", "the rehearsal must follow an APPROVED usability review", []))
    per_page = rehearsal.get("per_page_seconds")
    planned_ids = [str(entry.get("page_id", "")) for entry in (plan.get("pages", []) or []) if isinstance(entry, Mapping)]
    if isinstance(per_page, list):
        if [str(entry.get("page_id", "")) for entry in per_page if isinstance(entry, Mapping)] != planned_ids:
            errors.append(_error("REHEARSAL_PAGES_MISMATCH", "/per_page_seconds", "per-page rehearsal times must cover the planned pages in order", []))
        elif sum(int(entry.get("seconds", 0)) for entry in per_page if isinstance(entry, Mapping)) != rehearsal.get("actual_total_seconds"):
            errors.append(_error("REHEARSAL_TIME_INVALID", "/per_page_seconds", "per-page seconds must sum to the actual total", []))
    known_pages = set(page_ids(handoff))
    for field in ("stuck_pages", "skipped_pages", "hard_to_explain_pages"):
        for page_id in rehearsal.get(field, []) or []:
            if page_id not in known_pages:
                errors.append(_error("REF_NOT_FOUND", f"/{field}", f"page {page_id} is not part of this deck", [str(page_id)]))
    return (not errors), errors, recomputed_digest


def verify_usability_delivery(
    plan: JsonObject,
    review: JsonObject | None,
    rehearsal: JsonObject | None,
    handoff: JsonObject,
    *,
    expected_deck_sha256: str | None = None,
) -> tuple[bool, list[UsabilityError], JsonObject]:
    """Full ARCH-125 delivery verdict: plan + APPROVED human review + real rehearsal."""
    errors: list[UsabilityError] = []
    plan_ok, plan_errors = verify_plan(plan, handoff)
    errors.extend(plan_errors)
    review_ok, review_errors, review_digest = verify_review(review, plan, handoff, expected_deck_sha256=expected_deck_sha256)
    errors.extend(review_errors)
    rehearsal_ok, rehearsal_errors, rehearsal_digest = verify_rehearsal(rehearsal, plan, review, handoff, expected_deck_sha256=expected_deck_sha256)
    errors.extend(rehearsal_errors)
    verdict = {
        "mode": "DELIVERY",
        "validator_contract_version": USABILITY_CONTRACT_VERSION,
        "handoff_sha256": canonical_hash(handoff),
        "visible_copy_sha256": visible_copy_digest(handoff),
        "speaker_notes_sha256": speaker_notes_digest(handoff),
        "usability_review_sha256": review_digest if review_digest else None,
        "rehearsal_evidence_sha256": rehearsal_digest,
        "page_order": page_ids(handoff),
        "deck_sha256": expected_deck_sha256,
    }
    if errors:
        return False, errors, verdict
    assert plan_ok and review_ok and rehearsal_ok
    return True, [], verdict


def _resolve_schema(kind: str) -> JsonObject:
    defs = _usability_schema()["$defs"]
    return defs[kind]


def main(argv: Sequence[str]) -> int:
    """Run one usability mode and emit machine-readable JSON without touching inputs."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", nargs="?")
    parser.add_argument("plan_path", nargs="?")
    parser.add_argument("review_path", nargs="?")
    parser.add_argument("rehearsal_path", nargs="?")
    parser.add_argument("--handoff", type=str)
    parser.add_argument("--deck", type=str)
    parser.add_argument("--expect-deck-sha256", type=str)
    arguments = parser.parse_args(argv[1:])

    def _emit(payload: object, code: int) -> int:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return code

    valid = (
        (arguments.mode == "validate-plan" and bool(arguments.plan_path) and arguments.handoff and not arguments.review_path and not arguments.rehearsal_path)
        or (arguments.mode == "verify" and bool(arguments.plan_path) and bool(arguments.review_path) and bool(arguments.rehearsal_path) and arguments.handoff)
    )
    if not valid:
        return _emit({"ok": False, "errors": [_error("RUNTIME_ERROR", "", "usage: presentation_usability.py validate-plan <plan> --handoff <handoff.json> | verify <plan> <review> <rehearsal> --handoff <handoff.json> [--deck <deck> --expect-deck-sha256 <sha>]")]}, 3)
    try:
        handoff = load_json_object(Path(arguments.handoff))
        plan = load_json_object(Path(arguments.plan_path))
        if arguments.mode == "validate-plan":
            ok, errors = verify_plan(plan, handoff)
            return _emit({"ok": ok, "errors": errors}, 0 if ok else 1)
        review = load_json_object(Path(arguments.review_path))
        rehearsal = load_json_object(Path(arguments.rehearsal_path))
        deck_sha256 = arguments.expect_deck_sha256
        if arguments.deck:
            actual = hashlib.sha256(Path(arguments.deck).read_bytes()).hexdigest()
            if deck_sha256 is not None and deck_sha256 != actual:
                return _emit({"ok": False, "errors": [_error("DECK_HASH_MISMATCH", "--expect-deck-sha256", "the expected deck hash does not match the actual deck bytes")]}, 1)
            deck_sha256 = actual
        ok, errors, verdict = verify_usability_delivery(plan, review, rehearsal, handoff, expected_deck_sha256=deck_sha256)
        payload = dict(verdict)
        payload["ok"] = ok
        payload["errors"] = errors
        return _emit(payload, 0 if ok else 1)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return _emit({"ok": False, "errors": [_error("RUNTIME_ERROR", "", str(error))]}, 3)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
