"""Validate or propagate stale metadata for an Architecture Pre-design state package."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]
    Registry = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]
    SchemaError = Exception  # type: ignore[assignment,misc]

from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
EntityKind = Literal[
    "project", "source", "evidence", "constraint", "space", "relation",
    "hypothesis", "option", "criterion", "decision", "deliverable", "dependency",
]


class ValidationErrorRecord(TypedDict):
    """Machine-readable validation error defined by ADR-0001 section 13."""

    code: str
    path: str
    message: str
    related_ids: list[str]
    severity: Literal["ERROR"]


class ValidationResult(TypedDict):
    """Machine-readable validation result."""

    ok: bool
    errors: list[ValidationErrorRecord]


class PropagationResult(TypedDict):
    """Read-only result metadata for the propagate-stale public function."""

    affected_ids: list[str]
    output: dict[str, Any]


@dataclass(frozen=True)
class Entity:
    """An indexed state entity and its JSON Pointer location."""

    kind: EntityKind
    path: str
    value: JsonObject


SCHEMA_DIRECTORY = Path(__file__).resolve().parents[1] / "references"
ALLOWED_DEPENDENCY_PAIRS: set[tuple[EntityKind, EntityKind]] = {
    ("constraint", "option"),
    ("constraint", "decision"),
    ("constraint", "hypothesis"),
    ("space", "option"),
    ("space", "relation"),
    ("hypothesis", "option"),
    ("hypothesis", "decision"),
    ("evidence", "constraint"),
    ("evidence", "hypothesis"),
    ("evidence", "option"),
    ("evidence", "decision"),
    ("option", "decision"),
    ("criterion", "decision"),
    ("decision", "deliverable"),
}


def _error(code: str, path: str, message: str, related_ids: Sequence[str] = ()) -> ValidationErrorRecord:
    return {
        "code": code,
        "path": path,
        "message": message,
        "related_ids": list(related_ids),
        "severity": "ERROR",
    }


def _pointer(*tokens: object) -> str:
    """Build an RFC 6901 JSON Pointer from object keys or array indices."""
    if not tokens:
        return ""
    escaped = (str(token).replace("~", "~0").replace("/", "~1") for token in tokens)
    return "/" + "/".join(escaped)


def _parse_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def load_json_file(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object while rejecting non-finite JSON constants."""
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_parse_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def compute_input_hash(input_payload: JsonObject) -> str:
    """Return the ADR-0001 canonical SHA-256 for a schema-valid input payload."""
    encoded = json.dumps(
        input_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_schema(name: str) -> dict[str, Any]:
    return load_json_file(SCHEMA_DIRECTORY / name)


def _schema_registry(*schemas: JsonObject) -> Registry:
    if Registry is None or Resource is None:
        raise RuntimeError("jsonschema and referencing must be installed to validate state packages")
    resources: list[tuple[str, Resource]] = []
    for schema in schemas:
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise RuntimeError("schema is missing its $id")
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _format_checker() -> FormatChecker:
    if FormatChecker is None:
        raise RuntimeError("jsonschema must be installed to validate state packages")
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    return checker


def _schema_errors(
    instance: JsonObject,
    schema: JsonObject,
    registry: Registry,
) -> list[ValidationErrorRecord]:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema must be installed to validate state packages")
    validator = Draft202012Validator(schema, registry=registry, format_checker=_format_checker())
    errors: list[ValidationErrorRecord] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        path = _pointer(*error.absolute_path)
        code = error.validator or "schema"
        errors.append(_error(code, path, error.message))
    return errors


def _as_records(document: JsonObject, key: str) -> list[JsonObject]:
    value = document.get(key, [])
    return [record for record in value if isinstance(record, Mapping)] if isinstance(value, list) else []


def _input_entity_groups(document: JsonObject) -> list[tuple[EntityKind, str, list[JsonObject]]]:
    program = document.get("program")
    spaces = program.get("spaces", []) if isinstance(program, Mapping) else []
    project = document.get("project")
    projects = [project] if isinstance(project, Mapping) else []
    return [
        ("project", "project", projects),
        ("source", "sources", _as_records(document, "sources")),
        ("evidence", "evidence", _as_records(document, "evidence")),
        ("space", "program/spaces", [item for item in spaces if isinstance(item, Mapping)] if isinstance(spaces, list) else []),
        ("constraint", "constraints", _as_records(document, "constraints")),
        ("relation", "relations", _as_records(document, "relations")),
    ]


def _output_entity_groups(document: JsonObject) -> list[tuple[EntityKind, str, list[JsonObject]]]:
    return [
        ("source", "sources", _as_records(document, "sources")),
        ("dependency", "dependencies", _as_records(document, "dependencies")),
        ("evidence", "evidence", _as_records(document, "evidence")),
        ("constraint", "constraints", _as_records(document, "constraints")),
        ("space", "spaces", _as_records(document, "spaces")),
        ("relation", "relations", _as_records(document, "relations")),
        ("hypothesis", "hypotheses", _as_records(document, "hypotheses")),
        ("option", "options", _as_records(document, "options")),
        ("criterion", "criteria", _as_records(document, "criteria")),
        ("decision", "decisions", _as_records(document, "decisions")),
        ("deliverable", "deliverables", _as_records(document, "deliverables")),
    ]


def _index_entities(
    groups: Sequence[tuple[EntityKind, str, Sequence[JsonObject]]],
) -> tuple[dict[str, Entity], list[ValidationErrorRecord]]:
    index: dict[str, Entity] = {}
    errors: list[ValidationErrorRecord] = []
    for kind, collection, records in groups:
        for position, record in enumerate(records):
            entity_id = record.get("id")
            if not isinstance(entity_id, str):
                continue
            path = _pointer(*collection.split("/"), position, "id")
            if entity_id in index:
                errors.append(_error(
                    "ID_NOT_UNIQUE",
                    path,
                    f"Duplicate stable ID {entity_id}",
                    [entity_id],
                ))
                continue
            index[entity_id] = Entity(kind=kind, path=_pointer(*collection.split("/"), position), value=record)
    return index, errors


def _require_reference(
    index: Mapping[str, Entity],
    reference: object,
    path: str,
    message: str,
    code: str = "REF_NOT_FOUND",
) -> list[ValidationErrorRecord]:
    if not isinstance(reference, str) or reference not in index:
        rendered = reference if isinstance(reference, str) else "<invalid reference>"
        return [_error(code, path, message.format(reference=rendered), [rendered])]
    return []


def _require_kind(
    index: Mapping[str, Entity],
    reference: object,
    expected_kind: EntityKind,
    path: str,
    message: str,
    code: str = "REF_NOT_FOUND",
) -> list[ValidationErrorRecord]:
    """Require a stable reference that resolves to one expected entity kind."""
    errors = _require_reference(index, reference, path, message, code)
    if errors or not isinstance(reference, str):
        return errors
    entity = index[reference]
    if entity.kind != expected_kind:
        return [_error(
            code,
            path,
            f"{message.format(reference=reference)}; expected {expected_kind}, found {entity.kind}",
            [reference],
        )]
    return []


def _check_evidence_references(
    document: JsonObject,
    evidence_index: Mapping[str, Entity],
    source_index: Mapping[str, Entity],
    evidence_source: Literal["input", "output"],
) -> list[ValidationErrorRecord]:
    errors: list[ValidationErrorRecord] = []
    for position, evidence in enumerate(_as_records(document, "evidence")):
        base = _pointer("evidence", position)
        label = evidence.get("label")
        if "source_id" in evidence:
            errors.extend(_require_reference(
                source_index,
                evidence.get("source_id"),
                _pointer("evidence", position, "source_id"),
                "Referenced source ID {reference} not found",
            ))
        for field in ("inference_basis", "basis_evidence_ids"):
            values = evidence.get(field, [])
            if not isinstance(values, list):
                continue
            for item_position, reference in enumerate(values):
                errors.extend(_require_reference(
                    evidence_index,
                    reference,
                    _pointer("evidence", position, field, item_position),
                    "Referenced evidence ID {reference} not found",
                    "TRACE_NOT_FOUND" if evidence_source == "output" else "REF_NOT_FOUND",
                ))
        if label == "INFERRED" and evidence_source == "output":
            # ADR-0001 requires output inference to start from input evidence, checked by caller.
            continue
    return errors


def _check_evidence_id_list(
    record: JsonObject,
    base: Sequence[object],
    evidence_index: Mapping[str, Entity],
) -> list[ValidationErrorRecord]:
    values = record.get("evidence_ids", [])
    if not isinstance(values, list):
        return []
    errors: list[ValidationErrorRecord] = []
    for position, reference in enumerate(values):
        errors.extend(_require_reference(
            evidence_index,
            reference,
            _pointer(*base, "evidence_ids", position),
            "Referenced evidence ID {reference} not found",
        ))
    return errors


def _check_dependency_cycles(dependencies: Sequence[JsonObject]) -> list[ValidationErrorRecord]:
    graph: dict[str, list[str]] = {}
    for dependency in dependencies:
        upstream = dependency.get("upstream_id")
        downstream = dependency.get("downstream_id")
        if isinstance(upstream, str) and isinstance(downstream, str):
            graph.setdefault(upstream, []).append(downstream)

    visiting: set[str] = set()
    visited: set[str] = set()
    errors: list[ValidationErrorRecord] = []

    def visit(node: str) -> None:
        if node in visited or errors:
            return
        if node in visiting:
            errors.append(_error(
                "STALE_CYCLE",
                "/dependencies",
                f"Dependency graph contains a cycle through {node}",
                [node],
            ))
            return
        visiting.add(node)
        for downstream in graph.get(node, []):
            visit(downstream)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return errors


def _propagation_input_error(message: str) -> tuple[None, ValidationResult, int]:
    """Return the runtime contract used for invalid CLI propagation arguments."""
    return None, {"ok": False, "errors": [_error("RUNTIME_ERROR", "", message)]}, 3


def _downstream_adjacency(dependencies: Sequence[JsonObject]) -> dict[str, set[str]]:
    """Return deduplicated downstream edges without assigning any stale state."""
    graph: dict[str, set[str]] = {}
    for dependency in dependencies:
        upstream = dependency.get("upstream_id")
        downstream = dependency.get("downstream_id")
        if isinstance(upstream, str) and isinstance(downstream, str):
            graph.setdefault(upstream, set()).add(downstream)
    return graph


def propagate_stale(
    input_payload: JsonObject,
    output_payload: JsonObject,
    trigger_id: str,
    trigger_change_event: str,
    occurred_at: str,
) -> tuple[PropagationResult | None, ValidationResult, int]:
    """Return a new output state with every declared downstream object marked stale.

    Validate both state packages before traversal, never read a system clock, and
    never mutate either supplied payload.  The returned output is a complete
    output-schema document suitable for writing by the caller.
    """
    validation, exit_code = validate_state(input_payload, output_payload)
    if exit_code != 0:
        return None, validation, exit_code
    if not trigger_id:
        return _propagation_input_error("trigger_id must be a non-empty stable ID")
    if not trigger_change_event:
        return _propagation_input_error("trigger_change_event must be non-empty")
    if not is_rfc3339_datetime(occurred_at):
        return _propagation_input_error("occurred_at must be a strict RFC 3339 date-time")

    propagated = copy.deepcopy(dict(output_payload))
    output_index, output_errors = _index_entities(_output_entity_groups(propagated))
    if output_errors:
        return None, {"ok": False, "errors": output_errors}, 2
    if trigger_id not in output_index:
        return None, {
            "ok": False,
            "errors": [_error(
                "REF_NOT_FOUND",
                "/trigger_id",
                f"Stale trigger ID {trigger_id} not found",
                [trigger_id],
            )],
        }, 2

    graph = _downstream_adjacency(_as_records(propagated, "dependencies"))
    visited: set[str] = {trigger_id}
    pending: list[str] = [trigger_id]
    affected_ids: set[str] = set()
    while pending:
        upstream = pending.pop(0)
        for downstream in sorted(graph.get(upstream, set())):
            if downstream in visited:
                continue
            visited.add(downstream)
            pending.append(downstream)
            affected_ids.add(downstream)

    for entity_id in sorted(affected_ids):
        entity = output_index[entity_id]
        if not isinstance(entity.value, dict):
            return _propagation_input_error(f"State entity {entity_id} is not mutable")
        entity.value["stale"] = {
            "reason": f"Marked stale because {entity_id} is downstream of changed upstream {trigger_id}.",
            "trigger_id": trigger_id,
            "trigger_change_event": trigger_change_event,
            "occurred_at": occurred_at,
        }

    result, final_exit_code = validate_state(input_payload, propagated)
    if final_exit_code != 0:
        return None, result, final_exit_code
    return {"affected_ids": sorted(affected_ids), "output": propagated}, result, 0


def _check_output_consistency(
    input_payload: JsonObject,
    output_payload: JsonObject,
    input_index: Mapping[str, Entity],
    output_index: Mapping[str, Entity],
) -> list[ValidationErrorRecord]:
    errors: list[ValidationErrorRecord] = []
    project = input_payload.get("project")
    project_id = project.get("id") if isinstance(project, Mapping) else None
    if output_payload.get("project_id") != project_id:
        errors.append(_error(
            "REF_NOT_FOUND",
            "/project_id",
            f"Output project_id {output_payload.get('project_id')!r} does not resolve to the input project",
            [str(output_payload.get("project_id"))],
        ))

    for entity_id, entity in input_index.items():
        if entity.kind in {"project", "dependency"}:
            continue
        output_entity = output_index.get(entity_id)
        if output_entity is None:
            errors.append(_error(
                "TRACE_NOT_FOUND",
                entity.path,
                f"Input {entity.kind} {entity_id} is missing from the output state package",
                [entity_id],
            ))
            continue
        if entity.kind != output_entity.kind:
            errors.append(_error(
                "ID_NOT_UNIQUE",
                output_entity.path,
                f"ID {entity_id} changes entity kind from {entity.kind} to {output_entity.kind}",
                [entity_id],
            ))

    input_evidence = {item.get("id"): item for item in _as_records(input_payload, "evidence")}
    for position, evidence in enumerate(_as_records(output_payload, "evidence")):
        label = evidence.get("label")
        evidence_id = evidence.get("id")
        base = _pointer("evidence", position)
        if label in {"PROVIDED", "VERIFIED"}:
            inherited = input_evidence.get(evidence_id)
            inherited_material = {key: value for key, value in inherited.items() if key != "stale"} if isinstance(inherited, Mapping) else None
            output_material = {key: value for key, value in evidence.items() if key != "stale"}
            if inherited_material != output_material:
                errors.append(_error(
                    "TRACE_NOT_FOUND",
                    base,
                    f"Output {label} evidence {evidence_id} must originate unchanged from input evidence",
                    [str(evidence_id)],
                ))
        if label == "INFERRED":
            bases = evidence.get("inference_basis", [])
            if isinstance(bases, list):
                for item_position, reference in enumerate(bases):
                    errors.extend(_require_kind(
                        input_index,
                        reference,
                        "evidence",
                        _pointer("evidence", position, "inference_basis", item_position),
                        "Output INFERRED evidence basis {reference} is not in input evidence",
                        "TRACE_NOT_FOUND",
                    ))
    return errors


def validate_state(input_payload: JsonObject, output_payload: JsonObject) -> tuple[ValidationResult, int]:
    """Validate one input/output state pair and return its result plus ADR exit code."""
    try:
        evidence_schema = _load_schema("evidence.schema.json")
        area_schema = _load_schema("area-schedule.schema.json")
        input_schema = _load_schema("input.schema.json")
        output_schema = _load_schema("output.schema.json")
        registry = _schema_registry(evidence_schema, area_schema, input_schema, output_schema)
        if Draft202012Validator is None:
            raise RuntimeError("jsonschema must be installed to validate state packages")
        Draft202012Validator.check_schema(evidence_schema)
        Draft202012Validator.check_schema(area_schema)
        Draft202012Validator.check_schema(input_schema)
        Draft202012Validator.check_schema(output_schema)
        schema_errors = _schema_errors(input_payload, input_schema, registry)
        schema_errors.extend(_schema_errors(output_payload, output_schema, registry))
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return {"ok": False, "errors": [_error("RUNTIME_ERROR", "", str(error))]}, 3

    if schema_errors:
        return {"ok": False, "errors": schema_errors}, 1

    input_index, input_errors = _index_entities(_input_entity_groups(input_payload))
    output_index, output_errors = _index_entities(_output_entity_groups(output_payload))
    errors = [*input_errors, *output_errors]

    input_sources = {entity_id: entity for entity_id, entity in input_index.items() if entity.kind == "source"}
    input_evidence = {entity_id: entity for entity_id, entity in input_index.items() if entity.kind == "evidence"}
    output_sources = {entity_id: entity for entity_id, entity in output_index.items() if entity.kind == "source"}
    output_evidence = {entity_id: entity for entity_id, entity in output_index.items() if entity.kind == "evidence"}

    errors.extend(_check_evidence_references(input_payload, input_evidence, input_sources, "input"))
    errors.extend(_check_evidence_references(output_payload, output_evidence, output_sources, "output"))

    for kind, collection in (("constraints", "constraint"), ("hypotheses", "hypothesis"), ("options", "option"), ("criteria", "criterion")):
        for position, record in enumerate(_as_records(output_payload, kind)):
            errors.extend(_check_evidence_id_list(record, (kind, position), output_evidence))
            if collection == "option":
                assessments = record.get("assessments", [])
                if isinstance(assessments, list):
                    for assessment_position, assessment in enumerate(assessments):
                        if not isinstance(assessment, Mapping):
                            continue
                        errors.extend(_require_kind(
                            output_index,
                            assessment.get("criterion_id"),
                            "criterion",
                            _pointer(kind, position, "assessments", assessment_position, "criterion_id"),
                            "Referenced criterion ID {reference} not found",
                        ))
                        errors.extend(_check_evidence_id_list(
                            assessment,
                            (kind, position, "assessments", assessment_position),
                            output_evidence,
                        ))

    for position, relation in enumerate(_as_records(input_payload, "relations")):
        for field in ("from_space_id", "to_space_id"):
            errors.extend(_require_kind(
                input_index,
                relation.get(field),
                "space",
                _pointer("relations", position, field),
                "Referenced space ID {reference} not found",
            ))
    for position, relation in enumerate(_as_records(output_payload, "relations")):
        for field in ("from_space_id", "to_space_id"):
            errors.extend(_require_kind(
                output_index,
                relation.get(field),
                "space",
                _pointer("relations", position, field),
                "Referenced space ID {reference} not found",
            ))

    for position, decision in enumerate(_as_records(output_payload, "decisions")):
        for field in ("chosen_option_id", "target_option_id"):
            if field in decision:
                errors.extend(_require_kind(
                    output_index,
                    decision.get(field),
                    "option",
                    _pointer("decisions", position, field),
                    "Referenced option ID {reference} not found",
                ))
        criteria_ids = decision.get("criteria_ids", [])
        if isinstance(criteria_ids, list):
            for criterion_position, reference in enumerate(criteria_ids):
                errors.extend(_require_kind(
                    output_index,
                    reference,
                    "criterion",
                    _pointer("decisions", position, "criteria_ids", criterion_position),
                    "Referenced criterion ID {reference} not found",
                ))

    dependencies = _as_records(output_payload, "dependencies")
    for position, dependency in enumerate(dependencies):
        upstream = dependency.get("upstream_id")
        downstream = dependency.get("downstream_id")
        errors.extend(_require_reference(
            output_index,
            upstream,
            _pointer("dependencies", position, "upstream_id"),
            "Referenced upstream ID {reference} not found",
        ))
        errors.extend(_require_reference(
            output_index,
            downstream,
            _pointer("dependencies", position, "downstream_id"),
            "Referenced downstream ID {reference} not found",
        ))
        if isinstance(upstream, str) and isinstance(downstream, str):
            upstream_entity = output_index.get(upstream)
            downstream_entity = output_index.get(downstream)
            if upstream_entity and downstream_entity and (upstream_entity.kind, downstream_entity.kind) not in ALLOWED_DEPENDENCY_PAIRS:
                errors.append(_error(
                    "DEPENDENCY_INVALID_PAIR",
                    _pointer("dependencies", position),
                    f"Dependency pair {upstream_entity.kind} -> {downstream_entity.kind} is not allowed",
                    [upstream, downstream],
                ))
    errors.extend(_check_dependency_cycles(dependencies))

    for entity_id, entity in output_index.items():
        stale = entity.value.get("stale")
        if not isinstance(stale, Mapping):
            continue
        errors.extend(_require_reference(
            output_index,
            stale.get("trigger_id"),
            _pointer(*entity.path.strip("/").split("/"), "stale", "trigger_id"),
            "Stale trigger ID {reference} not found",
        ))

    try:
        expected_hash = compute_input_hash(input_payload)
    except (TypeError, ValueError) as error:
        return {"ok": False, "errors": [_error("RUNTIME_ERROR", "/state/input_hash", str(error))]}, 3
    state = output_payload.get("state")
    actual_hash = state.get("input_hash") if isinstance(state, Mapping) else None
    if actual_hash != expected_hash:
        errors.append(_error(
            "HASH_MISMATCH",
            "/state/input_hash",
            "Computed input hash does not match state.input_hash",
            [str(actual_hash), expected_hash],
        ))

    errors.extend(_check_output_consistency(input_payload, output_payload, input_index, output_index))
    if errors:
        return {"ok": False, "errors": errors}, 2
    return {"ok": True, "errors": []}, 0


def _write_result(result: ValidationResult) -> None:
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _write_output(output_payload: Mapping[str, Any]) -> None:
    """Emit one complete propagated output package without touching source files."""
    print(json.dumps(output_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: Sequence[str]) -> int:
    """Run ADR-0001 validate or propagate-stale mode without file mutation."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", nargs="?")
    parser.add_argument("input_path", nargs="?")
    parser.add_argument("output_path", nargs="?")
    parser.add_argument("trigger_id", nargs="?")
    parser.add_argument("trigger_change_event", nargs="?")
    parser.add_argument("occurred_at", nargs="?")
    args = parser.parse_args(argv[1:])
    valid_validate = (
        args.mode == "validate"
        and args.input_path
        and args.output_path
        and not args.trigger_id
        and not args.trigger_change_event
        and not args.occurred_at
    )
    valid_propagation = (
        args.mode == "propagate-stale"
        and args.input_path
        and args.output_path
        and args.trigger_id
        and args.trigger_change_event
        and args.occurred_at
    )
    if not valid_validate and not valid_propagation:
        _write_result({"ok": False, "errors": [_error(
            "RUNTIME_ERROR",
            "",
            "usage: validate_state.py validate <input.json> <output.json> | "
            "propagate-stale <input.json> <output.json> <trigger_id> "
            "<trigger_change_event> <occurred_at>",
        )]})
        return 3
    try:
        input_payload = load_json_file(Path(args.input_path))
        output_payload = load_json_file(Path(args.output_path))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        _write_result({"ok": False, "errors": [_error("RUNTIME_ERROR", "", str(error))]})
        return 3
    if args.mode == "validate":
        result, exit_code = validate_state(input_payload, output_payload)
        _write_result(result)
        return exit_code

    propagated, result, exit_code = propagate_stale(
        input_payload,
        output_payload,
        args.trigger_id,
        args.trigger_change_event,
        args.occurred_at,
    )
    if propagated is None:
        _write_result(result)
        return exit_code
    _write_output(propagated["output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
