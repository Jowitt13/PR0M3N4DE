"""Build one deterministic student circulation and environmental intent framework.

This deterministic, local-only slice accepts the full confirmed ARCH-101
chain: an ARCH-097 AssignmentBriefDigest, its exact ARCH-098 start board
projection, the confirmed ARCH-099 spatial program draft and its exact
spatial program, the confirmed ARCH-100 dimension draft, its exact dimension
plan, the human dimension selection, the confirmed ARCH-101 floor zoning
draft and its exact floor zoning framework, and one human-confirmed
circulation and environmental intent draft. It organizes only what the
student explicitly wrote: horizontal circulation relations between zones,
vertical movement intentions across levels, environmental preferences for
zones or spaces, and unresolved items. It is not a site analysis and never
upgrades a preference into a fact. It decides no entrance, core, stair,
lift, ramp position or count, orientation, wind direction, sun path, site
conclusion, coordinate, plan, massing, grid, elevation, or height; it
infers no path, priority, efficiency, or shortest distance; and it
recommends, ranks, scores, selects, or generates nothing. The output is JSON
data only: no PPTX, web page, image, or drawing. It opens no socket and
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
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
from build_student_design_start_board import compute_confirmed_digest_sha256
from build_student_floor_zoning import validate_floor_zoning
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

CONFIRM_ACTION = "CONFIRM_STUDENT_CIRCULATION_ENVIRONMENT_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

RESOLVE_GAPS_ACTION = {
    "action": "resolve_circulation_environment_gaps",
    "description": (
        "Next, resolve the listed unresolved items: complete the missing circulation relations, "
        "vertical movement intentions, or environmental intentions with student-written content. "
        "This framework fills nothing in for you."
    ),
}
MASSING_ACTION = {
    "action": "massing_grid_height_hypotheses",
    "description": (
        "Next, prepare massing, grid, and height hypotheses in a separately reviewed step. "
        "This framework supplies no massing, grid, or height content."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "This framework reflects only the circulation relations, vertical movement intentions, and environmental preferences written by the student; it infers no path, priority, efficiency, shortest distance, or activity gradient.",
    "It decides no entrance, core, stair, lift, or ramp count, size, position, or clearance, and makes no code, accessibility, fire, or structural claim.",
    "It decides no orientation, wind direction, sun path, site conclusion, coordinate, plan, site plan, massing, grid, elevation, or height.",
    "Environmental intentions are student preferences awaiting site evidence; they are not verified site facts, daylight or wind analyses, noise measurements, or performance proofs.",
    "It recommends, ranks, scores, selects, and generates nothing.",
)


class CirculationError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class CirculationResult(TypedDict):
    """The public result of confirming, building, or validating one circulation framework."""

    ok: bool
    errors: list[CirculationError]


def compute_pending_ce_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation circulation-environment draft.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_ce_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, CirculationResult]:
    """Bind one explicit human confirmation record to a pending circulation-environment draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "CIRCULATION_ENVIRONMENT_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("CIRCULATION_ENVIRONMENT_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[CirculationError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_circulation_environment_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_circulation_environment_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "/pending_circulation_environment_draft_sha256", "pending_circulation_environment_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_ce_draft_sha256(draft):
            errors.append(_error("CIRCULATION_ENVIRONMENT_DRAFT_HASH_MISMATCH", "/pending_circulation_environment_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_circulation_environment_draft_sha256": human_record["pending_circulation_environment_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "CIRCULATION_ENVIRONMENT_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_ce_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[CirculationError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched circulation-environment draft."""

    errors = _schema_errors(draft, draft_schema, registry, "CIRCULATION_ENVIRONMENT_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("CIRCULATION_ENVIRONMENT_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the circulation-environment draft must be confirmed before a framework can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_circulation_environment_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_ce_draft_sha256(draft):
        return [_error("CIRCULATION_ENVIRONMENT_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_circulation_environment_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _zoning_registries(zoning_draft: JsonObject) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Index the confirmed floor zoning draft's zones and levels for readable projection."""

    zone_registry: dict[str, dict[str, str]] = {}
    level_registry: dict[str, str] = {}
    for level in zoning_draft["levels"]:
        level_id = str(level["level_id"])
        level_registry[level_id] = str(level["label"])
        for zone in level["zones"]:
            zone_registry[str(zone["zone_id"])] = {"name": str(zone["name"]), "level_id": level_id}
    return zone_registry, level_registry


def _ce_semantic_errors(
    draft: JsonObject,
    zoning_draft: JsonObject,
    selection: JsonObject,
    zoning_framework: JsonObject,
) -> list[CirculationError]:
    """Check source binding, relation, movement, intent, and coverage rules without inferring anything."""

    errors: list[CirculationError] = []
    if draft["source_floor_zoning_sha256"] != _document_sha256(zoning_framework):
        errors.append(_error("CIRCULATION_ENVIRONMENT_SOURCE_ZONING_MISMATCH", "/source_floor_zoning_sha256", "the draft does not bind the supplied confirmed floor zoning framework"))
        return errors

    zone_registry, level_registry = _zoning_registries(zoning_draft)
    zone_names = {zone["name"] for zone in zone_registry.values()}
    space_names = {str(item["space_name"]) for item in selection["selections"]}

    relation_ids: set[str] = set()
    relation_pairs: set[tuple[str, str]] = set()
    circulation_touched_zones: set[str] = set()
    for index, relation in enumerate(draft["circulation_relations"]):
        pointer = f"/circulation_relations/{index}"
        relation_id = str(relation["relation_id"])
        if relation_id in relation_ids:
            errors.append(_error("CIRCULATION_RELATION_INVALID", f"{pointer}/relation_id", f"{relation_id} is declared more than once"))
        relation_ids.add(relation_id)
        from_id = str(relation["from_zone_id"])
        to_id = str(relation["to_zone_id"])
        if from_id not in zone_registry:
            errors.append(_error("CIRCULATION_RELATION_INVALID", f"{pointer}/from_zone_id", f"{from_id} is not a zone in the confirmed floor zoning draft"))
        if to_id not in zone_registry:
            errors.append(_error("CIRCULATION_RELATION_INVALID", f"{pointer}/to_zone_id", f"{to_id} is not a zone in the confirmed floor zoning draft"))
        if from_id == to_id:
            errors.append(_error("CIRCULATION_RELATION_INVALID", pointer, "a circulation relation must connect two different zones; use two_way instead of a self-loop"))
        pair = tuple(sorted((from_id, to_id)))
        if pair in relation_pairs:
            errors.append(_error("CIRCULATION_RELATION_INVALID", pointer, f"the same unordered zone pair already carries a circulation relation: {from_id} and {to_id}; use two_way for both directions"))
        relation_pairs.add(pair)
        circulation_touched_zones.update((from_id, to_id))

    transition_ids: set[str] = set()
    transition_pairs: set[tuple[str, str]] = set()
    movement_touched_levels: set[str] = set()
    for index, intent in enumerate(draft["vertical_movement_intents"]):
        pointer = f"/vertical_movement_intents/{index}"
        transition_id = str(intent["transition_id"])
        if transition_id in transition_ids:
            errors.append(_error("VERTICAL_MOVEMENT_INVALID", f"{pointer}/transition_id", f"{transition_id} is declared more than once"))
        transition_ids.add(transition_id)
        from_id = str(intent["from_zone_id"])
        to_id = str(intent["to_zone_id"])
        if from_id not in zone_registry:
            errors.append(_error("VERTICAL_MOVEMENT_INVALID", f"{pointer}/from_zone_id", f"{from_id} is not a zone in the confirmed floor zoning draft"))
        if to_id not in zone_registry:
            errors.append(_error("VERTICAL_MOVEMENT_INVALID", f"{pointer}/to_zone_id", f"{to_id} is not a zone in the confirmed floor zoning draft"))
        if from_id == to_id:
            errors.append(_error("VERTICAL_MOVEMENT_INVALID", pointer, "a vertical movement intent must connect two different zones"))
        elif from_id in zone_registry and to_id in zone_registry:
            from_level = zone_registry[from_id]["level_id"]
            to_level = zone_registry[to_id]["level_id"]
            if from_level == to_level:
                errors.append(_error("VERTICAL_MOVEMENT_INVALID", pointer, "a vertical movement intent must connect zones on different levels"))
            else:
                movement_touched_levels.update((from_level, to_level))
        pair = tuple(sorted((from_id, to_id)))
        if pair in transition_pairs:
            errors.append(_error("VERTICAL_MOVEMENT_INVALID", pointer, f"the same unordered zone pair already carries a vertical movement intent: {from_id} and {to_id}"))
        transition_pairs.add(pair)

    intent_ids: set[str] = set()
    for index, intent in enumerate(draft["environmental_intents"]):
        pointer = f"/environmental_intents/{index}"
        intent_id = str(intent["intent_id"])
        if intent_id in intent_ids:
            errors.append(_error("ENVIRONMENTAL_INTENT_INVALID", f"{pointer}/intent_id", f"{intent_id} is declared more than once"))
        intent_ids.add(intent_id)
        target_kind = str(intent["target_kind"])
        target_id = str(intent["target_id"])
        if target_kind == "zone" and target_id not in zone_registry:
            errors.append(_error("ENVIRONMENTAL_INTENT_INVALID", f"{pointer}/target_id", f"{target_id} is not a zone id in the confirmed floor zoning draft"))
        if target_kind == "space" and target_id not in space_names:
            errors.append(_error("ENVIRONMENTAL_INTENT_INVALID", f"{pointer}/target_id", f"{target_id} is not a dimension-selected space name in the bound selection"))

    record_ids: set[str] = set()
    unresolved_circulation_zones: set[str] = set()
    unresolved_movement_levels: set[str] = set()
    for index, record in enumerate(draft["unresolved_items"]):
        pointer = f"/unresolved_items/{index}"
        record_id = str(record["record_id"])
        if record_id in record_ids:
            errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/record_id", f"{record_id} is declared more than once"))
        record_ids.add(record_id)
        subject_kind = str(record["subject_kind"])
        target_kind = str(record["target_kind"])
        target_id = str(record["target_id"])
        if subject_kind == "circulation_relation":
            if target_kind != "zone":
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_kind", "a circulation_relation unresolved item must target a zone"))
            elif target_id not in zone_registry:
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_id", f"{target_id} is not a zone id in the confirmed floor zoning draft"))
            else:
                unresolved_circulation_zones.add(target_id)
        elif subject_kind == "vertical_movement":
            if target_kind != "level":
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_kind", "a vertical_movement unresolved item must target a level"))
            elif target_id not in level_registry:
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_id", f"{target_id} is not a level id in the confirmed floor zoning draft"))
            else:
                unresolved_movement_levels.add(target_id)
        else:
            if target_kind == "zone" and target_id not in zone_registry:
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_id", f"{target_id} is not a zone id in the confirmed floor zoning draft"))
            elif target_kind == "space" and target_id not in space_names:
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_id", f"{target_id} is not a dimension-selected space name in the bound selection"))
            elif target_kind == "level":
                errors.append(_error("CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID", f"{pointer}/target_kind", "an environmental_intent unresolved item must target a zone or a space"))

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return errors

    coverage_errors: list[CirculationError] = []
    for zone_id in sorted(zone_registry):
        if zone_id not in circulation_touched_zones and zone_id not in unresolved_circulation_zones:
            coverage_errors.append(
                _error(
                    "CIRCULATION_COVERAGE_INVALID",
                    "",
                    f"zone {zone_registry[zone_id]['name']} appears in no circulation relation and has no circulation_relation unresolved item; zones must not disappear at the circulation stage",
                )
            )
    if len(level_registry) > 1:
        for level_id in sorted(level_registry):
            if level_id not in movement_touched_levels and level_id not in unresolved_movement_levels:
                coverage_errors.append(
                    _error(
                        "VERTICAL_MOVEMENT_COVERAGE_INVALID",
                        "",
                        f"level {level_registry[level_id]} participates in no vertical movement intent and has no vertical_movement unresolved item",
                    )
                )
    return coverage_errors


def build_circulation_environment(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    zoning_draft: JsonObject,
    zoning_framework: JsonObject,
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
) -> tuple[dict[str, Any] | None, CirculationResult]:
    """Return one deterministic circulation framework, or no output on any failed gate."""

    upstream = validate_floor_zoning(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema,
    )
    draft_errors = _verify_confirmed_ce_draft(draft, ce_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors = _ce_semantic_errors(draft, zoning_draft, selection, zoning_framework)
    if semantic_errors:
        semantic_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": semantic_errors}

    zone_registry, level_registry = _zoning_registries(zoning_draft)

    def readable_target(target_kind: str, target_id: str) -> str:
        if target_kind == "zone" and target_id in zone_registry:
            return zone_registry[target_id]["name"]
        if target_kind == "level" and target_id in level_registry:
            return level_registry[target_id]
        return target_id

    circulation_view = [
        {
            "from_zone": zone_registry[str(relation["from_zone_id"])]["name"],
            "to_zone": zone_registry[str(relation["to_zone_id"])]["name"],
            "flow_scope": relation["flow_scope"],
            "directionality": relation["directionality"],
            "note": str(relation["note"]),
        }
        for relation in draft["circulation_relations"]
    ]
    movement_view = [
        {
            "from_zone": zone_registry[str(intent["from_zone_id"])]["name"],
            "from_level": level_registry[zone_registry[str(intent["from_zone_id"])]["level_id"]],
            "to_zone": zone_registry[str(intent["to_zone_id"])]["name"],
            "to_level": level_registry[zone_registry[str(intent["to_zone_id"])]["level_id"]],
            "mode": intent["mode"],
            "flow_scope": intent["flow_scope"],
            "note": str(intent["note"]),
        }
        for intent in draft["vertical_movement_intents"]
    ]
    environment_view = [
        {
            "target_kind": intent["target_kind"],
            "target_name": readable_target(str(intent["target_kind"]), str(intent["target_id"])),
            "topic": intent["topic"],
            "preference": intent["preference"],
            "note": str(intent["note"]),
        }
        for intent in draft["environmental_intents"]
    ]
    unresolved_view = [
        {
            "subject_kind": record["subject_kind"],
            "target_kind": record["target_kind"],
            "target_name": readable_target(str(record["target_kind"]), str(record["target_id"])),
            "reason": str(record["reason"]),
        }
        for record in draft["unresolved_items"]
    ]

    next_action = dict(RESOLVE_GAPS_ACTION) if unresolved_view else dict(MASSING_ACTION)

    framework: dict[str, Any] = {
        "schema_version": "1.0.0",
        "framework_kind": "student_circulation_environment_framework",
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
            "pending_circulation_environment_draft_sha256": draft["human_confirmation"]["pending_circulation_environment_draft_sha256"],
            "confirmed_circulation_environment_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "circulation_environment_intent_confirmed",
            "circulation_relations": circulation_view,
            "vertical_movements": movement_view,
            "environmental_intents": environment_view,
            "unresolved_items": unresolved_view,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": next_action,
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    framework_errors = _schema_errors(framework, ce_schema, registry, "STUDENT_CIRCULATION_ENVIRONMENT_SCHEMA_INVALID")
    if framework_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": framework_errors}
    return framework, {"ok": True, "errors": []}


def validate_circulation_environment(
    digest: JsonObject,
    board: JsonObject,
    program_draft: JsonObject,
    program: JsonObject,
    dimension_draft: JsonObject,
    dimension_plan: JsonObject,
    selection: JsonObject,
    zoning_draft: JsonObject,
    zoning_framework: JsonObject,
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
) -> CirculationResult:
    """Re-derive the expected framework from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema,
    )
    framework_errors = _schema_errors(framework, ce_schema, registry, "STUDENT_CIRCULATION_ENVIRONMENT_SCHEMA_INVALID")
    if framework_errors:
        return {"ok": False, "errors": framework_errors}

    expected, build_result = build_circulation_environment(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(framework) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_CIRCULATION_ENVIRONMENT_CONTENT_MISMATCH",
                    "",
                    "the supplied framework is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, CirculationResult]:
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
    """Confirm a pending circulation draft, build a framework, or validate one against its upstream chain."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending circulation-environment draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student circulation-environment draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one student circulation framework from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one student circulation framework against its upstream chain")
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
        upstream_parser.add_argument("draft", type=Path, help="confirmed student circulation-environment draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("framework", type=Path, help="student circulation-environment framework JSON")

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
            draft_document = load_json_object(arguments.draft)
            if arguments.command == "validate":
                framework_document = load_json_object(arguments.framework)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_ce_draft(draft_document, human_record, ce_draft_schema)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        framework, result = build_circulation_environment(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, draft_document,
            intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
            dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
            ce_draft_schema, ce_schema,
        )
        if framework is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(framework, arguments.output)
        return exit_code

    result = validate_circulation_environment(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, draft_document, framework_document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
