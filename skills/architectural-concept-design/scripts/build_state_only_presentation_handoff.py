"""Build a real-project state-only presentation handoff without external precedent transfer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_state  # noqa: E402
from _human_record import is_human_record_label  # noqa: E402
from _rfc3339 import is_rfc3339_datetime  # noqa: E402
from validate_state_only_presentation_handoff import (  # noqa: E402
    SCHEMA_PATH,
    canonical_sha256,
    load_json_object,
    validate_state_only_presentation_handoff,
)

JsonObject = dict[str, Any]


class BuildError(TypedDict):
    code: str
    path: str
    message: str


class BuildResult(TypedDict):
    ok: bool
    outcome: str
    errors: list[BuildError]


def _error(errors: list[BuildError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _state_ids(output_payload: JsonObject, collection: str) -> list[str]:
    records = output_payload.get(collection)
    if not isinstance(records, list):
        return []
    return [record["id"] for record in records if isinstance(record, Mapping) and isinstance(record.get("id"), str)]


def _contains_stale(value: object) -> bool:
    if isinstance(value, Mapping):
        return "stale" in value or any(_contains_stale(item) for item in value.values())
    return any(_contains_stale(item) for item in value) if isinstance(value, list) else False


def _select_decision(output_payload: JsonObject, errors: list[BuildError]) -> Mapping[str, Any] | None:
    records = output_payload.get("decisions")
    selected = [record for record in records if isinstance(record, Mapping) and record.get("decision_type") == "select"] if isinstance(records, list) else []
    if len(selected) != 1:
        _error(errors, "HUMAN_SELECTION_REQUIRED", "/decisions", "validated state must have exactly one explicit select decision")
        return None
    decision = selected[0]
    required = ("id", "chosen_option_id", "decided_by")
    if not all(isinstance(decision.get(field), str) and decision.get(field, "").strip() for field in required):
        _error(errors, "HUMAN_SELECTION_INVALID", "/decisions/0", "select decision must include ID, option, and human record label")
        return None
    if not is_human_record_label(decision.get("decided_by")):
        _error(errors, "SELECTION_NOT_HUMAN", "/decisions/0/decided_by", "select decision must be recorded by a human")
    criteria = decision.get("criteria_ids")
    if not isinstance(criteria, list) or not criteria or not all(isinstance(item, str) for item in criteria):
        _error(errors, "HUMAN_SELECTION_CRITERIA_INVALID", "/decisions/0/criteria_ids", "select decision must name one or more criteria")
    option_ids = set(_state_ids(output_payload, "options"))
    criterion_ids = set(_state_ids(output_payload, "criteria"))
    if isinstance(decision.get("chosen_option_id"), str) and decision["chosen_option_id"] not in option_ids:
        _error(errors, "HUMAN_SELECTION_OPTION_UNRESOLVED", "/decisions/0/chosen_option_id", "chosen option must resolve to validated state")
    for index, criterion_id in enumerate(criteria if isinstance(criteria, list) else []):
        if isinstance(criterion_id, str) and criterion_id not in criterion_ids:
            _error(errors, "HUMAN_SELECTION_CRITERION_UNRESOLVED", f"/decisions/0/criteria_ids/{index}", "criterion must resolve to validated state")
    return decision


def _page(page_id: str, title: str, purpose: str, state_ids: list[str]) -> JsonObject:
    return {
        "page_id": page_id,
        "title": title,
        "purpose": purpose,
        "required_state_ids": state_ids,
        "visible_state_only_notice": "STATE-ONLY HANDOFF — NO EXTERNAL PRECEDENT OR THIRD-PARTY MEDIA",
        "visual_strategy": "team_original_diagram_only",
        "speaker_note": "Use only the validated project state and team-original diagrams; preserve unresolved items for human review.",
    }


def build_state_only_presentation_handoff(
    input_payload: JsonObject,
    output_payload: JsonObject,
    handoff_id: str,
    validated_at: str,
    schema: JsonObject,
) -> tuple[JsonObject | None, BuildResult]:
    """Build one bounded real-project handoff, or fail closed without partial output."""

    errors: list[BuildError] = []
    state_result, _ = validate_state.validate_state(input_payload, output_payload)
    if not state_result["ok"]:
        _error(errors, "STATE_VALIDATION_FAILED", "/state_package", "input and output must pass validate_state before this transfer")
    if _contains_stale(output_payload):
        _error(errors, "STATE_STALE", "/state_package", "state-only handoff refuses stale records")
    project = _mapping(input_payload.get("project"))
    state_meta = _mapping(output_payload.get("state"))
    project_id = output_payload.get("project_id")
    if project is None or not isinstance(project.get("id"), str) or project.get("id") != project_id or not isinstance(project.get("name"), str) or not project["name"].strip():
        _error(errors, "PROJECT_BINDING_INVALID", "/project", "input project identity and validated output project must match")
    if state_meta is None or not isinstance(state_meta.get("input_hash"), str):
        _error(errors, "STATE_REFERENCE_INVALID", "/state", "validated output must provide its input hash")
    if not isinstance(handoff_id, str) or not handoff_id.startswith("SOH-") or not handoff_id[4:].isdigit():
        _error(errors, "HANDOFF_ID_INVALID", "/handoff_id", "handoff ID must be SOH followed by digits")
    if not is_rfc3339_datetime(validated_at):
        _error(errors, "VALIDATED_AT_INVALID", "/validated_at", "validated_at must be an RFC 3339 date-time")
    decision = _select_decision(output_payload, errors)
    collections = {
        "evidence_ids": _state_ids(output_payload, "evidence"),
        "constraint_ids": _state_ids(output_payload, "constraints"),
        "space_ids": _state_ids(output_payload, "spaces"),
        "relation_ids": _state_ids(output_payload, "relations"),
        "hypothesis_ids": _state_ids(output_payload, "hypotheses"),
        "option_ids": _state_ids(output_payload, "options"),
        "criterion_ids": _state_ids(output_payload, "criteria"),
        "decision_ids": _state_ids(output_payload, "decisions"),
        "deliverable_ids": _state_ids(output_payload, "deliverables"),
    }
    for field, identifiers in collections.items():
        if field != "relation_ids" and not identifiers:
            _error(errors, "STATE_CHAIN_INCOMPLETE", f"/state/{field}", "validated state lacks a required category for state-only handoff")
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    if errors:
        return None, {"ok": False, "outcome": "STATE_ONLY_HANDOFF_BUILD_FAILED", "errors": errors}

    assert project is not None and state_meta is not None and decision is not None
    decision_id = decision["id"]
    chosen_option_id = decision["chosen_option_id"]
    criteria_ids = [item for item in decision["criteria_ids"] if isinstance(item, str)]
    handoff: JsonObject = {
        "contract_version": "1.0.0",
        "mode": "STATE_ONLY_TEAM_ORIGINAL",
        "handoff_id": handoff_id,
        "project_id": output_payload["project_id"],
        "project_display_name": project["name"],
        "state_package": {"input_hash": state_meta["input_hash"], "output_hash": canonical_sha256(output_payload), "validated_at": validated_at},
        "human_design_decision": {
            "decision_id": decision_id,
            "decision_type": "select",
            "chosen_option_id": chosen_option_id,
            "criteria_ids": criteria_ids,
            "decided_by": decision["decided_by"],
            "recorded_in_validated_state": True,
        },
        "architectural_chain": collections,
        "deck_framework": [
            _page("SOP-01", "Selected direction", "Record the explicit human design selection.", [decision_id, chosen_option_id]),
            _page("SOP-02", "Brief evidence", "Frame the supplied project evidence without external transfer.", [collections["evidence_ids"][0]]),
            _page("SOP-03", "Site constraints", "Frame the state-recorded constraints and open questions.", [collections["constraint_ids"][0]]),
            _page("SOP-04", "Program and relations", "Show supplied program relationships as team-original diagrams.", [collections["space_ids"][0], *(collections["relation_ids"][:1])]),
            _page("SOP-05", "Working hypotheses", "Keep hypotheses conditional and traceable.", [collections["hypothesis_ids"][0]]),
            _page("SOP-06", "Options and criteria", "Compare existing state options against recorded criteria.", [collections["option_ids"][0], collections["criterion_ids"][0]]),
            _page("SOP-07", "Human-selected option", "Carry the human selection without adding a new decision.", [decision_id, chosen_option_id, criteria_ids[0]]),
            _page("SOP-08", "Team-original deliverable", "Request only the state-recorded team-original deliverable.", [collections["deliverable_ids"][0]]),
            _page("SOP-09", "Risks and next checks", "Retain evidence and hypotheses requiring later validation.", [collections["evidence_ids"][0], collections["hypothesis_ids"][0]]),
            _page("SOP-10", "Handoff boundary", "State what remains for human and specialist review.", [decision_id, collections["deliverable_ids"][0]]),
        ],
        "local_assets": [],
        "rendering_boundary": {
            "renderer_name": "ppt-master",
            "renderer_invoked": False,
            "network_accessed": False,
            "external_precedent_transferred": False,
            "third_party_media_packaged": False,
            "pptx_generated": False,
        },
    }
    result = validate_state_only_presentation_handoff(handoff, schema)
    if not result["ok"]:
        return None, {"ok": False, "outcome": "STATE_ONLY_HANDOFF_BUILD_FAILED", "errors": result["errors"]}
    return handoff, {"ok": True, "outcome": "STATE_ONLY_HANDOFF_BUILT", "errors": []}


def _atomic_write_json(path: Path, payload: JsonObject) -> None:
    """Write a completed JSON handoff atomically and only after validation succeeds."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_state", type=Path)
    parser.add_argument("output_state", type=Path)
    parser.add_argument("--handoff-id", required=True)
    parser.add_argument("--validated-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv[1:])
    try:
        handoff, result = build_state_only_presentation_handoff(
            load_json_object(arguments.input_state), load_json_object(arguments.output_state), arguments.handoff_id, arguments.validated_at, load_json_object(SCHEMA_PATH)
        )
        if handoff is not None:
            _atomic_write_json(arguments.output, handoff)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        result = {"ok": False, "outcome": "STATE_ONLY_HANDOFF_BUILD_FAILED", "errors": [{"code": "LOCAL_AUTHORITY_LOAD_FAILED", "path": "", "message": str(error)}]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
