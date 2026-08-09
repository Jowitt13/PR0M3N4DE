"""Build, verify, and clean-install a deterministic Skill release archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypedDict

from _rfc3339 import is_rfc3339_datetime


SKILL_ID = "architectural-concept-design"
MANIFEST_NAME = ".architecture-pre-design-release-manifest.json"
MANIFEST_VERSION = "1.0.0"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
GIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$",
)
ROOT_FILES = frozenset({"SKILL.md", "pyproject.toml", "uv.lock"})
PACKAGE_DIRECTORIES = frozenset({"assets", "references", "scripts"})
EXCLUDED_PARTS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache"})


class ReleaseResult(TypedDict):
    """Machine-readable result for one package operation."""

    ok: bool
    action: Literal["built", "verified", "installed", "already_installed", "failed"]
    manifest: dict[str, Any] | None
    errors: list[str]


def _result(
    ok: bool,
    action: Literal["built", "verified", "installed", "already_installed", "failed"],
    manifest: dict[str, Any] | None = None,
    errors: Sequence[str] = (),
) -> ReleaseResult:
    return {"ok": ok, "action": action, "manifest": manifest, "errors": list(errors)}


def _load_json_object(raw: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_excluded(relative: PurePosixPath) -> bool:
    return any(part in EXCLUDED_PARTS for part in relative.parts) or relative.suffix == ".pyc"


def _is_allowed_package_path(relative: PurePosixPath) -> bool:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return False
    if len(relative.parts) == 1:
        return relative.name in ROOT_FILES
    if relative.parts[0] == "agents":
        return relative.parts == ("agents", "openai.yaml")
    return relative.parts[0] in PACKAGE_DIRECTORIES


def _read_skill_version(source_root: Path) -> str:
    project_path = source_root / "pyproject.toml"
    try:
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"PYPROJECT_INVALID: {error}") from error
    metadata = project.get("project")
    version = metadata.get("version") if isinstance(metadata, Mapping) else None
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ValueError("PYPROJECT_INVALID: project.version must use SemVer")
    return version


def _collect_release_files(source_root: Path) -> list[tuple[PurePosixPath, bytes]]:
    if not source_root.is_dir():
        raise ValueError("SOURCE_ROOT_MISSING: Skill package directory is unavailable")
    files: list[tuple[PurePosixPath, bytes]] = []
    for path in sorted(source_root.rglob("*")):
        relative = PurePosixPath(path.relative_to(source_root).as_posix())
        if _is_excluded(relative):
            continue
        if path.is_symlink():
            raise ValueError("PACKAGE_SYMLINK_FORBIDDEN: release package must not contain symlinks")
        if not path.is_file():
            continue
        if not _is_allowed_package_path(relative):
            raise ValueError(f"PACKAGE_PATH_FORBIDDEN: {relative.as_posix()}")
        files.append((relative, path.read_bytes()))
    required = {
        PurePosixPath("SKILL.md"),
        PurePosixPath("pyproject.toml"),
        PurePosixPath("uv.lock"),
        PurePosixPath("agents/openai.yaml"),
    }
    present = {path for path, _ in files}
    if missing := sorted(required - present):
        raise ValueError(f"PACKAGE_REQUIRED_FILE_MISSING: {', '.join(path.as_posix() for path in missing)}")
    return files


def _archive_datetime(build_time: str) -> tuple[int, int, int, int, int, int]:
    if not is_rfc3339_datetime(build_time):
        raise ValueError("BUILD_TIME_INVALID: build time must be RFC 3339 with timezone")
    parsed = datetime.fromisoformat(build_time.replace("Z", "+00:00")).astimezone(timezone.utc)
    if parsed.year < 1980:
        raise ValueError("BUILD_TIME_INVALID: ZIP timestamps must be 1980 or later")
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second - parsed.second % 2)


def _manifest_for(
    files: Sequence[tuple[PurePosixPath, bytes]],
    *,
    source_commit: str,
    skill_version: str,
    build_time: str,
) -> dict[str, Any]:
    if not GIT_SHA_RE.fullmatch(source_commit):
        raise ValueError("SOURCE_COMMIT_INVALID: source commit must be a 40-character lowercase Git SHA")
    _archive_datetime(build_time)
    return {
        "manifest_version": MANIFEST_VERSION,
        "skill_id": SKILL_ID,
        "skill_version": skill_version,
        "source_commit": source_commit,
        "build_time": build_time,
        "files": [
            {"path": relative.as_posix(), "size": len(content), "sha256": _sha256(content)}
            for relative, content in files
        ],
    }


def _write_member(archive: zipfile.ZipFile, name: str, content: bytes, timestamp: tuple[int, int, int, int, int, int]) -> None:
    entry = zipfile.ZipInfo(filename=name, date_time=timestamp)
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_release_archive(source_root: Path, output: Path, *, source_commit: str, build_time: str) -> ReleaseResult:
    """Build one byte-stable archive from the declared runtime Skill contents."""

    try:
        resolved_source = source_root.resolve()
        if output.resolve().is_relative_to(resolved_source):
            raise ValueError("OUTPUT_INVALID: release archive must be outside the source Skill directory")
        files = _collect_release_files(source_root)
        skill_version = _read_skill_version(source_root)
        manifest = _manifest_for(files, source_commit=source_commit, skill_version=skill_version, build_time=build_time)
        timestamp = _archive_datetime(build_time)
        if output.suffix.lower() != ".zip":
            raise ValueError("OUTPUT_INVALID: release archive must use the .zip suffix")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
                for relative, content in files:
                    _write_member(archive, f"{SKILL_ID}/{relative.as_posix()}", content, timestamp)
                _write_member(archive, f"{SKILL_ID}/{MANIFEST_NAME}", _canonical_json(manifest), timestamp)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
        return _result(True, "built", manifest)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        return _result(False, "failed", errors=[str(error)])


def _manifest_errors(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        errors.append("MANIFEST_INVALID: manifest_version is unsupported")
    if manifest.get("skill_id") != SKILL_ID:
        errors.append("MANIFEST_INVALID: skill_id is incorrect")
    if not isinstance(manifest.get("skill_version"), str) or not SEMVER_RE.fullmatch(manifest["skill_version"]):
        errors.append("MANIFEST_INVALID: skill_version must use SemVer")
    if not isinstance(manifest.get("source_commit"), str) or not GIT_SHA_RE.fullmatch(manifest["source_commit"]):
        errors.append("MANIFEST_INVALID: source_commit must be a 40-character lowercase Git SHA")
    if not isinstance(manifest.get("build_time"), str) or not is_rfc3339_datetime(manifest["build_time"]):
        errors.append("MANIFEST_INVALID: build_time must be RFC 3339 with timezone")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("MANIFEST_INVALID: files must be a non-empty array")
        return errors
    seen: set[str] = set()
    for index, value in enumerate(files):
        if not isinstance(value, Mapping):
            errors.append(f"MANIFEST_INVALID: files[{index}] must be an object")
            continue
        path = value.get("path")
        size = value.get("size")
        checksum = value.get("sha256")
        relative = PurePosixPath(path) if isinstance(path, str) else PurePosixPath(".")
        if not isinstance(path, str) or not _is_allowed_package_path(relative) or _is_excluded(relative):
            errors.append(f"MANIFEST_INVALID: files[{index}].path is not a permitted runtime path")
        elif path in seen:
            errors.append(f"MANIFEST_INVALID: duplicate file path {path}")
        else:
            seen.add(path)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            errors.append(f"MANIFEST_INVALID: files[{index}].size must be a non-negative integer")
        if not isinstance(checksum, str) or not SHA256_RE.fullmatch(checksum):
            errors.append(f"MANIFEST_INVALID: files[{index}].sha256 must be a lowercase SHA-256")
    required = {"SKILL.md", "pyproject.toml", "uv.lock", "agents/openai.yaml"}
    if not errors and not required.issubset(seen):
        errors.append("MANIFEST_INVALID: required runtime package files are missing")
    return errors


def _safe_archive_name(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if not name or name.endswith("/") or path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        return None
    if path.parts[0] != SKILL_ID:
        return None
    return path


def verify_release_archive(archive_path: Path) -> ReleaseResult:
    """Verify a release archive's allowed paths, manifest, and every byte hash."""

    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                return _result(False, "failed", errors=["ARCHIVE_INVALID: duplicate ZIP member names are forbidden"])
            paths = [_safe_archive_name(name) for name in names]
            if any(path is None for path in paths):
                return _result(False, "failed", errors=["ARCHIVE_INVALID: ZIP contains unsafe or out-of-package member path"])
            manifest_member = f"{SKILL_ID}/{MANIFEST_NAME}"
            if manifest_member not in names:
                return _result(False, "failed", errors=["ARCHIVE_INVALID: release manifest is missing"])
            manifest = _load_json_object(archive.read(manifest_member))
            if errors := _manifest_errors(manifest):
                return _result(False, "failed", errors=errors)
            records = manifest["files"]
            assert isinstance(records, list)
            expected = {f"{SKILL_ID}/{record['path']}": record for record in records if isinstance(record, Mapping)}
            actual = set(names) - {manifest_member}
            if actual != set(expected):
                return _result(False, "failed", errors=["ARCHIVE_CONTENT_MISMATCH: archive members do not exactly match the manifest"])
            for name, record in expected.items():
                content = archive.read(name)
                if len(content) != record["size"] or _sha256(content) != record["sha256"]:
                    return _result(False, "failed", errors=[f"ARCHIVE_HASH_MISMATCH: {record['path']}"])
            return _result(True, "verified", manifest)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        return _result(False, "failed", errors=[f"ARCHIVE_INVALID: {error}"])


def verify_installed_skill(skill_root: Path) -> ReleaseResult:
    """Verify an extracted release directory without following generated environments."""

    manifest_path = skill_root / MANIFEST_NAME
    try:
        manifest = _load_json_object(manifest_path.read_bytes())
        if errors := _manifest_errors(manifest):
            return _result(False, "failed", errors=errors)
        records = manifest["files"]
        assert isinstance(records, list)
        expected = {str(record["path"]): record for record in records if isinstance(record, Mapping)}
        actual: set[str] = set()
        for path in skill_root.rglob("*"):
            if path.is_symlink():
                return _result(False, "failed", errors=["INSTALL_INVALID: installed Skill contains a symlink"])
            if not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(skill_root).as_posix())
            if relative.name == MANIFEST_NAME or _is_excluded(relative):
                continue
            actual.add(relative.as_posix())
        if actual != set(expected):
            return _result(False, "failed", errors=["INSTALL_CONTENT_MISMATCH: installed files do not exactly match the manifest"])
        for relative, record in expected.items():
            content = (skill_root / PurePosixPath(relative)).read_bytes()
            if len(content) != record["size"] or _sha256(content) != record["sha256"]:
                return _result(False, "failed", errors=[f"INSTALL_HASH_MISMATCH: {relative}"])
        return _result(True, "verified", manifest)
    except (OSError, ValueError, KeyError) as error:
        return _result(False, "failed", errors=[f"INSTALL_INVALID: {error}"])


def install_release_archive(archive_path: Path, skills_root: Path) -> ReleaseResult:
    """Atomically install one verified archive as a sibling Skill directory."""

    verification = verify_release_archive(archive_path)
    if not verification["ok"]:
        return verification
    manifest = verification["manifest"]
    assert manifest is not None
    destination = skills_root / SKILL_ID
    if destination.exists():
        installed = verify_installed_skill(destination)
        if installed["ok"] and installed["manifest"] == manifest:
            return _result(True, "already_installed", manifest)
        return _result(False, "failed", errors=["DESTINATION_CONFLICT: existing Skill does not match the verified release manifest"])
    stage: Path | None = None
    try:
        skills_root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{SKILL_ID}-", dir=skills_root))
        with zipfile.ZipFile(archive_path) as archive:
            for name in archive.namelist():
                path = _safe_archive_name(name)
                if path is None:
                    raise ValueError("ARCHIVE_INVALID: unsafe ZIP member during installation")
                relative = PurePosixPath(*path.parts[1:])
                target = stage.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        installed = verify_installed_skill(stage)
        if not installed["ok"] or installed["manifest"] != manifest:
            raise ValueError("INSTALL_INVALID: extracted package did not match the verified manifest")
        os.replace(stage, destination)
        return _result(True, "installed", manifest)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        return _result(False, "failed", errors=[str(error)])
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def main(argv: Sequence[str]) -> int:
    """Run one explicit build, verification, or clean-install operation."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--source-commit", required=True)
    build.add_argument("--build-time", required=True)
    build.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", required=True, type=Path)
    install = commands.add_parser("install")
    install.add_argument("--archive", required=True, type=Path)
    install.add_argument("--skills-root", required=True, type=Path)
    arguments = parser.parse_args(argv[1:])

    if arguments.command == "build":
        result = build_release_archive(arguments.source_root, arguments.output, source_commit=arguments.source_commit, build_time=arguments.build_time)
    elif arguments.command == "verify":
        result = verify_release_archive(arguments.archive)
    else:
        result = install_release_archive(arguments.archive, arguments.skills_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
