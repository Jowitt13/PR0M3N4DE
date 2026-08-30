"""Build and validate one student selected hypothesis state package.

This deterministic, local-only slice wraps one selected ARCH-104 comparison
document into a closed state package for the next separately reviewed stage.
It reuses the committed ``validate_comparison`` public entry, so the complete
ARCH-097~104 chain is re-verified, every upstream stable error code
propagates unchanged, and a tampered upstream document, comparison document,
or selection record can never produce an output. Only the ``selected``
comparison state is accepted: a pending document fails closed with
``SELECTED_STATE_NOT_SELECTED``, and the human selection is never replaced,
re-ranked, re-scored, or re-derived; guidance never becomes a selection.

The package carries four closed sections: a machine-only ``source_binding``
with the full upstream hash chain plus the selected document and human-record
binding, a machine-only ``selected_state`` marked as verification binding
only, a human-readable ``student_handoff`` without internal ids, hashes, or
decision semantics, and a ``handoff_contract`` stating what the next stage may
rely on, must not infer, and what invalidates the handoff. The next action is
``author_selected_plan_framework_draft``; the package decides no plan
coordinate, entrance, site, massing shape, structural system, regulation,
cost, performance, or constructibility, and generates no drawing, image,
PPTX, or three-dimensional model. This is not the generic project state
package and it never calls ``assemble_project_state``. The script opens no
socket and starts no subprocess, reads no system clock, never modifies an
input document, and writes a destination only after full validation. Validate
re-derives the expected package deterministically and requires exact byte
equality.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from build_student_hypothesis_comparison import (
    COMPARISON_DRAFT_SCHEMA_PATH,
    COMPARISON_SCHEMA_PATH,
    validate_comparison,
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
STATE_SCHEMA_PATH = REFERENCES / "student-selected-hypothesis-state.schema.json"

NEXT_ACTION = {
    "action": "author_selected_plan_framework_draft",
    "description": (
        "The human authors the next stage's plan-framework draft over this confirmed selected hypothesis; "
        "this state package supplies no plan coordinates, drawing, PPTX, or design decision."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "The selected hypothesis is the student's own confirmed input; it is not a verified architectural conclusion.",
    "The next stage remains organized by the human: spatial positions and relations, entrances, orientation, and any plan drawing are authored there, not derived here.",
    "This state package decides no plan coordinate, room rectangle, floor count beyond the written levels, entrance, total plan, massing shape, orientation, column grid value beyond the written bays, structural system, regulation, cost, performance, or constructibility.",
    "Guidance shown here, when present, is the student's own decision guidance, not an automatic architectural decision.",
    "This package generates no drawing, image, PPTX, or three-dimensional model, and it selects nothing.",
)

GUIDANCE_BOUNDS: tuple[str, ...] = (
    "This is decision guidance, not an automatic architectural decision.",
)

CONFIRMED_AVAILABLE: tuple[str, ...] = (
    "The student-written massing groups, grid intent, and vertical intervals of the human-selected hypothesis, as confirmed through the ARCH-097~104 chain.",
    "The student's own assessment of the selected candidate: applicable preconditions, advantages, costs or risks, and reconsider conditions.",
    "The explicit human selection record that binds this state package to the selected comparison document.",
    "The confirmed upstream floor zoning levels and zones that the selected hypothesis organizes.",
)

MUST_NOT_INFER: tuple[str, ...] = (
    "Plan coordinates, room rectangles, entrances, circulation drawings, or any total plan.",
    "Floor counts beyond the student-written levels, massing shape, orientation, or site position.",
    "Column grid values beyond the student-written bays, or any structural system, load, or span conclusion.",
    "Regulation, cost, performance, or constructibility conclusions.",
    "Any automatic design decision: this package is a verified record of a human selection, not a design instruction.",
)

INVALIDATED_BY_UPSTREAM_CHANGE: tuple[str, ...] = (
    "Any change to an ARCH-097~104 upstream document invalidates this handoff; the state package must be rebuilt and revalidated against the changed chain.",
    "A changed or re-selected comparison document invalidates this handoff; selection happens exactly once and the package must be rebuilt.",
    "The handoff stays valid only while the bound selected comparison document remains the exact deterministic projection of its upstream chain.",
)

PROHIBITED_OUTPUTS: tuple[str, ...] = (
    "Automatic plan generation, drawing, image, PPTX, or three-dimensional model.",
    "Automatic selection, ranking, scoring, or recommendation of a candidate.",
    "Any machine-made design conclusion derived from the selected hypothesis.",
)


class StateError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class StateResult(TypedDict):
    """The public result of building or validating one selected hypothesis state package."""

    ok: bool
    errors: list[StateError]


def _related_guidance(comparison_view: JsonObject, selected_label: str) -> dict[str, Any] | None:
    """Project the student's own guidance only when the selected candidate is in its focus."""

    guidance = comparison_view["guidance"]
    if guidance.get("status") != "guidance_available":
        return None
    focus_labels: list[str] = []
    if "recommended_to_consider_first" in guidance:
        focus_labels.append(str(guidance["recommended_to_consider_first"]))
    if "suggested_focus" in guidance:
        focus_labels.extend(str(label) for label in guidance["suggested_focus"])
    if selected_label not in focus_labels:
        return None
    return {
        "basis": str(guidance["basis"]),
        "basis_criteria": [str(item) for item in guidance["basis_criteria"]],
        "advantages": [str(item) for item in guidance["advantages"]],
        "costs_or_risks": [str(item) for item in guidance["costs_or_risks"]],
        "reconsider_when": [str(item) for item in guidance["reconsider_when"]],
        "bounds_statement": list(GUIDANCE_BOUNDS),
    }


def _project_state(
    mgh_draft: JsonObject,
    mgh_framework: JsonObject,
    comparison_draft: JsonObject,
    document: JsonObject,
    state_schema: JsonObject,
    registry: Any,
) -> dict[str, Any] | None:
    """Project one state package from an already-validated selected comparison document."""

    human_selection = document["human_selection"]
    selected_key = str(human_selection["selected_candidate_key"])
    hypothesis_index: int | None = None
    for index, hypothesis in enumerate(mgh_draft["hypotheses"]):
        if str(hypothesis["hypothesis_id"]) == selected_key:
            hypothesis_index = index
            break
    if hypothesis_index is None:  # pragma: no cover - defended by the upstream selection record verification.
        return None
    selected_view = mgh_framework["student_view"]["hypotheses"][hypothesis_index]
    selected_label = str(selected_view["label"])

    criterion_name_by_id = {str(criterion["criterion_id"]): str(criterion["name"]) for criterion in comparison_draft["criteria"]}
    assessment = next(
        item for item in comparison_draft["candidate_assessments"] if str(item["candidate_key"]) == selected_key
    )

    selected_candidate = {
        "label": selected_label,
        "massing_groups": json.loads(json.dumps(selected_view["massing_groups"])),
        "grid_intent": json.loads(json.dumps(selected_view["grid_intent"])),
        "vertical_intervals": json.loads(json.dumps(selected_view["vertical_intervals"])),
        "vertical_interval_subtotal_m": str(selected_view["vertical_interval_subtotal_m"]),
        "note": str(selected_view["note"]),
    }
    selected_assessment = {
        "applicable_preconditions": [str(item) for item in assessment["applicable_preconditions"]],
        "advantages": [str(item) for item in assessment["advantages"]],
        "costs_or_risks": [str(item) for item in assessment["costs_or_risks"]],
        "reconsider_when": [str(item) for item in assessment["reconsider_when"]],
        "criterion_judgments": [
            {"criterion": criterion_name_by_id[str(judgment["criterion_id"])], "judgment": str(judgment["judgment"])}
            for judgment in assessment["criterion_judgments"]
        ],
    }
    summary = document["student_view"]["human_selection_view"]
    package: dict[str, Any] = {
        "schema_version": "1.0.0",
        "state_kind": "student_selected_hypothesis_state",
        "source_binding": {
            **dict(document["source_binding"]),
            "selected_comparison_document_sha256": _document_sha256(document),
            "human_selection_action": str(human_selection["action"]),
            "human_selection_candidate_key": selected_key,
            "human_selection_selected_by": str(human_selection["selected_by"]),
            "human_selection_selected_at": str(human_selection["selected_at"]),
            "human_selection_source_comparison_document_sha256": str(human_selection["source_comparison_document_sha256"]),
        },
        "selected_state": {
            "purpose": "machine_verification_binding_only",
            "selected_candidate_key": selected_key,
            "selection_record": {
                "action": str(human_selection["action"]),
                "selected_by": str(human_selection["selected_by"]),
                "selected_at": str(human_selection["selected_at"]),
                "source_comparison_document_sha256": str(human_selection["source_comparison_document_sha256"]),
            },
        },
        "student_handoff": {
            "project_title": mgh_framework["student_view"]["project_title"],
            "stage": "selected_hypothesis_confirmed",
            "selected_candidate": selected_candidate,
            "selected_assessment": selected_assessment,
            "related_guidance": _related_guidance(document["student_view"], selected_label),
            "human_selection_summary": {
                "selected_label": str(summary["selected_label"]),
                "selected_by": str(summary["selected_by"]),
                "selected_at": str(summary["selected_at"]),
            },
            "next_action": dict(NEXT_ACTION),
            "boundaries_statement": list(BOUNDARIES_STATEMENT),
        },
        "handoff_contract": {
            "confirmed_available": list(CONFIRMED_AVAILABLE),
            "must_not_infer": list(MUST_NOT_INFER),
            "invalidated_by_upstream_change": list(INVALIDATED_BY_UPSTREAM_CHANGE),
            "prohibited_outputs": list(PROHIBITED_OUTPUTS),
        },
    }

    package_errors = _schema_errors(package, state_schema, registry, "STUDENT_SELECTED_HYPOTHESIS_STATE_SCHEMA_INVALID")
    if package_errors:  # pragma: no cover - defends the output contract against future drift.
        return None
    return package


def _verify_selected_document(document: JsonObject, comparison_schema: JsonObject, registry: Any) -> list[StateError]:
    """Accept only the selected comparison state; fail closed on pending or unselected documents."""

    document_errors = _schema_errors(document, comparison_schema, registry, "STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID")
    if document_errors:
        return [dict(error) for error in document_errors]
    if document.get("selection_status") != "selected":
        return [
            _error(
                "SELECTED_STATE_NOT_SELECTED",
                "/selection_status",
                "only a selected comparison document can form the selected hypothesis state package; a pending comparison selects nothing",
            )
        ]
    return []


def build_state(
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
    state_schema: JsonObject,
) -> tuple[dict[str, Any] | None, StateResult]:
    """Return one deterministic selected hypothesis state package, or no output on any failed gate."""

    upstream = validate_comparison(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema,
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema, state_schema,
    )
    selection_errors = _verify_selected_document(document, comparison_schema, registry)
    if selection_errors:
        return None, {"ok": False, "errors": selection_errors}

    package = _project_state(mgh_draft, mgh_framework, comparison_draft, document, state_schema, registry)
    if package is None:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": [_error("STUDENT_SELECTED_HYPOTHESIS_STATE_SCHEMA_INVALID", "", "the built state package failed its closed schema")]}
    return package, {"ok": True, "errors": []}


def validate_state(
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
    package: JsonObject,
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
) -> StateResult:
    """Re-derive the expected state package from the full upstream chain and compare it exactly."""

    registry = _registry(
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema, state_schema,
    )
    package_errors = _schema_errors(package, state_schema, registry, "STUDENT_SELECTED_HYPOTHESIS_STATE_SCHEMA_INVALID")
    if package_errors:
        return {"ok": False, "errors": package_errors}

    expected, build_result = build_state(
        digest, board, program_draft, program, dimension_draft, dimension_plan, selection, zoning_draft, zoning_framework, ce_draft, ce_framework, mgh_draft, mgh_framework, comparison_draft, document,
        intake_schema, digest_schema, board_schema, program_draft_schema, program_schema,
        dimension_draft_schema, dimension_plan_schema, selection_schema, zoning_draft_schema, zoning_schema,
        ce_draft_schema, ce_schema, mgh_draft_schema, mgh_schema, comparison_draft_schema, comparison_schema, state_schema,
    )
    if expected is None:
        return build_result
    if _canonical_json(package) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_SELECTED_HYPOTHESIS_STATE_CONTENT_MISMATCH",
                    "",
                    "the supplied state package is not the exact deterministic projection of its confirmed upstream chain and selected comparison document",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, StateResult]:
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


def main(argv: Sequence[str]) -> int:
    """Build or validate one selected hypothesis state package from a selected comparison document."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build one selected hypothesis state package from the confirmed upstream chain")
    validate_parser = subparsers.add_parser("validate", help="validate one selected hypothesis state package against its upstream chain")
    for upstream_parser in (build_parser, validate_parser):
        _add_upstream_arguments(upstream_parser)
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("state_package", type=Path, help="selected hypothesis state package JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
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
        if arguments.command == "validate":
            package_document = load_json_object(arguments.state_package)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        package, result = build_state(
            digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
            selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
            mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document,
            schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
            schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
            schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
            schemas["state"],
        )
        if package is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(package, arguments.output)
        return exit_code

    result = validate_state(
        digest, board, program_draft_document, program_document, dimension_draft_document, dimension_plan_document,
        selection_document, zoning_draft_document, zoning_framework_document, ce_draft_document, ce_framework_document,
        mgh_draft_document, mgh_framework_document, comparison_draft_document, document_document, package_document,
        schemas["intake"], schemas["digest"], schemas["board"], schemas["program_draft"], schemas["program"],
        schemas["dimension_draft"], schemas["dimension_plan"], schemas["selection"], schemas["zoning_draft"], schemas["zoning"],
        schemas["ce_draft"], schemas["ce"], schemas["mgh_draft"], schemas["mgh"], schemas["comparison_draft"], schemas["comparison"],
        schemas["state"],
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
