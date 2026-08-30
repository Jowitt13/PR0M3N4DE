"""Build and validate one student schematic plan blocks document.

This deterministic, local-only slice accepts one valid, untampered ARCH-106
plan framework without unresolved plan items and one confirmed
human-authored schematic plan draft. It reuses the committed
``validate_plan_framework`` public entry, so the complete ARCH-097~106
chain is re-verified and every upstream stable error code propagates
unchanged. A plan framework that still carries unresolved plan items fails
closed with ``SCHEMATIC_PLAN_UPSTREAM_UNRESOLVED`` before any output. The
builder never re-selects a hypothesis and never changes the
human-selected dimension options, levels, zones, space names, or confirmed
relations.

The student draft is a rectangle block table in local schematic
coordinates, not a drawing: one local container per confirmed level and
one placement per confirmed space with student-written x, y, and a
rotation of 0 or 90 degrees. Width and depth are never written by the
student: they follow from the ARCH-100 human-selected long and short
sides. The machine checks coverage, level and zone membership, container
bounds, positive-area overlap, and the declared adjacent and separate
geometry; near, buffered, and flexible relations stay human intent with no
fabricated distance or performance judgment. The machine never moves,
optimizes, or draws anything. The next action is
``human_review_schematic_plan_blocks``. The output is JSON data only. The
script opens no socket and starts no subprocess, reads no system clock,
never modifies an input document, and writes a destination only after full
validation. Validate re-derives the expected blocks deterministically and
requires exact byte equality.
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
from build_student_hypothesis_comparison import (
    COMPARISON_DRAFT_SCHEMA_PATH,
    COMPARISON_SCHEMA_PATH,
)
from build_student_plan_framework import (
    PLAN_DRAFT_SCHEMA_PATH,
    PLAN_SCHEMA_PATH,
    validate_plan_framework,
)
from build_student_selected_hypothesis_state import STATE_SCHEMA_PATH
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
SCHEMATIC_DRAFT_SCHEMA_PATH = REFERENCES / "student-schematic-plan-blocks-draft.schema.json"
SCHEMATIC_SCHEMA_PATH = REFERENCES / "student-schematic-plan-blocks.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_SCHEMATIC_PLAN_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

NEXT_ACTION = {
    "action": "human_review_schematic_plan_blocks",
    "description": (
        "The human reviews the projected rectangle blocks in local schematic coordinates as "
        "student-authored input; the machine never moves, optimizes, or draws anything."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "All coordinates are local schematic coordinates only: they carry no latitude, longitude, north direction, site coordinate, or elevation.",
    "The local container is a sketch frame, never a site boundary, a total plan, a final massing outline, a regulation conclusion, or a constructibility claim.",
    "Width and depth come only from the ARCH-100 human-selected long and short sides; the machine never rescales a rectangle.",
    "Near, buffered_transition, and flexibly_divisible relations stay human intent; no distance, adjacency, or performance judgment is derived from them.",
    "This stage generates no wall, door, column, stair, toilet, entrance, corridor, or building outline, and it decides no orientation, daylight, wind, view, noise, structure, fire, cost, performance, regulation, or constructibility.",
    "The machine never moves a rectangle, resolves a conflict, fills a gap, or optimizes area efficiency.",
)


class SchematicError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class SchematicResult(TypedDict):
    """The public result of confirming, building, or validating one schematic plan blocks document."""

    ok: bool
    errors: list[SchematicError]


def compute_pending_schematic_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation schematic plan draft.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_schematic_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, SchematicResult]:
    """Bind one explicit human confirmation record to a pending schematic plan draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "SCHEMATIC_PLAN_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("SCHEMATIC_PLAN_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[SchematicError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_student_schematic_plan_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_student_schematic_plan_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "/pending_student_schematic_plan_draft_sha256", "pending_student_schematic_plan_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_schematic_draft_sha256(draft):
            errors.append(_error("SCHEMATIC_PLAN_DRAFT_HASH_MISMATCH", "/pending_student_schematic_plan_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_student_schematic_plan_draft_sha256": human_record["pending_student_schematic_plan_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "SCHEMATIC_PLAN_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_schematic_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[SchematicError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched schematic draft."""

    errors = _schema_errors(draft, draft_schema, registry, "SCHEMATIC_PLAN_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("SCHEMATIC_PLAN_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the schematic plan draft must be confirmed before a blocks document can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_student_schematic_plan_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_schematic_draft_sha256(draft):
        return [_error("SCHEMATIC_PLAN_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_student_schematic_plan_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


Rect = tuple[Decimal, Decimal, Decimal, Decimal]


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:  # pragma: no cover - schema patterns already restrict the form.
        return None


def _rectangles_overlap(first: Rect, second: Rect) -> bool:
    """True when two rectangles overlap with positive area."""

    x1, y1, w1, d1 = first
    x2, y2, w2, d2 = second
    return x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + d2 and y2 < y1 + d1


def _rectangles_touch(first: Rect, second: Rect) -> bool:
    """True when two rectangles touch or overlap (closed-interval intersection)."""

    x1, y1, w1, d1 = first
    x2, y2, w2, d2 = second
    return x1 <= x2 + w2 and x2 <= x1 + w1 and y1 <= y2 + d2 and y2 <= y1 + d1


def _share_positive_boundary(first: Rect, second: Rect) -> bool:
    """True when two rectangles share a boundary segment of positive length."""

    x1, y1, w1, d1 = first
    x2, y2, w2, d2 = second
    vertical = (x1 + w1 == x2 or x2 + w2 == x1) and min(y1 + d1, y2 + d2) > max(y1, y2)
    horizontal = (y1 + d1 == y2 or y2 + d2 == y1) and min(x1 + w1, x2 + w2) > max(x1, x2)
    return vertical or horizontal


def _schematic_semantic_errors(draft: JsonObject, zoning_framework: JsonObject, plan_framework: JsonObject) -> list[SchematicError]:
    """Check level/space coverage, membership, container bounds, overlap, and declared adjacent/separate geometry without generating anything."""

    errors: list[SchematicError] = []

    levels = zoning_framework["student_view"]["levels"]
    level_labels = [str(level["label"]) for level in levels]
    space_names: list[str] = []
    level_of_space: dict[str, str] = {}
    zone_of_space: dict[str, str] = {}
    dimension_of_space: dict[str, tuple[str, str]] = {}
    for level in levels:
        for zone in level["zones"]:
            for space in zone["spaces"]:
                space_name = str(space["name"])
                if space_name not in level_of_space:
                    space_names.append(space_name)
                level_of_space[space_name] = str(level["label"])
                zone_of_space[space_name] = str(zone["name"])
                dimension_of_space[space_name] = (str(space["long_side_m"]), str(space["short_side_m"]))
    space_set = set(space_names)

    draft_levels: list[str] = []
    placed_spaces: list[str] = []
    rect_by_space: dict[str, Rect] = {}
    rects_by_level: dict[str, list[tuple[str, Rect]]] = {}
    for level_index, level_entry in enumerate(draft["levels"]):
        pointer = f"/levels/{level_index}"
        level_name = str(level_entry["level"])
        if level_name not in level_labels:
            errors.append(_error("SCHEMATIC_PLAN_LEVEL_INVALID", f"{pointer}/level", f"{level_name} is not a confirmed level"))
        if level_name in draft_levels:
            errors.append(_error("SCHEMATIC_PLAN_LEVEL_INVALID", f"{pointer}/level", f"{level_name} is declared more than once"))
        draft_levels.append(level_name)
        container = level_entry["container"]
        container_w = _decimal(container["width_m"])
        container_d = _decimal(container["depth_m"])
        if container_w is None or container_d is None:  # pragma: no cover - schema patterns already restrict the form.
            errors.append(_error("SCHEMATIC_PLAN_CONTAINER_INVALID", f"{pointer}/container", "container dimensions must be finite strictly positive decimals"))
            continue
        if not container_w.is_finite() or not container_d.is_finite() or container_w <= 0 or container_d <= 0:
            errors.append(_error("SCHEMATIC_PLAN_CONTAINER_INVALID", f"{pointer}/container", "container dimensions must be finite and strictly positive; a zero-area or non-finite container is not a valid local plan frame"))
            continue
        level_rects: list[tuple[str, Rect]] = []
        for placement_index, placement in enumerate(level_entry["placements"]):
            placement_pointer = f"{pointer}/placements/{placement_index}"
            space_name = str(placement["space_name"])
            if space_name not in space_set:
                errors.append(_error("SCHEMATIC_PLAN_SPACE_INVALID", f"{placement_pointer}/space_name", f"{space_name} is not a confirmed space"))
                continue
            if level_of_space.get(space_name) != level_name:
                errors.append(_error("SCHEMATIC_PLAN_LEVEL_INVALID", f"{placement_pointer}/space_name", f"{space_name} must stay in its confirmed level and zone"))
            if space_name in placed_spaces:
                errors.append(_error("SCHEMATIC_PLAN_COVERAGE_INVALID", f"{placement_pointer}/space_name", f"{space_name} is placed more than once"))
            placed_spaces.append(space_name)
            x = _decimal(placement["x_m"])
            y = _decimal(placement["y_m"])
            if x is None or y is None or not x.is_finite() or not y.is_finite():  # pragma: no cover - schema patterns already restrict the form.
                errors.append(_error("SCHEMATIC_PLAN_CONTAINER_INVALID", f"{placement_pointer}", "placement coordinates must be finite non-negative decimals"))
                continue
            rotation = int(placement["rotation_degrees"])
            long_side, short_side = dimension_of_space[space_name]
            width = _decimal(long_side if rotation == 0 else short_side)
            depth = _decimal(short_side if rotation == 0 else long_side)
            if width is None or depth is None:  # pragma: no cover - defended by the upstream dimension contract.
                errors.append(_error("SCHEMATIC_PLAN_CONTAINER_INVALID", f"{placement_pointer}", "the selected dimension sides could not be read"))
                continue
            if x + width > container_w or y + depth > container_d:
                errors.append(_error("SCHEMATIC_PLAN_CONTAINER_INVALID", f"{placement_pointer}", f"{space_name} extends outside its level container"))
            rect = (x, y, width, depth)
            rect_by_space[space_name] = rect
            level_rects.append((space_name, rect))
        rects_by_level[level_name] = level_rects

    for space_name in space_names:
        if space_name not in placed_spaces:
            errors.append(_error("SCHEMATIC_PLAN_COVERAGE_INVALID", "", f"{space_name} has no placement; every confirmed space is placed exactly once"))
    for level_label in level_labels:
        if level_label not in draft_levels:
            errors.append(_error("SCHEMATIC_PLAN_LEVEL_INVALID", "", f"{level_label} has no local container"))

    for level_name, level_rects in rects_by_level.items():
        for first_index in range(len(level_rects)):
            first_space, first_rect = level_rects[first_index]
            for second_index in range(first_index + 1, len(level_rects)):
                second_space, second_rect = level_rects[second_index]
                if _rectangles_overlap(first_rect, second_rect):
                    errors.append(_error("SCHEMATIC_PLAN_OVERLAP_INVALID", "", f"{first_space} and {second_space} overlap with positive area on {level_name}"))

    for index, relation in enumerate(plan_framework["student_view"]["relations"]):
        from_space = str(relation["from_space"])
        to_space = str(relation["to_space"])
        category = str(relation["relation_category"])
        if category not in ("adjacent", "separate"):
            continue
        first_rect = rect_by_space.get(from_space)
        second_rect = rect_by_space.get(to_space)
        if first_rect is None or second_rect is None:  # pragma: no cover - upstream relations reference confirmed spaces only.
            continue
        if category == "adjacent":
            if level_of_space.get(from_space) != level_of_space.get(to_space):
                errors.append(_error("SCHEMATIC_PLAN_ADJACENCY_INVALID", f"/student_view/relations/{index}", f"{from_space} and {to_space} are declared adjacent but sit on different levels"))
            elif not _share_positive_boundary(first_rect, second_rect):
                errors.append(_error("SCHEMATIC_PLAN_ADJACENCY_INVALID", f"/student_view/relations/{index}", f"{from_space} and {to_space} are declared adjacent but share no positive-length boundary"))
        else:
            if level_of_space.get(from_space) == level_of_space.get(to_space) and _rectangles_touch(first_rect, second_rect):
                errors.append(_error("SCHEMATIC_PLAN_SEPARATION_INVALID", f"/student_view/relations/{index}", f"{from_space} and {to_space} are declared separate but touch or overlap"))

    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _project_blocks(
    plan_framework: JsonObject,
    zoning_framework: JsonObject,
    draft: JsonObject,
    blocks_schema: JsonObject,
    registry: Any,
) -> dict[str, Any] | None:
    """Project one schematic plan blocks document from already-validated inputs."""

    zone_order_by_level: dict[str, list[str]] = {}
    zone_of_space: dict[str, str] = {}
    dimension_of_space: dict[str, tuple[str, str]] = {}
    for level in zoning_framework["student_view"]["levels"]:
        level_label = str(level["label"])
        zone_order_by_level[level_label] = [str(zone["name"]) for zone in level["zones"]]
        for zone in level["zones"]:
            for space in zone["spaces"]:
                space_name = str(space["name"])
                zone_of_space[space_name] = str(zone["name"])
                dimension_of_space[space_name] = (str(space["long_side_m"]), str(space["short_side_m"]))

    projected_levels: list[dict[str, Any]] = []
    for level_entry in draft["levels"]:
        level_name = str(level_entry["level"])
        placements_by_zone: dict[str, list[dict[str, Any]]] = {zone: [] for zone in zone_order_by_level[level_name]}
        for placement in level_entry["placements"]:
            space_name = str(placement["space_name"])
            long_side, short_side = dimension_of_space[space_name]
            rotation = int(placement["rotation_degrees"])
            width = long_side if rotation == 0 else short_side
            depth = short_side if rotation == 0 else long_side
            placements_by_zone[zone_of_space[space_name]].append(
                {
                    "space_name": space_name,
                    "x_m": str(placement["x_m"]),
                    "y_m": str(placement["y_m"]),
                    "rotation_degrees": rotation,
                    "width_m": width,
                    "depth_m": depth,
                }
            )
        projected_levels.append(
            {
                "level_label": level_name,
                "container": {"width_m": str(level_entry["container"]["width_m"]), "depth_m": str(level_entry["container"]["depth_m"])},
                "zones": [
                    {"zone_name": zone, "spaces": placements_by_zone[zone]}
                    for zone in zone_order_by_level[level_name]
                    if placements_by_zone[zone]
                ],
            }
        )

    projected_relations: list[dict[str, Any]] = []
    for relation in plan_framework["student_view"]["relations"]:
        category = str(relation["relation_category"])
        projected_relations.append(
            {
                "from_space": str(relation["from_space"]),
                "to_space": str(relation["to_space"]),
                "relation_category": category,
                "note": str(relation["note"]),
                "verification_status": "geometrically_verified" if category in ("adjacent", "separate") else "human_authored_intent_only",
            }
        )

    blocks: dict[str, Any] = {
        "schema_version": "1.0.0",
        "blocks_kind": "student_schematic_plan_blocks",
        "source_binding": {
            **dict(plan_framework["source_binding"]),
            "plan_framework_sha256": _document_sha256(plan_framework),
            "pending_student_schematic_plan_draft_sha256": str(draft["human_confirmation"]["pending_student_schematic_plan_draft_sha256"]),
            "confirmed_student_schematic_plan_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": plan_framework["student_view"]["project_title"],
            "stage": "schematic_plan_blocks_confirmed",
            "coordinate_scope": "local_schematic_coordinates_only",
            "levels": projected_levels,
            "relations": projected_relations,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": dict(NEXT_ACTION),
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    blocks_errors = _schema_errors(blocks, blocks_schema, registry, "STUDENT_SCHEMATIC_PLAN_BLOCKS_SCHEMA_INVALID")
    if blocks_errors:  # pragma: no cover - defends the output contract against future drift.
        return None
    return blocks


def build_schematic_plan_blocks(
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
    mgh_draft: JsonObject,
    mgh_framework: JsonObject,
    comparison_draft: JsonObject,
    document: JsonObject,
    state_package: JsonObject,
    plan_draft: JsonObject,
    plan_framework: JsonObject,
    schematic_draft: JsonObject,
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
    comparison_draft_schema: JsonObject,
    comparison_schema: JsonObject,
    state_schema: JsonObject,
    plan_draft_schema: JsonObject,
    plan_framework_schema: JsonObject,
    schematic_draft_schema: JsonObject,
    blocks_schema: JsonObject,
) -> tuple[dict[str, Any] | None, SchematicResult]:
    """Return one deterministic schematic plan blocks document, or no output on any failed gate."""

    upstream = validate_plan_framework(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document, state_package, plan_draft, plan_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, plan_framework_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    if plan_framework["student_view"]["unresolved_plan_items"]:
        return None, {
            "ok": False,
            "errors": [
                _error(
                    "SCHEMATIC_PLAN_UPSTREAM_UNRESOLVED",
                    "/student_view/unresolved_plan_items",
                    "the validated plan framework still carries unresolved plan items; resolve them first with resolve_plan_framework_gaps",
                )
            ],
        }

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, plan_framework_schema, schematic_draft_schema, blocks_schema,
    )
    draft_errors = _verify_confirmed_schematic_draft(schematic_draft, schematic_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    if draft_source := schematic_draft.get("source_plan_framework_sha256"):
        if not isinstance(draft_source, str) or draft_source != _document_sha256(plan_framework):
            return None, {
                "ok": False,
                "errors": [
                    _error(
                        "SCHEMATIC_PLAN_SOURCE_FRAMEWORK_MISMATCH",
                        "/source_plan_framework_sha256",
                        "the draft does not bind the supplied plan framework",
                    )
                ],
            }

    semantic_errors = _schematic_semantic_errors(schematic_draft, zoning_framework, plan_framework)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}

    blocks = _project_blocks(plan_framework, zoning_framework, schematic_draft, blocks_schema, registry)
    if blocks is None:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": [_error("STUDENT_SCHEMATIC_PLAN_BLOCKS_SCHEMA_INVALID", "", "the built schematic plan blocks failed its closed schema")]}
    return blocks, {"ok": True, "errors": []}


def validate_schematic_plan_blocks(
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
    mgh_draft: JsonObject,
    mgh_framework: JsonObject,
    comparison_draft: JsonObject,
    document: JsonObject,
    state_package: JsonObject,
    plan_draft: JsonObject,
    plan_framework: JsonObject,
    schematic_draft: JsonObject,
    blocks: JsonObject,
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
    comparison_draft_schema: JsonObject,
    comparison_schema: JsonObject,
    state_schema: JsonObject,
    plan_draft_schema: JsonObject,
    plan_framework_schema: JsonObject,
    schematic_draft_schema: JsonObject,
    blocks_schema: JsonObject,
) -> SchematicResult:
    """Re-derive the expected schematic plan blocks from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, plan_framework_schema, schematic_draft_schema, blocks_schema,
    )
    blocks_errors = _schema_errors(blocks, blocks_schema, registry, "STUDENT_SCHEMATIC_PLAN_BLOCKS_SCHEMA_INVALID")
    if blocks_errors:
        return {"ok": False, "errors": blocks_errors}

    expected, build_result = build_schematic_plan_blocks(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document, state_package, plan_draft, plan_framework, schematic_draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, plan_framework_schema, schematic_draft_schema, blocks_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(blocks) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_SCHEMATIC_PLAN_BLOCKS_CONTENT_MISMATCH",
                    "",
                    "the supplied schematic plan blocks are not the exact deterministic projection of their confirmed upstream chain, plan framework, and schematic draft",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, SchematicResult]:
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
    return {
        "intake": load_json_object(INTAKE_SCHEMA_PATH),
        "digest": load_json_object(DIGEST_SCHEMA_PATH),
        "board": load_json_object(BOARD_SCHEMA_PATH),
        "program_draft": load_json_object(PROGRAM_DRAFT_SCHEMA_PATH),
        "program": load_json_object(PROGRAM_SCHEMA_PATH),
        "dimension_draft": load_json_object(DIMENSION_DRAFT_SCHEMA_PATH),
        "dimension_plan": load_json_object(DIMENSION_PLAN_SCHEMA_PATH),
        "selection": load_json_object(SELECTION_SCHEMA_PATH),
        "zoning_draft": load_json_object(ZONING_DRAFT_SCHEMA_PATH),
        "zoning": load_json_object(ZONING_SCHEMA_PATH),
        "ce_draft": load_json_object(CE_DRAFT_SCHEMA_PATH),
        "ce": load_json_object(CE_SCHEMA_PATH),
        "mgh_draft": load_json_object(MGH_DRAFT_SCHEMA_PATH),
        "mgh": load_json_object(MGH_SCHEMA_PATH),
        "comparison_draft": load_json_object(COMPARISON_DRAFT_SCHEMA_PATH),
        "comparison": load_json_object(COMPARISON_SCHEMA_PATH),
        "state": load_json_object(STATE_SCHEMA_PATH),
        "plan_draft": load_json_object(PLAN_DRAFT_SCHEMA_PATH),
        "plan_framework": load_json_object(PLAN_SCHEMA_PATH),
        "schematic_draft": load_json_object(SCHEMATIC_DRAFT_SCHEMA_PATH),
        "schematic_blocks": load_json_object(SCHEMATIC_SCHEMA_PATH),
    }


def _add_upstream_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    parser.add_argument("board", type=Path, help="student design start board JSON")
    parser.add_argument("program_draft", type=Path, help="confirmed student spatial program draft JSON")
    parser.add_argument("program", type=Path, help="student spatial program JSON")
    parser.add_argument("dimension_draft", type=Path, help="confirmed student dimension plan draft JSON")
    parser.add_argument("dimension_plan", type=Path, help="student dimension plan JSON")
    parser.add_argument("selection", type=Path, help="human dimension selection record JSON")
    parser.add_argument("zoning_draft", type=Path, help="confirmed student floor zoning draft JSON")
    parser.add_argument("zoning_framework", type=Path, help="student floor zoning framework JSON")
    parser.add_argument("ce_draft", type=Path, help="confirmed student circulation-environment draft JSON")
    parser.add_argument("ce_framework", type=Path, help="student circulation-environment framework JSON")
    parser.add_argument("mgh_draft", type=Path, help="confirmed student massing-grid-height draft JSON")
    parser.add_argument("mgh_framework", type=Path, help="student massing-grid-height framework JSON")
    parser.add_argument("comparison_draft", type=Path, help="confirmed student hypothesis comparison draft JSON")
    parser.add_argument("document", type=Path, help="selected comparison document JSON")
    parser.add_argument("state_package", type=Path, help="selected hypothesis state package JSON")
    parser.add_argument("plan_draft", type=Path, help="confirmed student plan framework draft JSON")
    parser.add_argument("plan_framework", type=Path, help="student plan framework JSON")
    parser.add_argument("schematic_draft", type=Path, help="confirmed student schematic plan draft JSON")


def main(argv: Sequence[str]) -> int:
    """Confirm a pending schematic plan draft, build one schematic plan blocks document, or validate one."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending schematic plan draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student schematic plan draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one schematic plan blocks document from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one schematic plan blocks document against its upstream chain")
    for upstream_parser in (build_parser, validate_parser):
        _add_upstream_arguments(upstream_parser)
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("blocks", type=Path, help="student schematic plan blocks JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
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
            mgh_draft_document = load_json_object(arguments.mgh_draft)
            mgh_framework_document = load_json_object(arguments.mgh_framework)
            comparison_draft_document = load_json_object(arguments.comparison_draft)
            document_document = load_json_object(arguments.document)
            state_package_document = load_json_object(arguments.state_package)
            plan_draft_document = load_json_object(arguments.plan_draft)
            plan_framework_document = load_json_object(arguments.plan_framework)
            schematic_draft_document = load_json_object(arguments.schematic_draft)
            if arguments.command == "validate":
                blocks_document = load_json_object(arguments.blocks)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_schematic_draft(draft_document, human_record, schemas["schematic_draft"])
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        blocks, result = build_schematic_plan_blocks(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
            mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, state_package_document,
            plan_draft_document, plan_framework_document, schematic_draft_document,
            schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
            schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
            schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
            schemas["state"], schemas["plan_draft"], schemas["plan_framework"], schemas["schematic_draft"], schemas["schematic_blocks"],
        )
        if blocks is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(blocks, arguments.output)
        return exit_code

    result = validate_schematic_plan_blocks(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
        mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, state_package_document,
        plan_draft_document, plan_framework_document, schematic_draft_document, blocks_document,
        schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
        schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
        schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
        schemas["state"], schemas["plan_draft"], schemas["plan_framework"], schemas["schematic_draft"], schemas["schematic_blocks"],
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
