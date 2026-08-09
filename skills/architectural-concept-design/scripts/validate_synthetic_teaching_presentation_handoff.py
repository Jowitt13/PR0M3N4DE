"""Validate the isolated ADR-0008 synthetic teaching presentation handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict, cast

from jsonschema import Draft202012Validator, FormatChecker

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_ROOT / "references" / "synthetic-teaching-presentation-handoff.schema.json"

JsonObject = dict[str, Any]
TEACHING_LABELS = (
    "HUMAN_AUTHORIZED_ASSUMPTION",
    "DEMO_ONLY",
    "NOT_A_REAL_SITE_OR_BUILDABILITY_CONCLUSION",
)
FORBIDDEN_IDENTIFIER_RE = re.compile(r"(?:^|[^A-Za-z0-9-])(?:RC|RCR|SRC|E)-[0-9]{3,}(?:$|[^A-Za-z0-9-])")
FORBIDDEN_TEXT_RE = re.compile(r"https?://|\bVERIFIED\b|source[_ -]?locator|media[_ -]?authori[sz]ation", re.IGNORECASE)


class HandoffError(TypedDict):
    code: str
    path: str
    message: str


class HandoffValidationResult(TypedDict):
    ok: bool
    outcome: str
    errors: list[HandoffError]


def load_json_object(path: Path) -> JsonObject:
    """Load a finite JSON object without accepting JSON constants."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return cast(JsonObject, payload)


def canonical_sha256(payload: JsonObject) -> str:
    """Return the canonical content SHA-256 used by local handoff receipts."""

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pointer(path: Sequence[object]) -> str:
    return "/" + "/".join(str(item).replace("~", "~0").replace("/", "~1") for item in path)


def _error(errors: list[HandoffError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _schema_errors(handoff: JsonObject, schema: JsonObject) -> list[HandoffError]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        {"code": "SYNTHETIC_HANDOFF_SCHEMA_INVALID", "path": _pointer(error.absolute_path), "message": error.message}
        for error in sorted(validator.iter_errors(handoff), key=lambda item: (list(item.absolute_path), item.message))
    ]


def _walk(value: object, path: str, errors: list[HandoffError]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _error(errors, "SYNTHETIC_HANDOFF_FORBIDDEN_CONTENT", path, "handoff keys must be strings")
                continue
            key_path = f"{path}/{key}" if path else f"/{key}"
            if FORBIDDEN_TEXT_RE.search(key) or FORBIDDEN_IDENTIFIER_RE.search(key):
                _error(errors, "SYNTHETIC_HANDOFF_FORBIDDEN_CONTENT", key_path, "synthetic handoff may not carry source, media, verification, or runtime-candidate content")
            _walk(child, key_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}/{index}", errors)
    elif isinstance(value, str):
        if FORBIDDEN_TEXT_RE.search(value) or FORBIDDEN_IDENTIFIER_RE.search(value):
            _error(errors, "SYNTHETIC_HANDOFF_FORBIDDEN_CONTENT", path, "synthetic handoff may not carry source, media, verification, or runtime-candidate content")


def validate_synthetic_teaching_presentation_handoff(
    handoff: JsonObject,
    schema: JsonObject,
) -> HandoffValidationResult:
    """Validate schema and ADR-0008 semantic boundaries without I/O or network."""

    errors = _schema_errors(handoff, schema)
    if errors:
        return {"ok": False, "outcome": "SYNTHETIC_HANDOFF_INVALID", "errors": errors}

    labels = _strings(handoff.get("teaching_labels"))
    if tuple(labels) != TEACHING_LABELS:
        _error(errors, "SYNTHETIC_TEACHING_LABELS_INVALID", "/teaching_labels", "teaching labels must be complete and in the locked order")
    if handoff.get("not_real_project_validation") is not True:
        _error(errors, "SYNTHETIC_REAL_PROJECT_MARKER_INVALID", "/not_real_project_validation", "synthetic handoff must explicitly reject real-project validation")

    assumptions = _mapping(handoff.get("human_authorized_assumptions"))
    if assumptions is None or tuple(_strings(assumptions.get("classification"))) != TEACHING_LABELS:
        _error(errors, "SYNTHETIC_ASSUMPTION_LABELS_INVALID", "/human_authorized_assumptions/classification", "human-authorized assumption labels must match the top-level teaching labels")
    unresolved = assumptions.get("unresolved_inputs") if assumptions else None
    unresolved_fields = [entry.get("field") for entry in unresolved if isinstance(entry, Mapping) and isinstance(entry.get("field"), str)] if isinstance(unresolved, list) else []
    if len(unresolved_fields) != len(set(unresolved_fields)):
        _error(errors, "SYNTHETIC_UNRESOLVED_INPUT_DUPLICATE", "/human_authorized_assumptions/unresolved_inputs", "unresolved input fields must not repeat")

    decision = _mapping(handoff.get("human_design_decision"))
    if decision is None or decision.get("recorded_in_validated_state") is not True:
        _error(errors, "SYNTHETIC_HUMAN_DECISION_REQUIRED", "/human_design_decision", "handoff requires an explicit human decision recorded in validated state")

    content = _mapping(handoff.get("teaching_content"))
    if content is not None:
        program = content.get("program_spaces")
        program_ids = [item.get("id") for item in program if isinstance(item, Mapping) and isinstance(item.get("id"), str)] if isinstance(program, list) else []
        expected_program_ids = handoff.get("program_space_ids")
        if program_ids != expected_program_ids or len(program_ids) != len(set(program_ids)):
            _error(errors, "SYNTHETIC_TEACHING_PROGRAM_BINDING_INVALID", "/teaching_content/program_spaces", "teaching program content must exactly preserve the ordered synthetic program-space ids")

        options = content.get("concept_options")
        option_ids = [item.get("id") for item in options if isinstance(item, Mapping) and isinstance(item.get("id"), str)] if isinstance(options, list) else []
        selected = _mapping(content.get("selected_option"))
        selected_identifier = selected.get("id") if selected else None
        if len(option_ids) != len(set(option_ids)) or selected_identifier not in option_ids:
            _error(errors, "SYNTHETIC_TEACHING_OPTION_BINDING_INVALID", "/teaching_content", "teaching options must be unique and include the selected option")
        if decision is not None and selected_identifier != decision.get("chosen_option_id"):
            _error(errors, "SYNTHETIC_TEACHING_SELECTED_OPTION_MISMATCH", "/teaching_content/selected_option/id", "teaching content must preserve the explicit human-selected option")

        hypotheses = content.get("hypotheses")
        hypothesis_ids = [item.get("id") for item in hypotheses if isinstance(item, Mapping) and isinstance(item.get("id"), str)] if isinstance(hypotheses, list) else []
        if not hypothesis_ids or len(hypothesis_ids) != len(set(hypothesis_ids)):
            _error(errors, "SYNTHETIC_TEACHING_HYPOTHESIS_BINDING_INVALID", "/teaching_content/hypotheses", "teaching hypotheses must be non-empty and unique")

    framework = handoff.get("deck_framework")
    if isinstance(framework, list):
        page_ids = [page.get("page_id") for page in framework if isinstance(page, Mapping)]
        expected = [f"STP-{index:02d}" for index in range(1, 9)]
        if page_ids != expected:
            _error(errors, "SYNTHETIC_DECK_SEQUENCE_INVALID", "/deck_framework", "synthetic deck must keep the locked eight-page sequence")
        for index, page in enumerate(framework):
            if isinstance(page, Mapping) and page.get("visible_teaching_notice") != "TEACHING DEMO — NOT A REAL PROJECT VALIDATION":
                _error(errors, "SYNTHETIC_VISIBLE_NOTICE_INVALID", f"/deck_framework/{index}/visible_teaching_notice", "every page must visibly carry the teaching-demo notice")

    _walk(handoff, "", errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return {"ok": not errors, "outcome": "SYNTHETIC_HANDOFF_VALID" if not errors else "SYNTHETIC_HANDOFF_INVALID", "errors": errors}


def main(argv: Sequence[str]) -> int:
    """Run deterministic local validation and emit one JSON result."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    arguments = parser.parse_args(argv)
    try:
        handoff = load_json_object(arguments.handoff)
        schema = load_json_object(SCHEMA_PATH)
        result = validate_synthetic_teaching_presentation_handoff(handoff, schema)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {"ok": False, "outcome": "SYNTHETIC_HANDOFF_INVALID", "errors": [{"code": "SYNTHETIC_HANDOFF_LOAD_FAILED", "path": "", "message": str(error)}]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
