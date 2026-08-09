"""Validate a state-only presentation handoff without rendering or mutation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - incomplete local environment only.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "state-only-presentation-handoff.schema.json"
NOTICE = "STATE-ONLY HANDOFF — NO EXTERNAL PRECEDENT OR THIRD-PARTY MEDIA"
PAGE_IDS = tuple(f"SOP-{index:02d}" for index in range(1, 11))
PAGE_REQUIRED_PREFIXES: dict[str, tuple[str, ...]] = {
    "SOP-01": ("D-", "O-"),
    "SOP-02": ("E-",),
    "SOP-03": ("C-",),
    "SOP-04": ("S-",),
    "SOP-05": ("H-",),
    "SOP-06": ("O-", "K-"),
    "SOP-07": ("D-", "O-", "K-"),
    "SOP-08": ("A-",),
    "SOP-09": ("E-", "H-"),
    "SOP-10": ("D-", "A-"),
}
FORBIDDEN_TEXT = re.compile(r"https?://|(?:^|[^A-Z0-9-])(?:RC|RCR|SRC)-[0-9]{3,}(?:$|[^A-Z0-9-])|\bVERIFIED\b", re.IGNORECASE)


class HandoffError(TypedDict):
    code: str
    path: str
    message: str


class HandoffResult(TypedDict):
    ok: bool
    handoff_id: str | None
    errors: list[HandoffError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Read one finite UTF-8 JSON object without changing it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def canonical_sha256(payload: JsonObject) -> str:
    """Compute a deterministic JSON SHA-256 for a validated local record."""

    import hashlib

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _error(errors: list[HandoffError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _schema_errors(handoff: JsonObject, schema: JsonObject) -> list[HandoffError]:
    if Draft202012Validator is None or FormatChecker is None:
        return [{"code": "VALIDATOR_UNAVAILABLE", "path": "", "message": "jsonschema is required"}]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=checker)
    except Exception as error:  # pragma: no cover - bundled schema has dedicated evaluation.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    errors: list[HandoffError] = []
    for error in sorted(validator.iter_errors(handoff), key=lambda item: (list(item.absolute_path), item.message)):
        _error(errors, "SCHEMA_VALIDATION_FAILED", "/" + "/".join(str(token) for token in error.absolute_path), f"schema rule failed: {error.validator}")
    return errors


def _chain_ids(handoff: JsonObject, errors: list[HandoffError]) -> set[str]:
    chain = _mapping(handoff.get("architectural_chain"))
    if chain is None:
        return set()
    prefixes = {
        "evidence_ids": "E-",
        "constraint_ids": "C-",
        "space_ids": "S-",
        "relation_ids": "R-",
        "hypothesis_ids": "H-",
        "option_ids": "O-",
        "criterion_ids": "K-",
        "decision_ids": "D-",
        "deliverable_ids": "A-",
    }
    all_ids: set[str] = set()
    for field, prefix in prefixes.items():
        values = _strings(chain.get(field))
        if field != "relation_ids" and not values:
            _error(errors, "STATE_CHAIN_INCOMPLETE", f"/architectural_chain/{field}", "state-only handoff requires this transferred state category")
        for index, value in enumerate(values):
            if not value.startswith(prefix):
                _error(errors, "STATE_CHAIN_PREFIX_INVALID", f"/architectural_chain/{field}/{index}", f"state ID must begin with {prefix}")
            if value in all_ids:
                _error(errors, "STATE_CHAIN_ID_DUPLICATE", f"/architectural_chain/{field}/{index}", "a state ID may appear in only one transferred category")
            all_ids.add(value)
    return all_ids


def _validate_decision(handoff: JsonObject, chain_ids: set[str], errors: list[HandoffError]) -> None:
    decision = _mapping(handoff.get("human_design_decision"))
    if decision is None:
        return
    decided_by = decision.get("decided_by")
    if not is_human_record_label(decided_by):
        _error(errors, "SELECTION_NOT_HUMAN", "/human_design_decision/decided_by", "decision must be attributed to a human record label")
    decision_id = decision.get("decision_id")
    option_id = decision.get("chosen_option_id")
    criteria = _strings(decision.get("criteria_ids"))
    if isinstance(decision_id, str) and decision_id not in chain_ids:
        _error(errors, "DECISION_ID_UNRESOLVED", "/human_design_decision/decision_id", "decision ID must resolve to the transferred state chain")
    if isinstance(option_id, str) and option_id not in chain_ids:
        _error(errors, "DECISION_OPTION_UNRESOLVED", "/human_design_decision/chosen_option_id", "chosen option must resolve to the transferred state chain")
    for index, criterion_id in enumerate(criteria):
        if criterion_id not in chain_ids:
            _error(errors, "DECISION_CRITERION_UNRESOLVED", f"/human_design_decision/criteria_ids/{index}", "criterion must resolve to the transferred state chain")


def _validate_pages(handoff: JsonObject, chain_ids: set[str], errors: list[HandoffError]) -> None:
    pages = handoff.get("deck_framework")
    if not isinstance(pages, list):
        return
    actual_ids = [page.get("page_id") for page in pages if isinstance(page, Mapping)]
    if tuple(actual_ids) != PAGE_IDS:
        _error(errors, "PAGE_SEQUENCE_INVALID", "/deck_framework", "state-only deck pages must be exactly SOP-01 through SOP-10 in order")
    for index, page in enumerate(pages):
        record = _mapping(page)
        if record is None:
            continue
        page_id = record.get("page_id")
        if record.get("visible_state_only_notice") != NOTICE:
            _error(errors, "STATE_ONLY_NOTICE_INVALID", f"/deck_framework/{index}/visible_state_only_notice", "each page must retain the fixed state-only notice")
        if record.get("visual_strategy") != "team_original_diagram_only":
            _error(errors, "VISUAL_STRATEGY_INVALID", f"/deck_framework/{index}/visual_strategy", "only team-original diagrams are allowed")
        ids = _strings(record.get("required_state_ids"))
        for required_id in ids:
            if required_id not in chain_ids:
                _error(errors, "PAGE_STATE_ID_UNRESOLVED", f"/deck_framework/{index}/required_state_ids", "page ID must resolve to the transferred state chain")
        if isinstance(page_id, str) and page_id in PAGE_REQUIRED_PREFIXES:
            for prefix in PAGE_REQUIRED_PREFIXES[page_id]:
                if not any(value.startswith(prefix) for value in ids):
                    _error(errors, "PAGE_TRACEABILITY_INCOMPLETE", f"/deck_framework/{index}/required_state_ids", f"{page_id} requires a {prefix} trace")


def _validate_assets(handoff: JsonObject, chain_ids: set[str], errors: list[HandoffError]) -> None:
    assets = handoff.get("local_assets")
    if not isinstance(assets, list):
        return
    seen: set[str] = set()
    for index, asset in enumerate(assets):
        record = _mapping(asset)
        if record is None:
            continue
        asset_id = record.get("asset_id")
        if isinstance(asset_id, str):
            if asset_id in seen:
                _error(errors, "ASSET_ID_DUPLICATE", f"/local_assets/{index}/asset_id", "asset IDs must be unique")
            seen.add(asset_id)
        deliverable_id = record.get("state_deliverable_id")
        if isinstance(deliverable_id, str) and deliverable_id not in chain_ids:
            _error(errors, "ASSET_DELIVERABLE_UNRESOLVED", f"/local_assets/{index}/state_deliverable_id", "asset must bind to a transferred A deliverable")
        path = record.get("relative_path")
        if isinstance(path, str) and ("://" in path or path.startswith("/") or "\\" in path or ".." in path.split("/")):
            _error(errors, "ASSET_PATH_NOT_LOCAL", f"/local_assets/{index}/relative_path", "asset path must be a safe project-relative path")


def _validate_boundary_and_text(handoff: JsonObject, errors: list[HandoffError]) -> None:
    boundary = _mapping(handoff.get("rendering_boundary"))
    if boundary is not None:
        for field in ("renderer_invoked", "network_accessed", "external_precedent_transferred", "third_party_media_packaged", "pptx_generated"):
            if boundary.get(field) is not False:
                _error(errors, "RENDERING_BOUNDARY_INVALID", f"/rendering_boundary/{field}", "state-only handoff must not activate rendering or external transfer")
    rendered = json.dumps(handoff, ensure_ascii=False, sort_keys=True)
    if FORBIDDEN_TEXT.search(rendered):
        _error(errors, "EXTERNAL_PRECEDENT_CONTENT_FORBIDDEN", "", "state-only handoff must not contain URLs, RC/RCR/SRC IDs, or VERIFIED claims")


def validate_state_only_presentation_handoff(handoff: JsonObject, schema: JsonObject) -> HandoffResult:
    """Return a deterministic validation result and never render or mutate files."""

    errors = _schema_errors(handoff, schema)
    chain_ids = _chain_ids(handoff, errors)
    _validate_decision(handoff, chain_ids, errors)
    _validate_pages(handoff, chain_ids, errors)
    _validate_assets(handoff, chain_ids, errors)
    _validate_boundary_and_text(handoff, errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    handoff_id = handoff.get("handoff_id") if isinstance(handoff.get("handoff_id"), str) else None
    return {"ok": not errors, "handoff_id": handoff_id, "errors": errors}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        result = validate_state_only_presentation_handoff(load_json_object(arguments.handoff), load_json_object(SCHEMA_PATH))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        result = {"ok": False, "handoff_id": None, "errors": [{"code": "LOCAL_AUTHORITY_LOAD_FAILED", "path": "", "message": str(error)}]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
