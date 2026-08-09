"""Read-only end-to-end validation for a local architecture presentation handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict
from xml.etree import ElementTree

import validate_presentation_handoff
import validate_runtime_candidates
import validate_state

JsonObject = Mapping[str, Any]
REFERENCE_DIRECTORY = Path(__file__).resolve().parents[1] / "references"
LOCK_PATH = REFERENCE_DIRECTORY / "external-dependency-lock.json"
PPT_MASTER_MANIFEST_NAME = ".architecture-pre-design-external-dependency.json"
SLIDE_XML_RE = re.compile(r"^ppt/slides/slide[1-9][0-9]*\.xml$")
MAX_PPTX_ENTRIES = 500
MAX_PPTX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


class E2eError(TypedDict):
    """One deterministic cross-package evaluation error."""

    code: str
    path: str
    message: str


class E2eResult(TypedDict):
    """Machine-readable result emitted without rendering or mutation."""

    ok: bool
    outcome: Literal[
        "HANDOFF_READY",
        "PPTX_VALIDATED",
        "RENDERER_DEPENDENCY_UNAVAILABLE",
        "PPTX_VALIDATION_FAILED",
        "CONTRACT_VALIDATION_FAILED",
    ]
    errors: list[E2eError]
    checks: list[str]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object without modifying it."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def canonical_sha256(payload: JsonObject) -> str:
    """Return the fixed SHA-256 identity used by the handoff output reference."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _error(errors: list[E2eError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _summarize_upstream(
    result: Mapping[str, Any],
    code: str,
    path: str,
    errors: list[E2eError],
) -> None:
    if result.get("ok") is True:
        return
    _error(errors, code, path, "the referenced local contract validator did not pass")


def _validate_upstream_contracts(
    input_payload: JsonObject,
    output_payload: JsonObject,
    candidate_set: JsonObject,
    handoff: JsonObject,
    errors: list[E2eError],
) -> None:
    state_result, _ = validate_state.validate_state(input_payload, output_payload)
    _summarize_upstream(state_result, "STATE_VALIDATION_FAILED", "/state_package", errors)

    candidate_schema = validate_runtime_candidates.load_json_object(validate_runtime_candidates.SCHEMA_PATH)
    registry = validate_runtime_candidates.load_json_object(validate_runtime_candidates.REGISTRY_PATH)
    candidate_result = validate_runtime_candidates.validate_candidate_set(candidate_set, candidate_schema, registry)
    _summarize_upstream(candidate_result, "CANDIDATE_VALIDATION_FAILED", "/candidate_set", errors)

    handoff_schema = validate_presentation_handoff.load_json_object(validate_presentation_handoff.SCHEMA_PATH)
    handoff_result = validate_presentation_handoff.validate_presentation_handoff(handoff, handoff_schema)
    _summarize_upstream(handoff_result, "HANDOFF_VALIDATION_FAILED", "/handoff", errors)


def _candidate_index(candidate_set: JsonObject) -> dict[str, Mapping[str, Any]]:
    candidates = candidate_set.get("candidates")
    if not isinstance(candidates, list):
        return {}
    return {
        candidate_id: item
        for item in candidates if isinstance(item, Mapping)
        if isinstance((candidate_id := item.get("id")), str)
    }


def _validate_selection_transfer(candidate_set: JsonObject, handoff: JsonObject, errors: list[E2eError]) -> None:
    selection = _mapping(candidate_set.get("selection"))
    handoff_selection = _mapping(handoff.get("precedent_selection"))
    candidates_value = candidate_set.get("candidates")
    if not isinstance(candidates_value, list) or len(candidates_value) != 6:
        _error(errors, "CANDIDATE_COUNT_INVALID", "/candidate_set/candidates", "fixed end-to-end evaluation requires exactly six runtime candidates")
    if selection is None or handoff_selection is None:
        return
    if selection.get("state") != "HUMAN_SELECTED":
        _error(errors, "CANDIDATE_SELECTION_NOT_HUMAN", "/candidate_set/selection/state", "end-to-end evaluation requires HUMAN_SELECTED")
        return
    candidate_ids = _strings(selection.get("selected_candidate_ids"))
    handoff_ids = _strings(handoff_selection.get("selected_candidate_ids"))
    if candidate_ids != handoff_ids:
        _error(errors, "SELECTION_IDS_MISMATCH", "/handoff/precedent_selection/selected_candidate_ids", "handoff selected IDs must exactly match the runtime human selection order")
    if candidate_set.get("run_id") != handoff_selection.get("candidate_run_id"):
        _error(errors, "CANDIDATE_RUN_ID_MISMATCH", "/handoff/precedent_selection/candidate_run_id", "handoff candidate_run_id must match the candidate set")
    if candidate_set.get("registry_version") != handoff_selection.get("source_registry_version"):
        _error(errors, "REGISTRY_VERSION_MISMATCH", "/handoff/precedent_selection/source_registry_version", "handoff source_registry_version must match the candidate set")

    candidates = _candidate_index(candidate_set)
    records = handoff_selection.get("selected_precedents")
    if not isinstance(records, list):
        return
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        candidate_id = record.get("candidate_id")
        candidate = candidates.get(candidate_id) if isinstance(candidate_id, str) else None
        if candidate is None:
            _error(errors, "SELECTED_CANDIDATE_UNRESOLVED", f"/handoff/precedent_selection/selected_precedents/{index}/candidate_id", "selected precedent must resolve in the candidate set")
            continue
        identity = _mapping(candidate.get("project_identity"))
        source = _mapping(candidate.get("source"))
        operation = _mapping(candidate.get("spatial_operation"))
        expected = {
            "display_name": identity.get("name") if identity else None,
            "source_locator": source.get("canonical_locator") if source else None,
            "source_accessed_at": source.get("accessed_at") if source else None,
            "visual_strategy": candidate.get("visual_strategy"),
        }
        for field, value in expected.items():
            if record.get(field) != value:
                _error(errors, "SELECTED_PRECEDENT_TRANSFER_MISMATCH", f"/handoff/precedent_selection/selected_precedents/{index}/{field}", f"selected precedent {field} must equal candidate {candidate_id}")
        if operation is not None:
            handoff_operation = _mapping(record.get("spatial_operation"))
            for field in ("authorship", "summary", "falsification_condition"):
                if handoff_operation is None or handoff_operation.get(field) != operation.get(field):
                    _error(errors, "SELECTED_OPERATION_TRANSFER_MISMATCH", f"/handoff/precedent_selection/selected_precedents/{index}/spatial_operation/{field}", f"selected precedent operation {field} must equal candidate {candidate_id}")


def _records_by_id(output_payload: JsonObject, collection: str) -> set[str]:
    values = output_payload.get(collection)
    if not isinstance(values, list):
        return set()
    return {
        record_id
        for item in values if isinstance(item, Mapping)
        if isinstance((record_id := item.get("id")), str)
    }


def _validate_state_transfer(input_payload: JsonObject, output_payload: JsonObject, handoff: JsonObject, errors: list[E2eError]) -> None:
    state = _mapping(output_payload.get("state"))
    reference = _mapping(handoff.get("state_package"))
    if state is None or reference is None:
        return
    if handoff.get("project_id") != output_payload.get("project_id"):
        _error(errors, "PROJECT_ID_MISMATCH", "/handoff/project_id", "handoff project_id must equal output project_id")
    if reference.get("input_hash") != validate_state.compute_input_hash(input_payload):
        _error(errors, "HANDOFF_INPUT_HASH_MISMATCH", "/handoff/state_package/input_hash", "handoff input_hash must equal ADR-0001 canonical input hash")
    if reference.get("input_hash") != state.get("input_hash"):
        _error(errors, "STATE_INPUT_HASH_MISMATCH", "/handoff/state_package/input_hash", "handoff input_hash must equal output state input_hash")
    if reference.get("output_hash") != canonical_sha256(output_payload):
        _error(errors, "HANDOFF_OUTPUT_HASH_MISMATCH", "/handoff/state_package/output_hash", "handoff output_hash must equal canonical output-package SHA-256")

    chain = _mapping(handoff.get("architectural_chain"))
    if chain is None:
        return
    field_collections = {
        "brief_evidence_ids": "evidence",
        "site_constraint_ids": "constraints",
        "program_space_ids": "spaces",
        "circulation_relation_ids": "relations",
        "hypothesis_ids": "hypotheses",
        "option_ids": "options",
        "criterion_ids": "criteria",
    }
    for field, collection in field_collections.items():
        known_ids = _records_by_id(output_payload, collection)
        for index, entity_id in enumerate(_strings(chain.get(field))):
            if entity_id not in known_ids:
                _error(errors, "ARCHITECTURAL_CHAIN_UNRESOLVED", f"/handoff/architectural_chain/{field}/{index}", f"{entity_id} must resolve in output {collection}")
    if chain.get("decision_request_state") == "AWAITING_EXPLICIT_HUMAN_DESIGN_DECISION" and output_payload.get("decisions"):
        _error(errors, "DECK_ONLY_DECISION_FORBIDDEN", "/output/decisions", "pending handoff must not coexist with a pre-filled output D-xxx decision")


def _ppt_master_dependency(lock: JsonObject) -> Mapping[str, Any] | None:
    dependencies = lock.get("skill_dependencies")
    if not isinstance(dependencies, list):
        return None
    return next((item for item in dependencies if isinstance(item, Mapping) and item.get("id") == "ppt-master"), None)


def _expected_manifest(dependency: Mapping[str, Any]) -> dict[str, Any]:
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


def _git_blob_sha1(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _validate_renderer_receipt(renderer_root: Path | None, errors: list[E2eError], lock_path: Path) -> bool:
    if renderer_root is None:
        _error(errors, "RENDERER_DEPENDENCY_UNAVAILABLE", "/ppt-master-root", "--require-pptx requires a local pinned ppt-master installation root")
        return False
    try:
        lock = load_json_object(lock_path)
        dependency = _ppt_master_dependency(lock)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _error(errors, "RENDERER_DEPENDENCY_UNAVAILABLE", "/external-dependency-lock.json", str(error))
        return False
    if dependency is None or not renderer_root.is_dir():
        _error(errors, "RENDERER_DEPENDENCY_UNAVAILABLE", "/ppt-master-root", "ppt-master installation root is missing or lock entry is unavailable")
        return False
    for name in ("SKILL.md", "UPSTREAM_LICENSE", PPT_MASTER_MANIFEST_NAME):
        if not (renderer_root / name).is_file():
            _error(errors, "RENDERER_RECEIPT_INCOMPLETE", f"/ppt-master-root/{name}", "installed ppt-master receipt is incomplete")
    manifest_path = renderer_root / PPT_MASTER_MANIFEST_NAME
    if not manifest_path.is_file():
        return False
    try:
        manifest = load_json_object(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _error(errors, "RENDERER_RECEIPT_INVALID", f"/ppt-master-root/{PPT_MASTER_MANIFEST_NAME}", str(error))
        return False
    if manifest != _expected_manifest(dependency):
        _error(errors, "RENDERER_RECEIPT_MISMATCH", f"/ppt-master-root/{PPT_MASTER_MANIFEST_NAME}", "installation manifest must exactly match the locked ppt-master dependency")
        return False
    source_skill_path = dependency.get("source_skill_path")
    license_file = dependency.get("license_file")
    blobs = dependency.get("expected_blobs")
    if not isinstance(source_skill_path, str) or not isinstance(license_file, str) or not isinstance(blobs, list):
        _error(errors, "RENDERER_RECEIPT_INVALID", "/external-dependency-lock.json", "ppt-master lock entry is incomplete")
        return False
    for blob in blobs:
        if not isinstance(blob, Mapping) or not isinstance(blob.get("path"), str) or not isinstance(blob.get("sha"), str):
            _error(errors, "RENDERER_RECEIPT_INVALID", "/external-dependency-lock.json", "ppt-master expected blob is malformed")
            continue
        source_path = blob["path"]
        if source_path == license_file:
            installed_path = renderer_root / "UPSTREAM_LICENSE"
        elif source_path.startswith(f"{source_skill_path}/"):
            installed_path = renderer_root / source_path.removeprefix(f"{source_skill_path}/")
        else:
            _error(errors, "RENDERER_RECEIPT_INVALID", "/external-dependency-lock.json", "ppt-master expected blob is outside the copied skill or license")
            continue
        if not installed_path.is_file() or _git_blob_sha1(installed_path) != blob["sha"]:
            _error(errors, "RENDERER_RECEIPT_BLOB_MISMATCH", f"/ppt-master-root/{installed_path.name}", "installed ppt-master file must match its locked Git blob")
    return not errors


def _local_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _validate_pptx(pptx_path: Path | None, page_count: int, errors: list[E2eError]) -> bool:
    if pptx_path is None or not pptx_path.is_file():
        _error(errors, "PPTX_NOT_PROVIDED", "/pptx", "--require-pptx requires a local editable PPTX file")
        return False
    if pptx_path.suffix.lower() != ".pptx":
        _error(errors, "PPTX_SUFFIX_INVALID", "/pptx", "PPTX path must end in .pptx")
        return False
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            names = archive.namelist()
            uncompressed_bytes = sum(info.file_size for info in archive.infolist())
            if len(names) > MAX_PPTX_ENTRIES or uncompressed_bytes > MAX_PPTX_UNCOMPRESSED_BYTES:
                _error(errors, "PPTX_PACKAGE_LIMIT_EXCEEDED", "/pptx", "PPTX package exceeds the fixed local structural-audit limits")
                return False
            if "ppt/presentation.xml" not in names:
                _error(errors, "PPTX_PRESENTATION_MISSING", "/pptx", "PPTX must contain ppt/presentation.xml")
                return False
            presentation = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
            presentation_pages = [item for item in presentation.iter() if _local_name(item) == "sldId"]
            slide_parts = sorted(name for name in names if SLIDE_XML_RE.fullmatch(name))
            if len(presentation_pages) != page_count or len(slide_parts) != page_count:
                _error(errors, "PPTX_PAGE_COUNT_MISMATCH", "/pptx", f"PPTX must contain exactly {page_count} presentation and slide parts")
            for relationship_name in (name for name in names if name.endswith(".rels")):
                relationships = ElementTree.fromstring(archive.read(relationship_name))
                for relationship in relationships.iter():
                    if _local_name(relationship) != "Relationship":
                        continue
                    target = relationship.attrib.get("Target", "")
                    if relationship.attrib.get("TargetMode") == "External" or "://" in target:
                        _error(errors, "PPTX_EXTERNAL_RELATIONSHIP_FORBIDDEN", f"/pptx/{relationship_name}", "PPTX must not contain external relationship targets")
            for slide_name in slide_parts:
                slide = ElementTree.fromstring(archive.read(slide_name))
                editable = any(_local_name(item) in {"sp", "graphicFrame"} for item in slide.iter())
                if not editable:
                    _error(errors, "PPTX_EDITABLE_SHAPE_MISSING", f"/pptx/{slide_name}", "every slide must contain a native editable shape or graphic frame")
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        _error(errors, "PPTX_PACKAGE_INVALID", "/pptx", str(error))
    return not errors


def evaluate_presentation_e2e(
    input_payload: JsonObject,
    output_payload: JsonObject,
    candidate_set: JsonObject,
    handoff: JsonObject,
    *,
    renderer_root: Path | None = None,
    pptx_path: Path | None = None,
    require_pptx: bool = False,
    lock_path: Path = LOCK_PATH,
) -> E2eResult:
    """Cross-validate local handoff inputs and optionally audit a supplied PPTX."""

    errors: list[E2eError] = []
    _validate_upstream_contracts(input_payload, output_payload, candidate_set, handoff, errors)
    _validate_selection_transfer(candidate_set, handoff, errors)
    _validate_state_transfer(input_payload, output_payload, handoff, errors)
    checks = ["state", "runtime_candidates", "presentation_handoff", "cross_package_trace"]
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return {"ok": False, "outcome": "CONTRACT_VALIDATION_FAILED", "errors": errors, "checks": checks}

    if not require_pptx and renderer_root is None and pptx_path is None:
        return {"ok": True, "outcome": "HANDOFF_READY", "errors": [], "checks": checks}

    receipt_errors: list[E2eError] = []
    if not _validate_renderer_receipt(renderer_root, receipt_errors, lock_path):
        receipt_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return {"ok": False, "outcome": "RENDERER_DEPENDENCY_UNAVAILABLE", "errors": receipt_errors, "checks": checks}
    checks.append("ppt_master_receipt")
    if pptx_path is None and not require_pptx:
        return {"ok": True, "outcome": "HANDOFF_READY", "errors": [], "checks": checks}
    pptx_errors: list[E2eError] = []
    page_count = len(handoff.get("deck_framework", [])) if isinstance(handoff.get("deck_framework"), list) else 0
    if not _validate_pptx(pptx_path, page_count, pptx_errors):
        pptx_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return {"ok": False, "outcome": "PPTX_VALIDATION_FAILED", "errors": pptx_errors, "checks": checks}
    checks.append("pptx_structure")
    return {"ok": True, "outcome": "PPTX_VALIDATED", "errors": [], "checks": checks}


def _load_failure(message: str) -> E2eResult:
    return {
        "ok": False,
        "outcome": "CONTRACT_VALIDATION_FAILED",
        "errors": [{"code": "LOCAL_AUTHORITY_LOAD_FAILED", "path": "", "message": message}],
        "checks": [],
    }


def main(argv: Sequence[str]) -> int:
    """Emit one JSON result without network access, rendering, or writes."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("candidate_set", type=Path)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--ppt-master-root", type=Path)
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--require-pptx", action="store_true")
    arguments = parser.parse_args(argv[1:])
    try:
        result = evaluate_presentation_e2e(
            load_json_object(arguments.input),
            load_json_object(arguments.output),
            load_json_object(arguments.candidate_set),
            load_json_object(arguments.handoff),
            renderer_root=arguments.ppt_master_root,
            pptx_path=arguments.pptx,
            require_pptx=arguments.require_pptx,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = _load_failure(str(error))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
