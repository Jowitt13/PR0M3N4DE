"""Build one deterministic student dimension plan from confirmed upstream records.

This deterministic, local-only slice accepts exactly five confirmed upstream
documents: an ARCH-097 AssignmentBriefDigest, its exact ARCH-098 start board
projection, one human-confirmed ARCH-099 spatial program draft, its exact
ARCH-099 spatial program, and one human-confirmed dimension plan draft. It
checks only the long-side by short-side rectangles that the human explicitly
wrote: footprint area, area delta, area delta percentage, and aspect ratio are
computed with exact decimal arithmetic against the confirmed area, the
five-percent gate compares unrounded decimal values, and any candidate farther
than five percent from that area fails closed. Candidates
are human-authored, machine-checked candidates; the builder selects no
candidate, emits no recommendation, winner, or ranking, and decides no
dimension, floor count, site plan, entrance, circulation, massing, grid,
orientation, coordinate, level, height, or environmental conclusion. The plan
framework carries zones, confirmed space names, and confirmed relations
without coordinates. The output is JSON data only: no PPTX, image, HTML,
coordinate drawing, or plan drawing. It opens no socket and starts no
subprocess, reads no system clock, never modifies an input document, and
writes a destination only after full validation. Validate re-derives the
expected output deterministically and requires exact byte equality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
from build_student_design_start_board import compute_confirmed_digest_sha256
from build_student_spatial_program import (
    _canonical_json,
    _document_sha256,
    _error,
    _load_failure,
    _registry,
    _schema_errors,
    _write_atomically,
    load_json_object,
    validate_program,
)

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    Registry = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]

JsonObject = Mapping[str, Any]

REFERENCES = Path(__file__).resolve().parents[1] / "references"
INTAKE_SCHEMA_PATH = REFERENCES / "assignment-brief-intake.schema.json"
DIGEST_SCHEMA_PATH = REFERENCES / "assignment-brief-digest.schema.json"
BOARD_SCHEMA_PATH = REFERENCES / "student-design-start-board.schema.json"
PROGRAM_DRAFT_SCHEMA_PATH = REFERENCES / "student-spatial-program-draft.schema.json"
PROGRAM_SCHEMA_PATH = REFERENCES / "student-spatial-program.schema.json"
DIMENSION_DRAFT_SCHEMA_PATH = REFERENCES / "student-dimension-plan-draft.schema.json"
DIMENSION_PLAN_SCHEMA_PATH = REFERENCES / "student-dimension-plan.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_DIMENSION_PLAN_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
OPTION_KEYS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")
AREA_DELTA_LIMIT_PERCENT = Decimal("5")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def _decimal_text(value: Decimal) -> str:
    """Render one exact decimal without trailing zeros, deterministically."""

    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        normalized = normalized.quantize(Decimal(1))
    return format(normalized, "f")


RESOLVE_GAPS_ACTION = {
    "action": "resolve_dimension_gaps",
    "description": (
        "Next, close the listed gaps: supply candidates for the deferred numeric spaces and "
        "area values for the unresolved-area spaces. This plan does not fill them in for you."
    ),
}
HUMAN_SELECT_ACTION = {
    "action": "human_select_dimension_candidates",
    "description": (
        "Next, the human selects or revises one candidate per space. This plan picks no "
        "candidate and ranks none; the choice stays a human decision."
    ),
}

BOUNDARIES: tuple[str, ...] = (
    "Candidates are human-authored, machine-checked candidates; this plan selects no candidate and is no final decision.",
    "This plan decides no floor count, site plan, entrance, circulation, massing, grid, orientation, coordinate, level, height, or environmental conclusion.",
    "The five percent area deviation is a candidate-checking gate only; it is not a design, code, or constructibility judgment.",
    "Brief-stated and human-working area sources stay distinct; a human working figure is never presented as a brief fact.",
    "The plan framework carries no coordinates, positions, distances, roads, entrances, floors, or geometric layout.",
)

PLAN_FRAMEWORK_NOTE = (
    "Coordinate-free plan framework: it lists only the confirmed zones, space names, and confirmed "
    "relations, and supplies no position, orientation, adjacency distance, road, entrance, floor, or geometric layout."
)


class DimensionError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class DimensionResult(TypedDict):
    """The public result of confirming, building, or validating one dimension plan."""

    ok: bool
    errors: list[DimensionError]


def compute_pending_dimension_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation dimension draft document.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_dimension_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, DimensionResult]:
    """Bind one explicit human confirmation record to a pending dimension draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "DIMENSION_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("DIMENSION_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[DimensionError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_dimension_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_dimension_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "/pending_dimension_draft_sha256", "pending_dimension_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_dimension_draft_sha256(draft):
            errors.append(_error("DIMENSION_DRAFT_HASH_MISMATCH", "/pending_dimension_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_dimension_draft_sha256": human_record["pending_dimension_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "DIMENSION_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_dimension_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[DimensionError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched dimension draft."""

    errors = _schema_errors(draft, draft_schema, registry, "DIMENSION_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("DIMENSION_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the dimension draft must be confirmed before a dimension plan can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("DIMENSION_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_dimension_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_dimension_draft_sha256(draft):
        return [_error("DIMENSION_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_dimension_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _numeric_spaces(program: JsonObject) -> dict[str, dict[str, Any]]:
    """Index the confirmed program's numeric spaces by their unique student-visible name."""

    spaces: dict[str, dict[str, Any]] = {}
    for zone in program["student_view"]["spaces_by_zone"]:
        for space in zone["spaces"]:
            if "area_value_m2" in space:
                spaces[str(space["name"])] = dict(space)
    return spaces


def _decimal_area(value: Any) -> Decimal | None:
    """Parse one confirmed area value exactly, or return None for a non-exact value."""

    try:
        if isinstance(value, int):
            return Decimal(value)
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _check_candidates(
    candidate_set: JsonObject,
    confirmed_area: Decimal,
    pointer: str,
) -> tuple[list[dict[str, Any]], list[DimensionError]]:
    """Check one space's human-authored rectangles with exact decimal arithmetic."""

    errors: list[DimensionError] = []
    seen_rectangles: set[tuple[Decimal, Decimal]] = set()
    seen_keys: list[str] = []
    computed: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidate_set["candidates"]):
        candidate_pointer = f"{pointer}/candidates/{index}"
        option_key = str(candidate["option_key"])
        seen_keys.append(option_key)
        if option_key != OPTION_KEYS[index]:
            errors.append(_error("DIMENSION_CANDIDATE_INVALID", f"{candidate_pointer}/option_key", f"option keys must be consecutive from A without gaps or repeats; got {option_key} at position {index}"))
        try:
            long_side = Decimal(str(candidate["long_side_m"]))
            short_side = Decimal(str(candidate["short_side_m"]))
        except InvalidOperation:
            errors.append(_error("DIMENSION_CANDIDATE_INVALID", candidate_pointer, "side values must be exact decimal strings"))
            continue
        if short_side <= 0 or long_side <= 0:
            errors.append(_error("DIMENSION_CANDIDATE_INVALID", candidate_pointer, "side values must be greater than zero"))
        elif long_side < short_side:
            errors.append(_error("DIMENSION_CANDIDATE_INVALID", candidate_pointer, "long_side_m must be at least short_side_m; the builder never reorients a candidate"))
        rectangle = (long_side, short_side)
        if rectangle in seen_rectangles:
            errors.append(_error("DIMENSION_CANDIDATE_INVALID", candidate_pointer, "the same long by short rectangle already appears for this space"))
        seen_rectangles.add(rectangle)
        if errors:
            continue
        footprint = long_side * short_side
        delta = confirmed_area - footprint
        raw_delta_percent = (abs(delta) / confirmed_area) * Decimal(100)
        if raw_delta_percent > AREA_DELTA_LIMIT_PERCENT:
            errors.append(
                _error(
                    "DIMENSION_CANDIDATE_INVALID",
                    candidate_pointer,
                    f"candidate footprint deviates {raw_delta_percent}% from the confirmed area, beyond the 5% candidate-checking gate; this gate is no design, code, or constructibility judgment",
                )
            )
            continue
        view: dict[str, Any] = {
            "option_key": option_key,
            "long_side_m": str(candidate["long_side_m"]),
            "short_side_m": str(candidate["short_side_m"]),
            "footprint_area_m2": _decimal_text(footprint),
            "area_delta_m2": _decimal_text(delta),
            "area_delta_percent": _decimal_text(raw_delta_percent.quantize(FOUR_PLACES)),
            "aspect_ratio": _decimal_text((long_side / short_side).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)),
        }
        if "human_note" in candidate:
            view["human_note"] = candidate["human_note"]
        computed.append(view)
    return computed, errors


def _dimension_semantic_errors(draft: JsonObject, program: JsonObject) -> tuple[list[DimensionError], list[dict[str, Any]]]:
    """Check source binding, space coverage, and every candidate without choosing one."""

    errors: list[DimensionError] = []
    if draft["source_program_sha256"] != _document_sha256(program):
        errors.append(_error("DIMENSION_SOURCE_PROGRAM_HASH_MISMATCH", "/source_program_sha256", "the draft does not bind the supplied confirmed spatial program"))
        return errors, []

    numeric = _numeric_spaces(program)
    all_names: list[str] = []
    computed_sets: list[dict[str, Any]] = []
    for index, candidate_set in enumerate(draft["candidate_sets"]):
        pointer = f"/candidate_sets/{index}"
        name = str(candidate_set["space_name"])
        all_names.append(name)
        space = numeric.get(name)
        if space is None:
            if any(str(space_item["name"]) == name for zone in program["student_view"]["spaces_by_zone"] for space_item in zone["spaces"]):
                errors.append(_error("DIMENSION_AREA_UNRESOLVED", f"{pointer}/space_name", f"{name} has no confirmed area value yet, so it cannot carry dimension candidates"))
            else:
                errors.append(_error("DIMENSION_SOURCE_SPACE_UNKNOWN", f"{pointer}/space_name", f"{name} is not a space in the confirmed spatial program"))
            continue
        confirmed_area = _decimal_area(space["area_value_m2"])
        if confirmed_area is None or confirmed_area <= 0:
            errors.append(_error("DIMENSION_AREA_UNRESOLVED", f"{pointer}/space_name", f"{name} has no usable confirmed area value"))
            continue
        computed, candidate_errors = _check_candidates(candidate_set, confirmed_area, pointer)
        errors.extend(candidate_errors)
        computed_sets.append(
            {
                "space_name": name,
                "area_source": space["area_status"],
                "confirmed_area_m2": str(confirmed_area),
                "candidate_count_reason": str(candidate_set["candidate_count_reason"]),
                "candidates": computed,
            }
        )
    deferred_names: list[str] = []
    for index, deferred in enumerate(draft["deferred_numeric_spaces"]):
        name = str(deferred["space_name"])
        deferred_names.append(name)
        if name not in numeric:
            pointer = f"/deferred_numeric_spaces/{index}/space_name"
            if any(str(space_item["name"]) == name for zone in program["student_view"]["spaces_by_zone"] for space_item in zone["spaces"]):
                errors.append(_error("DIMENSION_AREA_UNRESOLVED", pointer, f"{name} has no confirmed area value; it is already listed among unresolved-area spaces"))
            else:
                errors.append(_error("DIMENSION_SOURCE_SPACE_UNKNOWN", pointer, f"{name} is not a space in the confirmed spatial program"))

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return errors, []

    coverage_errors: list[DimensionError] = []
    for name in all_names + deferred_names:
        if all_names.count(name) + deferred_names.count(name) > 1:
            coverage_errors.append(
                _error("DIMENSION_COVERAGE_INVALID", "", f"{name} is covered more than once; a numeric space keeps exactly one candidate set or one deferral")
            )
    for name in sorted(numeric):
        if name not in all_names and name not in deferred_names:
            coverage_errors.append(
                _error("DIMENSION_COVERAGE_INVALID", "", f"{name} has a confirmed area value but neither candidates nor a human deferral; numeric spaces must not disappear")
            )
    if coverage_errors:
        return coverage_errors, []
    return [], computed_sets


def build_dimension_plan(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    draft: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    program_draft_schema: JsonObject,
    program_schema: JsonObject,
    dimension_draft_schema: JsonObject,
    dimension_plan_schema: JsonObject,
) -> tuple[dict[str, Any] | None, DimensionResult]:
    """Return one deterministic student dimension plan, or no output on any failed gate."""

    upstream = validate_program(digest, board, program_draft, program, intake_schema, digest_schema, board_schema, program_draft_schema, program_schema)
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema)
    draft_errors = _verify_confirmed_dimension_draft(draft, dimension_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors, candidate_sets = _dimension_semantic_errors(draft, program)
    if semantic_errors:
        semantic_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": semantic_errors}

    spaces_by_zone: list[dict[str, Any]] = []
    for zone in program["student_view"]["spaces_by_zone"]:
        zone_spaces: list[dict[str, Any]] = []
        for space in zone["spaces"]:
            view_space: dict[str, Any] = {
                "name": space["name"],
                "activity_profile": space["activity_profile"],
                "area_status": space["area_status"],
            }
            if "area_value_m2" in space:
                decimal_area = _decimal_area(space["area_value_m2"])
                assert decimal_area is not None  # validated upstream
                view_space["area_source"] = space["area_status"]
                view_space["area_value_m2"] = _decimal_text(decimal_area)
            else:
                note = str(space["origin_basis"])
                view_space["area_note"] = note.removeprefix("area unresolved: ").strip() or note
            zone_spaces.append(view_space)
        spaces_by_zone.append({"zone": zone["zone"], "spaces": zone_spaces})

    unresolved_area_spaces = [
        {"name": item["name"], "note": item["note"]}
        for item in program["student_view"]["unresolved_program_items"]
        if item["kind"] == "area"
    ]
    deferred_numeric_spaces = [{"space_name": str(item["space_name"]), "reason": str(item["reason"])} for item in draft["deferred_numeric_spaces"]]

    plan_framework = {
        "zones": [{"zone": zone["zone"], "spaces": [str(space["name"]) for space in zone["spaces"]]} for zone in program["student_view"]["spaces_by_zone"]],
        "relations": [dict(relation) for relation in program["student_view"]["relations"]],
        "note": PLAN_FRAMEWORK_NOTE,
    }

    has_gaps = bool(deferred_numeric_spaces) or bool(unresolved_area_spaces)
    next_action = dict(RESOLVE_GAPS_ACTION) if has_gaps else dict(HUMAN_SELECT_ACTION)

    plan: dict[str, Any] = {
        "schema_version": "1.0.0",
        "plan_kind": "student_dimension_plan",
        "source_binding": {
            "digest_input_hash": digest["input_hash"],
            "confirmed_digest_sha256": compute_confirmed_digest_sha256(digest),
            "pending_digest_sha256": digest["human_confirmation"]["pending_digest_sha256"],
            "start_board_sha256": _document_sha256(board),
            "confirmed_program_draft_sha256": _document_sha256(program_draft),
            "pending_program_draft_sha256": program_draft["human_confirmation"]["pending_draft_sha256"],
            "confirmed_program_sha256": _document_sha256(program),
            "pending_dimension_draft_sha256": draft["human_confirmation"]["pending_dimension_draft_sha256"],
            "confirmed_dimension_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "dimension_candidates_ready_for_human_selection",
            "spaces_by_zone": spaces_by_zone,
            "candidate_sets": candidate_sets,
            "deferred_numeric_spaces": deferred_numeric_spaces,
            "unresolved_area_spaces": unresolved_area_spaces,
            "plan_framework": plan_framework,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": next_action,
            "boundaries": list(BOUNDARIES),
        },
    }

    plan_errors = _schema_errors(plan, dimension_plan_schema, registry, "STUDENT_DIMENSION_PLAN_SCHEMA_INVALID")
    if plan_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": plan_errors}
    return plan, {"ok": True, "errors": []}


def validate_dimension_plan(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    draft: JsonObject,
    plan: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    program_draft_schema: JsonObject,
    program_schema: JsonObject,
    dimension_draft_schema: JsonObject,
    dimension_plan_schema: JsonObject,
) -> DimensionResult:
    """Re-derive the expected plan from the five upstream inputs and compare it exactly."""

    registry = _registry(intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema)
    plan_errors = _schema_errors(plan, dimension_plan_schema, registry, "STUDENT_DIMENSION_PLAN_SCHEMA_INVALID")
    if plan_errors:
        return {"ok": False, "errors": plan_errors}

    expected, build_result = build_dimension_plan(
        digest, board, program_draft, program, draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(plan) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_DIMENSION_PLAN_CONTENT_MISMATCH",
                    "",
                    "the supplied plan is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, DimensionResult]:
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


def main(argv: Sequence[str]) -> int:
    """Confirm a pending dimension draft, build a plan, or validate one against its upstream documents."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending dimension draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student dimension plan draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one student dimension plan from five confirmed upstream documents")
    validate_parser = subparsers.add_parser("validate", help="validate one student dimension plan against its upstream documents")
    for upstream_parser in (build_parser, validate_parser):
        upstream_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
        upstream_parser.add_argument("board", type=Path, help="student design start board JSON")
        upstream_parser.add_argument("program_draft", type=Path, help="confirmed student spatial program draft JSON")
        upstream_parser.add_argument("program", type=Path, help="student spatial program JSON")
        upstream_parser.add_argument("draft", type=Path, help="confirmed student dimension plan draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("plan", type=Path, help="student dimension plan JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema = load_json_object(INTAKE_SCHEMA_PATH)
        digest_schema = load_json_object(DIGEST_SCHEMA_PATH)
        board_schema = load_json_object(BOARD_SCHEMA_PATH)
        program_draft_schema = load_json_object(PROGRAM_DRAFT_SCHEMA_PATH)
        program_schema = load_json_object(PROGRAM_SCHEMA_PATH)
        dimension_draft_schema = load_json_object(DIMENSION_DRAFT_SCHEMA_PATH)
        dimension_plan_schema = load_json_object(DIMENSION_PLAN_SCHEMA_PATH)
        if arguments.command == "confirm":
            draft_document = load_json_object(arguments.draft)
            human_record = load_json_object(arguments.human_record)
        else:
            digest = load_json_object(arguments.digest)
            board = load_json_object(arguments.board)
            program_draft_document = load_json_object(arguments.program_draft)
            program_document = load_json_object(arguments.program)
            draft_document = load_json_object(arguments.draft)
            if arguments.command == "validate":
                plan_document = load_json_object(arguments.plan)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_dimension_draft(draft_document, human_record, dimension_draft_schema)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        plan, result = build_dimension_plan(
            digest, board, program_draft_document, program_document, draft_document,
            intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema,
        )
        if plan is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(plan, arguments.output)
        return exit_code

    result = validate_dimension_plan(
        digest, board, program_draft_document, program_document, draft_document, plan_document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
