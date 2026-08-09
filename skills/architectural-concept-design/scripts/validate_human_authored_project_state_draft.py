"""Validate a human-authored project-state draft before ARCH-078 assembly.

This deterministic, local-only gate binds a human-authored ADR-0001 input
brief and ARCH-078 assembly draft to one valid ARCH-080 handoff. It validates
the declaration's canonical handoff digest, requires a caller attestation and
an exact resolution for every UNKNOWN or MISSING handoff todo, then checks the
brief and draft through ARCH-078 in memory. It emits a readiness receipt only;
it never writes a state package, creates design content, upgrades PROVIDED to
VERIFIED, chooses an option, opens a socket, starts a subprocess, or invokes a
runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import assemble_project_state as assembler
import build_normalized_brief_human_assembly_handoff as handoff_builder
import validate_state
from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
REFERENCES = Path(__file__).resolve().parents[1] / "references"
HANDOFF_SCHEMA_PATH = REFERENCES / "normalized-brief-human-assembly-handoff.schema.json"
DECLARATION_SCHEMA_PATH = REFERENCES / "human-authored-project-state-draft.schema.json"
ASSEMBLY_SCHEMA_PATH = REFERENCES / "project-state-assembly.schema.json"


class ReadinessError(TypedDict):
    """One machine-readable readiness error without an assembled state."""

    code: str
    path: str
    message: str


class ReadinessResult(TypedDict):
    """The public result for one authoring-gate validation."""

    ok: bool
    errors: list[ReadinessError]


class ReadinessReceipt(TypedDict):
    """The success-only, non-state receipt emitted by the command."""

    ok: bool
    authoring_state: str
    not_direct_assembly_input: bool
    handoff_sha256: str
    input_brief_sha256: str
    assembly_draft_sha256: str
    not_generated: list[str]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> ReadinessError:
    return {"code": code, "path": path, "message": message}


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(payload: JsonObject) -> str:
    """Return the SHA-256 of a canonical JSON document."""

    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _declaration_schema_errors(
    declaration: JsonObject,
    declaration_schema: JsonObject,
    handoff_schema: JsonObject,
) -> list[ReadinessError]:
    """Validate the declaration and resolve its one handoff field-name reference."""

    declaration_id = declaration_schema.get("$id")
    handoff_id = handoff_schema.get("$id")
    if not isinstance(declaration_id, str) or not isinstance(handoff_id, str):
        return [_error("AUTHORING_DECLARATION_SCHEMA_INVALID", "", "required schemas must declare string $id values")]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(dict(declaration_schema))
        Draft202012Validator.check_schema(dict(handoff_schema))
        registry = Registry().with_resources(
            (
                (declaration_id, Resource.from_contents(dict(declaration_schema))),
                (handoff_id, Resource.from_contents(dict(handoff_schema))),
            )
        )
        validator = Draft202012Validator(dict(declaration_schema), registry=registry, format_checker=checker)
    except Exception as error:  # pragma: no cover - committed schemas are independently tested.
        return [_error("AUTHORING_DECLARATION_SCHEMA_INVALID", "", str(error))]
    return [
        _error(
            "AUTHORING_DECLARATION_SCHEMA_INVALID",
            "/" + "/".join(str(token) for token in error.absolute_path),
            f"schema rule failed: {error.validator}",
        )
        for error in sorted(validator.iter_errors(declaration), key=lambda item: (list(item.absolute_path), item.message))
    ]


def _handoff_errors(result: handoff_builder.HandoffResult) -> list[ReadinessError]:
    return [_error(error["code"], error["path"], error["message"]) for error in result["errors"]]


def _assembly_errors(result: assembler.AssemblyResult) -> list[ReadinessError]:
    return [_error(error["code"], error["path"], error["message"]) for error in result["errors"]]


def _expected_todos(handoff: JsonObject) -> list[tuple[str, str]]:
    todos = handoff.get("human_authoring_todos")
    if not isinstance(todos, list):
        return []
    result: list[tuple[str, str]] = []
    for todo in todos:
        if isinstance(todo, Mapping):
            field = todo.get("field")
            status = todo.get("status")
            if isinstance(field, str) and isinstance(status, str):
                result.append((field, status))
    return result


def _actual_todos(declaration: JsonObject) -> list[tuple[str, str]]:
    resolutions = declaration.get("todo_resolutions")
    if not isinstance(resolutions, list):
        return []
    result: list[tuple[str, str]] = []
    for resolution in resolutions:
        if isinstance(resolution, Mapping):
            field = resolution.get("field")
            status = resolution.get("prior_status")
            if isinstance(field, str) and isinstance(status, str):
                result.append((field, status))
    return result


def validate_human_authored_project_state_draft(
    handoff: JsonObject,
    declaration: JsonObject,
    input_brief: JsonObject,
    assembly_draft: JsonObject,
    handoff_schema: JsonObject,
    declaration_schema: JsonObject,
    assembly_schema: JsonObject,
) -> tuple[ReadinessReceipt | None, ReadinessResult]:
    """Return a readiness receipt only when a human-authored pair clears every gate."""

    handoff_result = handoff_builder.validate_handoff(handoff, handoff_schema)
    if not handoff_result["ok"]:
        return None, {"ok": False, "errors": _handoff_errors(handoff_result)}

    declaration_errors = _declaration_schema_errors(declaration, declaration_schema, handoff_schema)
    if declaration_errors:
        return None, {"ok": False, "errors": declaration_errors}

    binding = declaration.get("handoff_binding")
    if not isinstance(binding, Mapping):  # Schema validation above makes this defensive branch unreachable.
        return None, {"ok": False, "errors": [_error("HANDOFF_BINDING_MISMATCH", "/handoff_binding", "handoff binding must be an object")]}
    actual_handoff_hash = canonical_sha256(handoff)
    if binding.get("handoff_sha256") != actual_handoff_hash:
        return None, {
            "ok": False,
            "errors": [_error("HANDOFF_BINDING_MISMATCH", "/handoff_binding/handoff_sha256", "declaration digest does not match the validated handoff")],
        }
    if binding.get("handoff_kind") != handoff.get("handoff_kind"):
        return None, {
            "ok": False,
            "errors": [_error("HANDOFF_BINDING_MISMATCH", "/handoff_binding/handoff_kind", "declaration handoff kind does not match the validated handoff")],
        }

    if _actual_todos(declaration) != _expected_todos(handoff):
        return None, {
            "ok": False,
            "errors": [_error("AUTHORING_TODO_RESOLUTIONS_MISMATCH", "/todo_resolutions", "resolutions must cover exactly the handoff UNKNOWN and MISSING todos in order with matching prior statuses")],
        }

    assembled_state, assembly_result = assembler.assemble_project_state(input_brief, assembly_draft, assembly_schema)
    if assembled_state is None:
        return None, {"ok": False, "errors": _assembly_errors(assembly_result)}

    receipt: ReadinessReceipt = {
        "ok": True,
        "authoring_state": "READY_FOR_ARCH_078_ASSEMBLY",
        "not_direct_assembly_input": True,
        "handoff_sha256": actual_handoff_hash,
        "input_brief_sha256": validate_state.compute_input_hash(input_brief),
        "assembly_draft_sha256": canonical_sha256(assembly_draft),
        "not_generated": [
            "state_package",
            "decision",
            "SRC",
            "Evidence",
            "CARD",
            "Candidate",
            "VERIFIED",
            "massing",
            "plan",
            "media",
            "PPTX",
        ],
    }
    return receipt, {"ok": True, "errors": []}


def _load_failure(code: str, message: str) -> ReadinessResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def main(argv: Sequence[str]) -> int:
    """Validate one local human-authored handoff/brief/draft quartet."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path, help="ARCH-080 human assembly handoff JSON")
    parser.add_argument("declaration", type=Path, help="human-authored project-state draft declaration JSON")
    parser.add_argument("input_brief", type=Path, help="human-authored ADR-0001 input brief JSON")
    parser.add_argument("assembly_draft", type=Path, help="human-authored ARCH-078 assembly draft JSON")
    arguments = parser.parse_args(argv[1:])
    try:
        handoff = load_json_object(arguments.handoff)
        declaration = load_json_object(arguments.declaration)
        input_brief = load_json_object(arguments.input_brief)
        assembly_draft = load_json_object(arguments.assembly_draft)
        handoff_schema = load_json_object(HANDOFF_SCHEMA_PATH)
        declaration_schema = load_json_object(DECLARATION_SCHEMA_PATH)
        assembly_schema = load_json_object(ASSEMBLY_SCHEMA_PATH)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    receipt, result = validate_human_authored_project_state_draft(
        handoff,
        declaration,
        input_brief,
        assembly_draft,
        handoff_schema,
        declaration_schema,
        assembly_schema,
    )
    if receipt is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
