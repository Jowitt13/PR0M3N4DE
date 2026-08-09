"""Build a human-mediated project state assembly handoff from one ledger.

This deterministic, local-only entry point re-validates an ARCH-079 normalized
brief ledger against its committed output Schema, re-verifies the ledger input
hash against the canonical raw input, propagates every PROVIDED / UNKNOWN /
MISSING status unchanged, and emits a handoff that binds to the ledger SHA-256,
names explicit human authoring todos for every UNKNOWN and MISSING field, and
lists the chapters only a human may author before any ARCH-078 assembly. It
authors no source, evidence, constraint, relation, space, hypothesis, option,
criterion, dependency, deliverable, or decision; registers no SRC, Evidence,
CARD, Candidate, or VERIFIED; opens no socket; starts no subprocess; and writes
a destination only after full validation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    Registry = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]

JsonObject = Mapping[str, Any]
FieldStatus = Literal["PROVIDED", "UNKNOWN", "MISSING"]

REFERENCES = Path(__file__).resolve().parents[1] / "references"
LEDGER_SCHEMA_PATH = REFERENCES / "normalized-brief-ledger.output.schema.json"
HANDOFF_SCHEMA_PATH = REFERENCES / "normalized-brief-human-assembly-handoff.schema.json"

FIELDS: tuple[str, ...] = (
    "project_name",
    "project_location",
    "site_boundary_or_redline",
    "north_orientation",
    "road_edges_and_access",
    "building_type",
    "target_area_or_scale",
    "users",
    "required_spaces",
    "budget_range",
    "target_opening_date",
    "design_goals",
    "known_regulations_or_assumptions",
)
HANDOFF_KIND = "HUMAN_MEDIATED_PROJECT_STATE_ASSEMBLY_HANDOFF"
AUTHORING_STATE = "AWAITING_HUMAN_AUTHORING"
HUMAN_AUTHORED_CHAPTERS: list[str] = [
    "sources",
    "evidence",
    "constraints",
    "relations",
    "program_spaces",
    "hypotheses",
    "options",
    "criteria",
    "dependencies",
    "deliverables",
]
NOT_GENERATED: list[str] = [
    "SRC",
    "Evidence",
    "CARD",
    "Candidate",
    "VERIFIED",
    "massing",
    "plan",
    "media",
    "PPTX",
]


class HandoffError(TypedDict):
    """One deterministic rejection without a partial handoff."""

    code: str
    path: str
    message: str


class HandoffResult(TypedDict):
    """The public result of building one human assembly handoff."""

    ok: bool
    errors: list[HandoffError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> HandoffError:
    return {"code": code, "path": path, "message": message}


def _schema_errors(instance: object, schema: JsonObject, code: str) -> list[HandoffError]:
    """Validate an instance against a committed Draft 2020-12 schema."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [_error("SCHEMA_INVALID", "", "schema is missing a string $id")]
    if Draft202012Validator is None or Registry is None or Resource is None:  # pragma: no cover - runtime guard.
        return [_error("SCHEMA_TOOLING_MISSING", "", "jsonschema and referencing are required")]
    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(
            dict(schema),
            registry=Registry().with_resource(schema_id, Resource.from_contents(dict(schema))),
        )
    except Exception as error:  # pragma: no cover - the committed Schema is checked separately.
        return [_error("SCHEMA_INVALID", "", str(error))]
    errors: list[HandoffError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(item.absolute_path), item.message)):
        pointer = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error(code, pointer, f"schema rule failed: {error.validator}"))
    return errors


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def ledger_sha256(ledger: JsonObject) -> str:
    """Return the SHA-256 of the canonical serialization of one accepted ledger."""

    return hashlib.sha256(_canonical_json(ledger)).hexdigest()


def compute_input_hash(raw_input: JsonObject) -> str:
    """Return the SHA-256 of the canonical raw human input carried by a ledger."""

    return hashlib.sha256(_canonical_json(raw_input)).hexdigest()


def _human_todo(field: str, status: FieldStatus) -> str:
    if status == "UNKNOWN":
        return f"human must author the {field} value into the ADR-0001 input brief or confirm it remains unknown"
    return f"human must author the missing {field} value into the ADR-0001 input brief or confirm it remains absent"


def validate_handoff(handoff: JsonObject, handoff_schema: JsonObject) -> HandoffResult:
    """Validate one handoff document structurally and semantically, fail-closed.

    The schema gate runs first and rejects unknown keys, injected chapter
    content, and non-field summary/todo names. The semantic gates then require
    the three summary lists to be duplicate-free with a union of exactly the
    thirteen known fields, each field classified exactly like
    ``fields[field].status``, counts equal to the matching list lengths, and the
    human authoring todos to cover exactly the UNKNOWN and MISSING fields in
    ``FIELDS`` order with matching statuses.
    """

    schema_errors = _schema_errors(handoff, handoff_schema, "HANDOFF_SCHEMA_INVALID")
    if schema_errors:
        return {"ok": False, "errors": schema_errors}

    fields = handoff.get("fields")
    if not isinstance(fields, Mapping) or any(name not in fields for name in FIELDS):
        return {"ok": False, "errors": [_error("HANDOFF_FIELDS_INCOMPLETE", "/fields", "handoff must carry all thirteen known fields")]}

    summary = handoff.get("status_summary")
    if not isinstance(summary, Mapping):
        return {"ok": False, "errors": [_error("HANDOFF_SUMMARY_INVALID", "/status_summary", "status summary must be an object")]}
    provided = summary.get("provided")
    unknown = summary.get("unknown")
    missing = summary.get("missing")
    if not all(isinstance(item, list) for item in (provided, unknown, missing)):
        return {"ok": False, "errors": [_error("HANDOFF_SUMMARY_INVALID", "/status_summary", "provided, unknown, and missing must be lists")]}

    errors: list[HandoffError] = []
    all_names = [*provided, *unknown, *missing]
    if len({str(name) for name in all_names}) != len(all_names):
        errors.append(_error("HANDOFF_SUMMARY_DUPLICATE_FIELD", "/status_summary", "a field name appears in more than one summary list"))
    if set(str(name) for name in all_names) != set(FIELDS):
        errors.append(_error("HANDOFF_SUMMARY_FIELD_SET_MISMATCH", "/status_summary", "summary lists must cover exactly the thirteen known fields"))

    expected_status_by_list = {"provided": "PROVIDED", "unknown": "UNKNOWN", "missing": "MISSING"}
    for name in FIELDS:
        expected = fields[name]["status"]
        for list_name, names in (("provided", provided), ("unknown", unknown), ("missing", missing)):
            listed = name in names
            if (expected_status_by_list[list_name] == expected and not listed) or (expected_status_by_list[list_name] != expected and listed):
                errors.append(_error("HANDOFF_SUMMARY_STATUS_MISMATCH", f"/status_summary/{list_name}", f"field {name} is classified {expected} but listed under {list_name}"))

    counts = summary.get("counts")
    if not isinstance(counts, Mapping):
        errors.append(_error("HANDOFF_COUNTS_MISMATCH", "/status_summary/counts", "counts must be an object"))
    else:
        for list_name, names in (("provided", provided), ("unknown", unknown), ("missing", missing)):
            if counts.get(list_name) != len(names):
                errors.append(_error("HANDOFF_COUNTS_MISMATCH", f"/status_summary/counts/{list_name}", f"count {counts.get(list_name)!r} does not match the {list_name} list length {len(names)}"))

    todos = handoff.get("human_authoring_todos")
    if not isinstance(todos, list):
        return {"ok": False, "errors": [_error("HANDOFF_TODOS_MISMATCH", "/human_authoring_todos", "human authoring todos must be a list")]}
    expected_todo_fields = [name for name in FIELDS if fields[name]["status"] in ("UNKNOWN", "MISSING")]
    actual_todo_fields = [todo.get("field") for todo in todos if isinstance(todo, Mapping)]
    if actual_todo_fields != expected_todo_fields:
        errors.append(_error("HANDOFF_TODOS_MISMATCH", "/human_authoring_todos", "todos must cover exactly the UNKNOWN and MISSING fields in FIELDS order"))
    for todo in todos:
        if isinstance(todo, Mapping) and todo.get("field") in fields and todo.get("status") != fields[todo["field"]]["status"]:
            errors.append(_error("HANDOFF_TODO_STATUS_MISMATCH", "/human_authoring_todos", f"todo status for {todo['field']} does not match its field status"))

    if errors:
        return {"ok": False, "errors": sorted(errors, key=lambda item: (item["path"], item["code"], item["message"]))}
    return {"ok": True, "errors": []}


def build_handoff(
    ledger: JsonObject,
    ledger_schema: JsonObject,
    handoff_schema: JsonObject,
) -> tuple[dict[str, Any] | None, HandoffResult]:
    """Return one conforming handoff, or no handoff on any failed gate."""

    schema_errors = _schema_errors(ledger, ledger_schema, "LEDGER_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    ledger_fields = ledger.get("fields")
    if not isinstance(ledger_fields, Mapping) or any(name not in ledger_fields for name in FIELDS):
        return None, {"ok": False, "errors": [_error("LEDGER_FIELDS_INCOMPLETE", "/fields", "ledger must carry all thirteen known fields")]}

    raw_input = ledger.get("raw_input")
    if not isinstance(raw_input, Mapping):
        return None, {"ok": False, "errors": [_error("LEDGER_RAW_INPUT_MISSING", "/raw_input", "ledger must carry the raw input object")]}

    expected_hash = ledger.get("input_hash")
    actual_hash = compute_input_hash(raw_input)
    if not isinstance(expected_hash, str) or expected_hash != actual_hash:
        return None, {
            "ok": False,
            "errors": [_error("LEDGER_INPUT_HASH_MISMATCH", "/input_hash", f"ledger input hash {expected_hash!r} does not match the canonical raw input {actual_hash}")],
        }

    fields: dict[str, dict[str, Any]] = {name: copy.deepcopy(dict(ledger_fields[name])) for name in FIELDS}
    provided = [name for name in FIELDS if fields[name]["status"] == "PROVIDED"]
    unknown = [name for name in FIELDS if fields[name]["status"] == "UNKNOWN"]
    missing = [name for name in FIELDS if fields[name]["status"] == "MISSING"]
    todos = [
        {"field": name, "status": fields[name]["status"], "todo": _human_todo(name, fields[name]["status"])}
        for name in FIELDS
        if fields[name]["status"] in ("UNKNOWN", "MISSING")
    ]

    handoff: dict[str, Any] = {
        "schema_version": "1.0.0",
        "handoff_kind": HANDOFF_KIND,
        "authoring_state": AUTHORING_STATE,
        "not_direct_assembly_input": True,
        "ledger_binding": {
            "ledger_schema_version": ledger.get("schema_version"),
            "ledger_kind": ledger.get("ledger_kind"),
            "input_hash": expected_hash,
            "ledger_sha256": ledger_sha256(ledger),
        },
        "fields": fields,
        "status_summary": {
            "counts": {"provided": len(provided), "unknown": len(unknown), "missing": len(missing)},
            "provided": provided,
            "unknown": unknown,
            "missing": missing,
        },
        "human_authoring_todos": todos,
        "human_authored_chapters": list(HUMAN_AUTHORED_CHAPTERS),
        "not_generated": list(NOT_GENERATED),
    }

    handoff_errors = validate_handoff(handoff, handoff_schema)
    if not handoff_errors["ok"]:  # pragma: no cover - defends the output contract against future drift.
        return None, handoff_errors
    return handoff, {"ok": True, "errors": []}


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write the fully validated handoff as UTF-8, replacing only at the end."""

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


def _load_failure(code: str, message: str) -> HandoffResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def main(argv: Sequence[str]) -> int:
    """Emit or atomically write one conforming human assembly handoff."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="ARCH-079 normalized brief ledger JSON")
    parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    arguments = parser.parse_args(argv[1:])
    try:
        ledger = load_json_object(arguments.ledger)
        ledger_schema = load_json_object(LEDGER_SCHEMA_PATH)
        handoff_schema = load_json_object(HANDOFF_SCHEMA_PATH)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    handoff, result = build_handoff(ledger, ledger_schema, handoff_schema)
    if handoff is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    if arguments.output is None:
        print(json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    try:
        output_hash = _write_atomically(arguments.output, handoff)
    except OSError as error:
        print(json.dumps(_load_failure("OUTPUT_WRITE_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
