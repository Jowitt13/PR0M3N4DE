"""Materialize six individually authorized canary observations into a handoff.

This module is the single offline entry from future, explicitly authorized
live-canary short-text observations to the existing runtime candidate handoff.
It is a gate implementation only: it reads explicit local JSON, enforces six
independent per-source human authorizations and six-source integrity, and then
delegates draft construction to the existing ARCH-076 handoff builder. It never
opens a socket, starts a subprocess, launches a browser or runtime, runs a
canary, backfills a historical observation, selects a candidate, or emits any
output when a single gate fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import build_runtime_candidate_handoff as handoff_builder
from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
MATERIALIZATION_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "runtime-observation-materialization.schema.json"
HANDOFF_SCHEMA_PATH = handoff_builder.SCHEMA_PATH
REGISTRY_PATH = handoff_builder.REGISTRY_PATH

HandoffError = handoff_builder.HandoffError
HandoffValidationResult = handoff_builder.HandoffValidationResult
load_json_object = handoff_builder.load_json_object


def _error(errors: list[HandoffError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _input_schema_errors(instance: object, schema: Mapping[str, Any]) -> list[HandoffError]:
    """Validate a materialization input against the fixed gate Schema."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [{"code": "SCHEMA_INVALID", "path": "", "message": "materialization schema is missing a string $id"}]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(
            dict(schema),
            registry=Registry().with_resource(schema_id, Resource.from_contents(dict(schema))),
            format_checker=checker,
        )
    except Exception as error:  # pragma: no cover - the in-package Schema is checked by tests.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    records: list[HandoffError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "MATERIALIZATION_INPUT_SCHEMA_INVALID", path, f"schema rule failed: {error.validator}")
    return records


def _authorization_errors(observations: Sequence[Mapping[str, Any]]) -> list[HandoffError]:
    """Enforce six independent, human, per-source authorizations."""

    errors: list[HandoffError] = []
    seen_references: set[str] = set()
    for index, observation in enumerate(observations):
        authorization = observation.get("human_authorization")
        if not isinstance(authorization, Mapping):
            continue
        path = f"/source_observations/{index}/human_authorization"
        confirmed_by = authorization.get("confirmed_by")
        if not is_human_record_label(confirmed_by):
            _error(errors, "AUTHORIZATION_NOT_HUMAN", f"{path}/confirmed_by", "confirmed_by must name a human, not an agent or model")
        reference = authorization.get("authorization_reference")
        if isinstance(reference, str):
            if reference in seen_references:
                _error(errors, "AUTHORIZATION_REFERENCE_NOT_INDEPENDENT", f"{path}/authorization_reference", "each source requires its own independent authorization reference")
            seen_references.add(reference)
    return errors


def _observation_errors(observations: Sequence[Mapping[str, Any]]) -> list[HandoffError]:
    """Enforce clean-200, no-redirect, and distinct-source observation integrity."""

    errors: list[HandoffError] = []
    seen_locators: set[str] = set()
    for index, observation in enumerate(observations):
        path = f"/source_observations/{index}"
        locator = observation.get("source_locator")
        if observation.get("observed_url") != locator:
            _error(errors, "OBSERVED_URL_NOT_EXACT_SEED", f"{path}/observed_url", "observed_url must exactly equal the reviewed source locator; redirects are ineligible")
        if isinstance(locator, str):
            if locator in seen_locators:
                _error(errors, "DUPLICATE_SOURCE", f"{path}/source_locator", "each observation must use a distinct reviewed source")
            seen_locators.add(locator)
    return errors


def materialize_candidate_handoff(
    materialization_input: JsonObject,
    materialization_schema: JsonObject,
    handoff_schema: JsonObject,
    registry: JsonObject,
) -> tuple[dict[str, Any] | None, HandoffValidationResult]:
    """Convert six authorized observations into one validated handoff, or nothing.

    All gates fail closed: on any schema, authorization, integrity, registry, or
    seed error the function returns ``(None, result)`` and produces no partial
    output. On success the returned handoff is exactly the existing
    runtime-candidate-handoff contract built by the ARCH-076 builder.
    """

    errors = _input_schema_errors(materialization_input, materialization_schema)
    if errors:
        return None, {"ok": False, "draft_count": 0, "errors": sorted(errors, key=lambda item: (item["path"], item["code"]))}

    observations = materialization_input["source_observations"]
    errors = _authorization_errors(observations) + _observation_errors(observations)
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "draft_count": 0, "errors": errors}

    handoff_input = {
        "contract_version": "1.0.0",
        "handoff_id": materialization_input["handoff_id"],
        "source_observations": [
            {
                "source_locator": observation["source_locator"],
                "accessed_at": observation["accessed_at"],
                "audit_status": observation["audit_status"],
                "source_text_trust": observation["source_text_trust"],
                "instruction_handling": observation["instruction_handling"],
                "short_text": dict(observation["short_text"]),
            }
            for observation in observations
        ],
    }
    return handoff_builder.build_candidate_handoff(handoff_input, handoff_schema, registry)


def main(argv: Sequence[str]) -> int:
    """Print one validated handoff, or a machine-readable failure, for one file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        materialization_input = load_json_object(arguments.input)
        materialization_schema = load_json_object(MATERIALIZATION_SCHEMA_PATH)
        handoff_schema = load_json_object(HANDOFF_SCHEMA_PATH)
        registry = load_json_object(REGISTRY_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "draft_count": 0, "errors": [{"code": "LOCAL_AUTHORITY_LOAD_FAILED", "path": "", "message": str(error)}]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    handoff, result = materialize_candidate_handoff(materialization_input, materialization_schema, handoff_schema, registry)
    if handoff is None:
        print(json.dumps({"ok": False, "draft_count": result["draft_count"], "errors": result["errors"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
