"""Prepare an offline-only invocation plan for an isolated Crawl4AI runtime."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Literal, TypedDict

import bootstrap_external_skills as runtime_bootstrap
from check_source_access import load_json_object
from execute_controlled_crawl_replay import _schema_codes
from validate_controlled_crawl_plan import validate_controlled_crawl_plan


JsonObject = Mapping[str, Any]
SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
REFERENCES_ROOT = SKILL_ROOT / "references"
DEFAULT_PLAN_SCHEMA_PATH = REFERENCES_ROOT / "controlled-crawl-plan.schema.json"
DEFAULT_DRY_RUN_SCHEMA_PATH = REFERENCES_ROOT / "controlled-crawl-runtime-dry-run.schema.json"
DEFAULT_REGISTRY_PATH = REFERENCES_ROOT / "source-access-registry.json"
DEFAULT_LOCK_PATH = REFERENCES_ROOT / "external-dependency-lock.json"
PLAN_ID_RE = re.compile(r"^CCP-[0-9]{3,}$")
DOMAIN_RE = re.compile(r"^[a-z0-9.-]+$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PYVENV_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PYVENV_VERSION_INFO_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:\.final\.0)?$")
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_FIXED = 3


class DryRunResult(TypedDict):
    """Safe deterministic result for one local runtime dry-run preflight."""

    contract_version: Literal["1.0.0"]
    ok: bool
    outcome: Literal["ready_dry_run", "blocked", "dependency_unavailable"]
    plan_id: str | None
    source_domain: str | None
    registry_version: str | None
    runtime_id: str | None
    runtime_status: Literal["receipt_and_local_layout_validated_dry_run_only", "not_available_or_not_validated"]
    invocation_kind: Literal["isolated_runtime_dry_run_only", "none"]
    controls_confirmation: Literal["all_controls_false", "not_confirmed"]
    budget_confirmation: dict[str, int] | None
    reason_codes: list[str]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _safe_identity(value: object, pattern: re.Pattern[str]) -> str | None:
    return value if isinstance(value, str) and pattern.fullmatch(value) else None


def _identity(plan: JsonObject) -> tuple[str | None, str | None, str | None]:
    return (
        _safe_identity(plan.get("plan_id"), PLAN_ID_RE),
        _safe_identity(plan.get("source_domain"), DOMAIN_RE),
        _safe_identity(plan.get("registry_version"), VERSION_RE),
    )


def _result(
    plan: JsonObject,
    *,
    ok: bool,
    outcome: Literal["ready_dry_run", "blocked", "dependency_unavailable"],
    reason_codes: Sequence[str],
    runtime_id: str | None = None,
    ready: bool = False,
    budget_confirmation: dict[str, int] | None = None,
) -> DryRunResult:
    """Build a result without carrying input paths, topics, URLs, or secrets."""

    plan_id, source_domain, registry_version = _identity(plan)
    return {
        "contract_version": "1.0.0",
        "ok": ok,
        "outcome": outcome,
        "plan_id": plan_id,
        "source_domain": source_domain,
        "registry_version": registry_version,
        "runtime_id": runtime_id if isinstance(runtime_id, str) and re.fullmatch(r"^[a-z][a-z0-9-]*$", runtime_id) else None,
        "runtime_status": "receipt_and_local_layout_validated_dry_run_only" if ready else "not_available_or_not_validated",
        "invocation_kind": "isolated_runtime_dry_run_only" if ready else "none",
        "controls_confirmation": "all_controls_false" if ready else "not_confirmed",
        "budget_confirmation": budget_confirmation if ready else None,
        "reason_codes": sorted(set(reason_codes)),
    }


def _fallback_result() -> DryRunResult:
    return _result({}, ok=False, outcome="blocked", reason_codes=["DRY_RUN_RESULT_SCHEMA_INVALID"])


def _finalize(result: DryRunResult, schema: JsonObject) -> DryRunResult:
    """Validate every emitted result with the ARCH-043 schema validation helper."""

    if not _schema_codes(result, schema, "DryRunResult"):
        return result
    fallback = _fallback_result()
    _schema_codes(fallback, schema, "DryRunResult")
    return fallback


def _source_contract(registry: JsonObject, domain: str | None) -> Mapping[str, Any] | None:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        return None
    source = next((item for item in sources if isinstance(item, Mapping) and item.get("domain") == domain), None)
    return _mapping(source.get("controlled_crawl")) if source is not None else None


def _budget_confirmation(plan: JsonObject, registry: JsonObject) -> dict[str, int] | None:
    _, domain, _ = _identity(plan)
    contract = _source_contract(registry, domain)
    pages = plan.get("requested_pages")
    if contract is None or not isinstance(pages, list):
        return None
    values = {
        "scheduled_page_count": len(pages),
        "maximum_page_count": contract.get("max_pages_per_run"),
        "maximum_depth": contract.get("max_depth"),
        "minimum_delay_ms": contract.get("minimum_delay_ms"),
    }
    return values if all(isinstance(value, int) and value >= 0 for value in values.values()) else None


def _inside(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        return False


def _is_unc_runtime_root(value: str) -> bool:
    """Return whether a Windows UNC spelling was supplied without opening it."""

    return value.replace("/", "\\").startswith("\\\\")


def _windows_drive_type(drive_root: str) -> int | None:
    """Return the Windows drive type without opening a path below its root."""

    try:
        return int(ctypes.windll.kernel32.GetDriveTypeW(drive_root))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _uses_windows_drive_contract() -> bool:
    """Return whether the local platform has the locked runtime's Windows guard."""

    return os.name == "nt"


def _runtime_drive_code(candidate: Path) -> str | None:
    """Fail closed unless the supplied Windows root is an explicit fixed drive."""

    if not _uses_windows_drive_contract():
        return None
    if not candidate.drive or not candidate.anchor:
        return "RUNTIME_ROOT_DRIVE_TYPE_UNVERIFIABLE"
    drive_type = _windows_drive_type(candidate.anchor)
    if drive_type is None or drive_type in {DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR}:
        return "RUNTIME_ROOT_DRIVE_TYPE_UNVERIFIABLE"
    return None if drive_type == DRIVE_FIXED else "RUNTIME_ROOT_DRIVE_NOT_LOCAL"


def _is_symlink_or_reparse(path_status: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(path_status, "st_file_attributes", 0)
    return stat.S_ISLNK(path_status.st_mode) or bool(reparse_flag and attributes & reparse_flag)


def _path_lstat(path: Path) -> os.stat_result:
    """Read metadata without following a link through a locally testable boundary."""

    return os.lstat(path)


def _runtime_root_component_code(candidate: Path) -> str | None:
    """Inspect each existing local path component without following links."""

    components = [Path(candidate.anchor)]
    current = components[0]
    for part in candidate.parts[1:]:
        current = current / part
        components.append(current)
    for component in components:
        try:
            path_status = _path_lstat(component)
        except FileNotFoundError:
            return "RUNTIME_ROOT_MISSING"
        except OSError:
            return "RUNTIME_ROOT_PATH_METADATA_UNVERIFIABLE"
        if _is_symlink_or_reparse(path_status):
            return "RUNTIME_ROOT_SYMLINK_OR_REPARSE_FORBIDDEN"
    return None


def _resolved_runtime_root(candidate: Path) -> tuple[Path | None, str | None]:
    """Resolve and classify a root only after non-following component checks."""

    lexical = candidate.absolute()
    resolved = candidate.resolve(strict=False)
    if os.path.normcase(str(lexical)) != os.path.normcase(str(resolved)):
        return None, "RUNTIME_ROOT_PATH_ESCAPE_FORBIDDEN"
    protected = (REPOSITORY_ROOT.resolve(), SKILL_ROOT.resolve())
    if any(_inside(resolved, root) or _inside(root, resolved) for root in protected):
        return None, "RUNTIME_ROOT_REPOSITORY_FORBIDDEN"
    if not resolved.exists():
        return None, "RUNTIME_ROOT_MISSING"
    if not resolved.is_dir():
        return None, "RUNTIME_ROOT_NOT_DIRECTORY"
    return resolved, None


def _runtime_root(value: object) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, "RUNTIME_ROOT_REQUIRED"
    if _is_unc_runtime_root(value):
        return None, "RUNTIME_ROOT_NETWORK_SHARE_FORBIDDEN"
    candidate = Path(value)
    if not candidate.is_absolute():
        return None, "RUNTIME_ROOT_ABSOLUTE_REQUIRED"
    if drive_code := _runtime_drive_code(candidate):
        return None, drive_code
    if component_code := _runtime_root_component_code(candidate):
        return None, component_code
    return _resolved_runtime_root(candidate)


def _receipt_codes(receipt: Mapping[str, Any], expected: Mapping[str, Any]) -> list[str]:
    if receipt.get("receipt_version") != expected.get("receipt_version"):
        return ["RUNTIME_RECEIPT_VERSION_MISMATCH"]
    if receipt.get("python_version") != expected.get("python_version"):
        return ["RUNTIME_PYTHON_VERSION_MISMATCH"]
    received_distribution = _mapping(receipt.get("distribution"))
    expected_distribution = _mapping(expected.get("distribution"))
    if received_distribution != expected_distribution:
        if received_distribution is not None and expected_distribution is not None and received_distribution.get("sha256") != expected_distribution.get("sha256"):
            return ["RUNTIME_LOCK_HASH_MISMATCH"]
        return ["RUNTIME_DISTRIBUTION_VERSION_MISMATCH"]
    received_browser = _mapping(receipt.get("browser_engine"))
    expected_browser = _mapping(expected.get("browser_engine"))
    if received_browser != expected_browser:
        if received_browser is not None and expected_browser is not None and received_browser.get("chromium_revision") != expected_browser.get("chromium_revision"):
            return ["RUNTIME_BROWSER_REVISION_MISMATCH"]
        return ["RUNTIME_BROWSER_VERSION_MISMATCH"]
    for field in ("project_definition_sha256", "project_lock_sha256", "browser_lock_sha256", "browser_metadata_sha256"):
        if receipt.get(field) != expected.get(field):
            return ["RUNTIME_LOCK_HASH_MISMATCH"]
    if receipt != expected:
        return ["RUNTIME_RECEIPT_LOCK_MISMATCH"]
    return []


def _python_executable_code(python_path: Path) -> str | None:
    if not python_path.is_file():
        return "RUNTIME_PYTHON_EXECUTABLE_MISSING"
    try:
        with python_path.open("rb") as executable:
            prefix = executable.read(2)
    except OSError:
        return "RUNTIME_PYTHON_EXECUTABLE_INVALID"
    return None if prefix == b"MZ" else "RUNTIME_PYTHON_EXECUTABLE_INVALID"


def _pyvenv_config_code(config_path: Path, expected_version: str) -> str | None:
    if not config_path.is_file():
        return "RUNTIME_PYVENV_CONFIG_MISSING"
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "RUNTIME_PYVENV_CONFIG_INVALID"
    versions: list[str] = []
    for line in lines:
        key_value = line.split("=", maxsplit=1)
        if len(key_value) != 2:
            continue
        key, value = (part.strip() for part in key_value)
        if key == "version":
            if PYVENV_VERSION_RE.fullmatch(value) is None:
                return "RUNTIME_PYVENV_CONFIG_INVALID"
            versions.append(value)
        elif key == "version_info":
            if PYVENV_VERSION_INFO_RE.fullmatch(value) is None:
                return "RUNTIME_PYVENV_CONFIG_INVALID"
            versions.append(value.removesuffix(".final.0"))
    if not versions:
        return "RUNTIME_PYVENV_CONFIG_INVALID"
    return None if all(version == expected_version for version in versions) else "RUNTIME_LOCAL_PYTHON_VERSION_MISMATCH"


def _package_metadata_code(site_packages: Path, package: str, version: str, label: str) -> str | None:
    package_path = site_packages / package
    if not package_path.is_dir():
        return f"RUNTIME_{label}_PACKAGE_MISSING"
    metadata_path = site_packages / f"{package}-{version}.dist-info" / "METADATA"
    if not metadata_path.is_file():
        return f"RUNTIME_{label}_METADATA_MISSING"
    try:
        metadata = BytesParser(policy=policy.default).parsebytes(metadata_path.read_bytes())
    except (OSError, UnicodeDecodeError):
        return f"RUNTIME_{label}_METADATA_INVALID"
    if metadata.defects:
        return f"RUNTIME_{label}_METADATA_INVALID"
    received_name = metadata.get("Name")
    received_version = metadata.get("Version")
    if not isinstance(received_name, str) or not isinstance(received_version, str):
        return f"RUNTIME_{label}_METADATA_INVALID"
    if received_name.lower() != package.lower():
        return f"RUNTIME_{label}_METADATA_NAME_MISMATCH"
    return None if received_version == version else f"RUNTIME_{label}_METADATA_VERSION_MISMATCH"


def _runtime_content_code(runtime_root: Path, runtime: Mapping[str, Any]) -> str | None:
    browser = _mapping(runtime.get("browser_engine"))
    distribution = _mapping(runtime.get("distribution"))
    python_version = runtime.get("python_version")
    if browser is None or distribution is None or not isinstance(python_version, str):
        return "RUNTIME_LOCK_INVALID"
    python_path = runtime_root / ".venv" / "Scripts" / "python.exe"
    pyvenv_config_path = runtime_root / ".venv" / "pyvenv.cfg"
    site_packages = runtime_root / ".venv" / "Lib" / "site-packages"
    browser_path = runtime_root / "browsers" / str(browser.get("installed_directory"))
    distribution_name = distribution.get("name")
    distribution_version = distribution.get("version")
    browser_provider = browser.get("provider")
    browser_version = browser.get("package_version")
    if not all(isinstance(value, str) and value for value in (distribution_name, distribution_version, browser_provider, browser_version)):
        return "RUNTIME_LOCK_INVALID"
    if code := _python_executable_code(python_path):
        return code
    if code := _pyvenv_config_code(pyvenv_config_path, python_version):
        return code
    if code := _package_metadata_code(site_packages, distribution_name, distribution_version, "CRAWL4AI"):
        return code
    if code := _package_metadata_code(site_packages, browser_provider, browser_version, "PLAYWRIGHT"):
        return code
    if not browser_path.is_dir():
        return "RUNTIME_BROWSER_DIRECTORY_MISSING"
    try:
        runtime_bootstrap._verify_runtime_browser_metadata(runtime_root, runtime)
    except RuntimeError as error:
        message = str(error)
        if "revision" in message:
            return "RUNTIME_BROWSER_REVISION_MISMATCH"
        if "hash" in message:
            return "RUNTIME_BROWSER_METADATA_HASH_MISMATCH"
        return "RUNTIME_DEPENDENCY_UNAVAILABLE"
    return None


def _installed_runtime_receipt(runtime_root: Path, runtime: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str | None]:
    """Read one installed receipt only after all root and platform gates pass."""

    receipt_path = runtime_root / str(runtime["receipt_file"])
    if not receipt_path.is_file():
        return None, "RUNTIME_RECEIPT_MISSING"
    try:
        return runtime_bootstrap._json_object(receipt_path), None
    except (OSError, ValueError, json.JSONDecodeError):
        return None, "RUNTIME_RECEIPT_INVALID"


def prepare_controlled_crawl_runtime_dry_run(
    payload: JsonObject,
    plan_schema: JsonObject,
    dry_run_schema: JsonObject,
    registry: JsonObject,
    lock: JsonObject,
) -> DryRunResult:
    """Validate a bounded plan and isolated receipt without invoking a runtime."""

    plan = _mapping(payload.get("plan")) or {}
    plan_result = validate_controlled_crawl_plan(plan, plan_schema, registry)
    if not plan_result["ok"]:
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=[error["code"] for error in plan_result["errors"]]), dry_run_schema)

    mode = payload.get("execution_mode")
    if mode != "dry_run":
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["LIVE_EXECUTION_NOT_IMPLEMENTED"]), dry_run_schema)
    if _schema_codes(payload, dry_run_schema, "DryRunInput"):
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["DRY_RUN_INPUT_SCHEMA_INVALID"]), dry_run_schema)
    lock_errors = runtime_bootstrap.validate_lock(lock)
    if lock_errors:
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["RUNTIME_LOCK_INVALID"]), dry_run_schema)
    if payload.get("lock_version") != lock.get("lock_version"):
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["RUNTIME_LOCK_VERSION_MISMATCH"]), dry_run_schema)

    runtime = runtime_bootstrap._crawl4ai_runtime(lock)
    supported_platform = runtime.get("supported_platform")
    if not isinstance(supported_platform, str) or runtime_bootstrap._host_platform() != supported_platform:
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["RUNTIME_PLATFORM_UNSUPPORTED"]), dry_run_schema)
    root, root_code = _runtime_root(payload.get("runtime_root"))
    if root_code is not None:
        outcome: Literal["blocked", "dependency_unavailable"] = "dependency_unavailable" if root_code in {"RUNTIME_ROOT_REQUIRED", "RUNTIME_ROOT_MISSING", "RUNTIME_ROOT_NOT_DIRECTORY"} else "blocked"
        return _finalize(_result(plan, ok=False, outcome=outcome, reason_codes=[root_code]), dry_run_schema)
    expected_receipt = runtime_bootstrap._runtime_receipt_for(runtime)
    supplied_receipt = _mapping(payload.get("runtime_receipt"))
    if supplied_receipt is None:
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["RUNTIME_RECEIPT_MISSING"]), dry_run_schema)
    if codes := _receipt_codes(supplied_receipt, expected_receipt):
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=codes), dry_run_schema)

    installed_receipt, receipt_code = _installed_runtime_receipt(root, runtime)
    if receipt_code is not None:
        return _finalize(_result(plan, ok=False, outcome="dependency_unavailable", reason_codes=[receipt_code]), dry_run_schema)
    assert installed_receipt is not None
    if codes := _receipt_codes(installed_receipt, expected_receipt):
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=codes), dry_run_schema)
    if content_code := _runtime_content_code(root, runtime):
        return _finalize(_result(plan, ok=False, outcome="dependency_unavailable", reason_codes=[content_code]), dry_run_schema)
    if not runtime_bootstrap._runtime_receipt_matches(root, runtime):
        return _finalize(_result(plan, ok=False, outcome="dependency_unavailable", reason_codes=["RUNTIME_DEPENDENCY_UNAVAILABLE"]), dry_run_schema)

    budget = _budget_confirmation(plan, registry)
    if budget is None:
        return _finalize(_result(plan, ok=False, outcome="blocked", reason_codes=["RUNTIME_PLAN_AUTHORITY_INVALID"]), dry_run_schema)
    return _finalize(_result(
        plan,
        ok=True,
        outcome="ready_dry_run",
        reason_codes=["RUNTIME_RECEIPT_AND_LOCAL_LAYOUT_VALIDATED"],
        runtime_id=str(runtime["id"]),
        ready=True,
        budget_confirmation=budget,
    ), dry_run_schema)


def _load_failure(schema: JsonObject | None) -> DryRunResult:
    result = _result({}, ok=False, outcome="blocked", reason_codes=["DRY_RUN_AUTHORITY_LOAD_FAILED"])
    return _finalize(result, schema) if schema is not None else result


def main(argv: Sequence[str]) -> int:
    """Print a deterministic dry-run result from one local JSON input."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        dry_run_schema = load_json_object(DEFAULT_DRY_RUN_SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        dry_run_schema = None
    try:
        payload = load_json_object(arguments.input)
        plan_schema = load_json_object(DEFAULT_PLAN_SCHEMA_PATH)
        registry = load_json_object(DEFAULT_REGISTRY_PATH)
        lock = load_json_object(DEFAULT_LOCK_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        result = _load_failure(dry_run_schema)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    if dry_run_schema is None:
        result = _fallback_result()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    result = prepare_controlled_crawl_runtime_dry_run(payload, plan_schema, dry_run_schema, registry, lock)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
