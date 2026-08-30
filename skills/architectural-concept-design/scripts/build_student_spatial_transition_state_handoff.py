"""Build and validate a human-reviewed spatial transition state handoff.

This local deterministic stage accepts only an exact, validated ARCH-110
spatial transition framework without unresolved items and one human review
record bound to that framework. It reuses ARCH-110's public validation entry,
therefore re-running the full ARCH-097~110 chain without changing a role,
pattern, or human review note. A revision outcome is valid human feedback but
produces no handoff. A continue outcome creates JSON data only; it is never a
drawing, geometry, or architectural decision.
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
import build_student_spatial_transition as transition_builder
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
HANDOFF_SCHEMA_PATH = REFERENCES / "student-spatial-transition-state-handoff.schema.json"

REVIEW_ACTION = "REVIEW_STUDENT_SPATIAL_TRANSITION_FRAMEWORK"
CONTINUE_OUTCOME = "continue_to_manual_spatial_design"
REVISE_OUTCOME = "revise_spatial_transition"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

_REVIEW_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "record_kind",
        "action",
        "reviewed_by",
        "reviewed_at",
        "source_spatial_transition_framework_sha256",
        "outcome",
        "review_notes",
    }
)

NEXT_ACTION = {
    "action": "human_continue_manual_spatial_design",
    "description": (
        "Continue manual spatial design from this reviewed hierarchy and transition record; "
        "the handoff generates no drawing, geometry, plan, or presentation."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "Spatial hierarchy and transition patterns are human-authored intentions only; they establish no size, distance, adjacency measurement, or performance result.",
    "The human review records continuation or revision only; it is not a quality, compliance, performance, constructibility, or professional-approval claim.",
    "This handoff never moves, resizes, rotates, adds, removes, or optimizes a block, and never applies a review note.",
    "It generates no drawing, image, presentation, three-dimensional model, site conclusion, or design decision.",
)

CONFIRMED_AVAILABLE: tuple[str, ...] = (
    "The exact human-reviewed ARCH-110 spatial hierarchy and transition patterns, backed by the validated ARCH-097~110 chain.",
    "The human review outcome and up to three verbatim review notes, bound to the exact reviewed spatial transition framework.",
)

MUST_NOT_INFER: tuple[str, ...] = (
    "Any coordinate, rectangle, size, distance, orientation, entrance, corridor, wall, door, column, stair, toilet, or plan layout.",
    "Any automatic selection, ranking, scoring, recommendation, pattern choice, or design decision.",
    "Any site, orientation, structure, regulation, cost, performance, environmental, constructibility, or professional-approval conclusion.",
)

INVALIDATED_BY_UPSTREAM_CHANGE: tuple[str, ...] = (
    "Any change to an ARCH-097~110 source document invalidates this handoff; rebuild and revalidate it against the changed chain.",
    "Any change to the bound spatial transition framework invalidates the review record and handoff; a human must review the changed framework again.",
)

PROHIBITED_OUTPUTS: tuple[str, ...] = (
    "Automatic plan generation, drawing, image, presentation, or three-dimensional model.",
    "Automatic selection, ranking, scoring, recommendation, or revision of a hierarchy or transition decision.",
    "A site, code, cost, structural, performance, or constructibility conclusion.",
)


class HandoffError(TypedDict):
    """One deterministic rejection without a partial handoff."""

    code: str
    path: str
    message: str


class HandoffResult(TypedDict):
    """The public result of building or validating one transition handoff."""

    ok: bool
    errors: list[HandoffError]


def _copy_json(value: Any) -> Any:
    """Return a detached JSON-compatible copy without changing the source value."""

    return json.loads(json.dumps(value, ensure_ascii=False))


def _handoff_registry(schemas: Mapping[str, JsonObject]) -> Any:
    """Return the closed registry for handoff validation over the full chain."""

    chain_builder = transition_builder.support_builder
    return _registry(
        *(schemas[key] for key in chain_builder.handoff_builder._BLOCK_SCHEMA_KEYS),
        schemas["review"],
        schemas["handoff"],
        schemas["draft"],
        schemas["framework"],
        schemas["transition_draft"],
        schemas["transition_framework"],
        schemas["state_handoff"],
    )


def _validate_spatial_transition(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> HandoffResult:
    """Run the sole ARCH-110 upstream entry over its complete source chain."""

    result = transition_builder.validate_spatial_transition_framework(
        chain, review, handoff, support_draft, support_framework, draft, framework, schemas
    )
    return {"ok": bool(result["ok"]), "errors": [dict(error) for error in result["errors"]]}  # type: ignore[return-value]


def _review_errors(record: JsonObject, framework: JsonObject) -> list[HandoffError]:
    """Validate the exact closed human review record and its framework binding."""

    errors: list[HandoffError] = []
    if set(record) != _REVIEW_RECORD_KEYS:
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "", "the review record must contain exactly schema_version, record_kind, action, reviewed_by, reviewed_at, source_spatial_transition_framework_sha256, outcome, and review_notes"))
        return errors
    if record.get("schema_version") != "1.0.0":
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/schema_version", "schema_version must be 1.0.0"))
    if record.get("record_kind") != "student_spatial_transition_review":
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/record_kind", "record_kind must be student_spatial_transition_review"))
    if record.get("action") != REVIEW_ACTION:
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/action", f"action must be {REVIEW_ACTION}"))
    if not is_human_record_label(record.get("reviewed_by")):
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/reviewed_by", "reviewed_by must name a human, not an agent"))
    if not is_rfc3339_datetime(record.get("reviewed_at")):
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/reviewed_at", "reviewed_at must be a timezone-qualified RFC 3339 date-time"))
    if record.get("outcome") not in (CONTINUE_OUTCOME, REVISE_OUTCOME):
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/outcome", f"outcome must be {CONTINUE_OUTCOME} or {REVISE_OUTCOME}"))
    notes = record.get("review_notes")
    if not isinstance(notes, Sequence) or isinstance(notes, str) or len(notes) > 3 or any(not isinstance(note, str) or not note for note in notes):
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/review_notes", "review_notes must be at most three non-empty human-authored strings"))
    bound_hash = record.get("source_spatial_transition_framework_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_RECORD_INVALID", "/source_spatial_transition_framework_sha256", "source_spatial_transition_framework_sha256 must be exactly 64 lowercase hex characters"))
    elif bound_hash != _document_sha256(framework):
        errors.append(_error("SPATIAL_TRANSITION_REVIEW_SOURCE_FRAMEWORK_MISMATCH", "/source_spatial_transition_framework_sha256", "the review record does not bind the supplied exact spatial transition framework"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _project_handoff(framework: JsonObject, record: JsonObject, schemas: Mapping[str, JsonObject]) -> dict[str, Any] | None:
    """Project only the reviewed human hierarchy, patterns, and review outcome."""

    view = framework["student_view"]
    handoff: dict[str, Any] = {
        "schema_version": "1.0.0",
        "handoff_kind": "student_spatial_transition_state_handoff",
        "source_binding": {
            "spatial_transition_framework_sha256": _document_sha256(framework),
            "review_record_sha256": _document_sha256(record),
            "review_action": REVIEW_ACTION,
            "reviewed_by": str(record["reviewed_by"]),
            "reviewed_at": str(record["reviewed_at"]),
            "review_outcome": CONTINUE_OUTCOME,
        },
        "student_handoff": {
            "project_title": str(view["project_title"]),
            "stage": "spatial_transition_reviewed_for_handoff",
            "space_hierarchy": _copy_json(view["space_hierarchy"]),
            "transition_patterns": _copy_json(view["transition_patterns"]),
            "clarification_questions": _copy_json(view["clarification_questions"]),
            "review_summary": {
                "reviewed_by": str(record["reviewed_by"]),
                "reviewed_at": str(record["reviewed_at"]),
                "outcome": CONTINUE_OUTCOME,
                "review_notes": _copy_json(record["review_notes"]),
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
    errors = _schema_errors(handoff, schemas["state_handoff"], _handoff_registry(schemas), "STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_SCHEMA_INVALID")
    if errors:  # pragma: no cover - protects output drift.
        return None
    return handoff


def build_spatial_transition_state_handoff(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    transition_review: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, HandoffResult]:
    """Build one state handoff only after valid framework and human continuation."""

    upstream = _validate_spatial_transition(chain, review, handoff, support_draft, support_framework, draft, framework, schemas)
    if not upstream["ok"]:
        return None, upstream
    if framework["student_view"]["unresolved_items"]:
        return None, {
            "ok": False,
            "errors": [_error("SPATIAL_TRANSITION_HANDOFF_UPSTREAM_UNRESOLVED", "/student_view/unresolved_items", "resolve_spatial_transition_gaps before reviewing and handing off a spatial transition framework")],
        }
    record_errors = _review_errors(transition_review, framework)
    if record_errors:
        return None, {"ok": False, "errors": record_errors}
    if transition_review.get("outcome") != CONTINUE_OUTCOME:
        return None, {
            "ok": False,
            "errors": [_error("SPATIAL_TRANSITION_REVIEW_NOT_CONTINUED", "/outcome", "the human requested revise_spatial_transition; revise and review a new framework before a handoff")],
        }
    built = _project_handoff(framework, transition_review, schemas)
    if built is None:  # pragma: no cover - protects output drift.
        return None, {
            "ok": False,
            "errors": [_error("STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_SCHEMA_INVALID", "", "the built spatial transition state handoff failed its closed schema")],
        }
    return built, {"ok": True, "errors": []}


def validate_spatial_transition_state_handoff(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    transition_review: JsonObject,
    transition_handoff: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> HandoffResult:
    """Rebuild the one permitted handoff and compare canonical bytes exactly."""

    errors = _schema_errors(transition_handoff, schemas["state_handoff"], _handoff_registry(schemas), "STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_SCHEMA_INVALID")
    if errors:
        return {"ok": False, "errors": [dict(error) for error in errors]}
    expected, result = build_spatial_transition_state_handoff(
        chain, review, handoff, support_draft, support_framework, draft, framework, transition_review, schemas
    )
    if expected is None:
        return result
    if _canonical_json(transition_handoff) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_CONTENT_MISMATCH",
                    "",
                    "the supplied spatial transition state handoff is not the exact deterministic projection of its validated framework and human review record",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, HandoffResult]:
    """Print JSON or atomically write it only after every prior gate succeeds."""

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
    """Load the committed ARCH-110 schemas plus this stage's closed contract."""

    schemas = dict(transition_builder._load_schemas())
    schemas["state_handoff"] = load_json_object(HANDOFF_SCHEMA_PATH)
    return schemas


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the fixed ARCH-097~110 documents, reviewed framework, and review record."""

    transition_builder._add_state_arguments(parser)
    parser.add_argument("draft", type=Path, help="confirmed ARCH-110 spatial transition draft JSON")
    parser.add_argument("framework", type=Path, help="validated ARCH-110 spatial transition framework JSON")
    parser.add_argument("transition_review", type=Path, help="human spatial transition review record JSON")


def _load_chain(arguments: argparse.Namespace) -> tuple[JsonObject, ...]:
    """Load the fixed ordered ARCH-097~107 chain reused by ARCH-110."""

    return transition_builder._load_chain(arguments)


def main(argv: Sequence[str]) -> int:
    """Build or validate a state handoff from a reviewed spatial transition framework."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build one handoff after human continuation")
    validate_parser = subparsers.add_parser("validate", help="validate one handoff against framework and review")
    for command_parser in (build_parser, validate_parser):
        _add_arguments(command_parser)
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("transition_handoff", type=Path, help="student spatial transition state handoff JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
        chain = _load_chain(arguments)
        review = load_json_object(arguments.review)
        handoff = load_json_object(arguments.handoff)
        support_draft = load_json_object(arguments.support_draft)
        support_framework = load_json_object(arguments.support_framework)
        draft = load_json_object(arguments.draft)
        framework = load_json_object(arguments.framework)
        transition_review = load_json_object(arguments.transition_review)
        if arguments.command == "validate":
            transition_handoff = load_json_object(arguments.transition_handoff)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        built, result = build_spatial_transition_state_handoff(
            chain, review, handoff, support_draft, support_framework, draft, framework, transition_review, schemas
        )
        if built is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(built, arguments.output)
        return exit_code

    result = validate_spatial_transition_state_handoff(
        chain, review, handoff, support_draft, support_framework, draft, framework, transition_review, transition_handoff, schemas
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
