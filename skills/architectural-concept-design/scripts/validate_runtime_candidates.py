"""Validate a local runtime candidate-card set without network access or mutation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlsplit

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - only an incomplete runtime install reaches this.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]

from _rfc3339 import is_rfc3339_datetime
from _human_record import is_human_record_label

JsonObject = Mapping[str, Any]
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "runtime-candidate-card.schema.json"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "source-access-registry.json"
AUTO_ACCESS_STATUSES = frozenset({"api_allowed", "automated_access_allowed"})
MANUAL_ONLY_STATUS = "manual_or_discovery_only"


class CandidateError(TypedDict):
    """One deterministic local candidate-card validation error."""

    code: str
    path: str
    message: str


class CandidateValidationResult(TypedDict):
    """Machine-readable, local-only result for candidate-card validation."""

    ok: bool
    candidate_count: int
    errors: list[CandidateError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object without changing it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(errors: list[CandidateError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _as_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _schema_errors(candidate_set: Mapping[str, Any], schema: Mapping[str, Any]) -> list[CandidateError]:
    if Draft202012Validator is None or FormatChecker is None:
        return [{"code": "VALIDATOR_UNAVAILABLE", "path": "", "message": "jsonschema is required for runtime candidate validation"}]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        validator = Draft202012Validator(schema, format_checker=checker)
        Draft202012Validator.check_schema(schema)
    except Exception as error:  # pragma: no cover - the in-package Schema is checked by tests.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": str(error)}]

    records: list[CandidateError] = []
    for error in sorted(validator.iter_errors(candidate_set), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "SCHEMA_VALIDATION_FAILED", path, f"schema rule failed: {error.validator}")
    return records


def _registered_source(registry: Mapping[str, Any], domain: str) -> Mapping[str, Any] | None:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        return None
    return next(
        (
            item
            for item in sources
            if isinstance(item, Mapping) and item.get("domain") == domain
        ),
        None,
    )


def _endpoint_is_allowed(request_endpoint: str, allowed_endpoint: str) -> bool:
    """Return whether an endpoint stays inside one exact registered HTTPS prefix."""

    request = urlsplit(request_endpoint)
    allowed = urlsplit(allowed_endpoint)
    if (request.scheme, request.hostname, request.port) != (allowed.scheme, allowed.hostname, allowed.port):
        return False
    return request.path.startswith(allowed.path) if allowed.path.endswith("/") else request.path == allowed.path


def _validate_gate_receipt(
    source: Mapping[str, Any],
    registered: Mapping[str, Any],
    path: str,
    errors: list[CandidateError],
) -> None:
    receipt = _as_mapping(source.get("gate_receipt"))
    if receipt is None:
        _error(errors, "GATE_RECEIPT_REQUIRED", f"{path}/gate_receipt", "automated candidates require a non-secret REQUEST_READY gate receipt")
        return
    operation = receipt.get("operation")
    if operation not in registered.get("allowed_operations", []):
        _error(errors, "GATE_RECEIPT_OPERATION_INVALID", f"{path}/gate_receipt/operation", "gate receipt operation must exactly match a registered operation")
    if receipt.get("response_kind") != registered.get("allowed_response_kind"):
        _error(errors, "GATE_RECEIPT_RESPONSE_KIND_INVALID", f"{path}/gate_receipt/response_kind", "gate receipt response_kind must exactly match the registered JSON response kind")
    endpoint = _as_string(receipt.get("endpoint"))
    allowed_endpoints = registered.get("allowed_api_endpoints")
    try:
        parsed_endpoint = urlsplit(endpoint) if endpoint is not None else None
        endpoint_has_forbidden_parts = (
            parsed_endpoint is None
            or parsed_endpoint.scheme != "https"
            or not parsed_endpoint.hostname
            or parsed_endpoint.username is not None
            or parsed_endpoint.password is not None
            or parsed_endpoint.port is not None
            or bool(parsed_endpoint.query)
            or bool(parsed_endpoint.fragment)
        )
    except ValueError:
        endpoint_has_forbidden_parts = True
    if endpoint is None or endpoint_has_forbidden_parts or not isinstance(allowed_endpoints, list) or not any(
        isinstance(allowed, str) and _endpoint_is_allowed(endpoint, allowed)
        for allowed in allowed_endpoints
    ):
        _error(errors, "GATE_RECEIPT_ENDPOINT_INVALID", f"{path}/gate_receipt/endpoint", "gate receipt endpoint must be a credential-free HTTPS registered prefix without port, query, or fragment")


def _validate_candidate_source(
    candidate: Mapping[str, Any],
    index: int,
    registry: Mapping[str, Any],
    errors: list[CandidateError],
) -> None:
    source = _as_mapping(candidate.get("source"))
    path = f"/candidates/{index}/source"
    if source is None:
        return

    domain = _as_string(source.get("domain"))
    if domain is None:
        return
    registered = _registered_source(registry, domain)
    if registered is None:
        _error(errors, "SOURCE_UNREGISTERED", f"{path}/domain", "candidate source domain is not registered")
        return

    if source.get("access_method") != registered.get("access_method"):
        _error(errors, "ACCESS_METHOD_MISMATCH", f"{path}/access_method", "candidate access_method must exactly match the source registry")

    registry_version = registry.get("version")
    candidate_version = candidate.get("source_registry_version")
    if candidate_version != registry_version:
        _error(errors, "REGISTRY_VERSION_MISMATCH", f"/candidates/{index}/source_registry_version", "candidate source_registry_version must equal the fixed registry version")

    status = registered.get("status")
    scope = source.get("source_capture_scope")
    decision = source.get("request_gate_decision")
    if status in AUTO_ACCESS_STATUSES:
        if scope != "structured_metadata_only" or decision != "REQUEST_READY":
            _error(errors, "AUTOMATED_CAPTURE_GATE_MISSING", path, "automated sources require structured_metadata_only and REQUEST_READY")
        _validate_gate_receipt(source, registered, path, errors)
    elif status == MANUAL_ONLY_STATUS:
        if scope != "manual_title_and_locator_only" or decision != "MANUAL_ONLY":
            _error(errors, "MANUAL_CAPTURE_SCOPE_INVALID", path, "manual-only sources require manual_title_and_locator_only and MANUAL_ONLY")
        if source.get("gate_receipt") is not None:
            _error(errors, "MANUAL_GATE_RECEIPT_FORBIDDEN", f"{path}/gate_receipt", "manual-only sources must not claim an automated gate receipt")
        if candidate.get("spatial_operation") is not None:
            _error(errors, "MANUAL_OPERATION_FORBIDDEN", f"/candidates/{index}/spatial_operation", "manual title-and-locator records must not include a spatial operation")
    else:
        _error(errors, "SOURCE_STATUS_NOT_ELIGIBLE", f"{path}/domain", "blocked and future-scope sources cannot form runtime candidates")

    locator = _as_string(source.get("canonical_locator"))
    if locator is None:
        return
    try:
        parsed = urlsplit(locator)
        locator_has_forbidden_parts = (
            parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
        )
    except ValueError:
        parsed = None
        locator_has_forbidden_parts = True
    allowed_hosts = {domain}
    api_host = _as_string(registered.get("api_host"))
    if api_host is not None:
        allowed_hosts.add(api_host)
    if parsed is None or parsed.scheme != "https" or locator_has_forbidden_parts or parsed.hostname not in allowed_hosts:
        _error(errors, "LOCATOR_NOT_REGISTERED_HOST", f"{path}/canonical_locator", "canonical locator must be credential-free HTTPS on the registered domain or api_host without a port")


def _validate_selection(candidate_set: Mapping[str, Any], errors: list[CandidateError]) -> None:
    selection = _as_mapping(candidate_set.get("selection"))
    candidates = candidate_set.get("candidates")
    candidate_ids = {
        item.get("id")
        for item in candidates
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    } if isinstance(candidates, list) else set()
    if selection is None or selection.get("state") != "HUMAN_SELECTED":
        return

    selected_ids = selection.get("selected_candidate_ids")
    if isinstance(selected_ids, list):
        for index, candidate_id in enumerate(selected_ids):
            if candidate_id not in candidate_ids:
                _error(errors, "SELECTION_ID_UNKNOWN", f"/selection/selected_candidate_ids/{index}", "selected candidate must exist in this run")

    selector = _as_string(selection.get("selected_by"))
    if not is_human_record_label(selector):
        _error(errors, "SELECTION_NOT_HUMAN", "/selection/selected_by", "selected_by must be a human-record label, not an agent or model")


def validate_candidate_set(
    candidate_set: JsonObject,
    schema: JsonObject,
    registry: JsonObject,
) -> CandidateValidationResult:
    """Validate one candidate set deterministically with fixed local authorities only."""

    errors = _schema_errors(candidate_set, schema)
    candidates = candidate_set.get("candidates")
    candidate_count = len(candidates) if isinstance(candidates, list) else 0

    if candidate_set.get("registry_version") != registry.get("version"):
        _error(errors, "RUN_REGISTRY_VERSION_MISMATCH", "/registry_version", "run registry_version must equal the fixed source registry version")

    if isinstance(candidates, list):
        ids = [item.get("id") for item in candidates if isinstance(item, Mapping)]
        if len(ids) != len(set(ids)):
            _error(errors, "CANDIDATE_ID_DUPLICATE", "/candidates", "candidate IDs must be unique within the runtime run")
        for index, candidate in enumerate(candidates):
            if isinstance(candidate, Mapping):
                _validate_candidate_source(candidate, index, registry, errors)

    insufficiency = _as_mapping(candidate_set.get("insufficiency_report"))
    if candidate_count < 6:
        if insufficiency is None:
            _error(errors, "INSUFFICIENCY_REPORT_REQUIRED", "/insufficiency_report", "zero through five candidates require an insufficiency report")
        elif insufficiency.get("available_count") != candidate_count:
            _error(errors, "INSUFFICIENCY_COUNT_MISMATCH", "/insufficiency_report/available_count", "available_count must equal the actual candidate count")
    elif "insufficiency_report" in candidate_set:
        _error(errors, "INSUFFICIENCY_REPORT_FORBIDDEN", "/insufficiency_report", "exactly six candidates must not include an insufficiency report")

    _validate_selection(candidate_set, errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return {"ok": not errors, "candidate_count": candidate_count, "errors": errors}


def _load_failure(code: str, message: str) -> CandidateValidationResult:
    return {"ok": False, "candidate_count": 0, "errors": [{"code": code, "path": "", "message": message}]}


def main(argv: Sequence[str]) -> int:
    """Emit a machine-readable, read-only validation result for one JSON file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_set", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        candidate_set = load_json_object(arguments.candidate_set)
        schema = load_json_object(SCHEMA_PATH)
        registry = load_json_object(REGISTRY_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True))
        return 2

    result = validate_candidate_set(candidate_set, schema, registry)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
