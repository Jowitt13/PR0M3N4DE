"""Validate a per-run, user-authorized local presentation-media manifest offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - only an incomplete runtime install reaches this.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime
import validate_runtime_candidates

JsonObject = Mapping[str, Any]
SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
REFERENCE_ROOT = SKILL_ROOT / "references"
SCHEMA_PATH = REFERENCE_ROOT / "user-authorized-media.schema.json"
CANDIDATE_SCHEMA_PATH = REFERENCE_ROOT / "runtime-candidate-card.schema.json"
REGISTRY_PATH = REFERENCE_ROOT / "source-access-registry.json"
_CONTENT_MAGIC = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "application/pdf": b"%PDF-",
}
_KIND_CONTENT_TYPES = {
    "image": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "drawing": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "pdf": frozenset({"application/pdf"}),
}


class MediaValidationError(TypedDict):
    """One deterministic validation error for a local media manifest."""

    code: str
    path: str
    message: str


class MediaValidationResult(TypedDict):
    """Machine-readable result for one offline authorization and manifest pair."""

    ok: bool
    authorization_id: str | None
    manifest_id: str | None
    asset_count: int
    errors: list[MediaValidationError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object without changing it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(errors: list[MediaValidationError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _schema_errors(bundle: JsonObject, schema: JsonObject) -> list[MediaValidationError]:
    if Draft202012Validator is None or FormatChecker is None:
        return [{"code": "VALIDATOR_UNAVAILABLE", "path": "", "message": "jsonschema is required for user-authorized media validation"}]
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=checker)
    except Exception:  # pragma: no cover - the bundled Schema is separately tested.
        return [{"code": "SCHEMA_INVALID", "path": "", "message": "bundled media Schema is invalid"}]
    records: list[MediaValidationError] = []
    for error in sorted(validator.iter_errors(bundle), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(token) for token in error.absolute_path)
        _error(records, "SCHEMA_VALIDATION_FAILED", path, f"schema rule failed: {error.validator}")
    return records


def _candidate_index(candidate_set: JsonObject, errors: list[MediaValidationError]) -> tuple[list[str], dict[str, Mapping[str, Any]]]:
    try:
        candidate_schema = load_json_object(CANDIDATE_SCHEMA_PATH)
        registry = load_json_object(REGISTRY_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        _error(errors, "LOCAL_AUTHORITY_LOAD_FAILED", "", "candidate validation authorities could not be loaded")
        return [], {}
    candidate_result = validate_runtime_candidates.validate_candidate_set(candidate_set, candidate_schema, registry)
    if not candidate_result["ok"]:
        _error(errors, "CANDIDATE_SET_INVALID", "/candidate_set", "candidate set must pass its bundled local validator")
        return [], {}
    selection = _mapping(candidate_set.get("selection"))
    if selection is None or selection.get("state") != "HUMAN_SELECTED":
        _error(errors, "CANDIDATE_SELECTION_NOT_HUMAN", "/candidate_set/selection", "candidate set must contain an explicit human selection")
        return [], {}
    selected_ids = _strings(selection.get("selected_candidate_ids"))
    selected_by = selection.get("selected_by")
    if not is_human_record_label(selected_by):
        _error(errors, "CANDIDATE_SELECTOR_NOT_HUMAN", "/candidate_set/selection/selected_by", "candidate selection must identify a human, not an agent or model")
    candidates = candidate_set.get("candidates")
    index: dict[str, Mapping[str, Any]] = {}
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, Mapping) and isinstance(candidate.get("id"), str) and candidate["id"] in selected_ids:
                index[candidate["id"]] = candidate
    return selected_ids, index


def _sniff_content_type(data: bytes) -> str | None:
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return next((content_type for content_type, magic in _CONTENT_MAGIC.items() if data.startswith(magic)), None)


def _safe_asset_path(assets_root: Path, relative_path: object) -> Path | None:
    if not isinstance(relative_path, str):
        return None
    root = assets_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _validate_authorization(
    authorization: Mapping[str, Any],
    selected_ids: list[str],
    errors: list[MediaValidationError],
) -> None:
    if not is_human_record_label(authorization.get("authorized_by")):
        _error(errors, "AUTHORIZATION_NOT_HUMAN", "/authorization/authorized_by", "authorized_by must identify a human, not an agent or model")
    authorized_ids = _strings(authorization.get("selected_candidate_ids"))
    if authorized_ids != selected_ids:
        _error(errors, "AUTHORIZATION_SELECTION_MISMATCH", "/authorization/selected_candidate_ids", "authorization selected_candidate_ids must exactly match the current human candidate selection")


def _validate_assets(
    authorization: Mapping[str, Any],
    manifest: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    assets_root: Path,
    errors: list[MediaValidationError],
) -> None:
    try:
        resolved_assets_root = assets_root.resolve()
        resolved_assets_root.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        resolved_assets_root = assets_root.resolve()
    else:
        _error(errors, "ASSETS_ROOT_IN_REPOSITORY_FORBIDDEN", "/assets_root", "per-run media must not be stored inside the repository")
        return
    if not resolved_assets_root.is_dir():
        _error(errors, "ASSETS_ROOT_INVALID", "/assets_root", "assets_root must be an existing local directory")
        return
    manifest_project = manifest.get("project_id")
    if manifest_project != authorization.get("project_id"):
        _error(errors, "MANIFEST_PROJECT_MISMATCH", "/manifest/project_id", "manifest project_id must equal authorization project_id")
    if manifest.get("authorization_id") != authorization.get("authorization_id"):
        _error(errors, "MANIFEST_AUTHORIZATION_MISMATCH", "/manifest/authorization_id", "manifest authorization_id must equal the active authorization")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return
    for index, asset in enumerate(assets):
        if not isinstance(asset, Mapping):
            continue
        path = f"/manifest/assets/{index}"
        asset_id = asset.get("asset_id")
        if isinstance(asset_id, str):
            if asset_id in seen_ids:
                _error(errors, "ASSET_ID_DUPLICATE", f"{path}/asset_id", "asset_id must be unique within a manifest")
            seen_ids.add(asset_id)
        if asset.get("project_id") != authorization.get("project_id"):
            _error(errors, "ASSET_PROJECT_MISMATCH", f"{path}/project_id", "asset project_id must equal authorization project_id")
        if asset.get("user_authorization_id") != authorization.get("authorization_id"):
            _error(errors, "ASSET_AUTHORIZATION_MISMATCH", f"{path}/user_authorization_id", "asset user_authorization_id must equal the active authorization")
        candidate_id = asset.get("source_candidate_id")
        candidate = candidates.get(candidate_id) if isinstance(candidate_id, str) else None
        if candidate is None:
            _error(errors, "ASSET_CANDIDATE_UNSELECTED", f"{path}/source_candidate_id", "asset must resolve to a selected runtime candidate")
        else:
            source = _mapping(candidate.get("source"))
            if source is None or asset.get("source_locator") != source.get("canonical_locator"):
                _error(errors, "ASSET_LOCATOR_MISMATCH", f"{path}/source_locator", "asset source_locator must equal the selected candidate attribution locator")
        relative_path = asset.get("relative_path")
        if isinstance(relative_path, str):
            if relative_path in seen_paths:
                _error(errors, "ASSET_PATH_DUPLICATE", f"{path}/relative_path", "relative_path must be unique within a manifest")
            seen_paths.add(relative_path)
        local_path = _safe_asset_path(resolved_assets_root, relative_path)
        if local_path is None:
            _error(errors, "ASSET_PATH_INVALID", f"{path}/relative_path", "relative_path must stay below assets_root")
            continue
        if not local_path.is_file():
            _error(errors, "ASSET_FILE_MISSING", f"{path}/relative_path", "manifest asset file is not present below assets_root")
            continue
        try:
            data = local_path.read_bytes()
        except OSError:
            _error(errors, "ASSET_READ_FAILED", f"{path}/relative_path", "manifest asset file could not be read")
            continue
        if hashlib.sha256(data).hexdigest() != asset.get("sha256"):
            _error(errors, "ASSET_HASH_MISMATCH", f"{path}/sha256", "asset sha256 must match the local asset bytes")
        observed_type = _sniff_content_type(data)
        if observed_type != asset.get("content_type"):
            _error(errors, "CONTENT_TYPE_MISMATCH", f"{path}/content_type", "content_type must match the local asset magic bytes")
        asset_kind = asset.get("asset_kind")
        if isinstance(asset_kind, str) and asset.get("content_type") not in _KIND_CONTENT_TYPES.get(asset_kind, frozenset()):
            _error(errors, "ASSET_KIND_CONTENT_TYPE_MISMATCH", f"{path}/asset_kind", "asset_kind must permit the declared content_type")


def validate_user_authorized_media(
    authorization: JsonObject,
    manifest: JsonObject,
    candidate_set: JsonObject,
    schema: JsonObject,
    assets_root: Path,
) -> MediaValidationResult:
    """Validate offline authorization, selected candidates, and existing local media without mutation."""
    bundle: dict[str, object] = {"authorization": authorization, "manifest": manifest}
    errors = _schema_errors(bundle, schema)
    selected_ids, candidates = _candidate_index(candidate_set, errors)
    authorization_record = _mapping(authorization)
    manifest_record = _mapping(manifest)
    if authorization_record is not None:
        _validate_authorization(authorization_record, selected_ids, errors)
    if authorization_record is not None and manifest_record is not None:
        _validate_assets(authorization_record, manifest_record, candidates, assets_root, errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    authorization_id = authorization.get("authorization_id") if isinstance(authorization.get("authorization_id"), str) else None
    manifest_id = manifest.get("manifest_id") if isinstance(manifest.get("manifest_id"), str) else None
    assets = manifest.get("assets")
    return {"ok": not errors, "authorization_id": authorization_id, "manifest_id": manifest_id, "asset_count": len(assets) if isinstance(assets, list) else 0, "errors": errors}


def _load_failure(code: str) -> MediaValidationResult:
    return {"ok": False, "authorization_id": None, "manifest_id": None, "asset_count": 0, "errors": [{"code": code, "path": "", "message": "local JSON authority could not be loaded"}]}


def main(argv: Sequence[str]) -> int:
    """Emit a deterministic, read-only validation result for local media records."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("authorization", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("candidate_set", type=Path)
    parser.add_argument("--assets-root", required=True, type=Path)
    arguments = parser.parse_args(argv[1:])
    try:
        authorization = load_json_object(arguments.authorization)
        manifest = load_json_object(arguments.manifest)
        candidate_set = load_json_object(arguments.candidate_set)
        schema = load_json_object(SCHEMA_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps(_load_failure("LOCAL_AUTHORITY_LOAD_FAILED"), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    result = validate_user_authorized_media(authorization, manifest, candidate_set, schema, arguments.assets_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
