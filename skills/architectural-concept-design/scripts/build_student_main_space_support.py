"""Confirm, build, and validate a human-authored main-space support framework.

This deterministic local stage consumes only one valid ARCH-108 schematic-plan
state handoff and a human-confirmed organization draft. It checks traceability
and coverage of roles, support links, and intended sequences without moving a
rectangle, making a recommendation, or generating a drawing.
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
import build_student_schematic_plan_state_handoff as handoff_builder
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

REFERENCES = Path(__file__).resolve().parents[1] / "references"
DRAFT_SCHEMA_PATH = REFERENCES / "student-main-space-support-draft.schema.json"
FRAMEWORK_SCHEMA_PATH = REFERENCES / "student-main-space-support.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_MAIN_SPACE_SUPPORT_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "Main-space, supporting-space, shared-service, and sequence records are human-authored organization intentions, not automatic design conclusions.",
    "This framework never moves, resizes, rotates, adds, removes, or optimizes a local schematic block or coordinate.",
    "A support link is not a measured distance, geometric adjacency, code separation, environmental claim, or mandatory layout rule.",
    "It generates no plan drawing, image, presentation, three-dimensional model, site conclusion, or professional-approval claim.",
)

CONFIRMED_AVAILABLE: tuple[str, ...] = (
    "The exact reviewed local schematic-plan state handoff and its validated ARCH-097~108 chain.",
    "The student's human-confirmed space roles, support relationships, sequence intentions, and unresolved items.",
)

MUST_NOT_INFER: tuple[str, ...] = (
    "Any preferred main space, support arrangement, transition, circulation layout, or completed design decision beyond what the student wrote.",
    "Any coordinate, rectangle, orientation, entrance, corridor, wall, door, column, stair, toilet, site plan, massing, or structural conclusion.",
    "Any regulation, cost, performance, environmental, constructibility, or professional-approval conclusion.",
)

INVALIDATED_BY_UPSTREAM_CHANGE: tuple[str, ...] = (
    "Any change to an ARCH-097~108 source document invalidates this framework and requires rebuild plus revalidation.",
    "Any change to the bound state handoff invalidates this draft confirmation and requires a new human confirmation.",
)

PROHIBITED_OUTPUTS: tuple[str, ...] = (
    "Automatic selection, ranking, scoring, recommendation, or modification of a spatial organization decision.",
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
    """Return the closed registry for the entire ARCH-097~109 validation chain."""

    return _registry(
        *(schemas[key] for key in handoff_builder._BLOCK_SCHEMA_KEYS),
        schemas["review"],
        schemas["handoff"],
        schemas["draft"],
        schemas["framework"],
    )


def _validate_state_handoff(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> FrameworkResult:
    """Run the sole ARCH-108 upstream entry over its complete source chain."""

    if len(chain) != len(handoff_builder._DOCUMENT_KEYS):
        return {
            "ok": False,
            "errors": [_error("MAIN_SPACE_SUPPORT_CHAIN_INVALID", "", "the main-space support command requires the complete ARCH-097~107 document chain")],
        }
    result = handoff_builder.validate_schematic_plan_state_handoff(chain, review, handoff, schemas)
    return {"ok": bool(result["ok"]), "errors": [dict(error) for error in result["errors"]]}  # type: ignore[return-value]


def _pending_draft(draft: JsonObject) -> dict[str, Any]:
    """Return the canonical pending form used for one human confirmation hash."""

    pending = _copy_json(draft)
    pending["human_confirmation"] = {"status": "pending"}
    return pending


def compute_pending_main_space_support_draft_sha256(draft: JsonObject) -> str:
    """Hash the complete canonical pending draft with one trailing newline."""

    return _document_sha256(_pending_draft(draft))


def _record_errors(record: JsonObject, pending_hash: str) -> list[FrameworkError]:
    """Validate the exact four-key human confirmation record."""

    required = {"action", "confirmed_by", "confirmed_at", "pending_main_space_support_draft_sha256"}
    errors: list[FrameworkError] = []
    if set(record) != required:
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID", "", "human confirmation must contain exactly action, confirmed_by, confirmed_at, and pending_main_space_support_draft_sha256"))
        return errors
    if record.get("action") != CONFIRM_ACTION:
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
    if not is_human_record_label(record.get("confirmed_by")):
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
    if not is_rfc3339_datetime(record.get("confirmed_at")):
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
    bound_hash = record.get("pending_main_space_support_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID", "/pending_main_space_support_draft_sha256", "pending_main_space_support_draft_sha256 must be exactly 64 lowercase hex characters"))
    elif bound_hash != pending_hash:
        errors.append(_error("MAIN_SPACE_SUPPORT_DRAFT_HASH_MISMATCH", "/pending_main_space_support_draft_sha256", "the human confirmation does not bind this exact pending main-space support draft"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def confirm_main_space_support_draft(
    draft: JsonObject,
    human_record: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, FrameworkResult]:
    """Bind one pending draft to one human confirmation without inventing data."""

    errors = _schema_errors(draft, schemas["draft"], _framework_registry(schemas), "MAIN_SPACE_SUPPORT_DRAFT_SCHEMA_INVALID")
    if errors:
        return None, {"ok": False, "errors": [dict(error) for error in errors]}
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("MAIN_SPACE_SUPPORT_DRAFT_NOT_CONFIRMED", "/human_confirmation/status", "confirm accepts only a pending main-space support draft")]}
    pending_hash = compute_pending_main_space_support_draft_sha256(draft)
    record_errors = _record_errors(human_record, pending_hash)
    if record_errors:
        return None, {"ok": False, "errors": record_errors}
    confirmed = _copy_json(draft)
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_main_space_support_draft_sha256": pending_hash,
    }
    final_errors = _schema_errors(confirmed, schemas["draft"], _framework_registry(schemas), "MAIN_SPACE_SUPPORT_DRAFT_SCHEMA_INVALID")
    if final_errors:  # pragma: no cover - guards a schema-contract regression.
        return None, {"ok": False, "errors": [dict(error) for error in final_errors]}
    return confirmed, {"ok": True, "errors": []}


def _confirmed_draft_errors(draft: JsonObject, schemas: Mapping[str, JsonObject]) -> list[FrameworkError]:
    """Verify the full confirmed draft and reconstruct its bound pending form."""

    errors = _schema_errors(draft, schemas["draft"], _framework_registry(schemas), "MAIN_SPACE_SUPPORT_DRAFT_SCHEMA_INVALID")
    if errors:
        return [dict(error) for error in errors]
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("MAIN_SPACE_SUPPORT_DRAFT_NOT_CONFIRMED", "/human_confirmation/status", "the main-space support draft is not confirmed")]
    record = {
        "action": confirmation.get("action"),
        "confirmed_by": confirmation.get("confirmed_by"),
        "confirmed_at": confirmation.get("confirmed_at"),
        "pending_main_space_support_draft_sha256": confirmation.get("pending_main_space_support_draft_sha256"),
    }
    return _record_errors(record, compute_pending_main_space_support_draft_sha256(draft))


def _source_spaces(handoff: JsonObject) -> dict[str, str]:
    """Map every validated state-handoff space name to its existing level label."""

    source: dict[str, str] = {}
    view = handoff["student_handoff"]
    for level in view["levels"]:
        for zone in level["zones"]:
            for space in zone["spaces"]:
                source[str(space["space_name"])] = str(level["level_label"])
    return source


def _semantic_errors(draft: JsonObject, handoff: JsonObject) -> list[FrameworkError]:
    """Check role coverage and human-authored organization references fail closed."""

    errors: list[FrameworkError] = []
    if draft.get("source_state_handoff_sha256") != _document_sha256(handoff):
        errors.append(_error("MAIN_SPACE_SUPPORT_SOURCE_HANDOFF_MISMATCH", "/source_state_handoff_sha256", "the draft does not bind the supplied exact ARCH-108 state handoff"))
        return errors
    spaces = _source_spaces(handoff)
    roles: dict[str, str] = {}
    for index, item in enumerate(draft["space_roles"]):
        name = str(item["space_name"])
        role = str(item["role"])
        if name not in spaces:
            errors.append(_error("MAIN_SPACE_SUPPORT_ROLE_INVALID", f"/space_roles/{index}/space_name", "space_name is not present in the state handoff"))
        elif name in roles:
            errors.append(_error("MAIN_SPACE_SUPPORT_ROLE_INVALID", f"/space_roles/{index}/space_name", "each state-handoff space must have exactly one role"))
        else:
            roles[name] = role
    missing = sorted(set(spaces) - set(roles))
    if missing:
        errors.append(_error("MAIN_SPACE_SUPPORT_ROLE_INVALID", "/space_roles", f"space_roles omits state-handoff spaces: {', '.join(missing)}"))
    main_spaces = {name for name, role in roles.items() if role == "main_space"}
    if not main_spaces:
        errors.append(_error("MAIN_SPACE_SUPPORT_ROLE_INVALID", "/space_roles", "at least one human-authored main_space is required"))

    linked_supports: set[str] = set()
    seen_links: set[tuple[str, str]] = set()
    for index, item in enumerate(draft["support_relationships"]):
        main_name = str(item["main_space_name"])
        support_name = str(item["support_space_name"])
        pair = (main_name, support_name)
        if main_name not in main_spaces:
            errors.append(_error("MAIN_SPACE_SUPPORT_RELATION_INVALID", f"/support_relationships/{index}/main_space_name", "main_space_name must have the human-authored main_space role"))
        if support_name not in roles or roles.get(support_name) not in {"supporting_space", "shared_service"}:
            errors.append(_error("MAIN_SPACE_SUPPORT_RELATION_INVALID", f"/support_relationships/{index}/support_space_name", "support_space_name must have supporting_space or shared_service role"))
        if main_name == support_name:
            errors.append(_error("MAIN_SPACE_SUPPORT_RELATION_INVALID", f"/support_relationships/{index}", "a support relationship cannot name the same space twice"))
        if pair in seen_links:
            errors.append(_error("MAIN_SPACE_SUPPORT_RELATION_INVALID", f"/support_relationships/{index}", "duplicate main-space/support-space relationship"))
        seen_links.add(pair)
        linked_supports.add(support_name)
    required_supports = {name for name, role in roles.items() if role in {"supporting_space", "shared_service"}}
    unlinked = sorted(required_supports - linked_supports)
    if unlinked:
        errors.append(_error("MAIN_SPACE_SUPPORT_RELATION_INVALID", "/support_relationships", f"supporting or shared-service spaces need a human support link: {', '.join(unlinked)}"))

    seen_sequences: set[tuple[str, tuple[str, ...], str]] = set()
    for index, item in enumerate(draft["sequence_intents"]):
        level = str(item["level_label"])
        names = tuple(str(value) for value in item["ordered_space_names"])
        fingerprint = (level, names, str(item["intent_kind"]))
        if fingerprint in seen_sequences:
            errors.append(_error("MAIN_SPACE_SUPPORT_SEQUENCE_INVALID", f"/sequence_intents/{index}", "duplicate human sequence intention"))
        seen_sequences.add(fingerprint)
        for name in names:
            if name not in spaces:
                errors.append(_error("MAIN_SPACE_SUPPORT_SEQUENCE_INVALID", f"/sequence_intents/{index}/ordered_space_names", "sequence names a space absent from the state handoff"))
            elif spaces[name] != level:
                errors.append(_error("MAIN_SPACE_SUPPORT_SEQUENCE_INVALID", f"/sequence_intents/{index}/level_label", "all sequence spaces must belong to the student-written level_label"))

    unresolved_ids: set[str] = set()
    for index, item in enumerate(draft["unresolved_items"]):
        record_id = str(item["record_id"])
        if record_id in unresolved_ids:
            errors.append(_error("MAIN_SPACE_SUPPORT_UNRESOLVED_INVALID", f"/unresolved_items/{index}/record_id", "unresolved record_id must be unique"))
        unresolved_ids.add(record_id)
        for name in item["subject_space_names"]:
            if str(name) not in spaces:
                errors.append(_error("MAIN_SPACE_SUPPORT_UNRESOLVED_INVALID", f"/unresolved_items/{index}/subject_space_names", "unresolved item names a space absent from the state handoff"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _next_action(unresolved: Sequence[Any]) -> dict[str, str]:
    """Return the only next action implied by the student's own unresolved list."""

    if unresolved:
        return {
            "action": "resolve_main_space_support_gaps",
            "description": "Resolve the student-recorded main-space, supporting-space, or sequence gaps before further manual refinement.",
        }
    return {
        "action": "human_refine_spatial_sequence",
        "description": "Continue manual refinement of the student-authored spatial sequence; no drawing or design decision is generated here.",
    }


def _project_framework(handoff: JsonObject, draft: JsonObject, schemas: Mapping[str, JsonObject]) -> dict[str, Any] | None:
    """Project only validated human organization content into the closed output."""

    pending_hash = compute_pending_main_space_support_draft_sha256(draft)
    view = handoff["student_handoff"]
    student_view = {
        "project_title": str(view["project_title"]),
        "stage": "main_space_support_framework_confirmed",
        "space_roles": _copy_json(draft["space_roles"]),
        "support_relationships": _copy_json(draft["support_relationships"]),
        "sequence_intents": _copy_json(draft["sequence_intents"]),
        "unresolved_items": [
            {"subject_space_names": _copy_json(item["subject_space_names"]), "reason": str(item["reason"])}
            for item in draft["unresolved_items"]
        ],
        "clarification_questions": _copy_json(view["clarification_questions"]),
        "next_action": _next_action(draft["unresolved_items"]),
        "boundaries_statement": list(BOUNDARIES_STATEMENT),
    }
    framework: dict[str, Any] = {
        "schema_version": "1.0.0",
        "framework_kind": "student_main_space_support_framework",
        "source_binding": {
            "state_handoff_sha256": _document_sha256(handoff),
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
    errors = _schema_errors(framework, schemas["framework"], _framework_registry(schemas), "STUDENT_MAIN_SPACE_SUPPORT_SCHEMA_INVALID")
    return None if errors else framework


def build_main_space_support_framework(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    draft: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, FrameworkResult]:
    """Build one framework only after the complete chain and draft pass every gate."""

    upstream = _validate_state_handoff(chain, review, handoff, schemas)
    if not upstream["ok"]:
        return None, upstream
    confirmation_errors = _confirmed_draft_errors(draft, schemas)
    if confirmation_errors:
        return None, {"ok": False, "errors": confirmation_errors}
    semantic_errors = _semantic_errors(draft, handoff)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}
    framework = _project_framework(handoff, draft, schemas)
    if framework is None:  # pragma: no cover - guards output contract drift.
        return None, {"ok": False, "errors": [_error("STUDENT_MAIN_SPACE_SUPPORT_SCHEMA_INVALID", "", "the built main-space support framework failed its closed schema")]}
    return framework, {"ok": True, "errors": []}


def validate_main_space_support_framework(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> FrameworkResult:
    """Rebuild the sole permitted framework and compare canonical bytes exactly."""

    errors = _schema_errors(framework, schemas["framework"], _framework_registry(schemas), "STUDENT_MAIN_SPACE_SUPPORT_SCHEMA_INVALID")
    if errors:
        return {"ok": False, "errors": [dict(error) for error in errors]}
    expected, result = build_main_space_support_framework(chain, review, handoff, draft, schemas)
    if expected is None:
        return result
    if _canonical_json(framework) + b"\n" != _canonical_json(expected) + b"\n":
        return {"ok": False, "errors": [_error("STUDENT_MAIN_SPACE_SUPPORT_CONTENT_MISMATCH", "", "the supplied main-space support framework is not the exact deterministic projection of its validated state handoff and confirmed draft")]}
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
    """Load the committed ARCH-108 schemas plus this stage's two contracts."""

    schemas = dict(handoff_builder._load_schemas())
    schemas["draft"] = load_json_object(DRAFT_SCHEMA_PATH)
    schemas["framework"] = load_json_object(FRAMEWORK_SCHEMA_PATH)
    return schemas


def _add_state_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the fixed ARCH-097~108 chain and its state-handoff document."""

    handoff_builder._add_arguments(parser)
    parser.add_argument("handoff", type=Path, help="validated ARCH-108 schematic-plan state handoff JSON")


def _load_chain(arguments: argparse.Namespace) -> tuple[JsonObject, ...]:
    """Load the fixed ordered ARCH-097~107 chain reused by ARCH-108."""

    return handoff_builder._load_chain(arguments)


def main(argv: Sequence[str]) -> int:
    """Confirm, build, or validate one human-authored organization framework."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    confirm_parser = subparsers.add_parser("confirm", help="confirm one pending human-authored draft")
    confirm_parser.add_argument("draft", type=Path)
    confirm_parser.add_argument("human_record", type=Path)
    confirm_parser.add_argument("--output", type=Path)
    build_parser = subparsers.add_parser("build", help="build one confirmed organization framework")
    validate_parser = subparsers.add_parser("validate", help="validate one organization framework")
    for command_parser in (build_parser, validate_parser):
        _add_state_arguments(command_parser)
        command_parser.add_argument("draft", type=Path, help="confirmed main-space support draft JSON")
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
            draft = load_json_object(arguments.draft)
            if arguments.command == "validate":
                framework = load_json_object(arguments.framework)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_main_space_support_draft(draft, human_record, schemas)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code
    if arguments.command == "build":
        built, result = build_main_space_support_framework(chain, review, handoff, draft, schemas)
        if built is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(built, arguments.output)
        return exit_code
    result = validate_main_space_support_framework(chain, review, handoff, draft, framework, schemas)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
