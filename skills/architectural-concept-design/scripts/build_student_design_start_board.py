"""Build one student-readable design start board from a confirmed digest.

This deterministic, local-only entry point accepts exactly one confirmed
ARCH-097 AssignmentBriefDigest and derives a two-layer start board: a machine
traceability ``source_binding`` (never default student-facing content) and a
``student_view`` that restates only confirmed literal requirements, unresolved
items, at most three clarification questions, and exactly one next action
(``program_and_area``). The board never reinterprets, extends, or repairs the
input, chooses no conflict winner, fills no missing value, and generates no
option, recommendation, area, dimension, floor count, entrance, circulation
scheme, massing, grid, height, environmental conclusion, or design scheme. It
is data only: no page, image, or plan. It opens no socket and starts
no subprocess, records no wall-clock time, never modifies the input digest,
and writes a destination only after full validation. Validate re-derives the expected board deterministically and requires exact byte equality.
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
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime

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

CATEGORY_ORDER: tuple[str, ...] = (
    "hard_constraint",
    "program",
    "site",
    "spatial_relationship",
    "circulation",
    "deliverable",
    "design_goal",
    "scoring_focus",
    "reference_only",
)
CONFIRMED_STATUSES: frozenset[str] = frozenset({"included", "duplicate_merged"})
UNRESOLVED_KIND_BY_STATUS: Mapping[str, str] = {
    "conflict": "conflict",
    "missing": "missing",
    "unreadable": "unreadable",
    "deferred_with_reason": "deferred_with_reason",
}
MISSING_LOCATOR = "no readable supplied source states this"
UNREADABLE_LOCATOR = "only an unreadable supplied source could state this"

NEXT_ACTION = {
    "action": "program_and_area",
    "description": (
        "Next, organize the functional spaces, their provided or unresolved areas, "
        "users, access levels, active and quiet needs, and adjacency or separation relationships."
    ),
}

BOUNDARIES: tuple[str, ...] = (
    "This board decides no area value, area total, or dimension.",
    "This board decides no floor count, storey height, or entrance position.",
    "This board decides no circulation scheme, massing, column grid, or structural system.",
    "This board decides no environmental conclusion.",
    "This board produces no design option, recommendation, or design scheme.",
)

SHA256_RE = re.compile(r"[0-9a-f]{64}")


class BoardError(TypedDict):
    """One deterministic rejection without a partial board."""

    code: str
    path: str
    message: str


class BoardResult(TypedDict):
    """The public result of building or validating one start board."""

    ok: bool
    errors: list[BoardError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> BoardError:
    return {"code": code, "path": path, "message": message}


def _registry(*schemas: JsonObject) -> Any:
    resources = []
    for schema in schemas:
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(dict(schema))))
    return Registry().with_resources(resources)


def _schema_errors(instance: object, schema: JsonObject, registry: Any, code: str) -> list[BoardError]:
    """Validate an instance against a committed Draft 2020-12 schema."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [_error("SCHEMA_INVALID", "", "schema is missing a string $id")]
    if Draft202012Validator is None or Registry is None or Resource is None:  # pragma: no cover - runtime guard.
        return [_error("SCHEMA_TOOLING_MISSING", "", "jsonschema and referencing are required")]
    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(dict(schema), registry=registry)
    except Exception as error:  # pragma: no cover - the committed schemas are checked separately.
        return [_error("SCHEMA_INVALID", "", str(error))]
    errors: list[BoardError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(map(str, item.absolute_path)), item.message)):
        pointer = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error(code, pointer, f"schema rule failed: {error.validator}"))
    return errors


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def compute_confirmed_digest_sha256(digest: JsonObject) -> str:
    """Return the SHA-256 of the canonical JSON plus newline bytes of the whole digest document."""

    return hashlib.sha256(_canonical_json(digest) + b"\n").hexdigest()


def _verify_confirmed_digest(
    digest: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    registry: Any,
) -> list[BoardError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched source digest."""

    errors = _schema_errors(digest, digest_schema, registry, "SOURCE_DIGEST_SCHEMA_INVALID")
    if errors:
        return errors

    confirmation = digest.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("SOURCE_DIGEST_NOT_CONFIRMED", "/human_confirmation", "the source digest must be confirmed before a start board can be built")]

    confirmation_errors: list[BoardError] = []
    if confirmation.get("action") != "CONFIRM_BRIEF_DIGEST":
        confirmation_errors.append(_error("SOURCE_DIGEST_CONFIRMATION_INVALID", "/human_confirmation/action", "confirmation action must be CONFIRM_BRIEF_DIGEST"))
    if not is_human_record_label(confirmation.get("confirmed_by")):
        confirmation_errors.append(_error("SOURCE_DIGEST_CONFIRMATION_INVALID", "/human_confirmation/confirmed_by", "confirmation must name a human, not an agent"))
    if not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        confirmation_errors.append(_error("SOURCE_DIGEST_CONFIRMATION_INVALID", "/human_confirmation/confirmed_at", "confirmation time must be a timezone-qualified RFC 3339 date-time"))
    bound_hash = confirmation.get("pending_digest_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
        confirmation_errors.append(_error("SOURCE_DIGEST_CONFIRMATION_INVALID", "/human_confirmation/pending_digest_sha256", "confirmation must carry a 64-character lowercase hex digest hash"))
    if confirmation_errors:
        return confirmation_errors

    pending_view = json.loads(json.dumps(digest))
    pending_view["human_confirmation"] = {"status": "pending"}
    if bound_hash != compute_confirmed_digest_sha256(pending_view):
        return [_error("SOURCE_DIGEST_HASH_MISMATCH", "/human_confirmation/pending_digest_sha256", "the recorded confirmation hash does not bind this digest's pre-confirmation document")]
    return []


def build_board(
    digest: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
) -> tuple[dict[str, Any] | None, BoardResult]:
    """Return one deterministic start board, or no board on any failed gate."""

    registry = _registry(intake_schema, digest_schema, board_schema)
    errors = _verify_confirmed_digest(digest, intake_schema, digest_schema, registry)
    if errors:
        return None, {"ok": False, "errors": errors}

    requirements: list[JsonObject] = list(digest.get("requirements", []))
    conflicts_by_id = {str(conflict["conflict_id"]): conflict for conflict in digest.get("conflicts", [])}

    grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORY_ORDER}
    unresolved: list[dict[str, Any]] = []
    for requirement in requirements:
        status = str(requirement["status"])
        if status in CONFIRMED_STATUSES:
            grouped[str(requirement["category"])].append(
                {
                    "requirement": requirement["concise_text"],
                    "source_locator": requirement["source_locator"],
                }
            )
            continue
        kind = UNRESOLVED_KIND_BY_STATUS.get(status)
        if kind is None:
            return None, {"ok": False, "errors": [_error("SOURCE_DIGEST_SCHEMA_INVALID", "/requirements", f"unrecognized requirement status: {status}")]}
        item: dict[str, Any] = {
            "kind": kind,
            "description": requirement["concise_text"],
            "source_locator": requirement["source_locator"],
        }
        if kind == "missing":
            item["source_locator"] = MISSING_LOCATOR
        elif kind == "unreadable":
            item["source_locator"] = UNREADABLE_LOCATOR
        elif kind == "conflict":
            conflict_ids = sorted(str(conflict_id) for conflict_id in requirement.get("conflict_ids", []))
            locators: list[str] = []
            seen_locators: set[str] = set()
            for conflict_id in conflict_ids:
                conflict = conflicts_by_id.get(conflict_id)
                if conflict is None:
                    return None, {"ok": False, "errors": [_error("SOURCE_DIGEST_SCHEMA_INVALID", "/requirements", "conflict requirement is not bound to a resolvable declared conflict")]}
                for locator in conflict["locators"]:
                    locator_text = str(locator)
                    if locator_text not in seen_locators:
                        seen_locators.add(locator_text)
                        locators.append(locator_text)
            item["conflicting_locators"] = locators
        elif kind == "deferred_with_reason":
            item["deferred_reason"] = requirement["deferred_reason"]
        unresolved.append(item)

    confirmation = digest["human_confirmation"]
    board: dict[str, Any] = {
        "schema_version": "1.0.0",
        "board_kind": "student_design_start_board",
        "source_binding": {
            "input_hash": digest["input_hash"],
            "confirmed_digest_sha256": compute_confirmed_digest_sha256(digest),
            "pending_digest_sha256": confirmation["pending_digest_sha256"],
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "brief_confirmed_ready_for_programming",
            "confirmed_requirements": [
                {"category": category, "items": grouped[category]} for category in CATEGORY_ORDER
            ],
            "unresolved_items": unresolved,
            "clarification_questions": [str(question) for question in digest.get("clarification_questions", [])],
            "next_action": dict(NEXT_ACTION),
            "boundaries": list(BOUNDARIES),
        },
    }

    board_errors = _schema_errors(board, board_schema, registry, "START_BOARD_SCHEMA_INVALID")
    if board_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": board_errors}
    return board, {"ok": True, "errors": []}


def validate_board(
    digest: JsonObject,
    board: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
) -> BoardResult:
    """Re-derive the source binding from the confirmed digest and compare it exactly."""

    registry = _registry(intake_schema, digest_schema, board_schema)
    errors = _verify_confirmed_digest(digest, intake_schema, digest_schema, registry)
    if errors:
        return {"ok": False, "errors": errors}

    board_errors = _schema_errors(board, board_schema, registry, "START_BOARD_SCHEMA_INVALID")
    if board_errors:
        return {"ok": False, "errors": board_errors}

    expected, build_result = build_board(digest, intake_schema, digest_schema, board_schema)
    if expected is None:  # pragma: no cover - the source digest has already passed the same gates.
        return build_result
    if _canonical_json(board) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "START_BOARD_CONTENT_MISMATCH",
                    "",
                    "the supplied board is not the exact deterministic projection of the confirmed source digest",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write the fully validated board as UTF-8, replacing only at the end."""

    encoded = _canonical_json(payload) + b"\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise
    return hashlib.sha256(encoded).hexdigest()


def _load_failure(code: str, message: str) -> BoardResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def main(argv: Sequence[str]) -> int:
    """Build a start board from a confirmed digest or validate one against it."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build one start board from a confirmed assignment brief digest")
    build_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    validate_parser = subparsers.add_parser("validate", help="validate one start board against its confirmed source digest")
    validate_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    validate_parser.add_argument("board", type=Path, help="student design start board JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema = load_json_object(INTAKE_SCHEMA_PATH)
        digest_schema = load_json_object(DIGEST_SCHEMA_PATH)
        board_schema = load_json_object(BOARD_SCHEMA_PATH)
        digest = load_json_object(arguments.digest)
        if arguments.command == "validate":
            board_document = load_json_object(arguments.board)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        board, result = build_board(digest, intake_schema, digest_schema, board_schema)
        if board is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        if arguments.output is None:
            print(json.dumps(board, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        try:
            output_hash = _write_atomically(arguments.output, board)
        except OSError as error:
            print(json.dumps(_load_failure("OUTPUT_WRITE_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 2
        print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0

    result = validate_board(digest, board_document, intake_schema, digest_schema, board_schema)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
