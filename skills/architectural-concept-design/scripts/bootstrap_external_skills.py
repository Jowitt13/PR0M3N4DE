"""Install reviewed external Skills and an optional isolated Crawl4AI runtime.

Normal Skill use never calls this bootstrap.  A dry run is local and read-only;
an apply requires an explicit human confirmation flag.  The Crawl4AI runtime is
copied as lock metadata into a separate target, then provisioned only there.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, TypedDict


SKILL_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = SKILL_ROOT / "references" / "external-dependency-lock.json"
SKILL_MANIFEST_NAME = ".architecture-pre-design-external-dependency.json"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
SHA1_RE = re.compile(r"^[a-f0-9]{40}$")
SAFE_PATH_RE = re.compile(r"^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]+$")
DEPENDENCY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
GITHUB_REPOSITORY_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")
RUNTIME_RECEIPT_VERSION = "1.0.0"
REQUIRED_PROHIBITED_IDS = {"curl-impersonate", "firecrawl", "scrapling"}
REQUIRED_RUNTIME_CAPABILITIES = {
    "undetected_browser_mode",
    "stealth_integration",
    "proxy_configuration",
    "custom_user_agent",
    "random_user_agent",
    "browser_script_injection",
    "fallback_fetch_function",
    "cookie_import",
    "credential_or_login_state",
    "captcha_solving",
    "cloudflare_solving",
    "browser_impersonation",
}

GitRunner = Callable[[Sequence[str]], str | bytes]
GitBlobBatchReader = Callable[[Path, Sequence[str]], Mapping[str, bytes]]
RuntimeRunner = Callable[[Sequence[str], Path, Mapping[str, str]], str]
RuntimeProcessQuiescence = Callable[[], str | None]
RuntimeCommitter = Callable[[Path, Path], None]

RUNTIME_ATOMIC_COMMIT_MAX_ATTEMPTS = 2
WINDOWS_ERROR_ACCESS_DENIED = 5
WINDOWS_DRIVE_FIXED = 3
PINNED_GIT_ACQUISITION_TIMEOUT_SECONDS = 120


class BootstrapDiagnostic(TypedDict):
    """A redacted, machine-readable installer failure detail."""

    code: str
    stage: str
    commit_attempts: int
    native_error: str


class BootstrapResult(TypedDict, total=False):
    """JSON-safe result for one explicit bootstrap invocation."""

    ok: bool
    dry_run: bool
    dependencies: list[dict[str, str]]
    errors: list[str]
    diagnostics: list[BootstrapDiagnostic]


class RuntimeInstallError(RuntimeError):
    """Carry a stable runtime-installation code without paths or commands."""

    def __init__(self, code: str, stage: str, *, commit_attempts: int = 0, native_error: str = "NONE") -> None:
        super().__init__(code)
        self.code = code
        self.diagnostic: BootstrapDiagnostic = {
            "code": code,
            "stage": stage,
            "commit_attempts": commit_attempts,
            "native_error": native_error,
        }


class PinnedGitAcquisitionError(RuntimeError):
    """Carry a redacted failure code for a lock-pinned Git object acquisition."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _json_object(path: Path) -> dict[str, Any]:
    """Load one finite JSON object without writing to it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON top-level value must be an object")
    return value


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha1(path: Path) -> str:
    """Return Git's blob id for the file bytes without applying filters."""

    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


def _safe_skill_path(value: object) -> Path | None:
    if not isinstance(value, str) or not SAFE_PATH_RE.fullmatch(value):
        return None
    candidate = (SKILL_ROOT / value).resolve()
    try:
        candidate.relative_to(SKILL_ROOT.resolve())
    except ValueError:
        return None
    return candidate


def _validate_skill_dependency(dependency: Mapping[str, Any], index: int, ids: set[str], destinations: set[str]) -> list[str]:
    errors: list[str] = []
    prefix = f"skill_dependencies[{index}]"
    dependency_id = dependency.get("id")
    if not isinstance(dependency_id, str) or not DEPENDENCY_ID_RE.fullmatch(dependency_id):
        errors.append(f"{prefix}.id must be a safe dependency ID")
    elif dependency_id in ids:
        errors.append(f"duplicate dependency id: {dependency_id}")
    else:
        ids.add(dependency_id)
    destination = dependency.get("destination_name")
    if not isinstance(destination, str) or not DEPENDENCY_ID_RE.fullmatch(destination):
        errors.append(f"{prefix}.destination_name must be a safe sibling name")
    elif destination in destinations:
        errors.append(f"duplicate destination_name: {destination}")
    else:
        destinations.add(destination)
    if not isinstance(dependency.get("optional"), bool):
        errors.append(f"{prefix}.optional must be boolean")
    repository = dependency.get("repository")
    if not isinstance(repository, str) or not GITHUB_REPOSITORY_RE.fullmatch(repository):
        errors.append(f"{prefix}.repository must be a pinned GitHub HTTPS repository")
    for field in ("commit", "tree_sha"):
        value = dependency.get(field)
        if not isinstance(value, str) or not SHA1_RE.fullmatch(value):
            errors.append(f"{prefix}.{field} must be a 40-character lowercase Git SHA")
    for field in ("license_file", "source_skill_path"):
        value = dependency.get(field)
        if not isinstance(value, str) or not SAFE_PATH_RE.fullmatch(value):
            errors.append(f"{prefix}.{field} must be a safe relative path")
    if dependency.get("runtime_environment") != "skill_only_no_runtime_environment":
        errors.append(f"{prefix}.runtime_environment must forbid runtime provisioning")
    blobs = dependency.get("expected_blobs")
    if not isinstance(blobs, list) or len(blobs) < 2:
        return errors + [f"{prefix}.expected_blobs must contain license and SKILL.md"]
    seen_paths: set[str] = set()
    for blob_index, blob_value in enumerate(blobs):
        blob = _mapping(blob_value)
        blob_prefix = f"{prefix}.expected_blobs[{blob_index}]"
        if blob is None:
            errors.append(f"{blob_prefix} must be an object")
            continue
        path = blob.get("path")
        sha = blob.get("sha")
        if not isinstance(path, str) or not SAFE_PATH_RE.fullmatch(path):
            errors.append(f"{blob_prefix}.path must be a safe relative path")
        elif path in seen_paths:
            errors.append(f"duplicate expected blob path: {path}")
        else:
            seen_paths.add(path)
        if not isinstance(sha, str) or not SHA1_RE.fullmatch(sha):
            errors.append(f"{blob_prefix}.sha must be a 40-character lowercase Git SHA")
    license_file = dependency.get("license_file")
    skill_path = dependency.get("source_skill_path")
    if isinstance(license_file, str) and license_file not in seen_paths:
        errors.append(f"{prefix}.expected_blobs must include license_file")
    if isinstance(skill_path, str) and f"{skill_path}/SKILL.md" not in seen_paths:
        errors.append(f"{prefix}.expected_blobs must include source_skill_path/SKILL.md")
    return errors


def _validate_runtime_metadata(runtime: Mapping[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    sources: dict[str, Path] = {}
    for field in ("project_definition", "project_lock", "browser_lock", "browser_metadata"):
        source = _safe_skill_path(runtime.get(field))
        if source is None:
            errors.append(f"{prefix}.{field} must be a safe Skill-relative path")
        elif not source.is_file():
            errors.append(f"{prefix}.{field} does not exist in the Skill package")
        else:
            sources[field] = source
    if len(sources) != 4:
        return errors
    try:
        project = tomllib.loads(sources["project_definition"].read_text(encoding="utf-8"))
        project_config = project.get("project")
        if not isinstance(project_config, Mapping):
            errors.append(f"{prefix}.project_definition missing [project]")
        else:
            if project_config.get("requires-python") != "==3.13.*":
                errors.append(f"{prefix}.project_definition must require Python 3.13 only")
            dependencies = _strings(project_config.get("dependencies"))
            if "crawl4ai==0.9.2" not in dependencies or "playwright==1.61.0" not in dependencies:
                errors.append(f"{prefix}.project_definition must pin crawl4ai and playwright")
        runtime_lock = tomllib.loads(sources["project_lock"].read_text(encoding="utf-8"))
        packages = runtime_lock.get("package")
        if not isinstance(packages, list):
            errors.append(f"{prefix}.project_lock missing package records")
        else:
            package_records = {
                item.get("name"): item
                for item in packages
                if isinstance(item, Mapping) and isinstance(item.get("name"), str)
            }
            if package_records.get("crawl4ai", {}).get("version") != "0.9.2":
                errors.append(f"{prefix}.project_lock must pin crawl4ai==0.9.2")
            if package_records.get("playwright", {}).get("version") != "1.61.0":
                errors.append(f"{prefix}.project_lock must pin playwright==1.61.0")
            crawl_wheels = package_records.get("crawl4ai", {}).get("wheels", [])
            if not isinstance(crawl_wheels, list) or not any(
                isinstance(wheel, Mapping) and wheel.get("hash") == "sha256:4efb2d0688aa3d66b48721a9031f7257bd2acb52b78d0a89d072741ac685f3f8"
                for wheel in crawl_wheels
            ):
                errors.append(f"{prefix}.project_lock must include the reviewed Crawl4AI wheel hash")
            playwright_wheels = package_records.get("playwright", {}).get("wheels", [])
            if not isinstance(playwright_wheels, list) or not any(
                isinstance(wheel, Mapping) and wheel.get("hash") == "sha256:35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597"
                for wheel in playwright_wheels
            ):
                errors.append(f"{prefix}.project_lock must include the reviewed Windows Playwright wheel hash")
        browser_lock = _json_object(sources["browser_lock"])
        browser = _mapping(browser_lock.get("browser"))
        wheel = _mapping(browser_lock.get("playwright_wheel"))
        if browser_lock.get("lock_version") != "1.0.0" or browser_lock.get("provider") != "playwright":
            errors.append(f"{prefix}.browser_lock must identify the reviewed Playwright lock")
        if browser_lock.get("playwright_version") != "1.61.0":
            errors.append(f"{prefix}.browser_lock must pin playwright==1.61.0")
        if browser is None or browser.get("name") != "chromium" or browser.get("revision") != "1228":
            errors.append(f"{prefix}.browser_lock must pin Chromium revision 1228")
        if wheel is None or wheel.get("sha256") != "35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597":
            errors.append(f"{prefix}.browser_lock must pin the reviewed Playwright wheel hash")
        if browser_lock.get("metadata_snapshot") != "playwright-browsers.json":
            errors.append(f"{prefix}.browser_lock must name the frozen Playwright metadata snapshot")
        if browser is not None and _sha256_file(sources["browser_metadata"]) != browser.get("browsers_json_sha256"):
            errors.append(f"{prefix}.browser_metadata must match the locked Playwright browsers.json hash")
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{prefix} metadata is unreadable: {error}")
    return errors


def _validate_runtime_dependency(runtime: Mapping[str, Any], index: int, ids: set[str]) -> list[str]:
    errors: list[str] = []
    prefix = f"runtime_dependencies[{index}]"
    runtime_id = runtime.get("id")
    if runtime_id != "crawl4ai-runtime":
        errors.append(f"{prefix}.id must be crawl4ai-runtime")
    elif runtime_id in ids:
        errors.append(f"duplicate dependency id: {runtime_id}")
    else:
        ids.add(runtime_id)
    if runtime.get("optional") is not True:
        errors.append(f"{prefix}.optional must be true so normal Skill use stays dependency-free")
    if runtime.get("runtime_kind") != "isolated_python_browser_runtime":
        errors.append(f"{prefix}.runtime_kind must be isolated_python_browser_runtime")
    if runtime.get("python_version") != "3.13.14":
        errors.append(f"{prefix}.python_version must pin 3.13.14")
    if runtime.get("receipt_file") != ".architecture-pre-design-crawl4ai-runtime.json":
        errors.append(f"{prefix}.receipt_file must pin the Crawl4AI receipt name")
    if runtime.get("supported_platform") != "windows-x86_64":
        errors.append(f"{prefix}.supported_platform must be windows-x86_64")
    distribution = _mapping(runtime.get("distribution"))
    if distribution is None or distribution.get("name") != "crawl4ai" or distribution.get("version") != "0.9.2":
        errors.append(f"{prefix}.distribution must pin crawl4ai==0.9.2")
    elif distribution.get("sha256") != "4efb2d0688aa3d66b48721a9031f7257bd2acb52b78d0a89d072741ac685f3f8":
        errors.append(f"{prefix}.distribution must pin the reviewed Crawl4AI wheel hash")
    browser = _mapping(runtime.get("browser_engine"))
    if browser is None or browser.get("provider") != "playwright" or browser.get("package_version") != "1.61.0":
        errors.append(f"{prefix}.browser_engine must pin Playwright 1.61.0")
    elif browser.get("chromium_revision") != "1228" or browser.get("installed_directory") != "chromium-1228":
        errors.append(f"{prefix}.browser_engine must pin Chromium revision 1228")
    capabilities = set(_strings(runtime.get("prohibited_capabilities")))
    missing_capabilities = sorted(REQUIRED_RUNTIME_CAPABILITIES - capabilities)
    if missing_capabilities:
        errors.append(f"{prefix}.prohibited_capabilities missing: {', '.join(missing_capabilities)}")
    commands = _strings(runtime.get("installation_commands"))
    expected_commands = [
        "uv python install 3.13.14",
        "uv sync --project <runtime-root> --python 3.13.14 --frozen --no-dev",
        "<runtime-root>/.venv/Scripts/python.exe -m playwright install chromium",
    ]
    if commands != expected_commands:
        errors.append(f"{prefix}.installation_commands must remain the reviewed explicit sequence")
    license_info = _mapping(runtime.get("upstream_license"))
    if license_info is None or license_info.get("spdx") != "Apache-2.0" or license_info.get("attribution_notice_required") is not True:
        errors.append(f"{prefix}.upstream_license must preserve Apache-2.0 and attribution notice requirements")
    errors.extend(_validate_runtime_metadata(runtime, prefix))
    return errors


def validate_lock(lock: Mapping[str, Any]) -> list[str]:
    """Return deterministic lock-contract errors without contacting a remote."""

    errors: list[str] = []
    if lock.get("lock_version") != "2.0.0":
        errors.append("lock_version must be 2.0.0")
    try:
        date.fromisoformat(str(lock.get("generated_at")))
    except ValueError:
        errors.append("generated_at must be an ISO calendar date")
    prohibited = set(_strings(lock.get("prohibited_dependency_ids")))
    missing_prohibitions = sorted(REQUIRED_PROHIBITED_IDS - prohibited)
    if missing_prohibitions:
        errors.append(f"prohibited_dependency_ids missing: {', '.join(missing_prohibitions)}")
    skill_dependencies = lock.get("skill_dependencies")
    if not isinstance(skill_dependencies, list) or not skill_dependencies:
        errors.append("skill_dependencies must be a non-empty array")
        skill_dependencies = []
    runtime_dependencies = lock.get("runtime_dependencies")
    if not isinstance(runtime_dependencies, list) or len(runtime_dependencies) != 1:
        errors.append("runtime_dependencies must contain exactly one reviewed runtime")
        runtime_dependencies = []
    ids: set[str] = set()
    destinations: set[str] = set()
    for index, item in enumerate(skill_dependencies):
        dependency = _mapping(item)
        if dependency is None:
            errors.append(f"skill_dependencies[{index}] must be an object")
            continue
        errors.extend(_validate_skill_dependency(dependency, index, ids, destinations))
    if [dependency.get("id") for dependency in skill_dependencies if isinstance(dependency, Mapping)] != ["ppt-master"]:
        errors.append("skill_dependencies must contain only the independently pinned ppt-master Skill")
    for index, item in enumerate(runtime_dependencies):
        runtime = _mapping(item)
        if runtime is None:
            errors.append(f"runtime_dependencies[{index}] must be an object")
            continue
        errors.extend(_validate_runtime_dependency(runtime, index, ids))
    return errors


def _selected_skill_dependencies(lock: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    dependencies = lock["skill_dependencies"]
    assert isinstance(dependencies, list)
    return [dependency for dependency in dependencies if isinstance(dependency, Mapping) and not dependency["optional"]]


def _crawl4ai_runtime(lock: Mapping[str, Any]) -> Mapping[str, Any]:
    runtimes = lock["runtime_dependencies"]
    assert isinstance(runtimes, list)
    runtime = runtimes[0]
    assert isinstance(runtime, Mapping)
    return runtime


def _skill_manifest_for(dependency: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "manifest_version": "1.0.0",
        "dependency_id": dependency["id"],
        "repository": dependency["repository"],
        "commit": dependency["commit"],
        "tree_sha": dependency["tree_sha"],
        "license_spdx": dependency["license_spdx"],
        "source_skill_path": dependency["source_skill_path"],
        "expected_blobs": dependency["expected_blobs"],
    }


def _installed_blob_path(destination: Path, dependency: Mapping[str, Any], source_path: str) -> Path | None:
    license_file = dependency.get("license_file")
    skill_path = dependency.get("source_skill_path")
    if not isinstance(license_file, str) or not isinstance(skill_path, str):
        return None
    if source_path == license_file:
        return destination / "UPSTREAM_LICENSE"
    prefix = f"{skill_path}/"
    if source_path.startswith(prefix):
        return destination / source_path.removeprefix(prefix)
    return None


def _installed_skill_blobs_match(destination: Path, dependency: Mapping[str, Any]) -> bool:
    """Prove the installed receipt files retain their exact locked Git bytes."""

    blobs = dependency.get("expected_blobs")
    if not isinstance(blobs, list):
        return False
    for blob in blobs:
        if not isinstance(blob, Mapping):
            return False
        source_path = blob.get("path")
        expected_sha = blob.get("sha")
        if not isinstance(source_path, str) or not isinstance(expected_sha, str):
            return False
        installed_path = _installed_blob_path(destination, dependency, source_path)
        if installed_path is None or not installed_path.is_file() or _git_blob_sha1(installed_path) != expected_sha:
            return False
    return True


def _skill_manifest_matches(destination: Path, dependency: Mapping[str, Any]) -> bool:
    manifest_path = destination / SKILL_MANIFEST_NAME
    if not destination.is_dir() or not manifest_path.is_file():
        return False
    try:
        return _json_object(manifest_path) == _skill_manifest_for(dependency) and _installed_skill_blobs_match(destination, dependency)
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _runtime_source_files(runtime: Mapping[str, Any]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for field in ("project_definition", "project_lock", "browser_lock"):
        source = _safe_skill_path(runtime[field])
        assert source is not None
        files[field] = source
    return files


def _browser_metadata_source(runtime: Mapping[str, Any]) -> Path:
    source = _safe_skill_path(runtime["browser_metadata"])
    assert source is not None
    return source


def _runtime_receipt_for(runtime: Mapping[str, Any]) -> dict[str, Any]:
    sources = _runtime_source_files(runtime)
    return {
        "receipt_version": RUNTIME_RECEIPT_VERSION,
        "runtime_id": runtime["id"],
        "python_version": runtime["python_version"],
        "distribution": runtime["distribution"],
        "browser_engine": runtime["browser_engine"],
        "project_definition_sha256": _sha256_file(sources["project_definition"]),
        "project_lock_sha256": _sha256_file(sources["project_lock"]),
        "browser_lock_sha256": _sha256_file(sources["browser_lock"]),
        "browser_metadata_sha256": _sha256_file(_browser_metadata_source(runtime)),
        "prohibited_capabilities": runtime["prohibited_capabilities"],
        "upstream_license": runtime["upstream_license"],
    }


def _runtime_receipt_matches(destination: Path, runtime: Mapping[str, Any]) -> bool:
    receipt_path = destination / str(runtime["receipt_file"])
    browser = _mapping(runtime["browser_engine"])
    assert browser is not None
    expected_browser = destination / "browsers" / str(browser["installed_directory"])
    python_path = destination / ".venv" / "Scripts" / "python.exe"
    if not destination.is_dir() or not receipt_path.is_file() or not expected_browser.is_dir() or not python_path.is_file():
        return False
    try:
        if _json_object(receipt_path) != _runtime_receipt_for(runtime):
            return False
        _verify_runtime_browser_metadata(destination, runtime)
        return True
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return False


def _run_supervised_process(
    command: Sequence[str],
    timeout: int | None,
    *,
    binary_stdout: bool = False,
) -> str | bytes:
    """Run one child process, terminating its whole tree if the timeout elapses.

    A stalled ``git`` fetch on Windows keeps a ``git-remote-https`` grandchild
    that holds the captured pipes, so ``subprocess`` cannot honour its own
    timeout and hangs forever.  Assigning the child to a Job Object lets the
    timeout terminate the entire process tree and fail closed instead.
    """

    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    job: _OwnedWindowsJob | None = None
    if os.name == "nt":
        try:
            job = _OwnedWindowsJob()
            job.assign(process)
        except RuntimeInstallError:
            job = None
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if job is not None:
                job.terminate()
            else:
                process.kill()
            try:
                process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                pass
            raise
        if process.returncode:
            error_output: str | bytes = stdout if binary_stdout else stdout.decode("utf-8")
            error_stderr: str | bytes = stderr if binary_stdout else stderr.decode("utf-8")
            raise subprocess.CalledProcessError(
                process.returncode,
                list(command),
                output=error_output,
                stderr=error_stderr,
            )
        # Drain stderr as bytes to prevent a full pipe from blocking a valid
        # worker result.  It is deliberately not decoded or returned on a
        # successful invocation.  The reviewed live worker opts into raw
        # stdout because its final observation has a separate private result
        # channel; all other callers retain the existing strict UTF-8 contract.
        if binary_stdout:
            return stdout
        return stdout.decode("utf-8").strip()
    finally:
        if job is not None:
            job.close()


def _production_git_runner(arguments: Sequence[str]) -> str | bytes:
    timeout = PINNED_GIT_ACQUISITION_TIMEOUT_SECONDS if "fetch" in arguments else None
    return _run_supervised_process(
        ["git", *arguments],
        timeout,
        binary_stdout=("ls-tree" in arguments or "show" in arguments),
    )


def _production_git_blob_batch_reader(checkout: Path, object_ids: Sequence[str]) -> Mapping[str, bytes]:
    """Read verified local Git blobs in one raw batch without worktree filters."""

    unique_ids = list(dict.fromkeys(object_ids))
    if not unique_ids or any(not SHA1_RE.fullmatch(object_id) for object_id in unique_ids):
        raise RuntimeError("locked Git blob batch request is invalid")
    process = subprocess.Popen(
        ["git", "-C", str(checkout), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate("".join(f"{object_id}\n" for object_id in unique_ids).encode("ascii"), timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise RuntimeError("locked Git blob batch timed out") from None
    if process.returncode:
        raise RuntimeError("locked Git blob batch failed")
    blobs: dict[str, bytes] = {}
    offset = 0
    for expected_id in unique_ids:
        line_end = stdout.find(b"\n", offset)
        if line_end < 0:
            raise RuntimeError("locked Git blob batch output is truncated")
        header = stdout[offset:line_end].split()
        offset = line_end + 1
        if len(header) != 3 or header[0].decode("ascii", "ignore") != expected_id or header[1] != b"blob":
            raise RuntimeError("locked Git blob batch output is invalid")
        try:
            size = int(header[2])
        except ValueError:
            raise RuntimeError("locked Git blob batch output has an invalid size") from None
        end = offset + size
        if size < 0 or end >= len(stdout) or stdout[end:end + 1] != b"\n":
            raise RuntimeError("locked Git blob batch content is truncated")
        blobs[expected_id] = stdout[offset:end]
        offset = end + 1
    if offset != len(stdout):
        raise RuntimeError("locked Git blob batch output has trailing data")
    return blobs


def _locked_commit_exists(checkout: Path, commit: str, git_runner: GitRunner) -> bool:
    """Return whether the exact locked object is locally present and a commit."""

    try:
        git_runner(["-C", str(checkout), "cat-file", "-e", f"{commit}^{{commit}}"])
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False
    return True


def _acquire_locked_commit(checkout: Path, dependency: Mapping[str, Any], git_runner: GitRunner) -> None:
    """Fetch only the exact lock pin, then prove it exists locally as a commit."""

    commit = str(dependency["commit"])
    try:
        git_runner(["-C", str(checkout), "fetch", "--no-tags", "--depth=1", "origin", commit])
    except subprocess.TimeoutExpired:
        raise PinnedGitAcquisitionError("PINNED_GIT_ACQUISITION_TIMEOUT") from None
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise PinnedGitAcquisitionError("PINNED_GIT_ACQUISITION_FAILED") from None
    if not _locked_commit_exists(checkout, commit, git_runner):
        raise PinnedGitAcquisitionError("PINNED_GIT_COMMIT_UNAVAILABLE")


class _WindowsJobAccounting(ctypes.Structure):
    """The small Job Object accounting record needed for child-process silence."""

    _fields_ = [
        ("total_user_time", ctypes.c_longlong),
        ("total_kernel_time", ctypes.c_longlong),
        ("this_period_total_user_time", ctypes.c_longlong),
        ("this_period_total_kernel_time", ctypes.c_longlong),
        ("total_page_fault_count", ctypes.c_uint32),
        ("total_processes", ctypes.c_uint32),
        ("active_processes", ctypes.c_uint32),
        ("total_terminated_processes", ctypes.c_uint32),
    ]


class _OwnedWindowsJob:
    """Track only descendants of one installer-started Windows process."""

    _BASIC_ACCOUNTING_INFORMATION = 1

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeInstallError("RUNTIME_OWNED_CHILD_PROCESS_TRACKING_UNAVAILABLE", "runtime_process_tracking")
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
            kernel32.CreateJobObjectW.restype = ctypes.c_void_p
            kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            kernel32.AssignProcessToJobObject.restype = ctypes.c_int
            kernel32.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
            kernel32.QueryInformationJobObject.restype = ctypes.c_int
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_int
            kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.TerminateJobObject.restype = ctypes.c_int
            handle = kernel32.CreateJobObjectW(None, None)
        except (AttributeError, OSError):
            raise RuntimeInstallError("RUNTIME_OWNED_CHILD_PROCESS_TRACKING_UNAVAILABLE", "runtime_process_tracking") from None
        if not handle:
            raise RuntimeInstallError("RUNTIME_OWNED_CHILD_PROCESS_TRACKING_UNAVAILABLE", "runtime_process_tracking")
        self._kernel32 = kernel32
        self._handle = handle

    def assign(self, process: subprocess.Popen[str]) -> None:
        process_handle = getattr(process, "_handle", None)
        if not process_handle or not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise RuntimeInstallError("RUNTIME_OWNED_CHILD_PROCESS_TRACKING_UNAVAILABLE", "runtime_process_tracking")

    def active_processes(self) -> int:
        accounting = _WindowsJobAccounting()
        if not self._kernel32.QueryInformationJobObject(
            self._handle,
            self._BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        ):
            raise RuntimeInstallError("RUNTIME_OWNED_CHILD_PROCESS_TRACKING_UNAVAILABLE", "runtime_process_tracking")
        return int(accounting.active_processes)

    def terminate(self) -> None:
        if self._handle:
            self._kernel32.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


class _OwnedRuntimeProcessTracker:
    """Run only installer commands in Jobs and prove their trees are quiet."""

    def __init__(self) -> None:
        self._jobs: list[_OwnedWindowsJob] = []

    def run(self, arguments: Sequence[str], cwd: Path, environment: Mapping[str, str]) -> str:
        job = _OwnedWindowsJob()
        try:
            process = subprocess.Popen(
                arguments,
                cwd=cwd,
                env={**os.environ, **environment},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                job.assign(process)
            except RuntimeInstallError:
                process.terminate()
                process.communicate()
                raise
            stdout, stderr = process.communicate()
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, list(arguments), output=stdout, stderr=stderr)
            self._jobs.append(job)
            return stdout.strip()
        except BaseException:
            job.close()
            raise

    def quiescence_code(self) -> str | None:
        try:
            return None if all(job.active_processes() == 0 for job in self._jobs) else "RUNTIME_OWNED_CHILD_PROCESS_ACTIVE"
        except RuntimeInstallError as error:
            return error.code

    def close(self) -> None:
        for job in self._jobs:
            job.close()
        self._jobs.clear()


def _verify_checkout(checkout: Path, dependency: Mapping[str, Any], git_runner: GitRunner) -> None:
    def git_output(*arguments: str) -> str:
        output = git_runner(["-C", str(checkout), *arguments])
        if not isinstance(output, str):
            raise RuntimeError(f"{dependency['id']}: Git text verification returned binary output")
        return output.strip()

    commit = str(dependency["commit"])
    if git_output("rev-parse", commit) != commit:
        raise RuntimeError(f"{dependency['id']}: verified commit does not match lock")
    if git_output("rev-parse", f"{commit}^{{tree}}") != dependency["tree_sha"]:
        raise RuntimeError(f"{dependency['id']}: verified tree does not match lock")
    for blob in dependency["expected_blobs"]:
        assert isinstance(blob, Mapping)
        path = blob["path"]
        if git_output("rev-parse", f"{commit}:{path}") != blob["sha"]:
            raise RuntimeError(f"{dependency['id']}: locked blob does not match: {path}")


def _safe_locked_tree_member_path(name: str) -> Path | None:
    """Accept only ordinary relative paths from a locked Git tree."""

    member_path = PurePosixPath(name)
    if not name or member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
        return None
    return Path(*member_path.parts)


def _locked_skill_tree_members(checkout: Path, dependency: Mapping[str, Any], git_runner: GitRunner) -> list[tuple[Path, str, str]]:
    """List regular source files from the verified commit without checkout filters."""

    source_path = str(dependency["source_skill_path"])
    commit = str(dependency["commit"])
    listing = git_runner(["-C", str(checkout), "ls-tree", "-r", "-z", commit, "--", source_path])
    if not isinstance(listing, bytes):
        raise RuntimeError(f"{dependency['id']}: locked Git tree listing must be read as raw bytes")
    members: list[tuple[Path, str, str]] = []
    prefix = f"{source_path}/"
    for record in listing.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_kind, encoded_sha = metadata.split(b" ", 2)
            full_path = encoded_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            raise RuntimeError(f"{dependency['id']}: locked Git tree listing is malformed") from None
        object_sha = encoded_sha.decode("ascii", "ignore")
        if object_kind != b"blob" or not SHA1_RE.fullmatch(object_sha) or not full_path.startswith(prefix):
            raise RuntimeError(f"{dependency['id']}: locked Git tree contains an unexpected member")
        relative = _safe_locked_tree_member_path(full_path.removeprefix(prefix))
        if relative is None or mode not in {b"100644", b"100755"}:
            raise RuntimeError(f"{dependency['id']}: locked Git tree contains an unsafe member")
        members.append((relative, full_path, object_sha))
    if not members or not any(relative == Path("SKILL.md") for relative, _, _ in members):
        raise RuntimeError(f"{dependency['id']}: verified source directory is incomplete")
    return members


def _copy_verified_skill(
    checkout: Path,
    destination: Path,
    dependency: Mapping[str, Any],
    git_runner: GitRunner,
    git_blob_batch_reader: GitBlobBatchReader | None,
) -> None:
    license_path = str(dependency["license_file"])
    commit = str(dependency["commit"])
    members = _locked_skill_tree_members(checkout, dependency, git_runner)
    license_id = git_runner(["-C", str(checkout), "rev-parse", f"{commit}:{license_path}"])
    if not isinstance(license_id, str) or not SHA1_RE.fullmatch(license_id.strip()):
        raise RuntimeError(f"{dependency['id']}: locked license blob id is invalid")
    license_id = license_id.strip()
    batch_blobs = git_blob_batch_reader(checkout, [license_id, *(object_sha for _, _, object_sha in members)]) if git_blob_batch_reader else None
    if batch_blobs is not None and any(object_id not in batch_blobs for object_id in [license_id, *(object_sha for _, _, object_sha in members)]):
        raise RuntimeError(f"{dependency['id']}: locked Git blob batch is incomplete")
    stage = destination.with_name(f".{destination.name}.staging-{os.getpid()}")
    if stage.exists():
        shutil.rmtree(stage)
    try:
        stage.mkdir()
        for relative, full_path, object_sha in members:
            content = batch_blobs[object_sha] if batch_blobs is not None else git_runner(["-C", str(checkout), "show", f"{commit}:{full_path}"])
            if not isinstance(content, bytes):
                raise RuntimeError(f"{dependency['id']}: locked Git blob must be read as raw bytes")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        license_bytes = batch_blobs[license_id] if batch_blobs is not None else git_runner(["-C", str(checkout), "show", f"{commit}:{license_path}"])
        if not isinstance(license_bytes, bytes):
            raise RuntimeError(f"{dependency['id']}: locked Git blob must be read as raw bytes")
        (stage / "UPSTREAM_LICENSE").write_bytes(license_bytes)
        if not (stage / "SKILL.md").is_file() or not _installed_skill_blobs_match(stage, dependency):
            raise RuntimeError(f"{dependency['id']}: copied receipt does not match locked Git blobs")
        (stage / SKILL_MANIFEST_NAME).write_text(
            json.dumps(_skill_manifest_for(dependency), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _host_platform() -> str:
    if sys.platform == "win32" and platform.machine().lower() in {"amd64", "x86_64"}:
        return "windows-x86_64"
    return f"{sys.platform}-{platform.machine().lower()}"


def _is_unc_path(path: Path) -> bool:
    """Reject a UNC spelling before any traversal below a remote share."""

    return str(path).replace("/", "\\").startswith("\\\\")


def _is_reparse_or_symlink(path_status: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(path_status, "st_file_attributes", 0)
    return stat.S_ISLNK(path_status.st_mode) or bool(reparse_flag and attributes & reparse_flag)


def _runtime_drive_code(path: Path) -> str | None:
    """Fail closed for a Windows root that is not explicitly on a fixed drive."""

    if _is_unc_path(path):
        return "RUNTIME_COMMIT_UNC_FORBIDDEN"
    if os.name != "nt":
        return None
    if not path.drive or not path.anchor:
        return "RUNTIME_COMMIT_DRIVE_UNVERIFIABLE"
    try:
        drive_type = int(ctypes.windll.kernel32.GetDriveTypeW(path.anchor))
    except (AttributeError, OSError, TypeError, ValueError):
        return "RUNTIME_COMMIT_DRIVE_UNVERIFIABLE"
    return None if drive_type == WINDOWS_DRIVE_FIXED else "RUNTIME_COMMIT_DRIVE_NOT_LOCAL"


def _runtime_existing_components_code(path: Path) -> str | None:
    """Inspect existing local components without following links or reparses."""

    if not path.is_absolute():
        return "RUNTIME_COMMIT_PATH_NOT_ABSOLUTE"
    if drive_code := _runtime_drive_code(path):
        return drive_code
    components = [Path(path.anchor)]
    current = components[0]
    for part in path.parts[1:]:
        current = current / part
        components.append(current)
    for component in components:
        try:
            path_status = os.lstat(component)
        except FileNotFoundError:
            continue
        except OSError:
            return "RUNTIME_COMMIT_PATH_METADATA_UNVERIFIABLE"
        if _is_reparse_or_symlink(path_status):
            return "RUNTIME_COMMIT_REPARSE_FORBIDDEN"
    return None


def _prepare_runtime_parent(parent: Path) -> None:
    """Create only a verified local parent without traversing an unsafe link."""

    if code := _runtime_existing_components_code(parent):
        raise RuntimeInstallError(code, "runtime_commit_path_validation")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise RuntimeInstallError("RUNTIME_COMMIT_PARENT_UNAVAILABLE", "runtime_commit_path_validation") from None
    if code := _runtime_existing_components_code(parent):
        raise RuntimeInstallError(code, "runtime_commit_path_validation")
    try:
        parent_status = os.lstat(parent)
    except OSError:
        raise RuntimeInstallError("RUNTIME_COMMIT_PARENT_UNAVAILABLE", "runtime_commit_path_validation") from None
    if not stat.S_ISDIR(parent_status.st_mode):
        raise RuntimeInstallError("RUNTIME_COMMIT_PARENT_UNAVAILABLE", "runtime_commit_path_validation")


def _runtime_target_preflight_code(destination: Path) -> str | None:
    """Reject unsafe target spelling before an idempotence receipt is inspected."""

    if code := _runtime_existing_components_code(destination.parent):
        return code
    if not os.path.lexists(destination):
        return None
    try:
        target_status = os.lstat(destination)
    except OSError:
        return "RUNTIME_COMMIT_PATH_METADATA_UNVERIFIABLE"
    return "RUNTIME_COMMIT_REPARSE_FORBIDDEN" if _is_reparse_or_symlink(target_status) else None


def _runtime_commit_path_code(stage: Path, destination: Path) -> str | None:
    """Prove that the exact staging-to-target commit is still locally safe."""

    if stage.parent != destination.parent:
        return "RUNTIME_COMMIT_PARENT_MISMATCH"
    for path in (destination.parent, stage):
        if code := _runtime_existing_components_code(path):
            return code
    try:
        stage_status = os.lstat(stage)
    except OSError:
        return "RUNTIME_COMMIT_STAGE_MISSING"
    if not stat.S_ISDIR(stage_status.st_mode) or _is_reparse_or_symlink(stage_status):
        return "RUNTIME_COMMIT_STAGE_UNSAFE"
    return "RUNTIME_COMMIT_TARGET_CONFLICT" if os.path.lexists(destination) else None


def _commit_runtime_stage(
    stage: Path,
    destination: Path,
    process_quiescence: RuntimeProcessQuiescence,
    committer: RuntimeCommitter,
) -> int:
    """Commit one verified stage, retrying only one transient Windows sharing error."""

    for attempt in range(1, RUNTIME_ATOMIC_COMMIT_MAX_ATTEMPTS + 1):
        if code := process_quiescence():
            raise RuntimeInstallError(code, "runtime_process_quiescence", commit_attempts=attempt - 1)
        if code := _runtime_commit_path_code(stage, destination):
            raise RuntimeInstallError(code, "runtime_atomic_commit", commit_attempts=attempt - 1)
        try:
            committer(stage, destination)
            return attempt
        except PermissionError as error:
            if getattr(error, "winerror", None) == WINDOWS_ERROR_ACCESS_DENIED and attempt < RUNTIME_ATOMIC_COMMIT_MAX_ATTEMPTS:
                continue
            native_error = "WINERROR_5" if getattr(error, "winerror", None) == WINDOWS_ERROR_ACCESS_DENIED else "PERMISSION_ERROR"
            raise RuntimeInstallError(
                "RUNTIME_ATOMIC_COMMIT_FAILED",
                "runtime_atomic_commit",
                commit_attempts=attempt,
                native_error=native_error,
            ) from None
        except OSError:
            raise RuntimeInstallError(
                "RUNTIME_ATOMIC_COMMIT_FAILED",
                "runtime_atomic_commit",
                commit_attempts=attempt,
                native_error="OSERROR",
            ) from None


def _write_runtime_receipt_after_commit(destination: Path, runtime: Mapping[str, Any]) -> None:
    """Write a receipt only after the runtime root has committed successfully."""

    receipt_path = destination / str(runtime["receipt_file"])
    temporary_receipt = receipt_path.with_name(f".{receipt_path.name}.staging-{os.getpid()}")
    if os.path.lexists(temporary_receipt):
        raise RuntimeInstallError("RUNTIME_RECEIPT_TEMPORARY_CONFLICT", "runtime_receipt_finalization")
    try:
        temporary_receipt.write_text(
            json.dumps(_runtime_receipt_for(runtime), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_receipt, receipt_path)
    except OSError:
        temporary_receipt.unlink(missing_ok=True)
        raise RuntimeInstallError("RUNTIME_RECEIPT_FINALIZATION_FAILED", "runtime_receipt_finalization") from None


def _verify_runtime_browser_metadata(stage: Path, runtime: Mapping[str, Any]) -> None:
    browser = _mapping(runtime["browser_engine"])
    assert browser is not None
    metadata_path = stage / ".venv" / "Lib" / "site-packages" / "playwright" / "driver" / "package" / "browsers.json"
    if not metadata_path.is_file():
        raise RuntimeError("crawl4ai-runtime: locked Playwright browser metadata is missing")
    if _sha256_file(_browser_metadata_source(runtime)) != browser["browsers_json_sha256"]:
        raise RuntimeError("crawl4ai-runtime: bundled Playwright metadata snapshot does not match lock")
    if _sha256_file(metadata_path) != browser["browsers_json_sha256"]:
        raise RuntimeError("crawl4ai-runtime: Playwright browser metadata hash does not match lock")
    metadata = _json_object(metadata_path)
    browsers = metadata.get("browsers")
    chromium = next((item for item in browsers if isinstance(item, Mapping) and item.get("name") == "chromium"), None) if isinstance(browsers, list) else None
    if chromium is None or chromium.get("revision") != browser["chromium_revision"] or chromium.get("browserVersion") != browser["chromium_version"]:
        raise RuntimeError("crawl4ai-runtime: Chromium revision does not match lock")
    expected_browser = stage / "browsers" / str(browser["installed_directory"])
    if not expected_browser.is_dir():
        raise RuntimeError("crawl4ai-runtime: installed Chromium directory does not match lock")


def _install_verified_runtime(
    destination: Path,
    runtime: Mapping[str, Any],
    runtime_runner: RuntimeRunner | None,
    host_platform: str,
    *,
    process_quiescence: RuntimeProcessQuiescence | None = None,
    committer: RuntimeCommitter | None = None,
) -> None:
    """Provision a staged runtime, then commit it only after owned processes exit."""

    if host_platform != runtime["supported_platform"]:
        raise RuntimeError(f"crawl4ai-runtime: supported platform is {runtime['supported_platform']}, found {host_platform}")
    if os.path.lexists(destination):
        raise RuntimeError("crawl4ai-runtime: runtime root exists without a matching receipt")
    _prepare_runtime_parent(destination.parent)
    stage = destination.with_name(f".{destination.name}.staging-{os.getpid()}")
    if os.path.lexists(stage):
        raise RuntimeInstallError("RUNTIME_COMMIT_STAGE_CONFLICT", "runtime_commit_path_validation")
    owned_processes: _OwnedRuntimeProcessTracker | None = None
    if runtime_runner is None:
        owned_processes = _OwnedRuntimeProcessTracker()
        runner = owned_processes.run
        quiet = owned_processes.quiescence_code
    else:
        runner = runtime_runner
        quiet = process_quiescence or (lambda: None)
    commit = committer or os.replace
    stage_created = False
    committed = False
    try:
        stage.mkdir(parents=True)
        stage_created = True
        for source in _runtime_source_files(runtime).values():
            shutil.copy2(source, stage / source.name)
        browser_directory = stage / "browsers"
        environment = {"PLAYWRIGHT_BROWSERS_PATH": str(browser_directory)}
        runner(["uv", "python", "install", str(runtime["python_version"])], stage, environment)
        runner(["uv", "sync", "--project", str(stage), "--python", str(runtime["python_version"]), "--frozen", "--no-dev"], stage, environment)
        python_path = stage / ".venv" / "Scripts" / "python.exe"
        if not python_path.is_file():
            raise RuntimeError("crawl4ai-runtime: uv sync did not create the locked Python runtime")
        runner([str(python_path), "-m", "playwright", "install", "chromium"], stage, environment)
        _verify_runtime_browser_metadata(stage, runtime)
        _commit_runtime_stage(stage, destination, quiet, commit)
        committed = True
        _write_runtime_receipt_after_commit(destination, runtime)
    except BaseException:
        if stage_created:
            shutil.rmtree(stage, ignore_errors=True)
        if committed:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        if owned_processes is not None:
            owned_processes.close()


def bootstrap_dependencies(
    lock: Mapping[str, Any],
    skills_root: Path | None,
    runtime_root: Path | None,
    *,
    dry_run: bool,
    include_crawl4ai_runtime: bool,
    git_runner: GitRunner | None = None,
    runtime_runner: RuntimeRunner | None = None,
    runtime_process_quiescence: RuntimeProcessQuiescence | None = None,
    runtime_committer: RuntimeCommitter | None = None,
    host_platform: str | None = None,
    git_blob_batch_reader: GitBlobBatchReader | None = None,
) -> BootstrapResult:
    """Plan or explicitly install the declared sibling Skill and runtime targets."""

    errors = validate_lock(lock)
    if errors:
        return {"ok": False, "dry_run": dry_run, "dependencies": [], "errors": errors}
    skills = _selected_skill_dependencies(lock)
    if skills and skills_root is None:
        return {"ok": False, "dry_run": dry_run, "dependencies": [], "errors": ["SKILLS_ROOT_REQUIRED: --skills-root is required for ppt-master"]}
    runtime = _crawl4ai_runtime(lock)
    if include_crawl4ai_runtime and runtime_root is None:
        return {"ok": False, "dry_run": dry_run, "dependencies": [], "errors": ["RUNTIME_ROOT_REQUIRED: --runtime-root is required with --include-crawl4ai-runtime"]}

    plans: list[dict[str, str]] = []
    for dependency in skills:
        assert skills_root is not None
        destination = skills_root / str(dependency["destination_name"])
        plans.append({
            "id": str(dependency["id"]),
            "kind": "sibling_skill",
            "action": "already_installed" if _skill_manifest_matches(destination, dependency) else "install",
            "version": str(dependency["commit"]),
        })
    if include_crawl4ai_runtime:
        assert runtime_root is not None
        distribution = _mapping(runtime["distribution"])
        assert distribution is not None
        if path_code := _runtime_target_preflight_code(runtime_root):
            return {"ok": False, "dry_run": dry_run, "dependencies": plans, "errors": [path_code]}
        plans.append({
            "id": "crawl4ai-runtime",
            "kind": "isolated_runtime",
            "action": "already_installed" if _runtime_receipt_matches(runtime_root, runtime) else "install",
            "version": str(distribution["version"]),
        })
    if dry_run:
        return {"ok": True, "dry_run": True, "dependencies": plans, "errors": []}

    git = git_runner or _production_git_runner
    blob_batch_reader = git_blob_batch_reader or (_production_git_blob_batch_reader if git_runner is None else None)
    if include_crawl4ai_runtime and plans[-1]["action"] != "already_installed":
        assert runtime_root is not None
        if os.path.lexists(runtime_root):
            return {"ok": False, "dry_run": False, "dependencies": plans, "errors": ["crawl4ai-runtime: runtime root exists without a matching receipt"]}
        actual_platform = host_platform or _host_platform()
        if actual_platform != runtime["supported_platform"]:
            return {"ok": False, "dry_run": False, "dependencies": plans, "errors": [f"crawl4ai-runtime: supported platform is {runtime['supported_platform']}, found {actual_platform}"]}
    try:
        assert skills_root is not None
        skills_root.parent.mkdir(parents=True, exist_ok=True)
        skills_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="architecture-skill-bootstrap-", dir=skills_root.parent) as temporary:
            temporary_root = Path(temporary)
            for dependency, plan in zip(skills, plans, strict=False):
                if plan["id"] != dependency["id"] or plan["action"] == "already_installed":
                    continue
                destination = skills_root / str(dependency["destination_name"])
                if destination.exists():
                    raise RuntimeError(f"{dependency['id']}: destination exists without matching manifest")
                checkout = temporary_root / str(dependency["id"])
                git(["init", "--quiet", str(checkout)])
                git(["-C", str(checkout), "remote", "add", "origin", str(dependency["repository"])])
                if not _locked_commit_exists(checkout, str(dependency["commit"]), git):
                    _acquire_locked_commit(checkout, dependency, git)
                if not _locked_commit_exists(checkout, str(dependency["commit"]), git):
                    raise PinnedGitAcquisitionError("PINNED_GIT_COMMIT_UNAVAILABLE")
                _verify_checkout(checkout, dependency, git)
                _copy_verified_skill(checkout, destination, dependency, git, blob_batch_reader)
        if include_crawl4ai_runtime and plans[-1]["action"] != "already_installed":
            assert runtime_root is not None
            _install_verified_runtime(
                runtime_root,
                runtime,
                runtime_runner,
                host_platform or _host_platform(),
                process_quiescence=runtime_process_quiescence,
                committer=runtime_committer,
            )
        return {"ok": True, "dry_run": False, "dependencies": plans, "errors": []}
    except RuntimeInstallError as error:
        return {
            "ok": False,
            "dry_run": False,
            "dependencies": plans,
            "errors": [error.code],
            "diagnostics": [error.diagnostic],
        }
    except PinnedGitAcquisitionError as error:
        return {"ok": False, "dry_run": False, "dependencies": plans, "errors": [error.code]}
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        return {"ok": False, "dry_run": False, "dependencies": plans, "errors": [str(error)]}


def main(argv: Sequence[str]) -> int:
    """Print one machine-readable plan/result without accepting secret inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-reviewed-plan", action="store_true", help="required for any non-dry-run installation")
    parser.add_argument("--include-crawl4ai-runtime", action="store_true", help="include the separately provisioned Crawl4AI runtime")
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    arguments = parser.parse_args(argv[1:])
    if not arguments.dry_run and not arguments.apply_reviewed_plan:
        result: BootstrapResult = {
            "ok": False,
            "dry_run": False,
            "dependencies": [],
            "errors": ["HUMAN_CONFIRMATION_REQUIRED: run --dry-run, review the plan, then repeat with --apply-reviewed-plan"],
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    try:
        lock = _json_object(arguments.lock)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {"ok": False, "dry_run": arguments.dry_run, "dependencies": [], "errors": [f"LOCK_LOAD_FAILED: {error}"]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    result = bootstrap_dependencies(
        lock,
        arguments.skills_root,
        arguments.runtime_root,
        dry_run=arguments.dry_run,
        include_crawl4ai_runtime=arguments.include_crawl4ai_runtime,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
