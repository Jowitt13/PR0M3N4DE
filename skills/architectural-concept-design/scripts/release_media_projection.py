"""Build and validate the data-driven case-media projection for release archives."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, TypedDict


CASE_MEDIA_MANIFEST_PATH = PurePosixPath("references/case-media-manifest.json")
CASE_MEDIA_REFERENCE_PATH = PurePosixPath("references/case-media-assets.md")
CASE_MEDIA_DIRECTORY = PurePosixPath("assets/case-media")
RETAINED_MEDIA_ORIGIN = "team_original"


class ReleaseMediaProjection(TypedDict):
    """One source-manifest projection and its retained/excluded asset paths."""

    manifest: bytes
    retained_asset_paths: frozenset[PurePosixPath]
    excluded_asset_paths: frozenset[PurePosixPath]


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _load_json_object(raw: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("CASE_MEDIA_MANIFEST_INVALID: root must be an object")
    return value


def _asset_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValueError("CASE_MEDIA_MANIFEST_INVALID: asset_path must be a string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != CASE_MEDIA_DIRECTORY.parts or len(path.parts) < 3:
        raise ValueError("CASE_MEDIA_MANIFEST_INVALID: asset_path must stay under assets/case-media")
    return path


def project_release_media_manifest(raw: bytes) -> ReleaseMediaProjection:
    """Keep only team-original media while preserving the source manifest on disk."""

    value = _load_json_object(raw)
    media = value.get("media")
    if not isinstance(media, list):
        raise ValueError("CASE_MEDIA_MANIFEST_INVALID: media must be an array")
    retained: list[dict[str, Any]] = []
    retained_paths: set[PurePosixPath] = set()
    excluded_paths: set[PurePosixPath] = set()
    seen_paths: set[PurePosixPath] = set()
    for row in media:
        if not isinstance(row, dict):
            raise ValueError("CASE_MEDIA_MANIFEST_INVALID: media rows must be objects")
        path = _asset_path(row.get("asset_path"))
        if path in seen_paths:
            raise ValueError(f"CASE_MEDIA_MANIFEST_INVALID: duplicate asset_path {path.as_posix()}")
        seen_paths.add(path)
        if row.get("asset_origin") == RETAINED_MEDIA_ORIGIN:
            retained.append(dict(row))
            retained_paths.add(path)
        else:
            excluded_paths.add(path)
    value["media"] = retained
    return {
        "manifest": _canonical_json(value),
        "retained_asset_paths": frozenset(retained_paths),
        "excluded_asset_paths": frozenset(excluded_paths),
    }


def release_case_media_reference() -> bytes:
    """Return the release-only case-media reference without source-media history."""

    return (
        "# Release Case-media Assets\n\n"
        "This release archive contains only team-original local diagrams listed in "
        "`case-media-manifest.json`. The manifest is an asset-selection record, not an "
        "architectural-evidence record, license statement, or verification status.\n\n"
        "## Release-package boundary\n\n"
        "- Each retained asset is package-root-relative under `assets/case-media/` and has a "
        "SHA-256 recorded in the manifest.\n"
        "- Missing optional media leaves an editorial card without media; do not fetch, download, "
        "or substitute content during rendering.\n"
        "- Optional visuals do not create evidence, change a card record, establish rights, or "
        "prove architectural correctness.\n"
    ).encode("utf-8")


def validate_release_media_projection(files: Mapping[PurePosixPath, bytes]) -> list[str]:
    """Return fail-closed errors when an archive projection and its assets disagree."""

    manifest_raw = files.get(CASE_MEDIA_MANIFEST_PATH)
    if manifest_raw is None:
        return ["RELEASE_MEDIA_MANIFEST_MISSING"]
    try:
        value = _load_json_object(manifest_raw)
        media = value.get("media")
        if not isinstance(media, list):
            return ["RELEASE_MEDIA_MANIFEST_INVALID: media must be an array"]
        paths: set[PurePosixPath] = set()
        for row in media:
            if not isinstance(row, dict):
                return ["RELEASE_MEDIA_MANIFEST_INVALID: media rows must be objects"]
            path = _asset_path(row.get("asset_path"))
            if path in paths:
                return [f"RELEASE_MEDIA_MANIFEST_INVALID: duplicate asset_path {path.as_posix()}"]
            paths.add(path)
            if row.get("asset_origin") != RETAINED_MEDIA_ORIGIN:
                return [f"RELEASE_MEDIA_ORIGIN_FORBIDDEN: {path.as_posix()}"]
            if row.get("asset_source_locator") is not None or row.get("source_accessed_on") is not None:
                return [f"RELEASE_MEDIA_SOURCE_METADATA_FORBIDDEN: {path.as_posix()}"]
            asset = files.get(path)
            if asset is None:
                return [f"RELEASE_MEDIA_ASSET_MISSING: {path.as_posix()}"]
            if row.get("asset_sha256") != hashlib.sha256(asset).hexdigest():
                return [f"RELEASE_MEDIA_ASSET_HASH_MISMATCH: {path.as_posix()}"]
        packaged_assets = {path for path in files if path.parts[:2] == CASE_MEDIA_DIRECTORY.parts}
        if unexpected := sorted(packaged_assets - paths, key=lambda item: item.as_posix()):
            return [f"RELEASE_MEDIA_ASSET_UNMANIFESTED: {unexpected[0].as_posix()}"]
        return []
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        return [f"RELEASE_MEDIA_MANIFEST_INVALID: {error}"]
