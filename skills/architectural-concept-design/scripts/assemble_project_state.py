"""Assemble one validated state package from an input brief and authored draft.

This deterministic, local-only helper reuses the existing ADR-0001 state
validator and output Schema.  It copies the validated brief ledger and only the
caller-authored hypotheses, options, criteria, dependencies, and deliverables.
It never invents content, assigns a human decision, opens a socket, starts a
subprocess, invokes a runtime, or emits a partial output on failure.
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
from typing import Any, TypedDict

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import validate_state
from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
ASSEMBLY_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "project-state-assembly.schema.json"


class AssemblyError(TypedDict):
    """One deterministic assembly error without a partial state package."""

    code: str
    path: str
    message: str


class AssemblyResult(TypedDict):
    """The public result of assembling one input/draft pair."""

    ok: bool
    errors: list[AssemblyError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> AssemblyError:
    return {"code": code, "path": path, "message": message}


def _schema_errors(instance: object, schema: JsonObject) -> list[AssemblyError]:
    """Validate the compact assembly draft contract with strict RFC-3339 time."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [_error("ASSEMBLY_SCHEMA_INVALID", "", "assembly schema is missing a string $id")]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(
            dict(schema),
            registry=Registry().with_resource(schema_id, Resource.from_contents(dict(schema))),
            format_checker=checker,
        )
    except Exception as error:  # pragma: no cover - the committed Schema is checked separately.
        return [_error("ASSEMBLY_SCHEMA_INVALID", "", str(error))]
    errors: list[AssemblyError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error("ASSEMBLY_DRAFT_SCHEMA_INVALID", path, f"schema rule failed: {error.validator}"))
    return errors


def _copy_if_present(source: JsonObject, key: str) -> Any:
    """Deep-copy a known optional input collection without manufacturing it."""

    return copy.deepcopy(source[key]) if key in source else None


def _input_program_spaces(input_payload: JsonObject) -> Any:
    """Return only present program spaces; final validation owns their structure."""

    program = input_payload.get("program")
    if isinstance(program, Mapping) and "spaces" in program:
        return copy.deepcopy(program["spaces"])
    return None


def _state_from(input_payload: JsonObject, draft_payload: JsonObject) -> dict[str, Any]:
    """Construct an output-shaped candidate without changing either caller input."""

    project = input_payload.get("project")
    project_id = project.get("id") if isinstance(project, Mapping) else None
    state: dict[str, Any] = {
        "schema_version": "1.0.0",
        "skill_version": draft_payload.get("skill_version"),
        "project_id": project_id,
        "state": {
            "input_hash": validate_state.compute_input_hash(input_payload),
            "generated_at": draft_payload.get("generated_at"),
        },
        "sources": copy.deepcopy(input_payload.get("sources", [])),
        "dependencies": copy.deepcopy(draft_payload.get("dependencies", [])),
        "evidence": copy.deepcopy(input_payload.get("evidence", [])),
        "hypotheses": copy.deepcopy(draft_payload.get("hypotheses", [])),
        "options": copy.deepcopy(draft_payload.get("options", [])),
        "criteria": copy.deepcopy(draft_payload.get("criteria", [])),
        "decisions": [],
        "deliverables": copy.deepcopy(draft_payload.get("deliverables", [])),
    }
    for key in ("constraints", "relations"):
        value = _copy_if_present(input_payload, key)
        if value is not None:
            state[key] = value
    spaces = _input_program_spaces(input_payload)
    if spaces is not None:
        state["spaces"] = spaces
    return state


def _state_errors(result: validate_state.ValidationResult) -> list[AssemblyError]:
    """Preserve the existing validator's stable error codes for callers."""

    return [
        _error(record["code"], record["path"], record["message"])
        for record in result["errors"]
    ]


def assemble_project_state(
    input_payload: JsonObject,
    draft_payload: JsonObject,
    assembly_schema: JsonObject,
) -> tuple[dict[str, Any] | None, AssemblyResult]:
    """Return one existing-schema state package or no output on any failed gate."""

    errors = _schema_errors(draft_payload, assembly_schema)
    if errors:
        return None, {"ok": False, "errors": errors}

    try:
        output_payload = _state_from(input_payload, draft_payload)
        state_result, _ = validate_state.validate_state(input_payload, output_payload)
    except (TypeError, ValueError) as error:
        return None, {"ok": False, "errors": [_error("ASSEMBLY_RUNTIME_ERROR", "", str(error))]}
    if not state_result["ok"]:
        return None, {"ok": False, "errors": _state_errors(state_result)}
    return output_payload, {"ok": True, "errors": []}


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write a fully validated state package as UTF-8, replacing only at the end."""

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


def _load_failure(code: str, message: str) -> AssemblyResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def main(argv: Sequence[str]) -> int:
    """Emit or atomically write one conforming state package."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="existing input.schema.json brief")
    parser.add_argument("draft", type=Path, help="project-state assembly draft")
    parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    arguments = parser.parse_args(argv[1:])
    try:
        input_payload = load_json_object(arguments.input)
        draft_payload = load_json_object(arguments.draft)
        assembly_schema = load_json_object(ASSEMBLY_SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    output_payload, result = assemble_project_state(input_payload, draft_payload, assembly_schema)
    if output_payload is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    if arguments.output is None:
        print(json.dumps(output_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    try:
        output_hash = _write_atomically(arguments.output, output_payload)
    except OSError as error:
        print(json.dumps(_load_failure("OUTPUT_WRITE_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
