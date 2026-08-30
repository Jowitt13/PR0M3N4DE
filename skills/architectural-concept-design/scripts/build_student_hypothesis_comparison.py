"""Build and validate one student hypothesis comparison with explicit human selection.

This deterministic, local-only slice accepts the full confirmed ARCH-103
chain: the ARCH-097 digest, the ARCH-098 start board, the ARCH-099 spatial
program draft and program, the ARCH-100 dimension draft, plan, and human
selection, the ARCH-101 floor zoning draft and framework, the ARCH-102
circulation-environment draft and framework, the ARCH-103 massing-grid-height
draft and framework, one human-confirmed comparison draft (ordered criteria,
one assessment per hypothesis, optional non-binding guidance), and, for the
selected state, one explicit human selection record. It reuses the committed
``validate_massing_grid_height`` public entry, so every upstream error code
propagates unchanged and the upstream unresolved gate is never bypassed.

The machine projects the student-written hypotheses, criteria, assessments,
and guidance verbatim, and derives no architectural conclusion, rank, score,
winner, or recommendation of its own. Guidance is projected only from the
human-written draft and always carries the fixed boundary sentence. A
selection requires exactly one explicit human record with the fixed action, a
human label, a timezone-qualified RFC 3339 time, one existing candidate key,
and the canonical JSON plus newline SHA-256 of the whole pending comparison
document; the machine never selects by default, by score, or by accepting a
recommendation. The pending document's next action is
``human_select_massing_grid_height_hypothesis``; the selected document ends in
a controlled handoff that does not enter PPTX generation or automatic plan
drawing. The output is JSON data only. The script opens no socket and starts
no subprocess, reads no system clock, never modifies an input document, and
writes a destination only after full validation. Validate re-derives the
expected document deterministically and requires exact byte equality.
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
from build_student_massing_grid_height import validate_massing_grid_height
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
COMPARISON_DRAFT_SCHEMA_PATH = REFERENCES / "student-hypothesis-comparison-draft.schema.json"
COMPARISON_SCHEMA_PATH = REFERENCES / "student-hypothesis-comparison.schema.json"

CONFIRM_ACTION = "CONFIRM_STUDENT_HYPOTHESIS_COMPARISON_DRAFT"
SELECT_ACTION = "SELECT_STUDENT_MASSING_GRID_HEIGHT_HYPOTHESIS"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CANDIDATE_KEY_RE = re.compile(r"MGH-[0-9]{3,}")

NEXT_ACTION_PENDING = {
    "action": "human_select_massing_grid_height_hypothesis",
    "description": (
        "The human compares the listed candidates and records exactly one explicit selection; "
        "the machine selects nothing and accepts no default or automatic recommendation."
    ),
}

NEXT_ACTION_SELECTED = {
    "action": "handoff_selected_massing_grid_height_hypothesis",
    "description": (
        "The human selection is bound to this comparison document. This is a controlled handoff "
        "to the next separately reviewed stage; it does not enter PPTX generation, automatic "
        "plan drawing, or any machine-made design conclusion."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "This comparison projects only the hypotheses, criteria, assessments, and guidance written by the student or human; it generates no candidate and picks no winner.",
    "Candidate facts restate the confirmed massing, grid, and height hypotheses and are student input, not verified architectural conclusions.",
    "Student assessments and any guidance are human judgment shown verbatim; guidance is decision guidance, not an automatic architectural decision.",
    "This stage ranks, scores, and selects nothing, and it decides no level count, entrance, plan coordinate, orientation, site plan, massing shape, structural system, regulation, cost, performance, or constructibility.",
    "Only an explicit human selection record completes this stage; the machine never selects by default, by score, or by accepting a recommendation.",
    "The selected output is a controlled handoff to the next separately reviewed stage; it does not enter PPTX generation or automatic plan drawing.",
)

GUIDANCE_BOUNDS: tuple[str, ...] = (
    "This is decision guidance, not an automatic architectural decision.",
)


class ComparisonError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class ComparisonResult(TypedDict):
    """The public result of confirming, building, selecting, or validating one comparison document."""

    ok: bool
    errors: list[ComparisonError]


def compute_pending_comparison_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation comparison draft.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_comparison_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, ComparisonResult]:
    """Bind one explicit human confirmation record to a pending comparison draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "COMPARISON_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("COMPARISON_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[ComparisonError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_student_hypothesis_comparison_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_student_hypothesis_comparison_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "/pending_student_hypothesis_comparison_draft_sha256", "pending_student_hypothesis_comparison_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_comparison_draft_sha256(draft):
            errors.append(_error("COMPARISON_DRAFT_HASH_MISMATCH", "/pending_student_hypothesis_comparison_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_student_hypothesis_comparison_draft_sha256": human_record["pending_student_hypothesis_comparison_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "COMPARISON_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_comparison_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[ComparisonError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched comparison draft."""

    errors = _schema_errors(draft, draft_schema, registry, "COMPARISON_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("COMPARISON_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the comparison draft must be confirmed before a comparison document can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("COMPARISON_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_student_hypothesis_comparison_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_comparison_draft_sha256(draft):
        return [_error("COMPARISON_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_student_hypothesis_comparison_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _comparison_semantic_errors(draft: JsonObject, mgh_draft: JsonObject, mgh_framework: JsonObject) -> list[ComparisonError]:
    """Check source binding, criteria, assessment, judgment, and guidance traceability without generating anything."""

    errors: list[ComparisonError] = []
    if draft["source_massing_grid_height_framework_sha256"] != _document_sha256(mgh_framework):
        errors.append(_error("COMPARISON_SOURCE_MASSING_MISMATCH", "/source_massing_grid_height_framework_sha256", "the draft does not bind the supplied confirmed massing-grid-height framework"))
        return errors

    criterion_ids: list[str] = []
    for index, criterion in enumerate(draft["criteria"]):
        criterion_id = str(criterion["criterion_id"])
        if criterion_id in criterion_ids:
            errors.append(_error("COMPARISON_CRITERION_INVALID", f"/criteria/{index}/criterion_id", f"{criterion_id} is declared more than once"))
        criterion_ids.append(criterion_id)

    hypothesis_keys = [str(hypothesis["hypothesis_id"]) for hypothesis in mgh_draft["hypotheses"]]
    seen_keys: list[str] = []
    for index, assessment in enumerate(draft["candidate_assessments"]):
        pointer = f"/candidate_assessments/{index}"
        candidate_key = str(assessment["candidate_key"])
        if candidate_key in seen_keys:
            errors.append(_error("COMPARISON_ASSESSMENT_INVALID", f"{pointer}/candidate_key", f"{candidate_key} is assessed more than once"))
        if candidate_key not in hypothesis_keys:
            errors.append(_error("COMPARISON_ASSESSMENT_INVALID", f"{pointer}/candidate_key", f"{candidate_key} is not a hypothesis in the confirmed massing-grid-height draft"))
        seen_keys.append(candidate_key)
        judgment_ids: list[str] = []
        for judgment_index, judgment in enumerate(assessment["criterion_judgments"]):
            judgment_pointer = f"{pointer}/criterion_judgments/{judgment_index}"
            criterion_id = str(judgment["criterion_id"])
            if criterion_id in judgment_ids:
                errors.append(_error("COMPARISON_JUDGMENT_INVALID", f"{judgment_pointer}/criterion_id", f"{criterion_id} is judged more than once for this candidate"))
            if criterion_id not in criterion_ids:
                errors.append(_error("COMPARISON_JUDGMENT_INVALID", f"{judgment_pointer}/criterion_id", f"{criterion_id} is not a criterion in this draft"))
            judgment_ids.append(criterion_id)
    for hypothesis_key in hypothesis_keys:
        if hypothesis_key not in seen_keys:
            errors.append(_error("COMPARISON_ASSESSMENT_COVERAGE_INVALID", "", f"{hypothesis_key} has no assessment; every hypothesis keeps exactly one assessment"))

    guidance = draft.get("guidance")
    if isinstance(guidance, Mapping):
        focus_keys = [str(key) for key in guidance["focus_candidate_keys"]]
        if len(set(focus_keys)) != len(focus_keys):
            errors.append(_error("COMPARISON_GUIDANCE_INVALID", "/guidance/focus_candidate_keys", "a focus candidate is declared more than once"))
        for key in focus_keys:
            if key not in hypothesis_keys:
                errors.append(_error("COMPARISON_GUIDANCE_INVALID", "/guidance/focus_candidate_keys", f"{key} is not a hypothesis in the confirmed massing-grid-height draft"))
        basis_ids = [str(criterion_id) for criterion_id in guidance["basis_criterion_ids"]]
        if len(set(basis_ids)) != len(basis_ids):
            errors.append(_error("COMPARISON_GUIDANCE_INVALID", "/guidance/basis_criterion_ids", "a basis criterion is declared more than once"))
        for criterion_id in basis_ids:
            if criterion_id not in criterion_ids:
                errors.append(_error("COMPARISON_GUIDANCE_INVALID", "/guidance/basis_criterion_ids", f"{criterion_id} is not a criterion in this draft; guidance must rest only on written criteria"))

    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _decision_prompt(criteria: Sequence[JsonObject], candidate_count: int) -> str:
    """Compose one deterministic natural-language decision prompt from upstream facts and human criteria."""

    if criteria:
        names = ", ".join(str(criterion["name"]) for criterion in criteria)
        criteria_part = f"The comparison uses the student's ordered comparison criteria: {names}."
    else:
        criteria_part = "The student supplied no comparison criteria, so the comparison below restates only the student-written hypothesis facts and assessments."
    return (
        f"Based on the confirmed assignment brief, design start board, spatial program, dimension plan, dimension selection, floor zoning framework, and circulation-environment framework, and on the {candidate_count} student-written massing, grid, and height hypotheses, {candidate_count} candidates are available for comparison and human selection. "
        + criteria_part
        + " The machine organizes, verifies, and compares these candidates and carries the student's own assessments and any student-written guidance; it selects nothing. Only an explicit human selection record completes this stage."
    )


def _project_guidance(draft: JsonObject, label_by_key: dict[str, str], criterion_name_by_id: dict[str, str]) -> dict[str, Any]:
    """Project only human-written guidance, or an honest inability statement with factual reasons."""

    guidance = draft.get("guidance")
    if not isinstance(guidance, Mapping):
        reasons = ["The student comparison draft carries no comparison guidance, so no candidate can be suggested."]
        if not draft["criteria"]:
            reasons.append("No ordered comparison criteria were supplied by the student.")
        return {"status": "unable_to_suggest_single_candidate", "reasons": reasons}

    focus_keys = [str(key) for key in guidance["focus_candidate_keys"]]
    if not focus_keys:
        return {
            "status": "unable_to_suggest_single_candidate",
            "reasons": ["The student's guidance names no focus candidate, and the machine never resolves a tie or conflict on its own."],
        }

    projected: dict[str, Any] = {
        "status": "guidance_available",
        "basis": str(guidance["basis"]),
        "basis_criteria": [criterion_name_by_id[str(criterion_id)] for criterion_id in guidance["basis_criterion_ids"]],
        "advantages": [str(item) for item in guidance["advantages"]],
        "costs_or_risks": [str(item) for item in guidance["costs_or_risks"]],
        "reconsider_when": [str(item) for item in guidance["reconsider_when"]],
        "bounds_statement": list(GUIDANCE_BOUNDS),
    }
    if len(focus_keys) == 1:
        projected["recommended_to_consider_first"] = label_by_key[focus_keys[0]]
    else:
        projected["suggested_focus"] = [label_by_key[key] for key in focus_keys]
    return projected


def _project_comparison(
    mgh_draft: JsonObject,
    mgh_framework: JsonObject,
    draft: JsonObject,
    comparison_schema: JsonObject,
    registry: Any,
) -> dict[str, Any] | None:
    """Project one pending comparison document from already-validated inputs."""

    criterion_name_by_id = {str(criterion["criterion_id"]): str(criterion["name"]) for criterion in draft["criteria"]}
    assessment_by_key = {str(assessment["candidate_key"]): assessment for assessment in draft["candidate_assessments"]}
    label_by_key: dict[str, str] = {}
    candidates_view: list[dict[str, Any]] = []
    for hypothesis_draft, hypothesis_view in zip(mgh_draft["hypotheses"], mgh_framework["student_view"]["hypotheses"]):
        candidate_key = str(hypothesis_draft["hypothesis_id"])
        label = str(hypothesis_view["label"])
        label_by_key[candidate_key] = label
        assessment = assessment_by_key[candidate_key]
        candidates_view.append(
            {
                "label": label,
                "massing_groups": json.loads(json.dumps(hypothesis_view["massing_groups"])),
                "grid_intent": json.loads(json.dumps(hypothesis_view["grid_intent"])),
                "vertical_intervals": json.loads(json.dumps(hypothesis_view["vertical_intervals"])),
                "vertical_interval_subtotal_m": str(hypothesis_view["vertical_interval_subtotal_m"]),
                "note": str(hypothesis_view["note"]),
                "student_assessment": {
                    "applicable_preconditions": [str(item) for item in assessment["applicable_preconditions"]],
                    "advantages": [str(item) for item in assessment["advantages"]],
                    "costs_or_risks": [str(item) for item in assessment["costs_or_risks"]],
                    "reconsider_when": [str(item) for item in assessment["reconsider_when"]],
                    "criterion_judgments": [
                        {"criterion": criterion_name_by_id[str(judgment["criterion_id"])], "judgment": str(judgment["judgment"])}
                        for judgment in assessment["criterion_judgments"]
                    ],
                },
            }
        )

    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "comparison_kind": "student_massing_grid_height_hypothesis_comparison",
        "source_binding": {
            **dict(mgh_framework["source_binding"]),
            "massing_grid_height_framework_sha256": _document_sha256(mgh_framework),
            "pending_student_hypothesis_comparison_draft_sha256": draft["human_confirmation"]["pending_student_hypothesis_comparison_draft_sha256"],
            "confirmed_student_hypothesis_comparison_draft_sha256": _document_sha256(draft),
        },
        "selection_status": "pending_selection",
        "human_selection": None,
        "student_view": {
            "project_title": mgh_framework["student_view"]["project_title"],
            "stage": "massing_grid_height_hypothesis_comparison",
            "decision_prompt": _decision_prompt(draft["criteria"], len(candidates_view)),
            "candidates": candidates_view,
            "comparison_criteria": [
                {"name": str(criterion["name"]), "description": str(criterion["description"])}
                for criterion in draft["criteria"]
            ],
            "guidance": _project_guidance(draft, label_by_key, criterion_name_by_id),
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "human_selection_view": None,
            "next_action": dict(NEXT_ACTION_PENDING),
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
    }

    document_errors = _schema_errors(document, comparison_schema, registry, "STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID")
    if document_errors:  # pragma: no cover - defends the output contract against future drift.
        return None
    return document


def build_comparison(
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
) -> tuple[dict[str, Any] | None, ComparisonResult]:
    """Return one deterministic pending comparison document, or no output on any failed gate."""

    upstream = validate_massing_grid_height(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    draft_errors = _verify_confirmed_comparison_draft(comparison_draft, comparison_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors = _comparison_semantic_errors(comparison_draft, mgh_draft, mgh_framework)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}

    document = _project_comparison(mgh_draft, mgh_framework, comparison_draft, comparison_schema, registry)
    if document is None:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": [_error("STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID", "", "the built comparison document failed its closed schema")]}
    return document, {"ok": True, "errors": []}


def _verify_selection_record(record: JsonObject, hypothesis_keys: Sequence[str], pending_hash: str) -> list[ComparisonError]:
    """Fail closed on any invalid, forged, or unbound human selection record."""

    errors: list[ComparisonError] = []
    expected_keys = {"action", "selected_by", "selected_at", "selected_candidate_key", "source_comparison_document_sha256"}
    if set(record.keys()) != expected_keys:
        return [_error("COMPARISON_SELECTION_RECORD_INVALID", "", f"selection record must contain exactly the keys {sorted(expected_keys)}")]
    if record.get("action") != SELECT_ACTION:
        errors.append(_error("COMPARISON_SELECTION_RECORD_INVALID", "/action", f"action must be {SELECT_ACTION}"))
    if not is_human_record_label(record.get("selected_by")):
        errors.append(_error("COMPARISON_SELECTION_RECORD_INVALID", "/selected_by", "selected_by must name a human, not an agent"))
    if not is_rfc3339_datetime(record.get("selected_at")):
        errors.append(_error("COMPARISON_SELECTION_RECORD_INVALID", "/selected_at", "selected_at must be a timezone-qualified RFC 3339 date-time"))
    candidate_key = record.get("selected_candidate_key")
    if not isinstance(candidate_key, str) or CANDIDATE_KEY_RE.fullmatch(candidate_key) is None or candidate_key not in hypothesis_keys:
        errors.append(_error("COMPARISON_SELECTION_CANDIDATE_INVALID", "/selected_candidate_key", "selected_candidate_key must be exactly one existing hypothesis key from the confirmed massing-grid-height draft"))
    bound_hash = record.get("source_comparison_document_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
        errors.append(_error("COMPARISON_SELECTION_RECORD_INVALID", "/source_comparison_document_sha256", "source_comparison_document_sha256 must be exactly 64 lowercase hex characters"))
    elif bound_hash != pending_hash:
        errors.append(_error("COMPARISON_SELECTION_SOURCE_MISMATCH", "/source_comparison_document_sha256", "recorded hash does not bind the whole pending comparison document being answered"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _apply_selection(pending: JsonObject, record: JsonObject, label_by_key: dict[str, str]) -> dict[str, Any]:
    """Bind one verified human selection record to the pending document deterministically."""

    selected: dict[str, Any] = json.loads(json.dumps(pending))
    candidate_key = str(record["selected_candidate_key"])
    selected["selection_status"] = "selected"
    selected["human_selection"] = {
        "status": "selected",
        "action": str(record["action"]),
        "selected_candidate_key": candidate_key,
        "selected_by": str(record["selected_by"]),
        "selected_at": str(record["selected_at"]),
        "source_comparison_document_sha256": str(record["source_comparison_document_sha256"]),
    }
    selected["student_view"]["human_selection_view"] = {
        "selected_label": label_by_key[candidate_key],
        "selected_by": str(record["selected_by"]),
        "selected_at": str(record["selected_at"]),
    }
    selected["student_view"]["next_action"] = dict(NEXT_ACTION_SELECTED)
    return selected


def _expected_pending(
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
) -> tuple[dict[str, Any] | None, ComparisonResult]:
    """Re-derive the deterministic pending document from the full validated chain."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    draft_errors = _verify_confirmed_comparison_draft(comparison_draft, comparison_draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}
    semantic_errors = _comparison_semantic_errors(comparison_draft, mgh_draft, mgh_framework)
    if semantic_errors:
        return None, {"ok": False, "errors": semantic_errors}
    document = _project_comparison(mgh_draft, mgh_framework, comparison_draft, comparison_schema, registry)
    if document is None:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": [_error("STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID", "", "the re-derived comparison document failed its closed schema")]}
    return document, {"ok": True, "errors": []}


def select_comparison(
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
    pending_document: JsonObject,
    selection_record: JsonObject,
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
) -> tuple[dict[str, Any] | None, ComparisonResult]:
    """Bind one explicit human selection record to one verified pending comparison document."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    document_errors = _schema_errors(pending_document, comparison_schema, registry, "STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID")
    if document_errors:
        return None, {"ok": False, "errors": document_errors}
    if pending_document.get("selection_status") == "selected":
        return None, {"ok": False, "errors": [_error("COMPARISON_ALREADY_SELECTED", "/selection_status", "this comparison document already carries a human selection; a selection is recorded exactly once")]}

    upstream = validate_massing_grid_height(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    expected, expected_result = _expected_pending(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    if expected is None:
        return None, expected_result
    if _canonical_json(pending_document) + b"\n" != _canonical_json(expected) + b"\n":
        return None, {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_HYPOTHESIS_COMPARISON_CONTENT_MISMATCH",
                    "",
                    "the supplied pending document is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }

    hypothesis_keys = [str(hypothesis["hypothesis_id"]) for hypothesis in mgh_draft["hypotheses"]]
    record_errors = _verify_selection_record(selection_record, hypothesis_keys, _document_sha256(expected))
    if record_errors:
        return None, {"ok": False, "errors": record_errors}

    label_by_key: dict[str, str] = {}
    for hypothesis_draft, hypothesis_view in zip(mgh_draft["hypotheses"], mgh_framework["student_view"]["hypotheses"]):
        label_by_key[str(hypothesis_draft["hypothesis_id"])] = str(hypothesis_view["label"])
    selected = _apply_selection(expected, selection_record, label_by_key)

    selected_errors = _schema_errors(selected, comparison_schema, registry, "STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID")
    if selected_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": selected_errors}
    return selected, {"ok": True, "errors": []}


def validate_comparison(
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
) -> ComparisonResult:
    """Re-derive the expected pending or selected document from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    document_errors = _schema_errors(document, comparison_schema, registry, "STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID")
    if document_errors:
        return {"ok": False, "errors": document_errors}

    upstream = validate_massing_grid_height(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema,
    )
    if not upstream["ok"]:
        return {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    expected, expected_result = _expected_pending(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    if expected is None:
        return expected_result

    if document.get("selection_status") == "pending_selection":
        if _canonical_json(document) + b"\n" != _canonical_json(expected) + b"\n":
            return {
                "ok": False,
                "errors": [
                    _error(
                        "STUDENT_HYPOTHESIS_COMPARISON_CONTENT_MISMATCH",
                        "",
                        "the supplied pending document is not the exact deterministic projection of its confirmed upstream documents",
                    )
                ],
            }
        return {"ok": True, "errors": []}

    human_selection = document.get("human_selection")
    if not isinstance(human_selection, Mapping):
        return {"ok": False, "errors": [_error("COMPARISON_SELECTION_RECORD_INVALID", "/human_selection", "a selected document must carry exactly one human selection record")]}
    record: JsonObject = {
        "action": human_selection.get("action"),
        "selected_by": human_selection.get("selected_by"),
        "selected_at": human_selection.get("selected_at"),
        "selected_candidate_key": human_selection.get("selected_candidate_key"),
        "source_comparison_document_sha256": human_selection.get("source_comparison_document_sha256"),
    }
    hypothesis_keys = [str(hypothesis["hypothesis_id"]) for hypothesis in mgh_draft["hypotheses"]]
    record_errors = _verify_selection_record(record, hypothesis_keys, _document_sha256(expected))
    if record_errors:
        return {"ok": False, "errors": record_errors}

    label_by_key: dict[str, str] = {}
    for hypothesis_draft, hypothesis_view in zip(mgh_draft["hypotheses"], mgh_framework["student_view"]["hypotheses"]):
        label_by_key[str(hypothesis_draft["hypothesis_id"])] = str(hypothesis_view["label"])
    selected_expected = _apply_selection(expected, record, label_by_key)
    if _canonical_json(document) + b"\n" != _canonical_json(selected_expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_HYPOTHESIS_COMPARISON_CONTENT_MISMATCH",
                    "",
                    "the supplied selected document is not the exact deterministic projection of its confirmed upstream documents and selection record",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, ComparisonResult]:
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
    }


def main(argv: Sequence[str]) -> int:
    """Confirm a pending comparison draft, build a pending document, bind a human selection, or validate a document."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending comparison draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student hypothesis comparison draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one pending comparison document from the confirmed upstream chain")
    select_parser = subparsers.add_parser("select", help="bind one explicit human selection record to one verified pending comparison document")
    validate_parser = subparsers.add_parser("validate", help="validate one pending or selected comparison document against its upstream chain")
    for upstream_parser in (build_parser, select_parser, validate_parser):
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
        upstream_parser.add_argument("mgh_draft", type=Path, help="confirmed student massing-grid-height draft JSON")
        upstream_parser.add_argument("mgh_framework", type=Path, help="student massing-grid-height framework JSON")
        upstream_parser.add_argument("comparison_draft", type=Path, help="confirmed student hypothesis comparison draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    select_parser.add_argument("document", type=Path, help="pending comparison document JSON being answered")
    select_parser.add_argument("selection_record", type=Path, help="human selection record JSON")
    select_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("document", type=Path, help="pending or selected comparison document JSON")

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
            if arguments.command in ("select", "validate"):
                document_document = load_json_object(arguments.document)
                if arguments.command == "select":
                    selection_record_document = load_json_object(arguments.selection_record)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_comparison_draft(draft_document, human_record, schemas["comparison_draft"])
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        document, result = build_comparison(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
            mgh_draft_document, mgh_framework_document, comparison_draft_document,
            schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
            schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
            schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
        )
        if document is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(document, arguments.output)
        return exit_code

    if arguments.command == "select":
        selected, result = select_comparison(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
            mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, selection_record_document,
            schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
            schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
            schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
        )
        if selected is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(selected, arguments.output)
        return exit_code

    result = validate_comparison(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
        mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document,
        schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
        schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
        schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
