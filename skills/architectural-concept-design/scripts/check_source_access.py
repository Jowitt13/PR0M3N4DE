"""Evaluate a local runtime source-access request plan without making a network request."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import urlsplit, urlunsplit

from _rfc3339 import is_rfc3339_datetime

JsonObject = Mapping[str, Any]
AUTO_ACCESS_STATUSES = frozenset({"api_allowed", "automated_access_allowed"})
REQUIRED_READINESS = "manual_current_rate_limit_confirmation_required"
SENSITIVE_QUERY_NAMES = frozenset({"api_key", "apikey", "authorization", "cookie", "key", "token", "access_token"})
REQUIRED_CONTROL_FLAGS = (
    "follow_redirects",
    "html_page_scrape",
    "media_download",
    "asset_scrape",
    "bulk_download",
    "stealth",
    "browser_impersonation",
    "captcha_solving",
    "cloudflare_solving",
    "proxy_rotation",
    "curl_impersonate",
)
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "source-access-registry.json"


class GateError(TypedDict):
    """A safe machine-readable reason why a request plan cannot proceed."""

    code: str
    path: str
    message: str


class GateResult(TypedDict):
    """Deterministic local gate result; it contains no request secrets or body content."""

    ok: bool
    decision: Literal["REQUEST_READY", "BLOCKED"]
    registry_version: str | None
    source: dict[str, str | None]
    request: dict[str, str | None]
    required_query_parameter_names: list[str]
    errors: list[GateError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite JSON object from a UTF-8 file."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(errors: list[GateError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _safe_url(endpoint: object, errors: list[GateError]) -> tuple[str | None, object | None]:
    endpoint_value = _string(endpoint)
    if endpoint_value is None:
        _error(errors, "ENDPOINT_INVALID", "/endpoint", "endpoint must be a non-empty HTTPS URL")
        return None, None
    try:
        parsed = urlsplit(endpoint_value)
        port = parsed.port
    except ValueError:
        _error(errors, "ENDPOINT_INVALID", "/endpoint", "endpoint URL cannot be parsed")
        return endpoint_value, None
    if parsed.scheme != "https" or not parsed.hostname:
        _error(errors, "ENDPOINT_INVALID", "/endpoint", "endpoint must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        _error(errors, "ENDPOINT_CREDENTIALS_FORBIDDEN", "/endpoint", "endpoint credentials are forbidden")
    if port is not None:
        _error(errors, "ENDPOINT_PORT_FORBIDDEN", "/endpoint", "endpoint must not declare a port")
    if parsed.query or parsed.fragment:
        _error(errors, "ENDPOINT_QUERY_FRAGMENT_FORBIDDEN", "/endpoint", "endpoint query and fragment belong outside the endpoint field")
    return endpoint_value, parsed


def _endpoint_is_allowed(request_endpoint: str, allowed_endpoint: str) -> bool:
    """Return whether a request remains inside one exact registered HTTPS endpoint prefix."""

    request = urlsplit(request_endpoint)
    allowed = urlsplit(allowed_endpoint)
    if (request.scheme, request.hostname, request.port) != (allowed.scheme, allowed.hostname, allowed.port):
        return False
    allowed_path = allowed.path
    if allowed_path.endswith("/"):
        return request.path.startswith(allowed_path)
    return request.path == allowed_path


def _query_pairs(value: object, errors: list[GateError]) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        _error(errors, "QUERY_PARAMETERS_INVALID", "/query_parameters", "query_parameters must be an array of {name,value} objects")
        return []
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        entry = _mapping(item)
        name = _string(entry.get("name")) if entry else None
        parameter_value = _string(entry.get("value")) if entry else None
        if name is None or parameter_value is None:
            _error(errors, "QUERY_PARAMETER_INVALID", f"/query_parameters/{index}", "every query parameter must contain non-empty string name and value")
            continue
        if name.casefold() in SENSITIVE_QUERY_NAMES:
            _error(errors, "QUERY_CREDENTIAL_FORBIDDEN", f"/query_parameters/{index}/name", "credentials, cookies, and tokens must stay outside the request plan")
        pairs.append((name, parameter_value))
    return pairs


def _validate_controls(value: object, errors: list[GateError]) -> None:
    controls = _mapping(value)
    if controls is None:
        _error(errors, "REQUEST_CONTROLS_INVALID", "/request_controls", "request_controls must be an object with every required false flag")
        return
    for flag in REQUIRED_CONTROL_FLAGS:
        if controls.get(flag) is not False:
            _error(errors, "REQUEST_CONTROL_FORBIDDEN", f"/request_controls/{flag}", f"{flag} must be explicitly false")
    for flag in controls:
        if flag not in REQUIRED_CONTROL_FLAGS:
            _error(errors, "REQUEST_CONTROL_UNKNOWN", f"/request_controls/{flag}", "unknown request controls are blocked until the gate contract is reviewed")


def _validate_confirmation(value: object, errors: list[GateError]) -> None:
    confirmation = _mapping(value)
    if confirmation is None:
        _error(errors, "RATE_LIMIT_CONFIRMATION_MISSING", "/manual_rate_limit_confirmation", "a run-specific manual rate-limit confirmation is required")
        return
    if confirmation.get("confirmed") is not True:
        _error(errors, "RATE_LIMIT_CONFIRMATION_MISSING", "/manual_rate_limit_confirmation/confirmed", "confirmed must be true")
    if confirmation.get("request_readiness") != REQUIRED_READINESS:
        _error(errors, "RATE_LIMIT_CONFIRMATION_INVALID", "/manual_rate_limit_confirmation/request_readiness", f"request_readiness must equal {REQUIRED_READINESS}")
    if _string(confirmation.get("confirmed_by")) is None:
        _error(errors, "RATE_LIMIT_CONFIRMATION_INVALID", "/manual_rate_limit_confirmation/confirmed_by", "confirmed_by must be a non-empty human-record label")
    if not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        _error(errors, "RATE_LIMIT_CONFIRMATION_INVALID", "/manual_rate_limit_confirmation/confirmed_at", "confirmed_at must be an RFC 3339 date-time with timezone")
    if _string(confirmation.get("confirmation_reference")) is None:
        _error(errors, "RATE_LIMIT_CONFIRMATION_INVALID", "/manual_rate_limit_confirmation/confirmation_reference", "confirmation_reference must be a non-empty review reference")


def _safe_endpoint_for_result(value: object) -> str | None:
    """Return an endpoint only when its representation cannot contain URL credentials or a query."""

    endpoint = _string(value)
    if endpoint is None:
        return None
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port is not None:
            return None
        if parsed.query or parsed.fragment:
            return None
    except ValueError:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _result(
    errors: list[GateError],
    registry: Mapping[str, Any],
    source: Mapping[str, Any] | None,
    request_plan: Mapping[str, Any],
) -> GateResult:
    source_data = source or {}
    required_parameters = source_data.get("required_query_parameters", [])
    parameter_names = [item["name"] for item in required_parameters if isinstance(item, Mapping) and isinstance(item.get("name"), str)]
    return {
        "ok": not errors,
        "decision": "REQUEST_READY" if not errors else "BLOCKED",
        "registry_version": registry.get("version") if isinstance(registry.get("version"), str) else None,
        "source": {
            "domain": source_data.get("domain") if isinstance(source_data.get("domain"), str) else None,
            "status": source_data.get("status") if isinstance(source_data.get("status"), str) else None,
            "provider": source_data.get("provider") if isinstance(source_data.get("provider"), str) else None,
            "api_host": source_data.get("api_host") if isinstance(source_data.get("api_host"), str) else None,
        },
        "request": {
            "method": request_plan.get("method") if isinstance(request_plan.get("method"), str) else None,
            "endpoint": _safe_endpoint_for_result(request_plan.get("endpoint")),
            "operation": request_plan.get("operation") if isinstance(request_plan.get("operation"), str) else None,
            "expected_response_kind": request_plan.get("expected_response_kind") if isinstance(request_plan.get("expected_response_kind"), str) else None,
        },
        "required_query_parameter_names": parameter_names,
        "errors": errors,
    }


def evaluate_request_plan(request_plan: JsonObject, registry: JsonObject) -> GateResult:
    """Return a default-deny local decision for one proposed request without performing I/O."""

    errors: list[GateError] = []
    sources = registry.get("sources")
    if not isinstance(sources, list):
        _error(errors, "REGISTRY_INVALID", "/sources", "registry sources must be an array")
        return _result(errors, registry, None, request_plan)

    domain = _string(request_plan.get("domain"))
    if domain is None:
        _error(errors, "DOMAIN_INVALID", "/domain", "domain must be a non-empty exact registry domain")
        return _result(errors, registry, None, request_plan)
    source = next((item for item in sources if isinstance(item, Mapping) and item.get("domain") == domain), None)
    if source is None:
        _error(errors, "DOMAIN_UNREGISTERED", "/domain", "domain is not registered and is blocked by default")
        return _result(errors, registry, None, request_plan)

    status = _string(source.get("status"))
    if status not in AUTO_ACCESS_STATUSES:
        _error(errors, "STATUS_NOT_AUTOMATED", "/domain", f"{domain} has status {status or 'invalid'} and permits no automated request")

    audit_records = registry.get("access_audit")
    audit = audit_records.get(domain) if isinstance(audit_records, Mapping) else None
    if not isinstance(audit, Mapping) or audit.get("request_readiness") != REQUIRED_READINESS:
        _error(errors, "AUDIT_NOT_REQUEST_READY", "/domain", "registry audit does not require the supported request-readiness gate")
    _validate_confirmation(request_plan.get("manual_rate_limit_confirmation"), errors)
    _validate_controls(request_plan.get("request_controls"), errors)

    endpoint_value, parsed_endpoint = _safe_url(request_plan.get("endpoint"), errors)
    api_host = _string(source.get("api_host"))
    if parsed_endpoint is not None and api_host is not None and parsed_endpoint.hostname != api_host:
        _error(errors, "ENDPOINT_HOST_MISMATCH", "/endpoint", "endpoint host must exactly match the registered api_host")
    allowed_endpoints = source.get("allowed_api_endpoints")
    if not isinstance(allowed_endpoints, list) or not allowed_endpoints:
        _error(errors, "ENDPOINT_NOT_ALLOWED", "/endpoint", "source has no allowed API endpoint")
    elif parsed_endpoint is not None and endpoint_value is not None:
        if not any(isinstance(item, str) and _endpoint_is_allowed(endpoint_value, item) for item in allowed_endpoints):
            _error(errors, "ENDPOINT_NOT_ALLOWED", "/endpoint", "endpoint is outside every registered exact HTTPS endpoint prefix")

    method = _string(request_plan.get("method"))
    allowed_methods = source.get("allowed_methods")
    if method is None or not isinstance(allowed_methods, list) or method not in allowed_methods:
        _error(errors, "METHOD_NOT_ALLOWED", "/method", "method must exactly match a registered allowed method")

    operation = _string(request_plan.get("operation"))
    allowed_operations = source.get("allowed_operations")
    if operation is None or not isinstance(allowed_operations, list) or operation not in allowed_operations:
        _error(errors, "OPERATION_NOT_ALLOWED", "/operation", "operation must exactly match a registered allowed operation")

    response_kind = _string(request_plan.get("expected_response_kind"))
    allowed_response_kind = _string(source.get("allowed_response_kind"))
    if response_kind is None or response_kind != allowed_response_kind:
        _error(errors, "RESPONSE_KIND_NOT_ALLOWED", "/expected_response_kind", "expected_response_kind must exactly match the registered JSON response kind")

    query_pairs = _query_pairs(request_plan.get("query_parameters"), errors)
    required_parameters = source.get("required_query_parameters")
    if not isinstance(required_parameters, list):
        _error(errors, "REGISTRY_INVALID", "/required_query_parameters", "registered required_query_parameters must be an array")
    else:
        for item in required_parameters:
            parameter = _mapping(item)
            name = _string(parameter.get("name")) if parameter else None
            value = _string(parameter.get("value")) if parameter else None
            if name is None or value is None:
                _error(errors, "REGISTRY_INVALID", "/required_query_parameters", "registered query parameters must contain non-empty name and value")
            elif (name, value) not in query_pairs:
                _error(errors, "REQUIRED_QUERY_PARAMETER_MISSING", "/query_parameters", f"required query parameter {name} is missing")

    if method == "POST":
        contract = _mapping(source.get("post_request_contract"))
        post_body = request_plan.get("post_body")
        if contract is None:
            _error(errors, "POST_CONTRACT_INVALID", "/post_body", "registered POST source has no structured post_request_contract")
        if not isinstance(post_body, str) or not post_body:
            _error(errors, "POST_BODY_INVALID", "/post_body", "POST request plans require a non-empty post_body string")
        elif contract is not None:
            markers = contract.get("required_body_markers")
            if not isinstance(markers, list):
                _error(errors, "POST_CONTRACT_INVALID", "/post_body", "registered post_request_contract has no marker array")
            else:
                for marker in markers:
                    if not isinstance(marker, str) or marker not in post_body:
                        _error(errors, "POST_BODY_MARKER_MISSING", "/post_body", "post_body is missing a required registered marker")
            if response_kind != contract.get("allowed_response_kind"):
                _error(errors, "POST_RESPONSE_KIND_NOT_ALLOWED", "/expected_response_kind", "POST response kind must match the post_request_contract")
    elif "post_body" in request_plan:
        _error(errors, "POST_BODY_UNEXPECTED", "/post_body", "post_body is allowed only for a registered POST request")

    return _result(errors, registry, source, request_plan)


def _load_failure(code: str, message: str) -> GateResult:
    error: GateError = {"code": code, "path": "", "message": message}
    return {
        "ok": False,
        "decision": "BLOCKED",
        "registry_version": None,
        "source": {"domain": None, "status": None, "provider": None, "api_host": None},
        "request": {"method": None, "endpoint": None, "operation": None, "expected_response_kind": None},
        "required_query_parameter_names": [],
        "errors": [error],
    }


def main(argv: Sequence[str]) -> int:
    """Evaluate a plan file locally and emit only safe machine-readable gate metadata."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_plan", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        request_plan = load_json_object(arguments.request_plan)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps(_load_failure("REQUEST_PLAN_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True))
        return 3
    try:
        registry = load_json_object(DEFAULT_REGISTRY_PATH)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps(_load_failure("REGISTRY_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True))
        return 3
    result = evaluate_request_plan(request_plan, registry)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
