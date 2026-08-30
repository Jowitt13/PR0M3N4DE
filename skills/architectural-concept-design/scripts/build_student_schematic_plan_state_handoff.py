"""Build and validate a human-reviewed student schematic-plan state handoff.

This local deterministic slice accepts only an exact, validated ARCH-107
schematic-blocks document and one human review record bound to that document.
It reuses ARCH-107's public validation entry, therefore re-running the full
ARCH-097~107 chain without changing a rectangle, relationship, dimension, or
human review note. A revision outcome is valid human feedback but produces no
handoff. A continue outcome creates JSON data only; it is never a drawing or
an architectural decision.
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
import build_student_schematic_plan_blocks as blocks_builder
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
REVIEW_SCHEMA_PATH = REFERENCES / "student-schematic-plan-review.schema.json"
HANDOFF_SCHEMA_PATH = REFERENCES / "student-schematic-plan-state-handoff.schema.json"

REVIEW_ACTION = "REVIEW_STUDENT_SCHEMATIC_PLAN_BLOCKS"
CONTINUE_OUTCOME = "continue_to_handoff"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

NEXT_ACTION = {
    "action": "human_continue_manual_schematic_design",
    "description": (
        "Continue manual schematic design from this reviewed local-coordinate record; "
        "the handoff generates no drawing, plan, or presentation."
    ),
}

BOUNDARIES_STATEMENT: tuple[str, ...] = (
    "All coordinates are local schematic coordinates only, never site, survey, north, elevation, or building coordinates.",
    "The human review records continuation or revision only; it is not a quality, compliance, performance, constructibility, or professional-approval claim.",
    "This handoff never moves, optimizes, rescales, redraws, or interprets a rectangle or review note.",
    "It generates no wall, door, column, stair, entrance, corridor, site plan, drawing, image, presentation, or three-dimensional model.",
)

CONFIRMED_AVAILABLE: tuple[str, ...] = (
    "The exact human-reviewed ARCH-107 local schematic containers, placements, selected dimensions, and relation verification statuses.",
    "The human review outcome and up to three verbatim review notes, bound to the exact reviewed blocks document.",
)

MUST_NOT_INFER: tuple[str, ...] = (
    "Any site plan, orientation, building outline, wall, door, column, stair, toilet, entrance, corridor, or circulation drawing.",
    "Any automatic rectangle movement, optimization, spatial recommendation, visual-quality judgment, or design decision.",
    "Any structure, regulation, cost, performance, environmental, constructibility, or professional-approval conclusion.",
)

INVALIDATED_BY_UPSTREAM_CHANGE: tuple[str, ...] = (
    "Any change to an ARCH-097~107 source document invalidates this handoff; rebuild and revalidate it against the changed chain.",
    "Any change to the bound schematic blocks document invalidates the review record and handoff; a human must review the changed blocks again.",
)

PROHIBITED_OUTPUTS: tuple[str, ...] = (
    "Automatic plan generation, drawing, image, presentation, or three-dimensional model.",
    "Automatic selection, ranking, scoring, recommendation, or revision of the schematic plan.",
    "A site, code, cost, structural, performance, or constructibility conclusion.",
)

_DOCUMENT_KEYS: tuple[str, ...] = (
    "digest",
    "board",
    "program_draft",
    "program",
    "dimension_draft",
    "dimension_plan",
    "selection",
    "zoning_draft",
    "zoning_framework",
    "ce_draft",
    "ce_framework",
    "mgh_draft",
    "mgh_framework",
    "comparison_draft",
    "document",
    "state_package",
    "plan_draft",
    "plan_framework",
    "schematic_draft",
    "blocks",
)

_BLOCK_SCHEMA_KEYS: tuple[str, ...] = (
    "intake",
    "digest",
    "board",
    "program_draft",
    "program",
    "dimension_draft",
    "dimension_plan",
    "selection",
    "zoning_draft",
    "zoning",
    "ce_draft",
    "ce",
    "mgh_draft",
    "mgh",
    "comparison_draft",
    "comparison",
    "state",
    "plan_draft",
    "plan_framework",
    "schematic_draft",
    "schematic_blocks",
)


class HandoffError(TypedDict):
    """One deterministic rejection without a partial handoff."""

    code: str
    path: str
    message: str


class HandoffResult(TypedDict):
    """The public result of building or validating one schematic-plan handoff."""

    ok: bool
    errors: list[HandoffError]


def _copy_json(value: Any) -> Any:
    """Return a detached JSON-compatible copy without changing the source value."""

    return json.loads(json.dumps(value, ensure_ascii=False))


def _handoff_registry(schemas: Mapping[str, JsonObject]) -> Any:
    """Return the closed registry for review and handoff validation."""

    return _registry(*(schemas[key] for key in _BLOCK_SCHEMA_KEYS), schemas["review"], schemas["handoff"])


def _validate_blocks_chain(chain: DocumentChain, schemas: Mapping[str, JsonObject]) -> HandoffResult:
    """Run the sole ARCH-107 upstream entry over the complete supplied chain."""

    if len(chain) != len(_DOCUMENT_KEYS):  # pragma: no cover - CLI and tests supply the fixed contract.
        return {
            "ok": False,
            "errors": [_error("SCHEMATIC_REVIEW_CHAIN_INVALID", "", "the schematic review command requires the complete ARCH-097~107 document chain")],
        }
    result = blocks_builder.validate_schematic_plan_blocks(
        *chain,
        *(schemas[key] for key in _BLOCK_SCHEMA_KEYS),
    )
    return {"ok": bool(result["ok"]), "errors": [dict(error) for error in result["errors"]]}  # type: ignore[return-value]


def _review_errors(review: JsonObject, blocks: JsonObject, schemas: Mapping[str, JsonObject]) -> list[HandoffError]:
    """Validate one human review record and its exact blocks binding."""

    registry = _handoff_registry(schemas)
    errors = _schema_errors(review, schemas["review"], registry, "SCHEMATIC_REVIEW_RECORD_SCHEMA_INVALID")
    if errors:
        return [dict(error) for error in errors]

    semantic_errors: list[HandoffError] = []
    if review.get("action") != REVIEW_ACTION:
        semantic_errors.append(_error("SCHEMATIC_REVIEW_RECORD_INVALID", "/action", f"action must be {REVIEW_ACTION}"))
    if not is_human_record_label(review.get("reviewed_by")):
        semantic_errors.append(_error("SCHEMATIC_REVIEW_RECORD_INVALID", "/reviewed_by", "reviewed_by must name a human, not an agent"))
    if not is_rfc3339_datetime(review.get("reviewed_at")):
        semantic_errors.append(_error("SCHEMATIC_REVIEW_RECORD_INVALID", "/reviewed_at", "reviewed_at must be a timezone-qualified RFC 3339 date-time"))
    source_hash = review.get("source_schematic_plan_blocks_sha256")
    if not isinstance(source_hash, str) or SHA256_RE.fullmatch(source_hash) is None:
        semantic_errors.append(_error("SCHEMATIC_REVIEW_RECORD_INVALID", "/source_schematic_plan_blocks_sha256", "source_schematic_plan_blocks_sha256 must be exactly 64 lowercase hex characters"))
    elif source_hash != _document_sha256(blocks):
        semantic_errors.append(_error("SCHEMATIC_REVIEW_SOURCE_BLOCKS_MISMATCH", "/source_schematic_plan_blocks_sha256", "the review record does not bind the supplied schematic plan blocks document"))
    semantic_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return semantic_errors


def _project_handoff(blocks: JsonObject, review: JsonObject, schemas: Mapping[str, JsonObject]) -> dict[str, Any] | None:
    """Project the exact local schematic view and human review into a closed handoff."""

    view = blocks["student_view"]
    handoff: dict[str, Any] = {
        "schema_version": "1.0.0",
        "handoff_kind": "student_schematic_plan_state_handoff",
        "source_binding": {
            "schematic_plan_blocks_sha256": _document_sha256(blocks),
            "review_record_sha256": _document_sha256(review),
            "review_action": REVIEW_ACTION,
            "reviewed_by": str(review["reviewed_by"]),
            "reviewed_at": str(review["reviewed_at"]),
            "review_outcome": CONTINUE_OUTCOME,
        },
        "student_handoff": {
            "project_title": str(view["project_title"]),
            "stage": "schematic_plan_reviewed_for_handoff",
            "coordinate_scope": "local_schematic_coordinates_only",
            "levels": _copy_json(view["levels"]),
            "relations": _copy_json(view["relations"]),
            "clarification_questions": _copy_json(view["clarification_questions"]),
            "review_summary": {
                "reviewed_by": str(review["reviewed_by"]),
                "reviewed_at": str(review["reviewed_at"]),
                "outcome": CONTINUE_OUTCOME,
                "review_notes": _copy_json(review["review_notes"]),
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
    errors = _schema_errors(handoff, schemas["handoff"], _handoff_registry(schemas), "STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_SCHEMA_INVALID")
    if errors:  # pragma: no cover - protects output drift.
        return None
    return handoff


def build_schematic_plan_state_handoff(
    chain: DocumentChain,
    review: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[dict[str, Any] | None, HandoffResult]:
    """Build one state handoff only after valid blocks and human continuation."""

    upstream = _validate_blocks_chain(chain, schemas)
    if not upstream["ok"]:
        return None, upstream
    blocks = chain[-1]
    review_errors = _review_errors(review, blocks, schemas)
    if review_errors:
        return None, {"ok": False, "errors": review_errors}
    if review.get("outcome") != CONTINUE_OUTCOME:
        return None, {
            "ok": False,
            "errors": [_error("SCHEMATIC_REVIEW_NOT_CONTINUED", "/outcome", "the human requested revise_schematic_plan; rebuild and review revised blocks before a handoff")],
        }

    handoff = _project_handoff(blocks, review, schemas)
    if handoff is None:  # pragma: no cover - protects output drift.
        return None, {
            "ok": False,
            "errors": [_error("STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_SCHEMA_INVALID", "", "the built schematic-plan state handoff failed its closed schema")],
        }
    return handoff, {"ok": True, "errors": []}


def validate_schematic_plan_state_handoff(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> HandoffResult:
    """Rebuild the one permitted handoff and compare canonical bytes exactly."""

    errors = _schema_errors(handoff, schemas["handoff"], _handoff_registry(schemas), "STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_SCHEMA_INVALID")
    if errors:
        return {"ok": False, "errors": [dict(error) for error in errors]}
    expected, result = build_schematic_plan_state_handoff(chain, review, schemas)
    if expected is None:
        return result
    if _canonical_json(handoff) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_CONTENT_MISMATCH",
                    "",
                    "the supplied schematic-plan state handoff is not the exact deterministic projection of its validated blocks and human review record",
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
    """Load the committed ARCH-107 schemas plus this slice's two closed contracts."""

    schemas = dict(blocks_builder._load_schemas())
    schemas["review"] = load_json_object(REVIEW_SCHEMA_PATH)
    schemas["handoff"] = load_json_object(HANDOFF_SCHEMA_PATH)
    return schemas


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the fixed ARCH-097~107 documents, reviewed blocks, and review record."""

    blocks_builder._add_upstream_arguments(parser)
    parser.add_argument("blocks", type=Path, help="validated student schematic plan blocks JSON")
    parser.add_argument("review", type=Path, help="human schematic-plan review record JSON")


def _load_chain(arguments: argparse.Namespace) -> tuple[JsonObject, ...]:
    """Load the fixed ordered chain required by the reused ARCH-107 validator."""

    return tuple(load_json_object(getattr(arguments, key)) for key in _DOCUMENT_KEYS)


def main(argv: Sequence[str]) -> int:
    """Build or validate a state handoff from reviewed local schematic plan blocks."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build one handoff after human continuation")
    validate_parser = subparsers.add_parser("validate", help="validate one handoff against blocks and review")
    for command_parser in (build_parser, validate_parser):
        _add_arguments(command_parser)
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    validate_parser.add_argument("handoff", type=Path, help="student schematic-plan state handoff JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
        chain = _load_chain(arguments)
        review = load_json_object(arguments.review)
        if arguments.command == "validate":
            handoff = load_json_object(arguments.handoff)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        built, result = build_schematic_plan_state_handoff(chain, review, schemas)
        if built is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(built, arguments.output)
        return exit_code

    result = validate_schematic_plan_state_handoff(chain, review, handoff, schemas)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
