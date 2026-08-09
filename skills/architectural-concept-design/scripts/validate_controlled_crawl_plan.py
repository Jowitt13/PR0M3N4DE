"""Validate one finite controlled-crawl plan without making a network request."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import SplitResult, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
from check_source_access import load_json_object

JsonObject = Mapping[str, Any]
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "controlled-crawl-plan.schema.json"
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "source-access-registry.json"
CONTROLLED_STATUS = "controlled_crawl_allowed"
REQUIRED_CONTROLS = (
    "follow_redirects", "html_page_scrape", "custom_user_agent",
    "random_user_agent", "injected_browser_script", "fallback_fetch",
    "cookie_import", "credentials", "login_state", "media_download",
    "asset_scrape", "bulk_download", "raw_html_retention", "stealth",
    "browser_impersonation", "captcha_solving", "cloudflare_solving",
    "proxy_rotation", "curl_impersonate",
)
REQUIRED_BLOCKED_BEHAVIORS = frozenset({
    "login", "paywall", "access_control_bypass", "follow_redirects",
    "html_page_scrape", "custom_user_agent", "random_user_agent",
    "injected_browser_script", "fallback_fetch", "cookie_import",
    "credentials", "login_state", "stealth", "browser_impersonation",
    "captcha_solving", "cloudflare_solving", "proxy_rotation",
    "curl_impersonate", "redirect_bypass", "media_download", "asset_scrape",
    "bulk_download", "raw_html_retention",
})
REQUIRED_RENDERED_SHORT_TEXT_EXTRACTION = {
    "approved_plan_pages_only": True,
    "normal_browser_rendering_only": True,
    "short_text_fields_only": True,
    "raw_html_collection": False,
    "raw_html_retention": False,
    "raw_html_output": False,
    "page_script_retention": False,
    "cookie_retention": False,
    "browser_state_retention": False,
    "media_retention": False,
}
REQUIRED_SOURCE_FALSE_FLAGS = ("html_page_scrape", "media_download", "asset_scrape")


class PlanError(TypedDict):
    """Safe machine-readable validation failure."""

    code: str
    path: str
    message: str


class PlanValidationResult(TypedDict):
    """Offline validation result that deliberately omits private topic text and URLs."""

    ok: bool
    plan_id: str | None
    source_domain: str | None
    scheduled_page_count: int
    minimum_delay_ms: int | None
    errors: list[PlanError]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _error(errors: list[PlanError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _safe_https_url(value: object, errors: list[PlanError], path: str) -> SplitResult | None:
    raw = _string(value)
    if raw is None:
        _error(errors, "URL_INVALID", path, "URL must be a non-empty HTTPS URL")
        return None
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        _error(errors, "URL_INVALID", path, "URL cannot be parsed")
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        _error(errors, "URL_INVALID", path, "URL must be absolute HTTPS")
    if parsed.username or parsed.password or port is not None:
        _error(errors, "URL_CREDENTIAL_OR_PORT_FORBIDDEN", path, "credentials and non-default ports are forbidden")
    if parsed.query or parsed.fragment:
        _error(errors, "URL_QUERY_OR_FRAGMENT_FORBIDDEN", path, "query and fragment are forbidden")
    return parsed


def _matches_prefix(path: str, prefix: str) -> bool:
    return path.startswith(prefix) if prefix.endswith("/") else path == prefix


def _schema_errors(plan: JsonObject, schema: JsonObject, errors: list[PlanError]) -> None:
    try:
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception:
        _error(errors, "SCHEMA_INVALID", "", "controlled crawl plan Schema is invalid")
        return
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.absolute_path)):
        location = "/" + "/".join(str(item) for item in error.absolute_path)
        _error(errors, "SCHEMA_VALIDATION_FAILED", location, "plan does not conform to the controlled crawl Schema")


def _controlled_source(registry: JsonObject, domain: str | None, errors: list[PlanError]) -> Mapping[str, Any] | None:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        _error(errors, "REGISTRY_INVALID", "/sources", "registry sources must be an array")
        return None
    source = next((item for item in sources if isinstance(item, Mapping) and item.get("domain") == domain), None)
    if source is None:
        _error(errors, "SOURCE_UNREGISTERED", "/source_domain", "source is not registered and is blocked")
        return None
    if source.get("status") != CONTROLLED_STATUS:
        _error(errors, "SOURCE_NOT_CONTROLLED_CRAWL_ALLOWED", "/source_domain", "source is not approved for controlled crawl")
        return None
    return source


def _controlled_contract(source: Mapping[str, Any], errors: list[PlanError]) -> Mapping[str, Any] | None:
    contract = _mapping(source.get("controlled_crawl"))
    if contract is None:
        _error(errors, "CONTROLLED_CRAWL_CONTRACT_MISSING", "/source_domain", "approved source lacks controlled_crawl contract")
        return None
    seed_urls = contract.get("seed_urls")
    prefixes = contract.get("allowed_path_prefixes")
    if not isinstance(seed_urls, list) or not seed_urls or not all(isinstance(item, str) for item in seed_urls):
        _error(errors, "CONTROLLED_CRAWL_SEEDS_INVALID", "/source_domain", "controlled source needs non-empty seed URLs")
    if not isinstance(prefixes, list) or not prefixes or not all(isinstance(item, str) and item.startswith("/") and "*" not in item and "?" not in item and "#" not in item for item in prefixes):
        _error(errors, "CONTROLLED_CRAWL_PREFIXES_INVALID", "/source_domain", "controlled source needs exact non-wildcard path prefixes")
    for field in ("max_pages_per_run", "minimum_delay_ms"):
        if not isinstance(contract.get(field), int) or contract[field] < 1:
            _error(errors, "CONTROLLED_CRAWL_BUDGET_INVALID", f"/source_domain/{field}", f"controlled source {field} must be a positive integer")
    if type(contract.get("max_depth")) is not int or contract["max_depth"] < 0:
        _error(errors, "CONTROLLED_CRAWL_BUDGET_INVALID", "/source_domain/max_depth", "controlled source max_depth must be a non-negative integer")
    fields = contract.get("allowed_text_fields")
    if not isinstance(fields, list) or not fields or any(not isinstance(item, str) or not item.strip() or item == "raw_html" for item in fields):
        _error(errors, "CONTROLLED_CRAWL_CONTENT_INVALID", "/source_domain/allowed_text_fields", "controlled source must allow only named short fields, never raw_html")
    for flag in REQUIRED_SOURCE_FALSE_FLAGS:
        if source.get(flag) is not False:
            _error(errors, "CONTROLLED_CRAWL_SOURCE_FLAG_FORBIDDEN", f"/source_domain/{flag}", f"controlled source {flag} must be explicitly false")
    extraction = _mapping(contract.get("rendered_short_text_extraction"))
    if extraction is None or any(extraction.get(field) is not expected for field, expected in REQUIRED_RENDERED_SHORT_TEXT_EXTRACTION.items()):
        _error(errors, "CONTROLLED_CRAWL_RENDERED_TEXT_EXTRACTION_INVALID", "/source_domain/rendered_short_text_extraction", "controlled source must limit extraction to approved rendered pages and forbid raw HTML, scripts, cookies, browser state, and media retention")
    blocked = source.get("blocked_behaviors")
    if not isinstance(blocked, list) or not REQUIRED_BLOCKED_BEHAVIORS <= {item for item in blocked if isinstance(item, str)}:
        _error(errors, "CONTROLLED_CRAWL_PROHIBITIONS_INCOMPLETE", "/source_domain/blocked_behaviors", "controlled source must retain every runtime anti-bypass, access, HTML, and download prohibition")
    return contract


def validate_controlled_crawl_plan(plan: JsonObject, schema: JsonObject, registry: JsonObject) -> PlanValidationResult:
    """Validate *plan* against the fixed source registry without I/O or mutation."""

    errors: list[PlanError] = []
    _schema_errors(plan, schema, errors)
    plan_id = _string(plan.get("plan_id"))
    domain = _string(plan.get("source_domain"))
    pages = plan.get("requested_pages")
    page_list = pages if isinstance(pages, list) else []
    source = _controlled_source(registry, domain, errors)
    contract = _controlled_contract(source, errors) if source is not None else None

    if plan.get("registry_version") != registry.get("version"):
        _error(errors, "REGISTRY_VERSION_MISMATCH", "/registry_version", "plan registry version must match the fixed registry")
    confirmation = _mapping(plan.get("run_confirmation"))
    if confirmation is None or confirmation.get("confirmed") is not True:
        _error(errors, "RUN_CONFIRMATION_MISSING", "/run_confirmation", "a current human run confirmation is required")
    else:
        if not is_human_record_label(confirmation.get("confirmed_by")):
            _error(errors, "RUN_CONFIRMATION_NOT_HUMAN", "/run_confirmation/confirmed_by", "confirmed_by must name a human, not an agent or model")
        if not is_rfc3339_datetime(confirmation.get("confirmed_at")):
            _error(errors, "RUN_CONFIRMATION_TIMESTAMP_INVALID", "/run_confirmation/confirmed_at", "confirmed_at must be RFC 3339 with timezone")

    controls = _mapping(plan.get("request_controls"))
    if controls is None:
        _error(errors, "REQUEST_CONTROLS_INVALID", "/request_controls", "request controls are required")
    else:
        for control in REQUIRED_CONTROLS:
            if controls.get(control) is not False:
                _error(errors, "REQUEST_CONTROL_FORBIDDEN", f"/request_controls/{control}", f"{control} must be explicitly false")

    if contract is not None:
        max_pages = contract.get("max_pages_per_run")
        max_depth = contract.get("max_depth")
        delay = contract.get("minimum_delay_ms")
        if isinstance(max_pages, int) and len(page_list) > max_pages:
            _error(errors, "PAGE_BUDGET_EXCEEDED", "/requested_pages", "requested pages exceed source page budget")
        if plan.get("minimum_delay_ms") != delay:
            _error(errors, "DELAY_BUDGET_MISMATCH", "/minimum_delay_ms", "plan delay must exactly match source minimum delay")
        seeds = set(contract.get("seed_urls", []))
        prefixes = contract.get("allowed_path_prefixes", [])
        page_ids: dict[str, Mapping[str, Any]] = {}
        seen_urls: set[str] = set()
        for index, page_value in enumerate(page_list):
            page = _mapping(page_value)
            path = f"/requested_pages/{index}"
            if page is None:
                continue
            page_id = _string(page.get("id"))
            if page_id is None:
                continue
            if page_id in page_ids:
                _error(errors, "PAGE_ID_DUPLICATE", f"{path}/id", "requested page IDs must be unique")
            page_ids[page_id] = page
            url = _string(page.get("url"))
            if url is not None:
                if url in seen_urls:
                    _error(errors, "PAGE_URL_DUPLICATE", f"{path}/url", "requested page URLs must be unique")
                seen_urls.add(url)
            parsed = _safe_https_url(url, errors, f"{path}/url")
            if parsed is not None:
                if parsed.hostname != source.get("domain"):
                    _error(errors, "PAGE_HOST_OUT_OF_BOUNDARY", f"{path}/url", "requested page host must exactly match source domain")
                if not isinstance(prefixes, list) or not any(isinstance(prefix, str) and _matches_prefix(parsed.path, prefix) for prefix in prefixes):
                    _error(errors, "PAGE_PATH_OUT_OF_BOUNDARY", f"{path}/url", "requested page path is outside approved prefixes")
            depth = page.get("depth")
            parent = page.get("parent_page_id")
            if isinstance(max_depth, int) and isinstance(depth, int) and depth > max_depth:
                _error(errors, "DEPTH_BUDGET_EXCEEDED", f"{path}/depth", "requested page depth exceeds source budget")
            if depth == 0:
                if parent is not None:
                    _error(errors, "SEED_PARENT_FORBIDDEN", f"{path}/parent_page_id", "seed pages must have null parent_page_id")
                if url not in seeds:
                    _error(errors, "SEED_URL_NOT_REVIEWED", f"{path}/url", "depth-zero page must be an exact reviewed seed URL")
            elif isinstance(depth, int):
                parent_page = page_ids.get(parent) if isinstance(parent, str) else None
                if parent_page is None:
                    _error(errors, "PARENT_PAGE_UNKNOWN", f"{path}/parent_page_id", "non-seed page must name an earlier requested parent")
                elif parent_page.get("depth") != depth - 1:
                    _error(errors, "PARENT_DEPTH_INVALID", f"{path}/parent_page_id", "parent page must be exactly one depth closer to seed")

    return {
        "ok": not errors,
        "plan_id": plan_id,
        "source_domain": domain,
        "scheduled_page_count": len(page_list),
        "minimum_delay_ms": plan.get("minimum_delay_ms") if isinstance(plan.get("minimum_delay_ms"), int) else None,
        "errors": errors,
    }


def _load_failure(code: str, message: str) -> PlanValidationResult:
    return {"ok": False, "plan_id": None, "source_domain": None, "scheduled_page_count": 0, "minimum_delay_ms": None, "errors": [{"code": code, "path": "", "message": message}]}


def main(argv: Sequence[str]) -> int:
    """Emit one safe JSON result for a local plan file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        plan = load_json_object(arguments.plan)
        schema = load_json_object(DEFAULT_SCHEMA_PATH)
        registry = load_json_object(DEFAULT_REGISTRY_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps(_load_failure("PLAN_OR_AUTHORITY_LOAD_FAILED", "plan, Schema, or registry could not be loaded as local JSON"), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    result = validate_controlled_crawl_plan(plan, schema, registry)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
