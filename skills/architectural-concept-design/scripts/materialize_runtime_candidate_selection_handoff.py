"""Bind a human selection receipt to one validated RCH runtime-draft handoff.

This local-only bridge preserves selected, untrusted observations for later
human authoring. It never creates an RCR candidate set, state evidence, media,
a presentation handoff, a subprocess, or a network request.
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

import build_runtime_candidate_handoff as candidate_handoff_builder
from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
REFERENCES = Path(__file__).resolve().parents[1] / "references"
SCHEMA_PATH = REFERENCES / "runtime-candidate-selection-handoff.schema.json"
SOURCE_HANDOFF_SCHEMA_PATH = REFERENCES / "runtime-candidate-handoff.schema.json"
REGISTRY_PATH = REFERENCES / "source-access-registry.json"
REQUIRED_AUTHORING = [
    "project_identity",
    "brief_linked_reasons",
    "team_authored_spatial_operation",
    "uncertainties",
]


class SelectionError(TypedDict):
    """One stable validation error for the local selection bridge."""

    code: str
    path: str
    message: str


class SelectionResult(TypedDict):
    """Machine-readable result for a selection build or validation."""

    ok: bool
    selected_count: int
    errors: list[SelectionError]


def _error(errors: list[SelectionError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _load_json(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 object without changing it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def _checker() -> FormatChecker:
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    return checker


def _schema_errors(value: object, schema: Mapping[str, Any], code: str) -> list[SelectionError]:
    """Return compact root-schema validation errors."""

    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(dict(schema), format_checker=_checker())
    except Exception as error:  # pragma: no cover - packaged schema is tested directly.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    errors: list[SelectionError] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(errors, code, path, f"schema rule failed: {error.validator}")
    return errors


def _selection_receipt_errors(receipt: Mapping[str, Any]) -> list[SelectionError]:
    """Validate the explicit-human fields not representable as schema patterns."""

    errors: list[SelectionError] = []
    if receipt.get("record_type") != "runtime_candidate_human_selection":
        _error(errors, "SELECTION_RECORD_TYPE_INVALID", "/record_type", "selection receipt must be runtime_candidate_human_selection")
    if receipt.get("contract_version") != "1.0.0":
        _error(errors, "SELECTION_CONTRACT_VERSION_INVALID", "/contract_version", "selection receipt contract_version must be 1.0.0")
    if receipt.get("selection_status") != "HUMAN_SELECTED":
        _error(errors, "SELECTION_STATUS_INVALID", "/selection_status", "selection receipt must be HUMAN_SELECTED")
    selected_by = receipt.get("selected_by")
    if not is_human_record_label(selected_by):
        _error(errors, "SELECTION_NOT_HUMAN", "/selected_by", "selected_by must name a human record, not an agent or model")
    return errors


def _receipt_schema() -> dict[str, Any]:
    """Return the narrow, local-only accepted receipt input contract."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "record_type", "contract_version", "selection_id", "project_id",
            "candidate_handoff_id", "candidate_handoff_sha256", "source_registry_version",
            "selection_method", "selected_by", "selected_at", "selected_candidate_ids",
            "selection_status", "boundaries",
        ],
        "properties": {
            "record_type": {"const": "runtime_candidate_human_selection"},
            "contract_version": {"const": "1.0.0"},
            "selection_id": {"type": "string", "pattern": "^RCS-[0-9]{3,}$"},
            "project_id": {"type": "string", "minLength": 1, "maxLength": 160},
            "candidate_handoff_id": {"type": "string", "pattern": "^RCH-[0-9]{3,}$"},
            "candidate_handoff_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "source_registry_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
            "selection_method": {"const": "explicit_human_selection"},
            "selected_by": {"type": "string", "minLength": 1},
            "selected_at": {"type": "string", "format": "date-time"},
            "selected_candidate_ids": {
                "type": "array", "minItems": 1, "maxItems": 3, "uniqueItems": True,
                "items": {"type": "string", "pattern": "^RC-[0-9]{3,}$"},
            },
            "selection_status": {"const": "HUMAN_SELECTED"},
            "boundaries": {
                "type": "object", "additionalProperties": False,
                "required": ["source_text_status", "evidence_registration_status"],
                "properties": {
                    "source_text_status": {"const": "untrusted_page_content"},
                    "evidence_registration_status": {"const": "unregistered_until_human_selected"},
                    "does_not_create": {
                        "type": "array", "minItems": 7, "maxItems": 7, "uniqueItems": True,
                        "items": {
                            "enum": ["SRC-xxx", "E-xxx", "CARD-xxx", "VERIFIED", "media_permission", "presentation_handoff", "PPTX"]
                        },
                    },
                },
            },
        },
    }


def _selection_handoff_id(selection_id: str) -> str:
    """Derive one stable output ID without letting a caller select it."""

    return f"RCSH-{selection_id.removeprefix('RCS-')}"


def build_selection_handoff(
    candidate_handoff: JsonObject,
    candidate_handoff_sha256: str,
    selection_receipt: JsonObject,
    output_schema: JsonObject,
    source_handoff_schema: JsonObject,
    registry: JsonObject,
) -> tuple[dict[str, Any] | None, SelectionResult]:
    """Build one selected-observation handoff or return no output on failure."""

    errors: list[SelectionError] = []
    source_result = candidate_handoff_builder.validate_candidate_handoff(candidate_handoff, source_handoff_schema, registry)
    if not source_result["ok"]:
        _error(errors, "CANDIDATE_HANDOFF_INVALID", "", "candidate handoff must pass its fixed local validator")

    errors.extend(_schema_errors(selection_receipt, _receipt_schema(), "SELECTION_RECEIPT_SCHEMA_INVALID"))
    errors.extend(_selection_receipt_errors(selection_receipt))
    if selection_receipt.get("candidate_handoff_id") != candidate_handoff.get("handoff_id"):
        _error(errors, "SELECTION_HANDOFF_ID_MISMATCH", "/candidate_handoff_id", "selection receipt must bind the supplied RCH handoff ID")
    if selection_receipt.get("candidate_handoff_sha256") != candidate_handoff_sha256:
        _error(errors, "SELECTION_HANDOFF_HASH_MISMATCH", "/candidate_handoff_sha256", "selection receipt must bind the exact raw candidate-handoff bytes")
    if selection_receipt.get("source_registry_version") != candidate_handoff.get("registry_version"):
        _error(errors, "SELECTION_REGISTRY_VERSION_MISMATCH", "/source_registry_version", "selection receipt registry version must match the RCH handoff")

    drafts = candidate_handoff.get("candidate_drafts")
    selected_ids = selection_receipt.get("selected_candidate_ids")
    draft_by_id = {
        draft.get("id"): draft
        for draft in drafts
        if isinstance(draft, Mapping) and isinstance(draft.get("id"), str)
    } if isinstance(drafts, list) else {}
    if isinstance(selected_ids, list):
        for index, candidate_id in enumerate(selected_ids):
            if candidate_id not in draft_by_id:
                _error(errors, "SELECTION_ID_UNKNOWN", f"/selected_candidate_ids/{index}", "selected candidate must exist in the RCH handoff")

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "selected_count": 0, "errors": errors}

    assert isinstance(selected_ids, list)
    selected_observations: list[dict[str, Any]] = []
    for candidate_id in selected_ids:
        draft = draft_by_id[candidate_id]
        source = draft["source"]
        observed = draft["observed_short_text"]
        selected_observations.append(
            {
                "candidate_id": candidate_id,
                "source": {
                    "canonical_locator": source["canonical_locator"],
                    "accessed_at": source["accessed_at"],
                },
                "observed_short_text": observed,
                "integration_status": "HUMAN_AUTHORING_REQUIRED",
                "required_human_authoring": REQUIRED_AUTHORING,
            }
        )

    handoff = {
        "contract_version": "1.0.0",
        "selection_handoff_id": _selection_handoff_id(selection_receipt["selection_id"]),
        "project_id": selection_receipt["project_id"],
        "candidate_handoff": {
            "handoff_id": candidate_handoff["handoff_id"],
            "sha256": candidate_handoff_sha256,
            "registry_version": candidate_handoff["registry_version"],
        },
        "selection": {
            "selection_id": selection_receipt["selection_id"],
            "selected_by": selection_receipt["selected_by"],
            "selected_at": selection_receipt["selected_at"],
            "selection_method": selection_receipt["selection_method"],
            "selected_candidate_ids": selected_ids,
        },
        "selected_observations": selected_observations,
        "boundaries": {
            "does_not_create_runtime_sources_or_evidence": True,
            "does_not_transfer_spatial_operations": True,
            "does_not_create_cards_or_media": True,
            "does_not_create_presentation_handoff_or_pptx": True,
            "network_accessed": False,
            "third_party_media_retained": False,
        },
    }
    result = validate_selection_handoff(handoff, output_schema)
    if not result["ok"]:
        return None, result
    return handoff, result


def validate_selection_handoff(handoff: JsonObject, output_schema: JsonObject) -> SelectionResult:
    """Validate a standalone selected-observation handoff without source reads."""

    errors = _schema_errors(handoff, output_schema, "SCHEMA_VALIDATION_FAILED")
    selection = handoff.get("selection")
    observations = handoff.get("selected_observations")
    selected_ids = selection.get("selected_candidate_ids") if isinstance(selection, Mapping) else None
    selection_id = selection.get("selection_id") if isinstance(selection, Mapping) else None
    observation_ids = [item.get("candidate_id") for item in observations if isinstance(item, Mapping)] if isinstance(observations, list) else []
    selected_count = len(observation_ids)
    if isinstance(selection_id, str) and handoff.get("selection_handoff_id") != _selection_handoff_id(selection_id):
        _error(errors, "SELECTION_HANDOFF_ID_DERIVATION_MISMATCH", "/selection_handoff_id", "selection_handoff_id must be deterministically derived from selection_id")
    if isinstance(selected_ids, list) and observation_ids != selected_ids:
        _error(errors, "SELECTION_OBSERVATION_ORDER_MISMATCH", "/selected_observations", "selected observations must exactly preserve the human selected_candidate_ids order")
    if len(observation_ids) != len(set(observation_ids)):
        _error(errors, "SELECTED_OBSERVATION_ID_DUPLICATE", "/selected_observations", "selected observation IDs must be unique")
    if isinstance(observations, list):
        for index, observation in enumerate(observations):
            if isinstance(observation, Mapping) and observation.get("required_human_authoring") != REQUIRED_AUTHORING:
                _error(errors, "REQUIRED_HUMAN_AUTHORING_INVALID", f"/selected_observations/{index}/required_human_authoring", "every selected observation must carry the fixed human-authoring checklist in order")
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return {"ok": not errors, "selected_count": selected_count, "errors": errors}


def _load_failure(code: str, message: str) -> SelectionResult:
    return {"ok": False, "selected_count": 0, "errors": [{"code": code, "path": "", "message": message}]}


def main(argv: Sequence[str]) -> int:
    """Print one compact JSON result for build or validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    build = subcommands.add_parser("build", help="bind one explicit human selection to an RCH handoff")
    build.add_argument("candidate_handoff", type=Path)
    build.add_argument("selection_receipt", type=Path)
    validate = subcommands.add_parser("validate", help="validate one RCSH handoff")
    validate.add_argument("selection_handoff", type=Path)
    arguments = parser.parse_args(argv[1:])

    try:
        output_schema = _load_json(SCHEMA_PATH)
        if arguments.command == "validate":
            result = validate_selection_handoff(_load_json(arguments.selection_handoff), output_schema)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0 if result["ok"] else 1

        source_handoff_schema = _load_json(SOURCE_HANDOFF_SCHEMA_PATH)
        registry = _load_json(REGISTRY_PATH)
        candidate_path = arguments.candidate_handoff
        candidate_handoff = _load_json(candidate_path)
        selection_receipt = _load_json(arguments.selection_receipt)
        handoff, result = build_selection_handoff(
            candidate_handoff,
            hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            selection_receipt,
            output_schema,
            source_handoff_schema,
            registry,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if handoff is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI tests.
    raise SystemExit(main(sys.argv))
