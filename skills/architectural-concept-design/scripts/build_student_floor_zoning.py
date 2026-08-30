"""Build one deterministic student floor and functional zoning framework.

This deterministic, local-only slice accepts the full confirmed upstream
chain: an ARCH-097 AssignmentBriefDigest, its exact ARCH-098 start board
projection, the confirmed ARCH-099 spatial program draft and its exact
spatial program, the confirmed ARCH-100 dimension draft and its exact
dimension plan, one direct human dimension selection record, and one
human-confirmed floor zoning draft. It organizes only what the student
explicitly wrote: level labels and sequence, zones, access and activity
attributes, non-geometric public-internal boundaries, and unresolved zoning
items. Humans select dimensions; humans write levels and zones; the machine
only validates, traces, projects, and rejects incomplete or tampered input.
It never adds, removes, reorders, or infers a level, assigns no space to a
level or zone, decides no entrance, exit, lobby, stair, elevator, evacuation,
or circulation, and emits no coordinate, dimension placement, orientation,
site plan, massing, grid, elevation, height, or environmental conclusion. It
recommends, ranks, selects, and judges no zone. The output is JSON data only:
no PPTX, web page, image, or drawing. It opens no socket and starts no
subprocess, reads no system clock, never modifies an input document, and
writes a destination only after full validation. Validate re-derives the
expected output deterministically and requires exact byte equality.
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
from build_student_design_start_board import compute_confirmed_digest_sha256
from build_student_dimension_plan import validate_dimension_plan
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

REFERENCES = Path(__file__).resolve().parents[1] / "references"
INTAKE_SCHEMA_PATH = REFERENCES / "assignment-brief-intake.schema.json"
DIGEST_SCHEMA_PATH = REFERENCES / "assignment-brief-digest.schema.json"
BOARD_SCHEMA_PATH = REFERENCES / "student-design-start-board.schema.json"
PROGRAM_DRAFT_SCHEMA_PATH = REFERENCES / "student-spatial-program-draft.schema.json"
PROGRAM_SCHEMA_PATH = REFERENCES / "student-spatial-program.schema.json"
DIMENSION_DRAFT_SCHEMA_PATH = REFERENCES / "student-dimension-plan-draft.schema.json"
DIMENSION_PLAN_SCHEMA_PATH = REFERENCES / "student-dimension-plan.schema.json"
SELECTION_SCHEMA_PATH = REFERENCES / "student-dimension-selection.schema.json"
ZONING_DRAFT_SCHEMA_PATH = REFERENCES / "student-floor-zoning-draft.schema.json"
ZONING_SCHEMA_PATH = REFERENCES / "student-floor-zoning.schema.json"

SELECT_ACTION = "SELECT_STUDENT_DIMENSION_CANDIDATES"
CONFIRM_ACTION = "CONFIRM_STUDENT_FLOOR_ZONING_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

RESOLVE_GAPS_ACTION = {
    "action": "resolve_floor_zoning_gaps",
    "description": (
        "Next, resolve the listed unresolved zoning items: place each named space into a zone or "
        "keep it explicitly unresolved with a reason. This output does not place spaces for you."
    ),
}
CIRCULATION_ACTION = {
    "action": "circulation_and_environment_framework",
    "description": (
        "Next, prepare the circulation and environment framework in a separately reviewed step. "
        "This output supplies no circulation or environment content."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "This output reflects only the levels, zones, and boundaries written by the student; it adds, removes, reorders, or infers no level.",
    "It decides no entrance, exit, lobby, stair, elevator, evacuation route, or circulation.",
    "It produces no coordinate, dimension placement, orientation, site plan, massing, grid, elevation, or height.",
    "It recommends, ranks, selects, and judges no zone; access and activity attributes are human projections only.",
    "Boundaries are student-declared non-geometric relations; they express no door, gate, stair, corridor, coordinate, or plan layout.",
)


class ZoningError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class ZoningResult(TypedDict):
    """The public result of confirming, building, or validating one floor zoning framework."""

    ok: bool
    errors: list[ZoningError]


def compute_pending_zoning_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation floor zoning draft document.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_zoning_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, ZoningResult]:
    """Bind one explicit human confirmation record to a pending floor zoning draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "FLOOR_ZONING_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("FLOOR_ZONING_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[ZoningError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_floor_zoning_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_floor_zoning_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "/pending_floor_zoning_draft_sha256", "pending_floor_zoning_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_zoning_draft_sha256(draft):
            errors.append(_error("FLOOR_ZONING_DRAFT_HASH_MISMATCH", "/pending_floor_zoning_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_floor_zoning_draft_sha256": human_record["pending_floor_zoning_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "FLOOR_ZONING_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_zoning_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[ZoningError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched floor zoning draft."""

    errors = _schema_errors(draft, draft_schema, registry, "FLOOR_ZONING_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("FLOOR_ZONING_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the floor zoning draft must be confirmed before a framework can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_floor_zoning_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_zoning_draft_sha256(draft):
        return [_error("FLOOR_ZONING_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_floor_zoning_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _candidate_index(dimension_plan: JsonObject) -> dict[str, dict[str, Any]]:
    """Index the confirmed dimension plan's candidate sets by space name."""

    index: dict[str, dict[str, Any]] = {}
    for candidate_set in dimension_plan["student_view"]["candidate_sets"]:
        index[str(candidate_set["space_name"])] = dict(candidate_set)
    return index


def _verify_selection(selection: JsonObject, dimension_plan: JsonObject, selection_schema: JsonObject, registry: Any) -> list[ZoningError]:
    """Fail closed on any invalid, forged, or incomplete human dimension selection."""

    errors = _schema_errors(selection, selection_schema, registry, "DIMENSION_SELECTION_SCHEMA_INVALID")
    if errors:
        return errors
    if selection.get("action") != SELECT_ACTION or not is_human_record_label(selection.get("selected_by")) or not is_rfc3339_datetime(selection.get("selected_at")):
        return [_error("DIMENSION_SELECTION_RECORD_INVALID", "", "the selection must be one valid human record with the fixed action, a human label, and a timezone-qualified RFC 3339 time")]
    if selection["source_dimension_plan_sha256"] != _document_sha256(dimension_plan):
        return [_error("DIMENSION_SELECTION_SOURCE_MISMATCH", "/source_dimension_plan_sha256", "the selection does not bind the supplied confirmed dimension plan")]

    candidate_index = _candidate_index(dimension_plan)
    errors = []
    seen: set[str] = set()
    for index, item in enumerate(selection["selections"]):
        pointer = f"/selections/{index}"
        name = str(item["space_name"])
        candidate_set = candidate_index.get(name)
        if candidate_set is None:
            errors.append(_error("DIMENSION_SELECTION_OPTION_INVALID", f"{pointer}/space_name", f"{name} has no candidate set in the confirmed dimension plan; deferred or unresolved spaces cannot be selected"))
            continue
        if name in seen:
            errors.append(_error("DIMENSION_SELECTION_OPTION_INVALID", f"{pointer}/space_name", f"{name} is selected more than once; one space keeps exactly one selection"))
            continue
        seen.add(name)
        option_key = str(item["selected_option_key"])
        available = {str(candidate["option_key"]) for candidate in candidate_set["candidates"]}
        if option_key not in available:
            errors.append(_error("DIMENSION_SELECTION_OPTION_INVALID", f"{pointer}/selected_option_key", f"{option_key} is not an existing candidate for {name}; only written candidates can be selected"))
    for name in sorted(candidate_index):
        if name not in seen:
            errors.append(_error("DIMENSION_SELECTION_COVERAGE_INVALID", "", f"{name} has a candidate set but no human selection; every candidate set keeps exactly one selection"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _zoning_semantic_errors(draft: JsonObject, selection: JsonObject, dimension_plan: JsonObject) -> list[ZoningError]:
    """Check source binding, uniqueness, coverage, and boundary rules without deciding anything."""

    errors: list[ZoningError] = []
    if draft["source_selection_sha256"] != _document_sha256(selection):
        errors.append(_error("FLOOR_ZONING_SOURCE_SELECTION_MISMATCH", "/source_selection_sha256", "the draft does not bind the supplied dimension selection record"))
        return errors

    selected_names = {str(item["space_name"]) for item in selection["selections"]}

    level_ids: set[str] = set()
    level_orders: set[int] = set()
    level_labels: set[str] = set()
    zone_ids: dict[str, str] = {}
    zone_names: set[str] = set()
    zone_scopes: dict[str, str] = {}
    space_counts: dict[str, int] = {name: 0 for name in selected_names}
    for level_index, level in enumerate(draft["levels"]):
        level_pointer = f"/levels/{level_index}"
        level_id = str(level["level_id"])
        if level_id in level_ids:
            errors.append(_error("FLOOR_ZONING_LEVEL_INVALID", f"{level_pointer}/level_id", f"{level_id} is declared more than once"))
        level_ids.add(level_id)
        order = int(level["order"])
        if order in level_orders:
            errors.append(_error("FLOOR_ZONING_LEVEL_INVALID", f"{level_pointer}/order", f"order {order} is used by more than one level; the human sequence must stay unambiguous"))
        level_orders.add(order)
        label = str(level["label"])
        if label in level_labels:
            errors.append(_error("FLOOR_ZONING_LEVEL_INVALID", f"{level_pointer}/label", f"label {label} is used by more than one level"))
        level_labels.add(label)
        for zone_index, zone in enumerate(level["zones"]):
            zone_pointer = f"{level_pointer}/zones/{zone_index}"
            zone_id = str(zone["zone_id"])
            if zone_id in zone_ids:
                errors.append(_error("FLOOR_ZONING_ZONE_INVALID", f"{zone_pointer}/zone_id", f"{zone_id} is declared more than once"))
            zone_ids[zone_id] = str(zone["name"])
            zone_name = str(zone["name"])
            if zone_name in zone_names:
                errors.append(_error("FLOOR_ZONING_ZONE_INVALID", f"{zone_pointer}/name", f"zone name {zone_name} is used more than once; the student view shows names only"))
            zone_names.add(zone_name)
            zone_scopes[zone_id] = str(zone["access_scope"])
            for space_index, space_name in enumerate(zone["space_names"]):
                name = str(space_name)
                if name not in selected_names:
                    errors.append(_error("FLOOR_ZONING_SPACE_UNKNOWN", f"{zone_pointer}/space_names/{space_index}", f"{name} is not a dimension-selected space in the bound selection"))
                    continue
                space_counts[name] += 1

    boundary_ids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for boundary_index, boundary in enumerate(draft["boundaries"]):
        pointer = f"/boundaries/{boundary_index}"
        boundary_id = str(boundary["boundary_id"])
        if boundary_id in boundary_ids:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", f"{pointer}/boundary_id", f"{boundary_id} is declared more than once"))
        boundary_ids.add(boundary_id)
        from_id = str(boundary["from_zone_id"])
        to_id = str(boundary["to_zone_id"])
        if from_id not in zone_ids:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", f"{pointer}/from_zone_id", f"{from_id} is not a declared zone"))
        if to_id not in zone_ids:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", f"{pointer}/to_zone_id", f"{to_id} is not a declared zone"))
        if from_id == to_id:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", pointer, "a boundary must connect two different zones"))
        pair = tuple(sorted((from_id, to_id)))
        if pair in pairs:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", pointer, f"the same unordered zone pair already carries a boundary: {from_id} and {to_id}"))
        pairs.add(pair)
        if from_id in zone_scopes and to_id in zone_scopes and zone_scopes[from_id] == zone_scopes[to_id]:
            errors.append(_error("FLOOR_ZONING_BOUNDARY_INVALID", pointer, "a public-internal boundary must connect zones with different access scopes"))

    record_ids: set[str] = set()
    for record_index, record in enumerate(draft["unresolved_zoning"]):
        pointer = f"/unresolved_zoning/{record_index}"
        record_id = str(record["record_id"])
        if record_id in record_ids:
            errors.append(_error("FLOOR_ZONING_UNRESOLVED_INVALID", f"{pointer}/record_id", f"{record_id} is declared more than once"))
        record_ids.add(record_id)
        name = str(record["space_name"])
        if name not in selected_names:
            errors.append(_error("FLOOR_ZONING_SPACE_UNKNOWN", f"{pointer}/space_name", f"{name} is not a dimension-selected space in the bound selection"))
            continue
        space_counts[name] += 1

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return errors

    coverage_errors: list[ZoningError] = []
    for name in sorted(space_counts):
        count = space_counts[name]
        if count == 0:
            coverage_errors.append(_error("FLOOR_ZONING_COVERAGE_INVALID", "", f"{name} is dimension-selected but neither zoned nor explicitly unresolved; selected spaces must not disappear"))
        elif count > 1:
            coverage_errors.append(_error("FLOOR_ZONING_COVERAGE_INVALID", "", f"{name} appears {count} times; a selected space keeps exactly one zone entry or one unresolved item"))
    return coverage_errors


def build_floor_zoning(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    draft: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    program_draft_schema: JsonObject,
    program_schema: JsonObject,
    dimension_draft_schema: JsonObject,
    dimension_plan_schema: JsonObject,
    selection_schema: JsonObject,
    zoning_draft_schema: JsonObject,
    zoning_schema: JsonObject,
) -> tuple[dict[str, Any] | None, ZoningResult]:
    """Return one deterministic floor zoning framework, or no output on any failed gate."""

    upstream = validate_dimension_plan(
        digest, board, program_draft, program, dimension_draft, dimension_plan,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema, dimension_draft_schema, dimension_plan_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
    )
    selection_errors = _verify_selection(selection, dimension_plan, selection_schema, registry)
    if selection_errors:
        return None, {"ok": False, "errors": selection_errors}

    draft_errors = _verify_confirmed_zoning_draft(draft, zoning_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors = _zoning_semantic_errors(draft, selection, dimension_plan)
    if semantic_errors:
        semantic_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": semantic_errors}

    candidate_index = _candidate_index(dimension_plan)
    selected_option: dict[str, str] = {str(item["space_name"]): str(item["selected_option_key"]) for item in selection["selections"]}

    def space_view(name: str) -> dict[str, Any]:
        candidate_set = candidate_index[name]
        option_key = selected_option[name]
        chosen = next(candidate for candidate in candidate_set["candidates"] if str(candidate["option_key"]) == option_key)
        return {
            "name": name,
            "selected_option_key": option_key,
            "long_side_m": chosen["long_side_m"],
            "short_side_m": chosen["short_side_m"],
            "footprint_area_m2": chosen["footprint_area_m2"],
            "area_source": candidate_set["area_source"],
            "confirmed_area_m2": candidate_set["confirmed_area_m2"],
        }

    zone_names = {str(zone["zone_id"]): str(zone["name"]) for level in draft["levels"] for zone in level["zones"]}
    levels_view = [
        {
            "label": str(level["label"]),
            "order": int(level["order"]),
            "zones": [
                {
                    "name": str(zone["name"]),
                    "access_scope": zone["access_scope"],
                    "activity_character": zone["activity_character"],
                    "spaces": [space_view(str(space_name)) for space_name in zone["space_names"]],
                }
                for zone in level["zones"]
            ],
        }
        for level in draft["levels"]
    ]
    boundaries_view = [
        {"from_zone": zone_names[str(boundary["from_zone_id"])], "to_zone": zone_names[str(boundary["to_zone_id"])], "note": str(boundary["note"])}
        for boundary in draft["boundaries"]
    ]
    unresolved_view = [{"space_name": str(record["space_name"]), "reason": str(record["reason"])} for record in draft["unresolved_zoning"]]

    next_action = dict(RESOLVE_GAPS_ACTION) if unresolved_view else dict(CIRCULATION_ACTION)

    zoning: dict[str, Any] = {
        "schema_version": "1.0.0",
        "zoning_kind": "student_floor_zoning",
        "source_binding": {
            "digest_input_hash": digest["input_hash"],
            "confirmed_digest_sha256": compute_confirmed_digest_sha256(digest),
            "pending_digest_sha256": digest["human_confirmation"]["pending_digest_sha256"],
            "start_board_sha256": _document_sha256(board),
            "confirmed_program_draft_sha256": _document_sha256(program_draft),
            "pending_program_draft_sha256": program_draft["human_confirmation"]["pending_draft_sha256"],
            "confirmed_program_sha256": _document_sha256(program),
            "pending_dimension_draft_sha256": dimension_draft["human_confirmation"]["pending_dimension_draft_sha256"],
            "confirmed_dimension_draft_sha256": _document_sha256(dimension_draft),
            "confirmed_dimension_plan_sha256": _document_sha256(dimension_plan),
            "dimension_selection_sha256": _document_sha256(selection),
            "pending_floor_zoning_draft_sha256": draft["human_confirmation"]["pending_floor_zoning_draft_sha256"],
            "confirmed_floor_zoning_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "floor_zoning_confirmed_ready_for_next_step",
            "levels": levels_view,
            "boundaries": boundaries_view,
            "unresolved_zoning": unresolved_view,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": next_action,
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    zoning_errors = _schema_errors(zoning, zoning_schema, registry, "STUDENT_FLOOR_ZONING_SCHEMA_INVALID")
    if zoning_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": zoning_errors}
    return zoning, {"ok": True, "errors": []}


def validate_floor_zoning(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    draft: JsonObject,
    zoning: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    program_draft_schema: JsonObject,
    program_schema: JsonObject,
    dimension_draft_schema: JsonObject,
    dimension_plan_schema: JsonObject,
    selection_schema: JsonObject,
    zoning_draft_schema: JsonObject,
    zoning_schema: JsonObject,
) -> ZoningResult:
    """Re-derive the expected framework from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
    )
    zoning_errors = _schema_errors(zoning, zoning_schema, registry, "STUDENT_FLOOR_ZONING_SCHEMA_INVALID")
    if zoning_errors:
        return {"ok": False, "errors": zoning_errors}

    expected, build_result = build_floor_zoning(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(zoning) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_FLOOR_ZONING_CONTENT_MISMATCH",
                    "",
                    "the supplied framework is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, ZoningResult]:
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
    """Confirm a pending zoning draft, build a framework, or validate one against its upstream chain."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending floor zoning draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student floor zoning draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one student floor zoning framework from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one student floor zoning framework against its upstream chain")
    for upstream_parser in (build_parser, validate_parser):
        upstream_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
        upstream_parser.add_argument("board", type=Path, help="student design start board JSON")
        upstream_parser.add_argument("program_draft", type=Path, help="confirmed student spatial program draft JSON")
        upstream_parser.add_argument("program", type=Path, help="student spatial program JSON")
        upstream_parser.add_argument("dimension_draft", type=Path, help="confirmed student dimension plan draft JSON")
        upstream_parser.add_argument("dimension_plan", type=Path, help="student dimension plan JSON")
        upstream_parser.add_argument("selection", type=Path, help="human dimension selection record JSON")
        upstream_parser.add_argument("draft", type=Path, help="confirmed student floor zoning draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("zoning", type=Path, help="student floor zoning framework JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema = load_json_object(INTAKE_SCHEMA_PATH)
        digest_schema = load_json_object(DIGEST_SCHEMA_PATH)
        board_schema = load_json_object(BOARD_SCHEMA_PATH)
        program_draft_schema = load_json_object(PROGRAM_DRAFT_SCHEMA_PATH)
        program_schema = load_json_object(PROGRAM_SCHEMA_PATH)
        dimension_draft_schema = load_json_object(DIMENSION_DRAFT_SCHEMA_PATH)
        dimension_plan_schema = load_json_object(DIMENSION_PLAN_SCHEMA_PATH)
        selection_schema = load_json_object(SELECTION_SCHEMA_PATH)
        zoning_draft_schema = load_json_object(ZONING_DRAFT_SCHEMA_PATH)
        zoning_schema = load_json_object(ZONING_SCHEMA_PATH)
        if arguments.command == "confirm":
            draft_document = load_json_object(arguments.draft)
            human_record = load_json_object(arguments.human_record)
        else:
            digest = load_json_object(arguments.digest)
            board = load_json_object(arguments.board)
            program_draft_document = load_json_object(arguments.program_draft)
            program_document = load_json_object(arguments.program)
            dimension_draft_document = load_json_object(arguments.dimension_draft)
            dimension_plan_document = load_json_object(arguments.dimension_plan)
            selection_document = load_json_object(arguments.selection)
            draft_document = load_json_object(arguments.draft)
            if arguments.command == "validate":
                zoning_document = load_json_object(arguments.zoning)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_zoning_draft(draft_document, human_record, zoning_draft_schema)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        zoning, result = build_floor_zoning(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document, selection_document, draft_document,
            intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
            dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        )
        if zoning is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(zoning, arguments.output)
        return exit_code

    result = validate_floor_zoning(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document, selection_document, draft_document, zoning_document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
