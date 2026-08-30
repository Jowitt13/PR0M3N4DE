"""Build and validate one student plan relationship and placement framework.

This deterministic, local-only slice accepts one valid, untampered selected
hypothesis state package (ARCH-105) and one confirmed human-authored
plan-framework draft. It reuses the committed ``validate_state`` public
entry, so the complete ARCH-097~105 chain is re-verified and every upstream
stable error code propagates unchanged. It takes no selection record of its
own, never re-selects or re-derives the hypothesis, and never turns
ARCH-104 guidance into a plan conclusion.

The student draft is a relationship table, not a coordinate drawing: one
readable placement or explicit deferral per confirmed space, space pair
relations with fixed categories, ordered movement gradients over real
spaces or confirmed zones, unresolved plan items, and at most three
clarification questions. The machine verifies coverage, references, and
traceability, and projects the student text verbatim; it generates no plan
coordinate, room rectangle, wall, door, column, entrance, circulation
drawing, or total plan, and it decides no orientation, massing shape,
structural system, regulation, cost, performance, or constructibility. The
next action is ``resolve_plan_framework_gaps`` while unresolved plan items
remain, otherwise ``human_review_plan_framework``. The output is JSON data
only. The script opens no socket and starts no subprocess, reads no system
clock, never modifies an input document, and writes a destination only
after full validation. Validate re-derives the expected framework
deterministically and requires exact byte equality.
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
from build_student_hypothesis_comparison import (
    COMPARISON_DRAFT_SCHEMA_PATH,
    COMPARISON_SCHEMA_PATH,
)
from build_student_selected_hypothesis_state import (
    STATE_SCHEMA_PATH,
    validate_state,
)
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
PLAN_DRAFT_SCHEMA_PATH = REFERENCES / "student-plan-framework-draft.schema.json"
PLAN_SCHEMA_PATH = REFERENCES / "student-plan-framework.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_PLAN_FRAMEWORK_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

NEXT_ACTION_RESOLVE = {
    "action": "resolve_plan_framework_gaps",
    "description": (
        "Unresolved plan items remain in this framework; the human resolves each one explicitly. "
        "The machine never fills, resolves, or guesses a placement or relation."
    ),
}

NEXT_ACTION_REVIEW = {
    "action": "human_review_plan_framework",
    "description": (
        "Every confirmed space is placed or deferred exactly once and no unresolved plan item "
        "remains; the human reviews the projected plan framework as student-authored input, "
        "not as an automatic design."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "This framework is a relationship table over the confirmed selected hypothesis; it is not a coordinate drawing.",
    "Placements, relations, sequences, and unresolved items project only what the student wrote; the machine adds, moves, renames, and generates nothing.",
    "This stage generates no plan coordinate, room rectangle, wall, door, column, entrance, circulation drawing, or total plan.",
    "It decides no orientation, massing shape, structural system, regulation, cost, performance, or constructibility, and no floor count beyond the written levels.",
    "Gradient intentions such as active-to-quiet or open-to-private are student judgment, never noise, daylight, wind, view, regulation, or performance facts.",
    "The machine ranks, scores, and recommends nothing, and it resolves no unresolved item.",
)


class PlanError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class PlanResult(TypedDict):
    """The public result of confirming, building, or validating one plan framework."""

    ok: bool
    errors: list[PlanError]


def compute_pending_plan_framework_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation plan-framework draft.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_plan_framework_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, PlanResult]:
    """Bind one explicit human confirmation record to a pending plan-framework draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "PLAN_FRAMEWORK_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("PLAN_FRAMEWORK_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[PlanError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_student_plan_framework_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_student_plan_framework_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "/pending_student_plan_framework_draft_sha256", "pending_student_plan_framework_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_plan_framework_draft_sha256(draft):
            errors.append(_error("PLAN_FRAMEWORK_DRAFT_HASH_MISMATCH", "/pending_student_plan_framework_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_student_plan_framework_draft_sha256": human_record["pending_student_plan_framework_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "PLAN_FRAMEWORK_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_plan_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[PlanError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched plan draft."""

    errors = _schema_errors(draft, draft_schema, registry, "PLAN_FRAMEWORK_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("PLAN_FRAMEWORK_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the plan-framework draft must be confirmed before a framework can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_student_plan_framework_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_plan_framework_draft_sha256(draft):
        return [_error("PLAN_FRAMEWORK_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_student_plan_framework_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _plan_semantic_errors(draft: JsonObject, zoning_framework: JsonObject, program: JsonObject) -> list[PlanError]:
    """Check placement coverage, level/zone membership, relation pairs, sequence elements, and unresolved subjects without generating anything."""

    errors: list[PlanError] = []

    levels = zoning_framework["student_view"]["levels"]
    level_labels = [str(level["label"]) for level in levels]
    level_set = set(level_labels)
    zone_names: list[str] = []
    space_names: list[str] = []
    zone_of_space: dict[str, tuple[str, str]] = {}
    for level in levels:
        for zone in level["zones"]:
            zone_name = str(zone["name"])
            zone_names.append(zone_name)
            for space in zone["spaces"]:
                space_name = str(space["name"])
                if space_name not in zone_of_space:
                    space_names.append(space_name)
                zone_of_space[space_name] = (str(level["label"]), zone_name)
    space_set = set(space_names)
    zone_set = set(zone_names)

    placed: list[str] = []
    for index, placement in enumerate(draft["placements"]):
        pointer = f"/placements/{index}"
        space_name = str(placement["space_name"])
        if space_name not in space_set:
            errors.append(_error("PLAN_SPACE_INVALID", f"{pointer}/space_name", f"{space_name} is not a confirmed space"))
            continue
        if space_name in placed:
            errors.append(_error("PLAN_COVERAGE_INVALID", f"{pointer}/space_name", f"{space_name} is placed more than once"))
        placed.append(space_name)
        level = str(placement["level"])
        zone = str(placement["zone"])
        if level not in level_set:
            errors.append(_error("PLAN_PLACEMENT_INVALID", f"{pointer}/level", f"{level} is not a confirmed level"))
        if zone not in zone_set:
            errors.append(_error("PLAN_PLACEMENT_INVALID", f"{pointer}/zone", f"{zone} is not a confirmed zone"))
        elif zone_of_space.get(space_name) != (level, zone):
            errors.append(_error("PLAN_PLACEMENT_INVALID", f"{pointer}/zone", f"{space_name} must stay in its confirmed level and zone"))

    deferred: list[str] = []
    for index, item in enumerate(draft["deferred_placements"]):
        pointer = f"/deferred_placements/{index}"
        space_name = str(item["space_name"])
        if space_name not in space_set:
            errors.append(_error("PLAN_SPACE_INVALID", f"{pointer}/space_name", f"{space_name} is not a confirmed space"))
            continue
        if space_name in deferred:
            errors.append(_error("PLAN_COVERAGE_INVALID", f"{pointer}/space_name", f"{space_name} is deferred more than once"))
        deferred.append(space_name)
        if space_name in placed:
            errors.append(_error("PLAN_COVERAGE_INVALID", f"{pointer}/space_name", f"{space_name} is both placed and deferred"))

    for space_name in space_names:
        if space_name not in placed and space_name not in deferred:
            errors.append(_error("PLAN_COVERAGE_INVALID", "", f"{space_name} has neither a placement nor an explicit deferral"))

    program_pair_kind: dict[frozenset[str], str] = {}
    for relation in program["student_view"]["relations"]:
        pair = frozenset({str(relation["from_space"]), str(relation["to_space"])})
        program_pair_kind.setdefault(pair, str(relation["kind"]))

    resolved_pairs: list[frozenset[str]] = []
    relation_ids: list[str] = []
    for index, relation in enumerate(draft["relations"]):
        pointer = f"/relations/{index}"
        relation_id = str(relation["relation_id"])
        if relation_id in relation_ids:
            errors.append(_error("PLAN_RELATION_INVALID", f"{pointer}/relation_id", f"{relation_id} is declared more than once"))
        relation_ids.append(relation_id)
        from_space = str(relation["from_space"])
        to_space = str(relation["to_space"])
        if from_space not in space_set:
            errors.append(_error("PLAN_SPACE_INVALID", f"{pointer}/from_space", f"{from_space} is not a confirmed space"))
        if to_space not in space_set:
            errors.append(_error("PLAN_SPACE_INVALID", f"{pointer}/to_space", f"{to_space} is not a confirmed space"))
        if from_space == to_space:
            errors.append(_error("PLAN_RELATION_INVALID", f"{pointer}/to_space", "a space cannot relate to itself"))
        pair = frozenset({from_space, to_space})
        if pair in resolved_pairs:
            errors.append(_error("PLAN_RELATION_INVALID", f"{pointer}/from_space", "this unordered pair is already related; a pair may appear at most once"))
        resolved_pairs.append(pair)
        upstream_kind = program_pair_kind.get(pair)
        category = str(relation["relation_category"])
        if upstream_kind == "must_be_separate" and category in ("adjacent", "near", "buffered_transition"):
            errors.append(_error("PLAN_RELATION_CONFLICT", f"{pointer}/relation_category", f"{category} contradicts the confirmed program relation must_be_separate for this pair"))
        if upstream_kind == "must_be_near" and category == "separate":
            errors.append(_error("PLAN_RELATION_CONFLICT", f"{pointer}/relation_category", "separate contradicts the confirmed program relation must_be_near for this pair"))

    sequence_ids: list[str] = []
    gradient_by_id: dict[str, str] = {}
    for index, sequence in enumerate(draft["sequences"]):
        pointer = f"/sequences/{index}"
        sequence_id = str(sequence["sequence_id"])
        if sequence_id in sequence_ids:
            errors.append(_error("PLAN_SEQUENCE_INVALID", f"{pointer}/sequence_id", f"{sequence_id} is declared more than once"))
        sequence_ids.append(sequence_id)
        gradient_by_id[sequence_id] = str(sequence["gradient_name"])
        seen_elements: list[tuple[str, str]] = []
        for element_index, element in enumerate(sequence["elements"]):
            element_pointer = f"{pointer}/elements/{element_index}"
            element_kind = str(element["element_kind"])
            element_name = str(element["element_name"])
            if element_kind == "space" and element_name not in space_set:
                errors.append(_error("PLAN_SEQUENCE_INVALID", f"{element_pointer}/element_name", f"{element_name} is not a confirmed space"))
            elif element_kind == "zone" and element_name not in zone_set:
                errors.append(_error("PLAN_SEQUENCE_INVALID", f"{element_pointer}/element_name", f"{element_name} is not a confirmed zone"))
            key = (element_kind, element_name)
            if key in seen_elements:
                errors.append(_error("PLAN_SEQUENCE_INVALID", f"{element_pointer}/element_name", f"{element_kind} {element_name} repeats inside this sequence"))
            seen_elements.append(key)

    unresolved_ids: list[str] = []
    unresolved_pairs: list[frozenset[str]] = []
    for index, item in enumerate(draft["unresolved_plan_items"]):
        pointer = f"/unresolved_plan_items/{index}"
        record_id = str(item["record_id"])
        if record_id in unresolved_ids:
            errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/record_id", f"{record_id} is declared more than once"))
        unresolved_ids.append(record_id)
        subject_kind = str(item["subject_kind"])
        reference = item["subject_reference"]
        if subject_kind == "space_placement":
            space_name = str(reference["space_name"])
            if space_name not in space_set:
                errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference/space_name", f"{space_name} is not a confirmed space"))
        elif subject_kind == "relation":
            from_space = str(reference["from_space"])
            to_space = str(reference["to_space"])
            if from_space not in space_set or to_space not in space_set:
                errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference", "an unresolved relation must name two confirmed spaces"))
            elif from_space == to_space:
                errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference", "an unresolved relation cannot be a self-loop"))
            else:
                pair = frozenset({from_space, to_space})
                if pair in resolved_pairs:
                    errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference", "this pair is already resolved; a pair can never be both resolved and unresolved"))
                if pair in unresolved_pairs:
                    errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference", "this unresolved pair is declared more than once"))
                unresolved_pairs.append(pair)
        else:
            sequence_id = str(reference["sequence_id"])
            if sequence_id not in sequence_ids:
                errors.append(_error("PLAN_UNRESOLVED_INVALID", f"{pointer}/subject_reference/sequence_id", f"{sequence_id} is not a sequence in this draft"))

    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _project_plan_framework(
    state_package: JsonObject,
    zoning_framework: JsonObject,
    draft: JsonObject,
    framework_schema: JsonObject,
    registry: Any,
) -> dict[str, Any] | None:
    """Project one plan framework from already-validated inputs."""

    placement_by_space = {str(placement["space_name"]): placement for placement in draft["placements"]}
    projected_levels: list[dict[str, Any]] = []
    for level in zoning_framework["student_view"]["levels"]:
        projected_zones: list[dict[str, Any]] = []
        for zone in level["zones"]:
            projected_spaces: list[dict[str, Any]] = []
            for space in zone["spaces"]:
                space_name = str(space["name"])
                placement = placement_by_space.get(space_name)
                if placement is None:
                    continue
                entry: dict[str, Any] = {"space_name": space_name, "placement_note": str(placement["placement_note"])}
                if placement.get("role") is not None:
                    entry["role"] = str(placement["role"])
                projected_spaces.append(entry)
            if projected_spaces:
                projected_zones.append({"zone_name": str(zone["name"]), "spaces": projected_spaces})
        if projected_zones:
            projected_levels.append({"level_label": str(level["label"]), "zones": projected_zones})

    gradient_by_id = {str(sequence["sequence_id"]): str(sequence["gradient_name"]) for sequence in draft["sequences"]}
    projected_unresolved: list[dict[str, Any]] = []
    for item in draft["unresolved_plan_items"]:
        subject_kind = str(item["subject_kind"])
        reference = item["subject_reference"]
        if subject_kind == "space_placement":
            subject_label = str(reference["space_name"])
        elif subject_kind == "relation":
            subject_label = f"Relation between {reference['from_space']} and {reference['to_space']}"
        else:
            subject_label = gradient_by_id[str(reference["sequence_id"])]
        projected_unresolved.append({"subject_kind": subject_kind, "subject_label": subject_label, "reason": str(item["reason"])})

    has_unresolved = bool(draft["unresolved_plan_items"])
    framework: dict[str, Any] = {
        "schema_version": "1.0.0",
        "framework_kind": "student_plan_framework",
        "source_binding": {
            **dict(state_package["source_binding"]),
            "selected_hypothesis_state_package_sha256": _document_sha256(state_package),
            "pending_student_plan_framework_draft_sha256": str(draft["human_confirmation"]["pending_student_plan_framework_draft_sha256"]),
            "confirmed_student_plan_framework_draft_sha256": _document_sha256(draft),
        },
        "student_view": {
            "project_title": state_package["student_handoff"]["project_title"],
            "stage": "plan_framework_confirmed",
            "levels": projected_levels,
            "deferred_placements": [
                {"space_name": str(item["space_name"]), "reason": str(item["reason"])}
                for item in draft["deferred_placements"]
            ],
            "relations": [
                {
                    "from_space": str(relation["from_space"]),
                    "to_space": str(relation["to_space"]),
                    "relation_category": str(relation["relation_category"]),
                    "note": str(relation["note"]),
                }
                for relation in draft["relations"]
            ],
            "sequences": [
                {
                    "gradient_name": str(sequence["gradient_name"]),
                    "elements": [
                        {"element_kind": str(element["element_kind"]), "element_name": str(element["element_name"])}
                        for element in sequence["elements"]
                    ],
                    "note": str(sequence["note"]),
                }
                for sequence in draft["sequences"]
            ],
            "unresolved_plan_items": projected_unresolved,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": dict(NEXT_ACTION_RESOLVE if has_unresolved else NEXT_ACTION_REVIEW),
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    framework_errors = _schema_errors(framework, framework_schema, registry, "STUDENT_PLAN_FRAMEWORK_SCHEMA_INVALID")
    if framework_errors:  # pragma: no cover - defends the output contract against future drift.
        return None
    return framework


def build_plan_framework(
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
    framework_schema: JsonObject,
) -> tuple[dict[str, Any] | None, PlanResult]:
    """Return one deterministic plan framework, or no output on any failed gate."""

    upstream = validate_state(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document, state_package,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema, state_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, framework_schema,
    )
    draft_errors = _verify_confirmed_plan_draft(plan_draft, plan_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    if draft_source := plan_draft.get("source_selected_hypothesis_state_sha256"):
        if not isinstance(draft_source, str) or draft_source != _document_sha256(state_package):
            return None, {
                "ok": False,
                "errors": [
                    _error(
                        "PLAN_SOURCE_STATE_MISMATCH",
                        "/source_selected_hypothesis_state_sha256",
                        "the draft does not bind the supplied selected hypothesis state package",
                    )
                ],
            }

    semantic_errors = _plan_semantic_errors(plan_draft, zoning_framework, program)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}

    framework = _project_plan_framework(state_package, zoning_framework, plan_draft, framework_schema, registry)
    if framework is None:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": [_error("STUDENT_PLAN_FRAMEWORK_SCHEMA_INVALID", "", "the built plan framework failed its closed schema")]}
    return framework, {"ok": True, "errors": []}


def validate_plan_framework(
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
    comparison_draft_schema: JsonObject,
    comparison_schema: JsonObject,
    state_schema: JsonObject,
    plan_draft_schema: JsonObject,
    framework_schema: JsonObject,
) -> PlanResult:
    """Re-derive the expected plan framework from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, framework_schema,
    )
    framework_errors = _schema_errors(framework, framework_schema, registry, "STUDENT_PLAN_FRAMEWORK_SCHEMA_INVALID")
    if framework_errors:
        return {"ok": False, "errors": framework_errors}

    expected, build_result = build_plan_framework(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document, state_package, plan_draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
        state_schema, plan_draft_schema, framework_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(framework) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_PLAN_FRAMEWORK_CONTENT_MISMATCH",
                    "",
                    "the supplied plan framework is not the exact deterministic projection of its confirmed upstream chain, selected state package, and plan-framework draft",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, PlanResult]:
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


def main(argv: Sequence[str]) -> int:
    """Confirm a pending plan-framework draft, build one plan framework, or validate one plan framework."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending plan-framework draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student plan framework draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one plan framework from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one plan framework against its upstream chain")
    for upstream_parser in (build_parser, validate_parser):
        _add_upstream_arguments(upstream_parser)
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("framework", type=Path, help="student plan framework JSON")

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
            if arguments.command == "validate":
                framework_document = load_json_object(arguments.framework)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_plan_framework_draft(draft_document, human_record, schemas["plan_draft"])
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        framework, result = build_plan_framework(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
            mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, state_package_document, plan_draft_document,
            schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
            schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
            schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
            schemas["state"], schemas["plan_draft"], schemas["plan_framework"],
        )
        if framework is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(framework, arguments.output)
        return exit_code

    result = validate_plan_framework(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
        mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, state_package_document, plan_draft_document, framework_document,
        schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
        schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
        schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
        schemas["state"], schemas["plan_draft"], schemas["plan_framework"],
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
