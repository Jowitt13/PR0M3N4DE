"""Build one deterministic student massing, grid, and height hypotheses framework.

This deterministic, local-only slice accepts the full confirmed ARCH-102
chain: an ARCH-097 AssignmentBriefDigest, its exact ARCH-098 start board
projection, the confirmed ARCH-099 spatial program draft and its exact
spatial program, the confirmed ARCH-100 dimension draft, its exact dimension
plan, the human dimension selection, the confirmed ARCH-101 floor zoning
draft and its exact floor zoning framework, the confirmed ARCH-102
circulation-environment draft and its exact circulation-environment
framework, and one human-confirmed massing-grid-height draft carrying two to
six student-written hypotheses. The machine only checks completeness, numeric
form, coverage, and traceability, and projects objective, fact-only
comparison rows; it never generates, ranks, scores, recommends, or selects a
hypothesis. Groups are student-declared functional combinations, never
coordinate volumes, building shapes, plan drawings, or final massing. Grid
bays and floor-to-floor values are checked as positive decimals only; no
structural safety, span, material, column size, load, seismic, foundation,
fire, or constructibility judgment is made. Vertical interval subtotals are
never called building height. The output is JSON data only: no PPTX, web
page, image, drawing, or three-dimensional model. It opens no socket and
starts no subprocess, reads no system clock, never modifies an input
document, and writes a destination only after full validation. Validate
re-derives the expected output deterministically and requires exact byte
equality.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
from build_student_circulation_environment import validate_circulation_environment
from build_student_design_start_board import compute_confirmed_digest_sha256
from build_student_dimension_plan import _decimal_text
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
CE_DRAFT_SCHEMA_PATH = REFERENCES / "student-circulation-environment-draft.schema.json"
CE_SCHEMA_PATH = REFERENCES / "student-circulation-environment.schema.json"
MGH_DRAFT_SCHEMA_PATH = REFERENCES / "student-massing-grid-height-draft.schema.json"
MGH_SCHEMA_PATH = REFERENCES / "student-massing-grid-height.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_MASSING_GRID_HEIGHT_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

NEXT_ACTION = {
    "action": "human_compare_and_select_massing_grid_height_hypotheses",
    "description": (
        "Next, the human compares the listed hypotheses and selects or revises one. "
        "This framework ranks, scores, recommends, and selects nothing."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "This framework projects only the massing groups, grid intents, and vertical intervals written by the student; it generates no hypothesis and selects nothing.",
    "Groups are student-declared functional combinations; they are not coordinate volumes, building shapes, plan drawings, or final massing.",
    "Group footprint subtotals account only for the dimension-declared footprints of the group's spaces; they are never building area, gross area, or actual massing.",
    "Vertical interval subtotals restate the student-declared floor-to-floor values; they are no building height, planning height, elevation, structural height, or code conclusion.",
    "It decides no entrance, plan coordinate, orientation, site conclusion, structural system, regulation, or constructibility.",
    "Comparison rows restate facts only; the framework ranks, scores, recommends, and selects nothing.",
)


class MassingError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class MassingResult(TypedDict):
    """The public result of confirming, building, or validating one massing-grid-height framework."""

    ok: bool
    errors: list[MassingError]


def compute_pending_mgh_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation massing-grid-height draft.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_mgh_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, MassingResult]:
    """Bind one explicit human confirmation record to a pending massing-grid-height draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "MASSING_GRID_HEIGHT_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("MASSING_GRID_HEIGHT_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[MassingError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_massing_grid_height_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_massing_grid_height_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "/pending_massing_grid_height_draft_sha256", "pending_massing_grid_height_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_mgh_draft_sha256(draft):
            errors.append(_error("MASSING_GRID_HEIGHT_DRAFT_HASH_MISMATCH", "/pending_massing_grid_height_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_massing_grid_height_draft_sha256": human_record["pending_massing_grid_height_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "MASSING_GRID_HEIGHT_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_mgh_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[MassingError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched massing-grid-height draft."""

    errors = _schema_errors(draft, draft_schema, registry, "MASSING_GRID_HEIGHT_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("MASSING_GRID_HEIGHT_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the massing-grid-height draft must be confirmed before a framework can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_massing_grid_height_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_mgh_draft_sha256(draft):
        return [_error("MASSING_GRID_HEIGHT_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_massing_grid_height_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _positive_decimal(value: object) -> Decimal | None:
    """Parse one strict positive finite decimal string, or return None."""

    if not isinstance(value, str):
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _decimal_canonical(value: object) -> str:
    """Return one stable canonical form for pseudo-option comparison."""

    try:
        return str(Decimal(str(value)).normalize())
    except InvalidOperation:
        return str(value)


def _hypothesis_fingerprint(hypothesis: JsonObject) -> tuple:
    """Capture only the substantive content: group composition, grid, and floor-to-floor values."""

    groups = tuple(
        sorted((str(group["level_id"]), tuple(sorted(str(zone_id) for zone_id in group["zone_ids"]))) for group in hypothesis["massing_groups"])
    )
    grid_intent = hypothesis["grid_intent"]
    grid = (
        str(grid_intent["grid_pattern"]),
        _decimal_canonical(grid_intent["primary_bay_m"]),
        _decimal_canonical(grid_intent["secondary_bay_m"]),
    )
    verticals = tuple(
        sorted((str(interval["level_id"]), _decimal_canonical(interval["floor_to_floor_m"])) for interval in hypothesis["vertical_intervals"])
    )
    return (groups, grid, verticals)


def _mgh_semantic_errors(draft: JsonObject, zoning_draft: JsonObject, ce_framework: JsonObject) -> list[MassingError]:
    """Check source binding, group, grid, vertical, and pseudo-option rules without generating anything."""

    errors: list[MassingError] = []
    if draft["source_circulation_environment_sha256"] != _document_sha256(ce_framework):
        errors.append(_error("MASSING_GRID_HEIGHT_SOURCE_CIRCULATION_MISMATCH", "/source_circulation_environment_sha256", "the draft does not bind the supplied confirmed circulation-environment framework"))
        return errors

    zone_registry: dict[str, dict[str, str]] = {}
    level_registry: dict[str, str] = {}
    for level in zoning_draft["levels"]:
        level_id = str(level["level_id"])
        level_registry[level_id] = str(level["label"])
        for zone in level["zones"]:
            zone_registry[str(zone["zone_id"])] = {"name": str(zone["name"]), "level_id": level_id}

    hypothesis_ids: set[str] = set()
    fingerprints: list[tuple] = []
    for index, hypothesis in enumerate(draft["hypotheses"]):
        pointer = f"/hypotheses/{index}"
        hypothesis_id = str(hypothesis["hypothesis_id"])
        if hypothesis_id in hypothesis_ids:
            errors.append(_error("MASSING_GRID_HEIGHT_HYPOTHESIS_INVALID", f"{pointer}/hypothesis_id", f"{hypothesis_id} is declared more than once"))
        hypothesis_ids.add(hypothesis_id)
        fingerprints.append(_hypothesis_fingerprint(hypothesis))

        group_ids: set[str] = set()
        zone_counts: dict[str, int] = {}
        for group_index, group in enumerate(hypothesis["massing_groups"]):
            group_pointer = f"{pointer}/massing_groups/{group_index}"
            group_id = str(group["group_id"])
            if group_id in group_ids:
                errors.append(_error("MASSING_GROUP_INVALID", f"{group_pointer}/group_id", f"{group_id} is declared more than once in this hypothesis"))
            group_ids.add(group_id)
            level_id = str(group["level_id"])
            if level_id not in level_registry:
                errors.append(_error("MASSING_GROUP_INVALID", f"{group_pointer}/level_id", f"{level_id} is not a level in the confirmed floor zoning draft"))
            for zone_index, zone_id_raw in enumerate(group["zone_ids"]):
                zone_id = str(zone_id_raw)
                zone = zone_registry.get(zone_id)
                if zone is None:
                    errors.append(_error("MASSING_GROUP_INVALID", f"{group_pointer}/zone_ids/{zone_index}", f"{zone_id} is not a zone in the confirmed floor zoning draft"))
                    continue
                if level_id in level_registry and zone["level_id"] != level_id:
                    errors.append(_error("MASSING_GROUP_INVALID", f"{group_pointer}/zone_ids/{zone_index}", f"zone {zone['name']} belongs to another level and cannot join this group"))
                zone_counts[zone_id] = zone_counts.get(zone_id, 0) + 1
        for zone_id in sorted(zone_registry):
            count = zone_counts.get(zone_id, 0)
            name = zone_registry[zone_id]["name"]
            if count == 0:
                errors.append(_error("MASSING_ZONE_COVERAGE_INVALID", pointer, f"zone {name} does not appear in any massing group of this hypothesis; zones must not disappear"))
            elif count > 1:
                errors.append(_error("MASSING_ZONE_COVERAGE_INVALID", pointer, f"zone {name} appears more than once in this hypothesis; a zone keeps exactly one group"))

        grid_pointer = f"{pointer}/grid_intent"
        grid_intent = hypothesis["grid_intent"]
        if _positive_decimal(grid_intent["primary_bay_m"]) is None:
            errors.append(_error("GRID_INTENT_INVALID", f"{grid_pointer}/primary_bay_m", "primary_bay_m must be a positive finite decimal string"))
        if _positive_decimal(grid_intent["secondary_bay_m"]) is None:
            errors.append(_error("GRID_INTENT_INVALID", f"{grid_pointer}/secondary_bay_m", "secondary_bay_m must be a positive finite decimal string"))

        interval_levels: list[str] = []
        for interval_index, interval in enumerate(hypothesis["vertical_intervals"]):
            interval_pointer = f"{pointer}/vertical_intervals/{interval_index}"
            level_id = str(interval["level_id"])
            if level_id not in level_registry:
                errors.append(_error("VERTICAL_INTERVAL_INVALID", f"{interval_pointer}/level_id", f"{level_id} is not a level in the confirmed floor zoning draft"))
            interval_levels.append(level_id)
            if _positive_decimal(interval["floor_to_floor_m"]) is None:
                errors.append(_error("VERTICAL_INTERVAL_INVALID", f"{interval_pointer}/floor_to_floor_m", "floor_to_floor_m must be a positive finite decimal string"))
        for level_id in sorted(level_registry):
            occurrences = interval_levels.count(level_id)
            if occurrences == 0:
                errors.append(_error("VERTICAL_INTERVAL_INVALID", pointer, f"level {level_registry[level_id]} has no vertical interval in this hypothesis; every level appears exactly once"))
            elif occurrences > 1:
                errors.append(_error("VERTICAL_INTERVAL_INVALID", pointer, f"level {level_registry[level_id]} carries more than one vertical interval in this hypothesis"))

    seen_fingerprints: set[tuple] = set()
    for fingerprint in fingerprints:
        if fingerprint in seen_fingerprints:
            errors.append(_error("MASSING_GRID_HEIGHT_HYPOTHESIS_INVALID", "/hypotheses", "two hypotheses differ only in label or note; pseudo-options are forbidden"))
            break
        seen_fingerprints.add(fingerprint)

    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def build_massing_grid_height(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    zoning_draft: JsonObject,
    zoning_framework: JsonObject,
    ce_draft: JsonObject,
    ce_framework: JsonObject,
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
    ce_draft_schema: JsonObject,
    ce_schema: JsonObject,
    mgh_draft_schema: JsonObject,
    mgh_schema: JsonObject,
) -> tuple[dict[str, Any] | None, MassingResult]:
    """Return one deterministic massing-grid-height framework, or no output on any failed gate."""

    upstream = validate_circulation_environment(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    unresolved_items = ce_framework["student_view"].get("unresolved_items")
    if unresolved_items:
        return None, {
            "ok": False,
            "errors": [
                _error(
                    "MASSING_GRID_HEIGHT_UPSTREAM_UNRESOLVED",
                    "/upstream/unresolved_items",
                    "the upstream circulation-environment framework still carries unresolved items; they must be resolved via resolve_circulation_environment_gaps before forming massing, grid, and height hypotheses",
                )
            ],
        }

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    draft_errors = _verify_confirmed_mgh_draft(draft, mgh_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors = _mgh_semantic_errors(draft, zoning_draft, ce_framework)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}

    zone_registry: dict[str, dict[str, str]] = {}
    level_registry: dict[str, str] = {}
    zone_spaces: dict[str, list[str]] = {}
    for level in zoning_draft["levels"]:
        level_id = str(level["level_id"])
        level_registry[level_id] = str(level["label"])
        for zone in level["zones"]:
            zone_id = str(zone["zone_id"])
            zone_registry[zone_id] = {"name": str(zone["name"]), "level_id": level_id}
            zone_spaces[zone_id] = [str(space_name) for space_name in zone["space_names"]]

    footprint_by_space: dict[str, Decimal] = {}
    for candidate_set in dimension_plan["student_view"]["candidate_sets"]:
        space_name = str(candidate_set["space_name"])
        selected_key = next(
            str(item["selected_option_key"]) for item in selection["selections"] if str(item["space_name"]) == space_name
        )
        chosen = next(candidate for candidate in candidate_set["candidates"] if str(candidate["option_key"]) == selected_key)
        footprint_by_space[space_name] = Decimal(str(chosen["footprint_area_m2"]))

    hypotheses_view: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    for hypothesis in draft["hypotheses"]:
        groups_view: list[dict[str, Any]] = []
        for group in hypothesis["massing_groups"]:
            subtotal = Decimal(0)
            for zone_id in (str(zone_id) for zone_id in group["zone_ids"]):
                for space_name in zone_spaces[zone_id]:
                    subtotal += footprint_by_space[space_name]
            groups_view.append(
                {
                    "level": level_registry[str(group["level_id"])],
                    "zones": [zone_registry[str(zone_id)]["name"] for zone_id in group["zone_ids"]],
                    "role": group["role"],
                    "note": str(group["note"]),
                    "space_footprint_subtotal_m2": _decimal_text(subtotal),
                }
            )
        grid_intent = hypothesis["grid_intent"]
        intervals_view = [
            {
                "level": level_registry[str(interval["level_id"])],
                "floor_to_floor_m": str(interval["floor_to_floor_m"]),
                "note": str(interval["note"]),
            }
            for interval in hypothesis["vertical_intervals"]
        ]
        vertical_subtotal = sum(
            (_positive_decimal(interval["floor_to_floor_m"]) for interval in hypothesis["vertical_intervals"]),
            Decimal(0),
        )
        vertical_subtotal_text = _decimal_text(vertical_subtotal)
        hypotheses_view.append(
            {
                "label": str(hypothesis["label"]),
                "massing_groups": groups_view,
                "grid_intent": {
                    "grid_pattern": grid_intent["grid_pattern"],
                    "primary_bay_m": str(grid_intent["primary_bay_m"]),
                    "secondary_bay_m": str(grid_intent["secondary_bay_m"]),
                    "note": str(grid_intent["note"]),
                },
                "vertical_intervals": intervals_view,
                "vertical_interval_subtotal_m": vertical_subtotal_text,
                "note": str(hypothesis["note"]),
            }
        )
        comparison_rows.append(
            {
                "label": str(hypothesis["label"]),
                "group_count": len(groups_view),
                "grid_pattern": grid_intent["grid_pattern"],
                "primary_bay_m": str(grid_intent["primary_bay_m"]),
                "secondary_bay_m": str(grid_intent["secondary_bay_m"]),
                "vertical_interval_subtotal_m": vertical_subtotal_text,
            }
        )

    framework: dict[str, Any] = {
        "schema_version": "1.0.0",
        "framework_kind": "student_massing_grid_height_hypotheses",
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
            "pending_floor_zoning_draft_sha256": zoning_draft["human_confirmation"]["pending_floor_zoning_draft_sha256"],
            "confirmed_floor_zoning_draft_sha256": _document_sha256(zoning_draft),
            "floor_zoning_framework_sha256": _document_sha256(zoning_framework),
            "pending_circulation_environment_draft_sha256": ce_draft["human_confirmation"]["pending_circulation_environment_draft_sha256"],
            "confirmed_circulation_environment_draft_sha256": _document_sha256(ce_draft),
            "circulation_environment_framework_sha256": _document_sha256(ce_framework),
            "pending_massing_grid_height_draft_sha256": draft["human_confirmation"]["pending_massing_grid_height_draft_sha256"],
            "confirmed_massing_grid_height_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "massing_grid_height_hypotheses_confirmed",
            "hypotheses": hypotheses_view,
            "comparison_summary": comparison_rows,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": dict(NEXT_ACTION),
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    framework_errors = _schema_errors(framework, mgh_schema, registry, "STUDENT_MASSING_GRID_HEIGHT_SCHEMA_INVALID")
    if framework_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": framework_errors}
    return framework, {"ok": True, "errors": []}


def validate_massing_grid_height(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    zoning_draft: JsonObject,
    zoning_framework: JsonObject,
    ce_draft: JsonObject,
    ce_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
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
    ce_draft_schema: JsonObject,
    ce_schema: JsonObject,
    mgh_draft_schema: JsonObject,
    mgh_schema: JsonObject,
) -> MassingResult:
    """Re-derive the expected framework from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    framework_errors = _schema_errors(framework, mgh_schema, registry, "STUDENT_MASSING_GRID_HEIGHT_SCHEMA_INVALID")
    if framework_errors:
        return {"ok": False, "errors": framework_errors}

    expected, build_result = build_massing_grid_height(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(framework) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_MASSING_GRID_HEIGHT_CONTENT_MISMATCH",
                    "",
                    "the supplied framework is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, MassingResult]:
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
    """Confirm a pending massing draft, build a framework, or validate one against its upstream chain."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending massing-grid-height draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student massing-grid-height draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one student massing-grid-height framework from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one student massing-grid-height framework against its upstream chain")
    for upstream_parser in (build_parser, validate_parser):
        upstream_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
        upstream_parser.add_argument("board", type=Path, help="student design start board JSON")
        upstream_parser.add_argument("program_draft", type=Path, help="confirmed student spatial program draft JSON")
        upstream_parser.add_argument("program", type=Path, help="student spatial program JSON")
        upstream_parser.add_argument("dimension_draft", type=Path, help="confirmed student dimension plan draft JSON")
        upstream_parser.add_argument("dimension_plan", type=Path, help="student dimension plan JSON")
        upstream_parser.add_argument("selection", type=Path, help="human dimension selection record JSON")
        upstream_parser.add_argument("zoning_draft", type=Path, help="confirmed student floor zoning draft JSON")
        upstream_parser.add_argument("zoning_framework", type=Path, help="student floor zoning framework JSON")
        upstream_parser.add_argument("ce_draft", type=Path, help="confirmed student circulation-environment draft JSON")
        upstream_parser.add_argument("ce_framework", type=Path, help="student circulation-environment framework JSON")
        upstream_parser.add_argument("draft", type=Path, help="confirmed student massing-grid-height draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("framework", type=Path, help="student massing-grid-height framework JSON")

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
        ce_draft_schema = load_json_object(CE_DRAFT_SCHEMA_PATH)
        ce_schema = load_json_object(CE_SCHEMA_PATH)
        mgh_draft_schema = load_json_object(MGH_DRAFT_SCHEMA_PATH)
        mgh_schema = load_json_object(MGH_SCHEMA_PATH)
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
            zoning_draft_document = load_json_object(arguments.zoning_draft)
            zoning_framework_document = load_json_object(arguments.zoning_framework)
            ce_draft_document = load_json_object(arguments.ce_draft)
            ce_framework_document = load_json_object(arguments.ce_framework)
            draft_document = load_json_object(arguments.draft)
            if arguments.command == "validate":
                framework_document = load_json_object(arguments.framework)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_mgh_draft(draft_document, human_record, mgh_draft_schema)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        framework, result = build_massing_grid_height(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document, draft_document,
            intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
            dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
            ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
        )
        if framework is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(framework, arguments.output)
        return exit_code

    result = validate_massing_grid_height(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document, draft_document, framework_document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
