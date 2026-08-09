"""Validate a local architecture presentation handoff without rendering or mutation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - only an incomplete runtime install reaches this.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]

from _rfc3339 import is_rfc3339_datetime
from _human_record import is_human_record_label

JsonObject = Mapping[str, Any]
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "presentation-handoff.schema.json"
PAGE_REQUIRED_PREFIXES: dict[str, tuple[str, ...]] = {
    "P-01-cover": ("RC-",),
    "P-02-brief-evidence": ("E-",),
    "P-03-precedent-selection": ("RC-",),
    "P-04-precedent-operations": ("RC-",),
    "P-05-site-context": ("C-",),
    "P-06-program-circulation": ("S-", "R-"),
    "P-07-grid-core-height": ("H-",),
    "P-08-concept-directions": ("O-",),
    "P-09-option-comparison": ("O-", "K-"),
    "P-10-human-decision-request": ("O-", "K-"),
    "P-11-sources-risks-next-actions": ("E-", "RC-"),
}


class HandoffError(TypedDict):
    """One deterministic presentation-handoff validation error."""

    code: str
    path: str
    message: str


class HandoffValidationResult(TypedDict):
    """Machine-readable, read-only result for one presentation handoff."""

    ok: bool
    handoff_id: str | None
    errors: list[HandoffError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object without changing it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(errors: list[HandoffError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _schema_errors(handoff: JsonObject, schema: JsonObject) -> list[HandoffError]:
    if Draft202012Validator is None or FormatChecker is None:
        return [{"code": "VALIDATOR_UNAVAILABLE", "path": "", "message": "jsonschema is required for presentation handoff validation"}]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=checker)
    except Exception as error:  # pragma: no cover - bundled Schema is separately tested.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    records: list[HandoffError] = []
    for error in sorted(validator.iter_errors(handoff), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "SCHEMA_VALIDATION_FAILED", path, f"schema rule failed: {error.validator}")
    return records


def _validate_selection(handoff: JsonObject, errors: list[HandoffError]) -> set[str]:
    selection = _mapping(handoff.get("precedent_selection"))
    if selection is None:
        return set()
    selected_ids = _strings(selection.get("selected_candidate_ids"))
    records = selection.get("selected_precedents")
    record_ids = [record.get("candidate_id") for record in records if isinstance(record, Mapping)] if isinstance(records, list) else []
    if selected_ids != record_ids:
        _error(errors, "SELECTION_RECORD_MISMATCH", "/precedent_selection", "selected_candidate_ids must exactly match selected_precedents candidate_id order")
    selected_by = selection.get("selected_by")
    if not is_human_record_label(selected_by):
        _error(errors, "SELECTION_NOT_HUMAN", "/precedent_selection/selected_by", "selected_by must identify a human, not an agent or model")
    return set(selected_ids)


def _authoritative_ids(handoff: JsonObject, selected_ids: set[str]) -> set[str]:
    chain = _mapping(handoff.get("architectural_chain"))
    if chain is None:
        return selected_ids
    ids = set(selected_ids)
    for key in [
        "brief_evidence_ids", "site_constraint_ids", "program_space_ids", "circulation_relation_ids",
        "hypothesis_ids", "option_ids", "criterion_ids",
    ]:
        ids.update(_strings(chain.get(key)))
    return ids


def _validate_pages(handoff: JsonObject, valid_ids: set[str], errors: list[HandoffError]) -> None:
    pages = handoff.get("deck_framework")
    if not isinstance(pages, list):
        return
    for index, page in enumerate(pages):
        if not isinstance(page, Mapping):
            continue
        page_id = page.get("page_id")
        entity_ids = _strings(page.get("required_entity_ids"))
        for entity_index, entity_id in enumerate(entity_ids):
            if entity_id not in valid_ids:
                _error(errors, "PAGE_ENTITY_UNRESOLVED", f"/deck_framework/{index}/required_entity_ids/{entity_index}", "page entity ID must resolve from selected candidates or architectural-chain references")
        if isinstance(page_id, str) and page_id in PAGE_REQUIRED_PREFIXES:
            for prefix in PAGE_REQUIRED_PREFIXES[page_id]:
                if not any(entity_id.startswith(prefix) for entity_id in entity_ids):
                    _error(errors, "PAGE_TRACE_FOCUS_MISSING", f"/deck_framework/{index}/required_entity_ids", f"{page_id} must include a {prefix} entity ID")


def _validate_assets(handoff: JsonObject, selected_ids: set[str], errors: list[HandoffError]) -> None:
    assets = handoff.get("local_assets")
    if not isinstance(assets, list):
        return
    seen: set[str] = set()
    for index, asset in enumerate(assets):
        if not isinstance(asset, Mapping):
            continue
        asset_id = asset.get("asset_id")
        if isinstance(asset_id, str):
            if asset_id in seen:
                _error(errors, "ASSET_ID_DUPLICATE", f"/local_assets/{index}/asset_id", "local asset IDs must be unique")
            seen.add(asset_id)
        candidate_id = asset.get("source_candidate_id")
        if isinstance(candidate_id, str) and candidate_id not in selected_ids:
            _error(errors, "ASSET_CANDIDATE_UNSELECTED", f"/local_assets/{index}/source_candidate_id", "local asset must belong to a selected runtime candidate")
        path = asset.get("relative_path")
        if isinstance(path, str) and ("://" in path or path.startswith("/") or ".." in path.split("/")):
            _error(errors, "ASSET_PATH_NOT_LOCAL", f"/local_assets/{index}/relative_path", "local asset path must remain a safe project-relative path")


def validate_presentation_handoff(handoff: JsonObject, schema: JsonObject) -> HandoffValidationResult:
    """Validate one local handoff deterministically without rendering or mutation."""

    errors = _schema_errors(handoff, schema)
    selected_ids = _validate_selection(handoff, errors)
    _validate_pages(handoff, _authoritative_ids(handoff, selected_ids), errors)
    _validate_assets(handoff, selected_ids, errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    handoff_id = handoff.get("handoff_id") if isinstance(handoff.get("handoff_id"), str) else None
    return {"ok": not errors, "handoff_id": handoff_id, "errors": errors}


def _load_failure(code: str, message: str) -> HandoffValidationResult:
    return {"ok": False, "handoff_id": None, "errors": [{"code": code, "path": "", "message": message}]}


def main(argv: Sequence[str]) -> int:
    """Emit a machine-readable, read-only result for a presentation handoff JSON file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        handoff = load_json_object(arguments.handoff)
        schema = load_json_object(SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True))
        return 2
    result = validate_presentation_handoff(handoff, schema)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
