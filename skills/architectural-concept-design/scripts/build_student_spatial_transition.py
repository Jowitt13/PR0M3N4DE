"""Confirm, build, and validate a human-authored spatial transition framework.

This deterministic local stage consumes only a valid ARCH-109 main-space
support framework without unresolved items and a human-confirmed transition
draft. It checks traceability and coverage of human-written transition patterns
without moving a block, calculating a dimension, or generating a drawing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
import build_student_main_space_support as support_builder
from build_student_spatial_program import (
    _canonical_json,
    _document_sha256,
    _error,
    _load_failure,
    _registry,
    _schema_errors,
    _write_atomically,
    load_json_object,
)

JsonObject = Mapping[str, Any]
DocumentChain = Sequence[JsonObject]
Pair = tuple[str, str]

REFERENCES = Path(__file__).resolve().parents[1] / "references"
DRAFT_SCHEMA_PATH = REFERENCES / "student-spatial-transition-draft.schema.json"
FRAMEWORK_SCHEMA_PATH = REFERENCES / "student-spatial-transition.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_SPATIAL_TRANSITION_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "Spatial hierarchy is inherited from the human-authored ARCH-109 roles; transition patterns are human-authored intentions, not automatic design conclusions.",
    "Gradual opening, gradual enclosure, buffering, interwoven access, and independence do not establish a measured size, distance, adjacency, opening, or performance result.",
    "This framework never moves, resizes, rotates, adds, removes, or optimizes a local schematic block or coordinate.",
    "It generates no plan drawing, image, presentation, three-dimensional model, site conclusion, or professional-approval claim.",
)

CONFIRMED_AVAILABLE: tuple[str, ...] = (
    "The exact ARCH-109 main-space-support framework and its validated ARCH-097~109 chain.",
    "The inherited human-authored space roles and the student's human-confirmed spatial transition patterns or unresolved items.",
)

MUST_NOT_INFER: tuple[str, ...] = (
    "Any role change, preferred transition pattern, completed circulation layout, or design decision beyond what the student wrote.",
    "Any coordinate, rectangle, size, orientation, entrance, corridor, wall, door, column, stair, toilet, site plan, massing, or structural conclusion.",
    "Any regulation, cost, performance, environmental, constructibility, or professional-approval conclusion.",
)

INVALIDATED_BY_UPSTREAM_CHANGE: tuple[str, ...] = (
    "Any change to an ARCH-097~109 source document invalidates this framework and requires rebuild plus revalidation.",
    "Any change to the bound main-space-support framework invalidates this draft confirmation and requires a new human confirmation.",
)

PROHIBITED_OUTPUTS: tuple[str, ...] = (
    "Automatic selection, ranking, scoring, recommendation, or modification of a spatial hierarchy or transition decision.",
    "Automatic plan generation, drawing, image, presentation, or three-dimensional model.",
    "A site, code, cost, structural, performance, environmental, or constructibility conclusion.",
)


class FrameworkError(TypedDict):
    """One deterministic rejection without a partial framework."""

    code: str
    path: str
    message: str


class FrameworkResult(TypedDict):
    """The public result of confirming, building, or validating this framework."""

    ok: bool
    errors: list[FrameworkError]


def _copy_json(value: Any) -> Any:
    """Return a detached JSON-compatible copy without changing source input."""

    return json.loads(json.dumps(value, ensure_ascii=False))


def _framework_registry(schemas: Mapping[str, JsonObject]) -> Any:
    """Return the closed registry for the complete ARCH-097~110 validation chain."""

    handoff_builder = support_builder.handoff_builder
    return _registry(
        *(schemas[key] for key in handoff_builder._BLOCK_SCHEMA_KEYS),
        schemas["review"],
        schemas["handoff"],
        schemas["draft"],
        schemas["framework"],
        schemas["transition_draft"],
        schemas["transition_framework"],
    )


def _validate_main_space_support(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> FrameworkResult:
    """Run the sole ARCH-109 upstream entry over its complete source chain."""

    result = support_builder.validate_main_space_support_framework(
        chain, review, handoff, support_draft, support_framework, schemas
    )
    return {"ok": bool(result["ok"]), "errors": [dict(error) for error in result["errors"]]}  # type: ignore[return-value]


def _pending_draft(draft: JsonObject) -> dict[str, Any]:
    """Return the canonical pending form used for one human confirmation hash."""

    pending = _copy_json(draft)
    pending["human_confirmation"] = {"status": "pending"}
    return pending


def compute_pending_spatial_transition_draft_sha256(draft: JsonObject) -> str:
    """Hash the complete canonical pending draft with one trailing newline."""

    return _document_sha256(_pending_draft(draft))


def _record_errors(record: JsonObject, pending_hash: str) -> list[FrameworkError]:
    """Validate the exact four-key human confirmation record."""

    required = {"action", "confirmed_by", "confirmed_at", "pending_spatial_transition_draft_sha256"}
    errors: list[FrameworkError] = []
    if set(record) != required:
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID", "", "human confirmation must contain exactly action, confirmed_by, confirmed_at, and pending_spatial_transition_draft_sha256"))
        return errors
    if record.get("action") != CONFIRM_ACTION:
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
    if not is_human_record_label(record.get("confirmed_by")):
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
    if not is_rfc3339_datetime(record.get("confirmed_at")):
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
    bound_hash = record.get("pending_spatial_transition_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID", "/pending_spatial_transition_draft_sha256", "pending_spatial_transition_draft_sha256 must be exactly 64 lowercase hex characters"))
    elif bound_hash != pending_hash:
        errors.append(_error("SPATIAL_TRANSITION_DRAFT_HASH_MISMATCH", "/pending_spatial_transition_draft_sha256", "the human confirmation does not bind this exact pending spatial transition draft"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def confirm_spatial_transition_draft(
    draft: JsonObject,
    human_record: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, FrameworkResult]:
    """Bind one pending draft to one human confirmation without inventing data."""

    errors = _schema_errors(draft, schemas["transition_draft"], _framework_registry(schemas), "SPATIAL_TRANSITION_DRAFT_SCHEMA_INVALID")
    if errors:
        return None, {"ok": False, "errors": [dict(error) for error in errors]}
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("SPATIAL_TRANSITION_DRAFT_NOT_CONFIRMED", "/human_confirmation/status", "confirm accepts only a pending spatial transition draft")]}
    pending_hash = compute_pending_spatial_transition_draft_sha256(draft)
    record_errors = _record_errors(human_record, pending_hash)
    if record_errors:
        return None, {"ok": False, "errors": record_errors}
    confirmed = _copy_json(draft)
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_spatial_transition_draft_sha256": pending_hash,
    }
    final_errors = _schema_errors(confirmed, schemas["transition_draft"], _framework_registry(schemas), "SPATIAL_TRANSITION_DRAFT_SCHEMA_INVALID")
    if final_errors:  # pragma: no cover - guards a schema-contract regression.
        return None, {"ok": False, "errors": [dict(error) for error in final_errors]}
    return confirmed, {"ok": True, "errors": []}


def _confirmed_draft_errors(draft: JsonObject, schemas: Mapping[str, JsonObject]) -> list[FrameworkError]:
    """Verify the full confirmed draft and reconstruct its bound pending form."""

    errors = _schema_errors(draft, schemas["transition_draft"], _framework_registry(schemas), "SPATIAL_TRANSITION_DRAFT_SCHEMA_INVALID")
    if errors:
        return [dict(error) for error in errors]
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("SPATIAL_TRANSITION_DRAFT_NOT_CONFIRMED", "/human_confirmation/status", "the spatial transition draft is not confirmed")]
    record = {
        "action": confirmation.get("action"),
        "confirmed_by": confirmation.get("confirmed_by"),
        "confirmed_at": confirmation.get("confirmed_at"),
        "pending_spatial_transition_draft_sha256": confirmation.get("pending_spatial_transition_draft_sha256"),
    }
    return _record_errors(record, compute_pending_spatial_transition_draft_sha256(draft))


def _space_levels(handoff: JsonObject) -> dict[str, str]:
    """Map every reviewed handoff space name to its already-confirmed level."""

    levels: dict[str, str] = {}
    for level in handoff["student_handoff"]["levels"]:
        for zone in level["zones"]:
            for space in zone["spaces"]:
                levels[str(space["space_name"])] = str(level["level_label"])
    return levels


def _pair(first: str, second: str) -> Pair:
    """Return the stable unordered identity of one two-space transition pair."""

    return tuple(sorted((first, second)))


def _eligible_pairs(handoff: JsonObject, support_framework: JsonObject) -> set[Pair]:
    """Derive only real same-level pairs already named by ARCH-109 humans."""

    levels = _space_levels(handoff)
    eligible: set[Pair] = set()
    view = support_framework["student_view"]
    for sequence in view["sequence_intents"]:
        names = [str(value) for value in sequence["ordered_space_names"]]
        for first, second in zip(names, names[1:], strict=False):
            if levels.get(first) == levels.get(second):
                eligible.add(_pair(first, second))
    for relation in view["support_relationships"]:
        first = str(relation["main_space_name"])
        second = str(relation["support_space_name"])
        if levels.get(first) == levels.get(second):
            eligible.add(_pair(first, second))
    return eligible


def _semantic_errors(
    draft: JsonObject,
    handoff: JsonObject,
    support_framework: JsonObject,
) -> list[FrameworkError]:
    """Check binding and exact coverage of human-authored eligible pairs."""

    errors: list[FrameworkError] = []
    if draft.get("source_main_space_support_framework_sha256") != _document_sha256(support_framework):
        return [_error("SPATIAL_TRANSITION_SOURCE_FRAMEWORK_MISMATCH", "/source_main_space_support_framework_sha256", "the draft does not bind the supplied exact ARCH-109 main-space-support framework")]
    eligible = _eligible_pairs(handoff, support_framework)
    resolved: set[Pair] = set()
    unresolved: set[Pair] = set()
    transition_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    for index, item in enumerate(draft["transition_patterns"]):
        record_id = str(item["record_id"])
        first = str(item["from_space_name"])
        second = str(item["to_space_name"])
        pair = _pair(first, second)
        if record_id in transition_ids:
            errors.append(_error("SPATIAL_TRANSITION_PAIR_INVALID", f"/transition_patterns/{index}/record_id", "transition record_id must be unique"))
        transition_ids.add(record_id)
        if first == second or pair not in eligible:
            errors.append(_error("SPATIAL_TRANSITION_PAIR_INVALID", f"/transition_patterns/{index}", "transition patterns must name a distinct eligible same-level sequence or support pair"))
            continue
        if pair in resolved:
            errors.append(_error("SPATIAL_TRANSITION_PAIR_INVALID", f"/transition_patterns/{index}", "each eligible unordered pair may have only one transition pattern"))
        resolved.add(pair)
    for index, item in enumerate(draft["unresolved_items"]):
        record_id = str(item["record_id"])
        first = str(item["from_space_name"])
        second = str(item["to_space_name"])
        pair = _pair(first, second)
        if record_id in unresolved_ids:
            errors.append(_error("SPATIAL_TRANSITION_UNRESOLVED_INVALID", f"/unresolved_items/{index}/record_id", "unresolved record_id must be unique"))
        unresolved_ids.add(record_id)
        if first == second or pair not in eligible:
            errors.append(_error("SPATIAL_TRANSITION_UNRESOLVED_INVALID", f"/unresolved_items/{index}", "unresolved items must name a distinct eligible same-level sequence or support pair"))
            continue
        if pair in unresolved:
            errors.append(_error("SPATIAL_TRANSITION_UNRESOLVED_INVALID", f"/unresolved_items/{index}", "each eligible unordered pair may have only one unresolved record"))
        unresolved.add(pair)
    overlap = sorted(resolved & unresolved)
    missing = sorted(eligible - resolved - unresolved)
    if overlap:
        errors.append(_error("SPATIAL_TRANSITION_COVERAGE_INVALID", "/unresolved_items", "an eligible pair cannot appear as both a transition pattern and an unresolved item"))
    if missing:
        rendered = "; ".join(f"{first} / {second}" for first, second in missing)
        errors.append(_error("SPATIAL_TRANSITION_COVERAGE_INVALID", "", f"eligible same-level pairs need exactly one transition pattern or unresolved item: {rendered}"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _next_action(unresolved: Sequence[Any]) -> dict[str, str]:
    """Return the only next action implied by the student's own unresolved list."""

    if unresolved:
        return {
            "action": "resolve_spatial_transition_gaps",
            "description": "Resolve the student-recorded spatial transition gaps before further manual plan refinement.",
        }
    return {
        "action": "human_review_spatial_transition_framework",
        "description": "Review the human-authored hierarchy and transition intentions before any later manual design work.",
    }


def _project_framework(
    support_framework: JsonObject,
    draft: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> dict[str, Any] | None:
    """Project only validated human hierarchy and transition content."""

    pending_hash = compute_pending_spatial_transition_draft_sha256(draft)
    source_view = support_framework["student_view"]
    student_view = {
        "project_title": str(source_view["project_title"]),
        "stage": "spatial_transition_framework_confirmed",
        "space_hierarchy": _copy_json(source_view["space_roles"]),
        "transition_patterns": [
            {
                "from_space_name": str(item["from_space_name"]),
                "to_space_name": str(item["to_space_name"]),
                "transition_kind": str(item["transition_kind"]),
                "note": str(item["note"]),
            }
            for item in draft["transition_patterns"]
        ],
        "unresolved_items": [
            {
                "from_space_name": str(item["from_space_name"]),
                "to_space_name": str(item["to_space_name"]),
                "reason": str(item["reason"]),
            }
            for item in draft["unresolved_items"]
        ],
        "clarification_questions": _copy_json(source_view["clarification_questions"]),
        "next_action": _next_action(draft["unresolved_items"]),
        "boundaries_statement": list(BOUNDARIES_STATEMENT),
    }
    framework: dict[str, Any] = {
        "schema_version": "1.0.0",
        "framework_kind": "student_spatial_transition_framework",
        "source_binding": {
            "main_space_support_framework_sha256": _document_sha256(support_framework),
            "confirmed_draft_sha256": _document_sha256(draft),
            "pending_draft_sha256": pending_hash,
        },
        "student_view": student_view,
        "framework_contract": {
            "confirmed_available": list(CONFIRMED_AVAILABLE),
            "must_not_infer": list(MUST_NOT_INFER),
            "invalidated_by_upstream_change": list(INVALIDATED_BY_UPSTREAM_CHANGE),
            "prohibited_outputs": list(PROHIBITED_OUTPUTS),
        },
    }
    errors = _schema_errors(framework, schemas["transition_framework"], _framework_registry(schemas), "STUDENT_SPATIAL_TRANSITION_SCHEMA_INVALID")
    return None if errors else framework


def build_spatial_transition_framework(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, FrameworkResult]:
    """Build only after the complete chain and transition draft pass every gate."""

    upstream = _validate_main_space_support(chain, review, handoff, support_draft, support_framework, schemas)
    if not upstream["ok"]:
        return None, upstream
    if support_framework["student_view"]["unresolved_items"]:
        return None, {"ok": False, "errors": [_error("SPATIAL_TRANSITION_UPSTREAM_UNRESOLVED", "/student_view/unresolved_items", "resolve_main_space_support_gaps before building a spatial transition framework")]}
    confirmation_errors = _confirmed_draft_errors(draft, schemas)
    if confirmation_errors:
        return None, {"ok": False, "errors": confirmation_errors}
    semantic_errors = _semantic_errors(draft, handoff, support_framework)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}
    framework = _project_framework(support_framework, draft, schemas)
    if framework is None:  # pragma: no cover - guards output contract drift.
        return None, {"ok": False, "errors": [_error("STUDENT_SPATIAL_TRANSITION_SCHEMA_INVALID", "", "the built spatial transition framework failed its closed schema")]}
    return framework, {"ok": True, "errors": []}


def validate_spatial_transition_framework(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> FrameworkResult:
    """Rebuild the sole permitted framework and compare canonical bytes exactly."""

    errors = _schema_errors(framework, schemas["transition_framework"], _framework_registry(schemas), "STUDENT_SPATIAL_TRANSITION_SCHEMA_INVALID")
    if errors:
        return {"ok": False, "errors": [dict(error) for error in errors]}
    expected, result = build_spatial_transition_framework(chain, review, handoff, support_draft, support_framework, draft, schemas)
    if expected is None:
        return result
    if _canonical_json(framework) + b"\n" != _canonical_json(expected) + b"\n":
        return {"ok": False, "errors": [_error("STUDENT_SPATIAL_TRANSITION_CONTENT_MISMATCH", "", "the supplied spatial transition framework is not the exact deterministic projection of its validated ARCH-109 framework and confirmed draft")]}
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, FrameworkResult]:
    """Print JSON or atomically write it only after every preceding gate succeeds."""

    if output is None:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0, {"ok": True, "errors": []}
    try:
        output_hash = _write_atomically(output, payload)
    except OSError as error:
        failure = _load_failure("OUTPUT_WRITE_FAILED", str(error))
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2, failure
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0, {"ok": True, "errors": []}


def _load_schemas() -> dict[str, JsonObject]:
    """Load committed ARCH-109 schemas plus this stage's two contracts."""

    schemas = dict(support_builder._load_schemas())
    schemas["transition_draft"] = load_json_object(DRAFT_SCHEMA_PATH)
    schemas["transition_framework"] = load_json_object(FRAMEWORK_SCHEMA_PATH)
    return schemas


def _add_state_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the fixed ARCH-097~109 chain and main-space-support documents."""

    support_builder._add_state_arguments(parser)
    parser.add_argument("support_draft", type=Path, help="confirmed ARCH-109 main-space-support draft JSON")
    parser.add_argument("support_framework", type=Path, help="validated ARCH-109 main-space-support framework JSON")


def _load_chain(arguments: argparse.Namespace) -> tuple[JsonObject, ...]:
    """Load the fixed ordered ARCH-097~107 chain reused by ARCH-109."""

    return support_builder._load_chain(arguments)


def main(argv: Sequence[str]) -> int:
    """Confirm, build, or validate one human-authored spatial transition framework."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    confirm_parser = subparsers.add_parser("confirm", help="confirm one pending human-authored draft")
    confirm_parser.add_argument("draft", type=Path)
    confirm_parser.add_argument("human_record", type=Path)
    confirm_parser.add_argument("--output", type=Path)
    build_parser = subparsers.add_parser("build", help="build one confirmed spatial transition framework")
    validate_parser = subparsers.add_parser("validate", help="validate one spatial transition framework")
    for command_parser in (build_parser, validate_parser):
        _add_state_arguments(command_parser)
        command_parser.add_argument("draft", type=Path, help="confirmed spatial transition draft JSON")
    build_parser.add_argument("--output", type=Path)
    validate_parser.add_argument("framework", type=Path)

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
        if arguments.command == "confirm":
            draft = load_json_object(arguments.draft)
            human_record = load_json_object(arguments.human_record)
        else:
            chain = _load_chain(arguments)
            review = load_json_object(arguments.review)
            handoff = load_json_object(arguments.handoff)
            support_draft = load_json_object(arguments.support_draft)
            support_framework = load_json_object(arguments.support_framework)
            draft = load_json_object(arguments.draft)
            if arguments.command == "validate":
                framework = load_json_object(arguments.framework)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_spatial_transition_draft(draft, human_record, schemas)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code
    if arguments.command == "build":
        built, result = build_spatial_transition_framework(chain, review, handoff, support_draft, support_framework, draft, schemas)
        if built is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(built, arguments.output)
        return exit_code
    result = validate_spatial_transition_framework(chain, review, handoff, support_draft, support_framework, draft, framework, schemas)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
