"""Normalize a human project brief into a status-preserving ledger.

This deterministic, local-only entry point accepts a loose, human-authored
project brief and reports every known field as PROVIDED, UNKNOWN, or MISSING.
It preserves the raw human input, offers normalized values a human can author
into an existing ADR-0001 input brief, and fails closed on unknown keys, type
errors, empty strings masquerading as UNKNOWN, illegal status objects, and a
missing required project name. It never infers a missing value into a real
fact and never generates evidence, sources, hypotheses, options, decisions,
massing, plans, SRC, Evidence, CARD, or VERIFIED content. It opens no socket
and starts no subprocess, and writes a destination only after full validation.
"""

from __future__ import annotations

import argparse
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
INPUT_SCHEMA_PATH = REFERENCES / "normalized-brief-ledger.input.schema.json"
OUTPUT_SCHEMA_PATH = REFERENCES / "normalized-brief-ledger.output.schema.json"

TEXT_FIELDS: tuple[str, ...] = (
    "project_name",
    "project_location",
    "site_boundary_or_redline",
    "north_orientation",
    "road_edges_and_access",
    "building_type",
    "target_area_or_scale",
    "users",
    "budget_range",
    "target_opening_date",
    "known_regulations_or_assumptions",
)
LIST_FIELDS: tuple[str, ...] = ("required_spaces", "design_goals")
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
REQUIRED_PROVIDED_FIELDS: frozenset[str] = frozenset({"project_name"})
UNKNOWN_LITERAL = "UNKNOWN"


class NormalizationError(TypedDict):
    """One deterministic rejection without a partial ledger."""

    code: str
    path: str
    message: str


class FieldEntry(TypedDict):
    """The normalized status of one known brief field."""

    status: FieldStatus
    normalized_value: str | list[str] | None
    raw_present: bool


class NormalizationResult(TypedDict):
    """The public result of normalizing one human brief."""

    ok: bool
    errors: list[NormalizationError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> NormalizationError:
    return {"code": code, "path": path, "message": message}


def _schema_errors(instance: object, schema: JsonObject, code: str) -> list[NormalizationError]:
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
    errors: list[NormalizationError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(item.absolute_path), item.message)):
        pointer = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error(code, pointer, f"schema rule failed: {error.validator}"))
    return errors


def _normalize_text(value: str) -> str:
    return value.strip()


def _normalize_list(value: Sequence[Any]) -> list[str]:
    return [str(item).strip() for item in value]


def _resolve_field(name: str, value: Any) -> tuple[FieldEntry, list[NormalizationError]]:
    """Resolve one present field into its status entry, failing closed on abuse."""

    path = f"/{name}"
    is_list = name in LIST_FIELDS

    # Explicit status object form.
    if isinstance(value, Mapping):
        status = value.get("status")
        if status == "UNKNOWN":
            return {"status": "UNKNOWN", "normalized_value": None, "raw_present": True}, []
        if status == "PROVIDED":
            inner = value.get("value")
            if is_list:
                if isinstance(inner, list) and inner and all(isinstance(item, str) and item.strip() for item in inner):
                    return {"status": "PROVIDED", "normalized_value": _normalize_list(inner), "raw_present": True}, []
                if inner is not None and not isinstance(inner, list):
                    return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
                        _error("TYPE_ERROR", path, "PROVIDED list field requires a list value, not text")
                    ]
                return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
                    _error("PROVIDED_VALUE_INVALID", path, "PROVIDED list field requires a non-empty list of non-empty strings")
                ]
            if isinstance(inner, str) and inner.strip():
                return {"status": "PROVIDED", "normalized_value": _normalize_text(inner), "raw_present": True}, []
            if inner is not None and not isinstance(inner, str):
                return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
                    _error("TYPE_ERROR", path, "PROVIDED text field requires a string value, not a list")
                ]
            return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
                _error("PROVIDED_VALUE_INVALID", path, "PROVIDED text field requires a non-empty string")
            ]
        return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
            _error("ILLEGAL_STATUS", path, "status must be PROVIDED or UNKNOWN; MISSING is derived from absence")
        ]

    # Explicit UNKNOWN literal.
    if value == UNKNOWN_LITERAL:
        return {"status": "UNKNOWN", "normalized_value": None, "raw_present": True}, []

    # Provided list.
    if is_list:
        if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
            return {"status": "PROVIDED", "normalized_value": _normalize_list(value), "raw_present": True}, []
        return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
            _error("TYPE_ERROR", path, "expected a non-empty list of non-empty strings or the UNKNOWN literal")
        ]

    # Provided text.
    if isinstance(value, str):
        if not value.strip():
            return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
                _error("EMPTY_STRING_NOT_ALLOWED", path, "an empty or whitespace-only string cannot masquerade as UNKNOWN")
            ]
        return {"status": "PROVIDED", "normalized_value": _normalize_text(value), "raw_present": True}, []

    return {"status": "MISSING", "normalized_value": None, "raw_present": True}, [
        _error("TYPE_ERROR", path, "expected a non-empty string, the UNKNOWN literal, or an explicit status object")
    ]


def normalize_brief(
    brief: JsonObject,
    input_schema: JsonObject,
    output_schema: JsonObject,
) -> tuple[dict[str, Any] | None, NormalizationResult]:
    """Return one status-preserving ledger, or no ledger on any failed gate."""

    schema_errors = _schema_errors(brief, input_schema, "BRIEF_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    fields: dict[str, FieldEntry] = {}
    errors: list[NormalizationError] = []
    for name in FIELDS:
        if name not in brief:
            fields[name] = {"status": "MISSING", "normalized_value": None, "raw_present": False}
            continue
        entry, field_errors = _resolve_field(name, brief[name])
        fields[name] = entry
        errors.extend(field_errors)

    for name in REQUIRED_PROVIDED_FIELDS:
        if fields[name]["status"] != "PROVIDED":
            errors.append(_error("PROJECT_NAME_REQUIRED", f"/{name}", f"{name} must be PROVIDED with a real value"))

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    provided = [name for name in FIELDS if fields[name]["status"] == "PROVIDED"]
    unknown = [name for name in FIELDS if fields[name]["status"] == "UNKNOWN"]
    missing = [name for name in FIELDS if fields[name]["status"] == "MISSING"]
    ledger: dict[str, Any] = {
        "schema_version": "1.0.0",
        "ledger_kind": "normalized_brief_ledger",
        "input_hash": compute_input_hash(brief),
        "raw_input": json.loads(json.dumps(brief)),
        "fields": {name: dict(fields[name]) for name in FIELDS},
        "summary": {
            "counts": {"provided": len(provided), "unknown": len(unknown), "missing": len(missing)},
            "provided": provided,
            "unknown": unknown,
            "missing": missing,
        },
        "downstream": {
            "consumable_by": "existing ADR-0001 input brief authoring for the project-state assembly entry point",
            "mapping_note": "PROVIDED fields become candidate facts a human authors as sourced evidence; UNKNOWN and MISSING fields become the missing-information register; concept direction stays a human decision. This ledger authors no evidence, source, or decision itself.",
        },
        "not_generated": [
            "hypotheses",
            "options",
            "decisions",
            "massing",
            "plan",
            "SRC",
            "Evidence",
            "CARD",
            "VERIFIED",
        ],
    }

    ledger_errors = _schema_errors(ledger, output_schema, "LEDGER_SCHEMA_INVALID")
    if ledger_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": ledger_errors}
    return ledger, {"ok": True, "errors": []}


def compute_input_hash(brief: JsonObject) -> str:
    """Return the SHA-256 of the canonical raw human brief."""

    return hashlib.sha256(_canonical_json(brief)).hexdigest()


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write the fully validated ledger as UTF-8, replacing only at the end."""

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


def _load_failure(code: str, message: str) -> NormalizationResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def main(argv: Sequence[str]) -> int:
    """Emit or atomically write one normalized brief ledger."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path, help="loose human-authored project brief JSON")
    parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")
    arguments = parser.parse_args(argv[1:])
    try:
        brief = load_json_object(arguments.brief)
        input_schema = load_json_object(INPUT_SCHEMA_PATH)
        output_schema = load_json_object(OUTPUT_SCHEMA_PATH)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("BRIEF_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    ledger, result = normalize_brief(brief, input_schema, output_schema)
    if ledger is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    if arguments.output is None:
        print(json.dumps(ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    try:
        output_hash = _write_atomically(arguments.output, ledger)
    except OSError as error:
        print(json.dumps(_load_failure("OUTPUT_WRITE_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
