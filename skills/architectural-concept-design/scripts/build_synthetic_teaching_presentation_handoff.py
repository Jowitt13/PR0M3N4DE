"""Build the ADR-0008 teaching-only presentation handoff from validated state."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict, cast

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_state  # noqa: E402
from validate_synthetic_teaching_presentation_handoff import (  # noqa: E402
    SCHEMA_PATH,
    TEACHING_LABELS,
    canonical_sha256,
    load_json_object,
    validate_synthetic_teaching_presentation_handoff,
)

JsonObject = dict[str, Any]
ALLOWED_UNRESOLVED_FIELDS = ("budget_range", "target_opening_date", "known_regulations_or_assumptions")


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


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _confirmation_errors(confirmation: JsonObject) -> list[BuildError]:
    errors: list[BuildError] = []
    required = {"confirmation_kind", "confirmed_by", "confirmed_at", "teaching_labels", "not_real_project_validation", "unresolved_inputs"}
    unknown = set(confirmation) - required
    missing = required - set(confirmation)
    if missing or unknown:
        _error(errors, "SYNTHETIC_CONFIRMATION_SHAPE_INVALID", "", "confirmation must have exactly the allowed fields")
        return errors
    if confirmation.get("confirmation_kind") != "SYNTHETIC_TEACHING_DEMO_HUMAN_CONFIRMATION":
        _error(errors, "SYNTHETIC_CONFIRMATION_KIND_INVALID", "/confirmation_kind", "confirmation kind must be the locked teaching-demo value")
    if not isinstance(confirmation.get("confirmed_by"), str) or not confirmation["confirmed_by"].strip():
        _error(errors, "SYNTHETIC_CONFIRMATION_HUMAN_REQUIRED", "/confirmed_by", "a non-empty human confirmer is required")
    if not isinstance(confirmation.get("confirmed_at"), str) or not confirmation["confirmed_at"].strip():
        _error(errors, "SYNTHETIC_CONFIRMATION_TIME_REQUIRED", "/confirmed_at", "a confirmation timestamp is required")
    if tuple(_strings(confirmation.get("teaching_labels"))) != TEACHING_LABELS:
        _error(errors, "SYNTHETIC_CONFIRMATION_LABELS_INVALID", "/teaching_labels", "the three teaching labels must be complete and ordered")
    if confirmation.get("not_real_project_validation") is not True:
        _error(errors, "SYNTHETIC_CONFIRMATION_REAL_PROJECT_MARKER_INVALID", "/not_real_project_validation", "confirmation must explicitly reject real-project validation")
    unresolved = confirmation.get("unresolved_inputs")
    if not isinstance(unresolved, list):
        _error(errors, "SYNTHETIC_CONFIRMATION_UNRESOLVED_INVALID", "/unresolved_inputs", "unresolved inputs must be a list")
    else:
        fields: list[str] = []
        for index, entry in enumerate(unresolved):
            record = _mapping(entry)
            if record is None or set(record) != {"field", "status"} or record.get("status") != "UNKNOWN" or record.get("field") not in ALLOWED_UNRESOLVED_FIELDS:
                _error(errors, "SYNTHETIC_CONFIRMATION_UNRESOLVED_INVALID", f"/unresolved_inputs/{index}", "unresolved input must be an allowed UNKNOWN field")
            elif isinstance(record["field"], str):
                fields.append(record["field"])
        if len(fields) != len(set(fields)):
            _error(errors, "SYNTHETIC_CONFIRMATION_UNRESOLVED_DUPLICATE", "/unresolved_inputs", "unresolved input fields must not repeat")
    return errors


def _state_ids(output_payload: JsonObject, collection: str) -> list[str]:
    records = output_payload.get(collection)
    if not isinstance(records, list):
        return []
    return [record["id"] for record in records if isinstance(record, Mapping) and isinstance(record.get("id"), str)]


def _teaching_spaces(output_payload: JsonObject, errors: list[BuildError]) -> list[JsonObject]:
    """Transfer only local synthetic program labels and assumed areas for diagrams."""

    records = output_payload.get("spaces")
    result: list[JsonObject] = []
    if not isinstance(records, list):
        _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", "/spaces", "validated state must provide program spaces for the teaching deck")
        return result
    for index, item in enumerate(records):
        record = _mapping(item)
        area = _mapping(record.get("area")) if record else None
        identifier = record.get("id") if record else None
        name = record.get("name") if record else None
        value = area.get("value") if area else None
        if not isinstance(identifier, str) or not isinstance(name, str) or not name.strip() or not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", f"/spaces/{index}", "teaching program content requires id, non-empty name, and positive assumed area")
            continue
        result.append({"id": identifier, "name": name, "area_m2": value})
    return result


def _teaching_options(output_payload: JsonObject, errors: list[BuildError]) -> list[JsonObject]:
    """Transfer only locally authored option wording, never evidence or sources."""

    records = output_payload.get("options")
    result: list[JsonObject] = []
    if not isinstance(records, list):
        _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", "/options", "validated state must provide at least two options for the teaching deck")
        return result
    for index, item in enumerate(records):
        record = _mapping(item)
        identifier = record.get("id") if record else None
        name = record.get("name") if record else None
        operation = record.get("spatial_operation") if record else None
        if not isinstance(identifier, str) or not isinstance(name, str) or not name.strip() or not isinstance(operation, str) or not operation.strip():
            _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", f"/options/{index}", "teaching option content requires id, non-empty name, and spatial operation")
            continue
        result.append({"id": identifier, "name": name, "spatial_operation": operation})
    return result


def _teaching_hypotheses(output_payload: JsonObject, errors: list[BuildError]) -> list[JsonObject]:
    records = output_payload.get("hypotheses")
    result: list[JsonObject] = []
    if not isinstance(records, list):
        _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", "/hypotheses", "validated state must provide at least one hypothesis for the teaching deck")
        return result
    for index, item in enumerate(records):
        record = _mapping(item)
        identifier = record.get("id") if record else None
        description = record.get("description") if record else None
        if not isinstance(identifier, str) or not isinstance(description, str) or not description.strip():
            _error(errors, "SYNTHETIC_TEACHING_CONTENT_INVALID", f"/hypotheses/{index}", "teaching hypothesis content requires id and non-empty description")
            continue
        result.append({"id": identifier, "description": description})
    return result


def _select_human_decision(output_payload: JsonObject, errors: list[BuildError]) -> Mapping[str, Any] | None:
    decisions = output_payload.get("decisions")
    records = [item for item in decisions if isinstance(item, Mapping) and item.get("decision_type") == "select"] if isinstance(decisions, list) else []
    if len(records) != 1:
        _error(errors, "SYNTHETIC_HUMAN_DECISION_REQUIRED", "/decisions", "validated state must contain exactly one explicit human select decision")
        return None
    decision = records[0]
    if not all(isinstance(decision.get(key), str) and decision[key] for key in ("id", "chosen_option_id", "decided_by")):
        _error(errors, "SYNTHETIC_HUMAN_DECISION_INVALID", "/decisions/0", "human decision is incomplete")
        return None
    option_ids = set(_state_ids(output_payload, "options"))
    if decision["chosen_option_id"] not in option_ids:
        _error(errors, "SYNTHETIC_HUMAN_DECISION_OPTION_UNRESOLVED", "/decisions/0/chosen_option_id", "human decision must resolve to an existing state option")
        return None
    return decision


def _page(page_id: str, title: str, purpose: str, required_state_ids: list[str]) -> JsonObject:
    return {
        "page_id": page_id,
        "title": title,
        "purpose": purpose,
        "required_state_ids": required_state_ids,
        "visible_teaching_notice": "TEACHING DEMO — NOT A REAL PROJECT VALIDATION",
        "visual_strategy": "team_original_vector_diagram_only",
        "speaker_note": "仅用于教学演示；不构成真实项目、法规、可建性或生产验证结论。",
    }


def build_synthetic_teaching_presentation_handoff(
    input_payload: JsonObject,
    output_payload: JsonObject,
    confirmation: JsonObject,
    handoff_id: str,
    validated_at: str,
    schema: JsonObject,
) -> tuple[JsonObject | None, BuildResult]:
    """Build a no-precedent handoff or fail closed without partial output."""

    errors = _confirmation_errors(confirmation)
    state_result, _ = validate_state.validate_state(input_payload, output_payload)
    if not state_result["ok"]:
        _error(errors, "SYNTHETIC_STATE_VALIDATION_FAILED", "/state_package", "input and output must pass validate_state before presentation transfer")
    project = _mapping(input_payload.get("project"))
    project_id = output_payload.get("project_id")
    if project is None or project.get("id") != project_id or not isinstance(project.get("name"), str):
        _error(errors, "SYNTHETIC_PROJECT_BINDING_INVALID", "/project", "input project identity must match the validated output project")
    decision = _select_human_decision(output_payload, errors)
    spaces = _state_ids(output_payload, "spaces")
    constraints = _state_ids(output_payload, "constraints")
    relations = _state_ids(output_payload, "relations")
    hypotheses = _state_ids(output_payload, "hypotheses")
    options = _state_ids(output_payload, "options")
    criteria = _state_ids(output_payload, "criteria")
    if not all((spaces, constraints, hypotheses, options, criteria)):
        _error(errors, "SYNTHETIC_STATE_TRANSFER_INCOMPLETE", "/state_package", "validated state must contain spaces, constraints, hypotheses, options, and criteria")
    teaching_spaces = _teaching_spaces(output_payload, errors)
    teaching_options = _teaching_options(output_payload, errors)
    teaching_hypotheses = _teaching_hypotheses(output_payload, errors)
    selected_teaching_option = next((item for item in teaching_options if item["id"] == (decision.get("chosen_option_id") if decision else None)), None)
    if selected_teaching_option is None:
        _error(errors, "SYNTHETIC_TEACHING_SELECTED_OPTION_UNRESOLVED", "/options", "the selected teaching option must be present in transferred local option content")
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    if errors:
        return None, {"ok": False, "outcome": "SYNTHETIC_HANDOFF_BUILD_FAILED", "errors": errors}

    assert project is not None and isinstance(project_id, str) and decision is not None
    chosen_option_id = cast(str, decision["chosen_option_id"])
    decision_id = cast(str, decision["id"])
    handoff: JsonObject = {
        "contract_version": "1.0.0",
        "mode": "SYNTHETIC_NO_PRECEDENT_DEMO",
        "handoff_id": handoff_id,
        "project_id": project_id,
        "project_display_name": project["name"],
        "state_package": {
            "input_hash": output_payload["state"]["input_hash"],
            "output_hash": canonical_sha256(output_payload),
            "validated_at": validated_at,
        },
        "human_design_decision": {
            "decision_id": decision_id,
            "decision_type": "select",
            "chosen_option_id": chosen_option_id,
            "decided_by": decision["decided_by"],
            "recorded_in_validated_state": True,
        },
        "teaching_labels": list(TEACHING_LABELS),
        "not_real_project_validation": True,
        "human_authorized_assumptions": {
            "classification": list(TEACHING_LABELS),
            "unresolved_inputs": confirmation["unresolved_inputs"],
        },
        "program_space_ids": spaces,
        "teaching_content": {
            "program_spaces": teaching_spaces,
            "concept_options": teaching_options,
            "selected_option": selected_teaching_option,
            "hypotheses": teaching_hypotheses,
        },
        "deck_framework": [
            _page("STP-01", "合成教学演示", "确认本页仅为假设教学展示。", [decision_id]),
            _page("STP-02", "假设任务书", "呈现人类授权的教学输入与其边界。", [constraints[0]]),
            _page("STP-03", "功能清单", "呈现已在人类输入中给出的功能组织。", spaces),
            _page("STP-04", "空间关系", "呈现已验证状态中的假设关系，不作技术推断。", [constraints[0], *(relations[:1] or spaces[:1])]),
            _page("STP-05", "概念方向", "并列呈现已记录的多个方向，不重新评分。", options),
            _page("STP-06", "人类已选方向", "呈现已经由人类选择并写入状态包的方向。", [decision_id, chosen_option_id, hypotheses[0]]),
            _page("STP-07", "仍待确认", "保留预算、时间与法规相关未知项。", [criteria[0]]),
            _page("STP-08", "教学下一步", "说明本次产物只验证本地教学链路。", [decision_id, criteria[0]]),
        ],
        "local_assets": [],
        "rendering_boundary": {
            "renderer_name": "ppt-master",
            "network_accessed": False,
            "third_party_media_packaged": False,
            "external_urls_permitted": False,
            "source_or_evidence_transferred": False,
            "rendering_authority": "validated_synthetic_handoff_and_team_original_vector_diagrams_only",
        },
    }
    semantic = validate_synthetic_teaching_presentation_handoff(handoff, schema)
    if not semantic["ok"]:
        converted = [{"code": item["code"], "path": item["path"], "message": item["message"]} for item in semantic["errors"]]
        return None, {"ok": False, "outcome": "SYNTHETIC_HANDOFF_BUILD_FAILED", "errors": converted}
    return handoff, {"ok": True, "outcome": "SYNTHETIC_HANDOFF_BUILT", "errors": []}


def _atomic_write_json(path: Path, payload: JsonObject) -> None:
    """Write one UTF-8-without-BOM JSON file atomically in its destination directory."""

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
    """Build one local teaching handoff and preserve an existing output on failure."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_state", type=Path)
    parser.add_argument("output_state", type=Path)
    parser.add_argument("confirmation", type=Path)
    parser.add_argument("--handoff-id", required=True)
    parser.add_argument("--validated-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        handoff, result = build_synthetic_teaching_presentation_handoff(
            load_json_object(arguments.input_state),
            load_json_object(arguments.output_state),
            load_json_object(arguments.confirmation),
            arguments.handoff_id,
            arguments.validated_at,
            load_json_object(SCHEMA_PATH),
        )
        if handoff is not None:
            _atomic_write_json(arguments.output, handoff)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {"ok": False, "outcome": "SYNTHETIC_HANDOFF_BUILD_FAILED", "errors": [{"code": "SYNTHETIC_HANDOFF_LOAD_FAILED", "path": "", "message": str(error)}]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
