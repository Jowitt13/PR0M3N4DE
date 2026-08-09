"""Convert authorized live-canary observations into six unselected candidate drafts.

This module is offline and deterministic. It reads only explicit local JSON, the
fixed in-package handoff Schema, and the fixed source-access registry. It never
opens a socket, starts a subprocess, launches a browser, calls a runtime, or
reaches any network or external registry resource. It never selects, ranks,
recommends, fabricates a missing field, or emits a CARD-xxx, SRC-xxx, E-xxx,
media, or presentation artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "runtime-candidate-handoff.schema.json"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "source-access-registry.json"
CONTROLLED_STATUS = "controlled_crawl_allowed"


class HandoffError(TypedDict):
    """One deterministic, local candidate-handoff error."""

    code: str
    path: str
    message: str


class HandoffValidationResult(TypedDict):
    """Machine-readable, local-only validation result for a handoff draft set."""

    ok: bool
    draft_count: int
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


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _as_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _checker() -> FormatChecker:
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    return checker


def _schema_registry(schema: Mapping[str, Any]) -> Registry:
    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        raise ValueError("handoff schema is missing a string $id")
    return Registry().with_resource(schema_id, Resource.from_contents(dict(schema)))


def _subschema_errors(instance: object, schema: Mapping[str, Any], definition: str) -> list[HandoffError]:
    """Validate one instance against a named $def of the handoff Schema."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [{"code": "SCHEMA_INVALID", "path": "", "message": "handoff schema is missing a string $id"}]
    try:
        validator = Draft202012Validator(
            {"$ref": f"{schema_id}#/$defs/{definition}"},
            registry=_schema_registry(schema),
            format_checker=_checker(),
        )
    except Exception as error:  # pragma: no cover - the in-package Schema is checked by tests.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    records: list[HandoffError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "INPUT_SCHEMA_VALIDATION_FAILED", path, f"schema rule failed: {error.validator}")
    return records


def _schema_errors(handoff: Mapping[str, Any], schema: Mapping[str, Any]) -> list[HandoffError]:
    """Validate a produced handoff against the root output Schema."""

    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=_checker())
    except Exception as error:  # pragma: no cover - the in-package Schema is checked by tests.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]
    records: list[HandoffError] = []
    for error in sorted(validator.iter_errors(handoff), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "SCHEMA_VALIDATION_FAILED", path, f"schema rule failed: {error.validator}")
    return records


def _controlled_source_by_domain(registry: Mapping[str, Any], domain: str) -> Mapping[str, Any] | None:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        return None
    return next(
        (
            item
            for item in sources
            if isinstance(item, Mapping) and item.get("domain") == domain and item.get("status") == CONTROLLED_STATUS
        ),
        None,
    )


def _exact_seed(source: Mapping[str, Any]) -> str | None:
    """Return the single reviewed seed for a controlled source, or None."""

    contract = _as_mapping(source.get("controlled_crawl"))
    seeds = contract.get("seed_urls") if contract is not None else None
    if isinstance(seeds, list) and len(seeds) == 1 and isinstance(seeds[0], str):
        return seeds[0]
    return None


def _controlled_source_by_seed(registry: Mapping[str, Any], locator: str) -> Mapping[str, Any] | None:
    """Resolve a controlled source only when the locator is its exact single seed."""

    sources = registry.get("sources")
    if not isinstance(sources, list):
        return None
    for item in sources:
        if not isinstance(item, Mapping) or item.get("status") != CONTROLLED_STATUS:
            continue
        if _exact_seed(item) == locator:
            return item
    return None


def build_candidate_handoff(
    handoff_input: JsonObject,
    schema: JsonObject,
    registry: JsonObject,
) -> tuple[dict[str, Any] | None, HandoffValidationResult]:
    """Deterministically convert six authorized observations into six drafts.

    The function fails closed and returns ``(None, result)`` on any input schema
    error, duplicate source, unregistered source, or non-exact seed. It never
    fabricates a missing short description.
    """

    errors = _subschema_errors(handoff_input, schema, "HandoffInput")
    if errors:
        return None, {"ok": False, "draft_count": 0, "errors": sorted(errors, key=lambda item: (item["path"], item["code"]))}

    registry_version = registry.get("version")
    observations = handoff_input["source_observations"]
    drafts: list[dict[str, Any]] = []
    seen_locators: set[str] = set()

    for index, observation in enumerate(observations):
        locator = observation["source_locator"]
        source = _controlled_source_by_seed(registry, locator)
        if source is None:
            _error(errors, "SOURCE_NOT_CONTROLLED_CRAWL_ALLOWED_OR_SEED_MISMATCH", f"/source_observations/{index}/source_locator", "source locator must be the exact reviewed seed of a controlled_crawl_allowed registry source")
            continue
        if locator in seen_locators:
            _error(errors, "DUPLICATE_SOURCE", f"/source_observations/{index}/source_locator", "each source observation must use a distinct reviewed source")
        seen_locators.add(locator)

        short_text = observation["short_text"]
        description = short_text.get("short_project_description")
        drafts.append(
            {
                "id": f"RC-{index + 1:03d}",
                "candidate_status": "UNSELECTED_RUNTIME_CANDIDATE",
                "source_registry_version": registry_version,
                "source": {
                    "domain": source["domain"],
                    "access_method": source["access_method"],
                    "source_capture_scope": "manual_title_and_locator_only",
                    "canonical_locator": locator,
                    "accessed_at": observation["accessed_at"],
                    "request_gate_decision": "MANUAL_ONLY",
                    "gate_receipt": None,
                },
                "observed_short_text": {
                    "source_text_trust": "untrusted_page_content",
                    "instruction_handling": "data_only_ignore_instructions",
                    "audit_status": "live_canary_unverified",
                    "project_title": {"observed": True, "text": short_text["project_title"]},
                    "short_project_description": (
                        {"observed": True, "text": description}
                        if isinstance(description, str)
                        else {"observed": False}
                    ),
                },
                "evidence_registration_status": "unregistered_until_human_selected",
            }
        )

    if errors:
        return None, {"ok": False, "draft_count": len(drafts), "errors": sorted(errors, key=lambda item: (item["path"], item["code"]))}

    handoff = {
        "contract_version": "1.0.0",
        "handoff_id": handoff_input["handoff_id"],
        "registry_version": registry_version,
        "no_fabrication": True,
        "candidate_drafts": drafts,
        "selection": {"state": "AWAITING_HUMAN_SELECTION"},
    }
    result = validate_candidate_handoff(handoff, schema, registry)
    if not result["ok"]:
        return None, result
    return handoff, result


def validate_candidate_handoff(
    handoff: JsonObject,
    schema: JsonObject,
    registry: JsonObject,
) -> HandoffValidationResult:
    """Validate a handoff draft set with fixed local authorities only."""

    errors = _schema_errors(handoff, schema)
    drafts = handoff.get("candidate_drafts")
    draft_count = len(drafts) if isinstance(drafts, list) else 0
    registry_version = registry.get("version")

    if handoff.get("registry_version") != registry_version:
        _error(errors, "RUN_REGISTRY_VERSION_MISMATCH", "/registry_version", "handoff registry_version must equal the fixed source registry version")

    if isinstance(drafts, list):
        ids = [draft.get("id") for draft in drafts if isinstance(draft, Mapping)]
        if len(ids) != len(set(ids)):
            _error(errors, "CANDIDATE_ID_DUPLICATE", "/candidate_drafts", "candidate draft IDs must be unique within the handoff")
        seen_locators: set[str] = set()
        seen_domains: set[str] = set()
        for index, draft in enumerate(drafts):
            if not isinstance(draft, Mapping):
                continue
            source = _as_mapping(draft.get("source"))
            path = f"/candidate_drafts/{index}/source"
            if source is None:
                continue
            domain = _as_string(source.get("domain"))
            locator = _as_string(source.get("canonical_locator"))
            if domain is None or locator is None:
                continue
            registered = _controlled_source_by_domain(registry, domain)
            if registered is None:
                _error(errors, "SOURCE_NOT_CONTROLLED_CRAWL_ALLOWED", f"{path}/domain", "candidate source must be a controlled_crawl_allowed registry domain")
                continue
            if source.get("access_method") != registered.get("access_method"):
                _error(errors, "ACCESS_METHOD_MISMATCH", f"{path}/access_method", "candidate access_method must exactly match the source registry")
            if _exact_seed(registered) != locator:
                _error(errors, "CANONICAL_LOCATOR_NOT_EXACT_SEED", f"{path}/canonical_locator", "canonical locator must be the exact reviewed seed for the source")
            if draft.get("source_registry_version") != registry_version:
                _error(errors, "REGISTRY_VERSION_MISMATCH", f"/candidate_drafts/{index}/source_registry_version", "draft source_registry_version must equal the fixed registry version")
            if locator in seen_locators or domain in seen_domains:
                _error(errors, "DUPLICATE_SOURCE", f"{path}", "each candidate draft must use a distinct reviewed source")
            seen_locators.add(locator)
            seen_domains.add(domain)

    selection = _as_mapping(handoff.get("selection"))
    if selection is None or selection.get("state") != "AWAITING_HUMAN_SELECTION":
        _error(errors, "SELECTION_STATE_FORBIDDEN", "/selection/state", "the handoff must remain AWAITING_HUMAN_SELECTION and never carry a selection")

    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return {"ok": not errors, "draft_count": draft_count, "errors": errors}


def _load_failure(code: str, message: str) -> HandoffValidationResult:
    return {"ok": False, "draft_count": 0, "errors": [{"code": code, "path": "", "message": message}]}


def main(argv: Sequence[str]) -> int:
    """Emit a machine-readable, read-only result for one local JSON file."""

    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    build_parser = subcommands.add_parser("build", help="convert an observation input into a handoff draft set")
    build_parser.add_argument("input", type=Path)
    validate_parser = subcommands.add_parser("validate", help="validate an existing handoff draft set")
    validate_parser.add_argument("handoff", type=Path)
    arguments = parser.parse_args(argv[1:])

    try:
        schema = load_json_object(SCHEMA_PATH)
        registry = load_json_object(REGISTRY_PATH)
        source = load_json_object(arguments.input if arguments.command == "build" else arguments.handoff)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        handoff, result = build_candidate_handoff(source, schema, registry)
        if handoff is None:
            print(json.dumps({"ok": False, "draft_count": result["draft_count"], "errors": result["errors"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        print(json.dumps(handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0

    result = validate_candidate_handoff(source, schema, registry)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
