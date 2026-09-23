"""Shared design-data maturity, staleness, and public-wording enforcement (ARCH-124, R1).

Single authority for the design-data ledger: structural validation, deterministic
freshness recomputation against ACTUAL files, independent human-review
verification, copy-slot binding, delivery verification, and the release verdict
consumed by the unique Node release entry. Renderer, E2E, and release paths must
call this module instead of re-implementing any freshness judgment.

R1 anchors: data binds to actual source documents through JSON pointers (a
ledger-only value edit cannot pass), artifacts bind to builder-owned provenance
sidecars (a consistent ledger edit without a rebuild cannot pass), copy slots
bind to the actual handoff text (deleted or edited copy fails closed), and the
human freeze/review confirmation is a separate caller-supplied receipt whose
hashes void it on any relevant change. Freshness is never stored and never
trusted from a receipt: every verification recomputes. No network, no clock
reads, no subprocesses, and no in-place file modification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    SchemaError = Exception  # type: ignore[assignment,misc]

from _rfc3339 import is_rfc3339_datetime
from presentation_audience_copy import is_human_reviewer_label
from validate_state import JsonObject, compute_input_hash, stale_entity_records

SKILL_ROOT = Path(__file__).resolve().parents[1]
LEDGER_SCHEMA_PATH = SKILL_ROOT / "references" / "design-data-maturity.schema.json"
HUMAN_REVIEW_SCHEMA_PATH = SKILL_ROOT / "references" / "design-data-human-review.schema.json"

LEDGER_CONTRACT_VERSION = "2.0.0"
RECEIPT_VERSION = "2.0.0"
REVIEW_RULES_VERSION = "1.0.0"
VALIDATOR_CONTRACT_VERSION = "1.0.0"
HANDOFF_PRESENTATION_ROLE = "presentation_handoff"

PHYSICAL_ARTIFACT_KINDS = frozenset({
    "svg_editable", "svg_compiled", "svg_preview", "svg_manifest",
    "pptx_deck", "delivery_package",
})
VALUE_TEMPLATE_PLACEHOLDER = "{value}"


class LedgerError(TypedDict):
    code: str
    path: str
    message: str
    related_ids: list[str]
    severity: str


def _error(code: str, path: str, message: str, related_ids: Sequence[str] = ()) -> LedgerError:
    return {
        "code": code,
        "path": path,
        "message": message,
        "related_ids": list(related_ids),
        "severity": "ERROR",
    }


def _parse_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def load_json_object(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_parse_constant)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a top-level JSON object")
    return payload


def canonical_data_hash(value: Any) -> str:
    """Canonical SHA-256 of one data value; identical to the ADR-0001 input hash."""
    return compute_input_hash({"value": value})


def canonical_ledger_hash(ledger: JsonObject) -> str:
    """Order-insensitive canonical hash: keyed record collections sort by stable ID."""
    normalized = dict(ledger)
    for key, id_field in (("data_records", "data_id"), ("artifacts", "artifact_id"), ("copy_bindings", "json_pointer"), ("change_events", "event_id")):
        records = normalized.get(key)
        if isinstance(records, list):
            normalized[key] = sorted(
                (record for record in records if isinstance(record, Mapping)),
                key=lambda record: str(record.get(id_field, "")),
            )
    return canonical_data_hash(normalized)


def canonical_copy_bindings_digest(ledger: JsonObject) -> str:
    """Order-insensitive canonical digest of the copy_bindings section."""
    bindings = sorted(
        (record for record in _records(ledger, "copy_bindings")),
        key=lambda record: (str(record.get("json_pointer", "")), str(record.get("page_id", ""))),
    )
    return canonical_data_hash(bindings)


def artifact_input_bindings_digest(ledger: JsonObject, artifact_id: str) -> str:
    """Canonical digest of one artifact's build-time input binding over current data hashes."""
    current = _current_data_hashes(ledger)
    for record in _records(ledger, "artifacts"):
        if record.get("artifact_id") == artifact_id:
            built_ids = sorted((record.get("built_from") or {}).get("data_ids", []) or [])
            return canonical_data_hash([
                {"data_id": bound_id, "canonical_sha256": current.get(bound_id)}
                for bound_id in built_ids
            ])
    return canonical_data_hash([])


def _ledger_schema() -> JsonObject:
    return load_json_object(LEDGER_SCHEMA_PATH)


def _human_review_schema() -> JsonObject:
    return load_json_object(HUMAN_REVIEW_SCHEMA_PATH)


def _format_checker() -> Any:
    from jsonschema import FormatChecker

    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_datetime)
    return checker


def _schema_errors(payload: JsonObject, schema: JsonObject) -> list[LedgerError]:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema must be installed to validate the design-data ledger")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=_format_checker())
    errors: list[LedgerError] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        path = "/" + "/".join(
            str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path
        )
        errors.append(_error(str(error.validator), path or "/", error.message))
    return errors


def _records(payload: JsonObject, key: str) -> list[JsonObject]:
    value = payload.get(key, [])
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _resolve_pointer(document: JsonObject, pointer: str) -> tuple[bool, Any]:
    if not pointer.startswith("/"):
        return False, None
    current: Any = document
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return False, None
        elif isinstance(current, Mapping):
            if token not in current:
                return False, None
            current = current[token]
        else:
            return False, None
    return True, current


def _consistency_errors(ledger: JsonObject) -> list[LedgerError]:
    errors: list[LedgerError] = []
    data_by_id: dict[str, JsonObject] = {}
    for position, record in enumerate(_records(ledger, "data_records")):
        data_id = record.get("data_id")
        if isinstance(data_id, str):
            if data_id in data_by_id:
                errors.append(_error("DATA_ID_NOT_UNIQUE", f"/data_records/{position}", f"Duplicate data ID {data_id}", [data_id]))
            data_by_id[data_id] = record
    artifact_by_id: dict[str, JsonObject] = {}
    for position, record in enumerate(_records(ledger, "artifacts")):
        artifact_id = record.get("artifact_id")
        if isinstance(artifact_id, str):
            if artifact_id in artifact_by_id:
                errors.append(_error("ARTIFACT_ID_NOT_UNIQUE", f"/artifacts/{position}", f"Duplicate artifact ID {artifact_id}", [artifact_id]))
            artifact_by_id[artifact_id] = record
    event_ids: set[str] = set()
    for position, record in enumerate(_records(ledger, "change_events")):
        event_id = record.get("event_id")
        if isinstance(event_id, str):
            if event_id in event_ids:
                errors.append(_error("EVENT_ID_NOT_UNIQUE", f"/change_events/{position}", f"Duplicate change event ID {event_id}", [event_id]))
            event_ids.add(event_id)

    def require(target: Mapping[str, Any], reference: object, path: str) -> None:
        if not isinstance(reference, str) or reference not in target:
            errors.append(_error("REF_NOT_FOUND", path, f"Referenced ID {reference!r} not found", [str(reference)]))

    for position, record in enumerate(_records(ledger, "data_records")):
        data_id = record.get("data_id")
        base = f"/data_records/{position}"
        if not isinstance(data_id, str):
            continue
        binding = record.get("source_binding") or {}
        if isinstance(binding, Mapping) and not str(binding.get("json_pointer", "")).startswith("/"):
            errors.append(_error("SOURCE_BINDING_INVALID", f"{base}/source_binding/json_pointer", "source_binding requires an RFC 6901 pointer", [data_id]))
        for edge_position, artifact_id in enumerate(record.get("used_by", []) or []):
            require(artifact_by_id, artifact_id, f"{base}/used_by/{edge_position}")
        for edge_position, upstream_id in enumerate(record.get("stale_if", []) or []):
            require(data_by_id, upstream_id, f"{base}/stale_if/{edge_position}")
        derivation = record.get("derivation")
        if isinstance(derivation, Mapping):
            for edge_position, input_id in enumerate(derivation.get("input_data_ids", []) or []):
                require(data_by_id, input_id, f"{base}/derivation/input_data_ids/{edge_position}")
        wording = record.get("public_wording")
        template = record.get("public_wording_template")
        if wording in {"QUALIFIED_ESTIMATE", "CURRENT_DESIGN_VALUE"} and (not isinstance(template, str) or VALUE_TEMPLATE_PLACEHOLDER not in template):
            errors.append(_error(
                "WORDING_TEMPLATE_INVALID",
                f"{base}/public_wording_template",
                f"{wording} requires a template containing " + VALUE_TEMPLATE_PLACEHOLDER,
                [data_id],
            ))
        if record.get("maturity") in {"UNRESOLVED", "WORKING"} and wording == "CURRENT_DESIGN_VALUE":
            errors.append(_error(
                "MATURITY_WORDING_CONFLICT",
                f"{base}/public_wording",
                f"{record.get('maturity')} data must not use public_wording CURRENT_DESIGN_VALUE",
                [data_id],
            ))

    for position, record in enumerate(_records(ledger, "artifacts")):
        artifact_id = record.get("artifact_id")
        base = f"/artifacts/{position}"
        if not isinstance(artifact_id, str):
            continue
        built_from = record.get("built_from") or {}
        data_ids = built_from.get("data_ids", []) or []
        artifact_ids = built_from.get("artifact_ids", []) or []
        for edge_position, bound_id in enumerate(data_ids):
            require(data_by_id, bound_id, f"{base}/built_from/data_ids/{edge_position}")
        for edge_position, upstream_id in enumerate(artifact_ids):
            require(artifact_by_id, upstream_id, f"{base}/built_from/artifact_ids/{edge_position}")
        build_event_id = record.get("build_event_id")
        if build_event_id is not None:
            require(event_ids, build_event_id, f"{base}/build_event_id")
        if record.get("artifact_kind") in PHYSICAL_ARTIFACT_KINDS and not record.get("relative_path"):
            errors.append(_error(
                "PHYSICAL_ARTIFACT_PATH_REQUIRED",
                f"{base}/relative_path",
                f"physical artifact {artifact_id} requires relative_path for hash recomputation",
                [artifact_id],
            ))
        if record.get("deterministic") and not record.get("provenance"):
            errors.append(_error(
                "PROVENANCE_REQUIRED",
                f"{base}/provenance",
                f"deterministic artifact {artifact_id} requires a builder-owned provenance sidecar",
                [artifact_id],
            ))

    # Every data->artifact edge must be declared on both ends exactly once.
    declared_upstream: dict[str, set[str]] = {}
    for record in _records(ledger, "data_records"):
        data_id = record.get("data_id")
        if isinstance(data_id, str):
            for artifact_id in record.get("used_by", []) or []:
                if isinstance(artifact_id, str):
                    declared_upstream.setdefault(artifact_id, set()).add(data_id)
    for position, record in enumerate(_records(ledger, "artifacts")):
        artifact_id = record.get("artifact_id")
        if not isinstance(artifact_id, str):
            continue
        built_ids = {item for item in (record.get("built_from") or {}).get("data_ids", []) or [] if isinstance(item, str)}
        for bound_id in sorted(built_ids ^ declared_upstream.get(artifact_id, set())):
            errors.append(_error(
                "DATA_ARTIFACT_EDGE_MISMATCH",
                f"/artifacts/{position}/built_from/data_ids",
                f"data/artifact edge {bound_id}->{artifact_id} is not declared on both ends",
                [bound_id, artifact_id],
            ))

    # Copy bindings: XOR between data-bound slots and explicit no-dependency slots.
    for position, record in enumerate(_records(ledger, "copy_bindings")):
        base = f"/copy_bindings/{position}"
        data_ids = [item for item in record.get("data_ids", []) or [] if isinstance(item, str)]
        for edge_position, bound_id in enumerate(data_ids):
            require(data_by_id, bound_id, f"{base}/data_ids/{edge_position}")
        has_data = bool(data_ids)
        no_dependency = record.get("no_key_data_dependency") is True
        if has_data == no_dependency:
            errors.append(_error(
                "COPY_BINDING_AMBIGUOUS",
                base,
                "a copy binding declares either bound data or no_key_data_dependency, never both and never neither",
                [str(record.get("page_id", position))],
            ))
            continue
        wording_mode = record.get("wording_mode")
        if has_data:
            if wording_mode is None:
                errors.append(_error("COPY_WORDING_MISMATCH", f"{base}/wording_mode", "a data-bound copy slot requires its wording_mode", []))
            for bound_id in data_ids:
                bound = data_by_id.get(bound_id)
                if not isinstance(bound, Mapping):
                    continue
                if bound.get("maturity") == "UNRESOLVED":
                    errors.append(_error(
                        "UNRESOLVED_DATA_BOUND_TO_COPY",
                        base,
                        f"UNRESOLVED data {bound_id} must never bind to visible copy",
                        [bound_id],
                    ))
                if bound.get("public_wording") == "NOT_PUBLIC":
                    errors.append(_error(
                        "NOT_PUBLIC_DATA_BOUND_TO_COPY",
                        base,
                        f"NOT_PUBLIC data {bound_id} must never bind to visible copy",
                        [bound_id],
                    ))
                if wording_mode is not None and wording_mode != bound.get("public_wording"):
                    errors.append(_error(
                        "COPY_WORDING_MISMATCH",
                        f"{base}/wording_mode",
                        f"wording_mode {wording_mode} does not match data {bound_id} public_wording {bound.get('public_wording')}",
                        [bound_id],
                    ))
        elif not isinstance(record.get("human_review_note"), str) or not record.get("human_review_note"):
            errors.append(_error(
                "COPY_BINDING_NOTE_REQUIRED",
                f"{base}/human_review_note",
                "a no_key_data_dependency copy slot requires its human review note",
                [],
            ))

    # Cycle detection over the union graph (stale_if + built_from edges).
    graph: dict[str, set[str]] = {}
    for record in _records(ledger, "data_records"):
        data_id = record.get("data_id")
        if isinstance(data_id, str):
            graph.setdefault(data_id, set()).update(
                item for item in record.get("stale_if", []) or [] if isinstance(item, str)
            )
    for record in _records(ledger, "artifacts"):
        artifact_id = record.get("artifact_id")
        if isinstance(artifact_id, str):
            built_from = record.get("built_from") or {}
            graph.setdefault(artifact_id, set()).update(
                item for item in built_from.get("artifact_ids", []) or [] if isinstance(item, str)
            )
            graph.setdefault(artifact_id, set()).update(
                item for item in built_from.get("data_ids", []) or [] if isinstance(item, str)
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited or errors:
            return
        if node in visiting:
            errors.append(_error("LEDGER_GRAPH_CYCLE", "/ledger", f"dependency graph contains a cycle through {node}", [node]))
            return
        visiting.add(node)
        for downstream in sorted(graph.get(node, set())):
            visit(downstream)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return errors


def validate_ledger(ledger: JsonObject) -> tuple[bool, list[LedgerError]]:
    """Structural and cross-consistency validation; freshness is computed separately."""
    try:
        errors = _schema_errors(ledger, _ledger_schema())
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return False, [_error("RUNTIME_ERROR", "", str(error))]
    errors.extend(_consistency_errors(ledger))
    return (not errors), errors


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _manifest_asset_errors(ledger_base: Path, artifact: JsonObject) -> set[str]:
    """Recompute the asset hashes referenced by one svg_manifest artifact."""
    reasons: set[str] = set()
    manifest_path = ledger_base / str(artifact.get("relative_path"))
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"), parse_constant=_parse_constant)
    except (OSError, UnicodeError, ValueError):
        return {"MANIFEST_ASSET_MISMATCH"}
    assets = manifest.get("assets") if isinstance(manifest, Mapping) else None
    if not isinstance(assets, Mapping):
        return {"MANIFEST_ASSET_MISMATCH"}
    manifest_dir = manifest_path.parent
    for key in ("editable", "compiled", "preview"):
        ref = assets.get(key)
        if not isinstance(ref, Mapping):
            reasons.add("MANIFEST_ASSET_MISMATCH")
            continue
        actual = _file_sha256(manifest_dir / str(ref.get("relative_path", "")))
        if actual is None or actual != ref.get("sha256"):
            reasons.add("MANIFEST_ASSET_MISMATCH")
    return reasons


def _provenance_errors(
    ledger_base: Path | None,
    artifact: JsonObject,
    current_data_hashes: Mapping[str, str],
) -> set[str]:
    """Validate the builder-owned provenance sidecar of one deterministic artifact."""
    provenance_ref = artifact.get("provenance")
    if not isinstance(provenance_ref, Mapping):
        return {"PROVENANCE_MISMATCH"}
    if ledger_base is None:
        return {"PROVENANCE_MISMATCH"}
    provenance_path = ledger_base / str(provenance_ref.get("path", ""))
    actual_bytes = provenance_path.read_bytes() if provenance_path.is_file() else None
    if actual_bytes is None or hashlib.sha256(actual_bytes).hexdigest() != provenance_ref.get("sha256"):
        return {"PROVENANCE_MISMATCH"}
    try:
        provenance = json.loads(actual_bytes.decode("utf-8"), parse_constant=_parse_constant)
    except (UnicodeError, ValueError):
        return {"PROVENANCE_MISMATCH"}
    if not isinstance(provenance, Mapping):
        return {"PROVENANCE_MISMATCH"}
    reasons: set[str] = set()
    if provenance.get("output_sha256") != artifact.get("content_sha256"):
        reasons.add("PROVENANCE_OUTPUT_MISMATCH")
    inputs = provenance.get("inputs")
    if not isinstance(inputs, list):
        reasons.add("PROVENANCE_MISMATCH")
        return reasons
    for entry in inputs:
        if not isinstance(entry, Mapping):
            reasons.add("PROVENANCE_MISMATCH")
            continue
        data_id = entry.get("data_id")
        if current_data_hashes.get(data_id) != entry.get("canonical_sha256"):
            reasons.add("INPUT_HASH_CHANGED")
    return reasons


def _copy_binding_errors(ledger: JsonObject, handoff: JsonObject) -> tuple[list[LedgerError], str]:
    """Verify copy bindings against the actual handoff text; return errors and digest."""
    errors: list[LedgerError] = []
    data_by_id = {record["data_id"]: record for record in _records(ledger, "data_records") if isinstance(record.get("data_id"), str)}
    deck_framework = handoff.get("deck_framework")
    actual_slots: dict[str, tuple[str, str]] = {}  # pointer -> (page_id, text)
    if isinstance(deck_framework, list):
        for page_position, page in enumerate(deck_framework):
            if not isinstance(page, Mapping):
                continue
            page_id = str(page.get("page_id", f"page-{page_position}"))
            copy_block = page.get("visible_slide_copy")
            if not isinstance(copy_block, Mapping):
                continue
            headline = copy_block.get("headline")
            if isinstance(headline, str):
                actual_slots[f"/deck_framework/{page_position}/visible_slide_copy/headline"] = (page_id, headline)
            supporting = copy_block.get("supporting_points")
            if isinstance(supporting, list):
                for point_position, point in enumerate(supporting):
                    if isinstance(point, str):
                        actual_slots[f"/deck_framework/{page_position}/visible_slide_copy/supporting_points/{point_position}"] = (page_id, point)
    else:
        errors.append(_error(
            "COPY_SHAPE_UNKNOWN",
            "/copy_bindings",
            "the actual handoff does not expose a known visible-copy shape (deck_framework pages)",
            [],
        ))
        return errors, canonical_data_hash(_records(ledger, "copy_bindings"))

    bindings = _records(ledger, "copy_bindings")
    bound_pointers: set[str] = set()
    for position, record in enumerate(bindings):
        base = f"/copy_bindings/{position}"
        pointer = record.get("json_pointer")
        if not isinstance(pointer, str):
            continue
        bound_pointers.add(pointer)
        found, value = _resolve_pointer(handoff, pointer)
        if not found:
            errors.append(_error("COPY_POINTER_NOT_FOUND", f"{base}/json_pointer", f"copy binding pointer {pointer} does not resolve in the actual handoff", [pointer]))
            continue
        if not isinstance(value, str):
            errors.append(_error("COPY_POINTER_NOT_FOUND", f"{base}/json_pointer", f"copy binding pointer {pointer} does not address a copy string", [pointer]))
            continue
        if hashlib.sha256(value.encode("utf-8")).hexdigest() != record.get("text_sha256"):
            errors.append(_error("COPY_TEXT_CHANGED", base, f"actual copy text at {pointer} no longer matches the binding hash", [pointer]))
            continue
        for bound_id in record.get("data_ids", []) or []:
            bound = data_by_id.get(bound_id)
            if not isinstance(bound, Mapping):
                continue
            if bound.get("maturity") == "UNRESOLVED":
                errors.append(_error("UNRESOLVED_DATA_IN_VISIBLE_COPY", base, f"UNRESOLVED data {bound_id} is bound to visible copy", [bound_id]))
            if bound.get("public_wording") == "NOT_PUBLIC":
                errors.append(_error("NOT_PUBLIC_VALUE_VISIBLE", base, f"NOT_PUBLIC data {bound_id} is bound to visible copy", [bound_id]))
            if bound.get("public_wording") == "QUALIFIED_ESTIMATE":
                template = bound.get("public_wording_template", "")
                required_phrase = str(template).replace(VALUE_TEMPLATE_PLACEHOLDER, json.dumps(bound.get("canonical_value"), ensure_ascii=False, allow_nan=False))
                if required_phrase not in value:
                    errors.append(_error(
                        "UNQUALIFIED_ESTIMATE_VISIBLE",
                        base,
                        f"estimate data {bound_id} appears in visible copy without its declared qualified wording",
                        [bound_id],
                    ))
            if bound.get("public_wording") == "CURRENT_DESIGN_VALUE":
                # R2: the visible copy must express the CURRENT canonical value
                # through the record's declared template; an old value, a value
                # that only appears on another page, or a bare number anywhere
                # else is not proof.
                template = bound.get("public_wording_template", "")
                required_phrase = str(template).replace(VALUE_TEMPLATE_PLACEHOLDER, json.dumps(bound.get("canonical_value"), ensure_ascii=False, allow_nan=False))
                if required_phrase not in value:
                    errors.append(_error(
                        "CURRENT_DESIGN_VALUE_VISIBLE_MISMATCH",
                        base,
                        f"visible copy for data {bound_id} does not express its current canonical value through the declared wording template",
                        [bound_id],
                    ))
    for pointer in sorted(set(actual_slots) - bound_pointers):
        errors.append(_error(
            "COPY_BINDING_MISSING",
            "/copy_bindings",
            f"actual copy slot {pointer} ({actual_slots[pointer][0]}) has no copy binding",
            [pointer],
        ))
    return errors, canonical_data_hash(bindings)


def _current_data_hashes(ledger: JsonObject) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for record in _records(ledger, "data_records"):
        data_id = record.get("data_id")
        if not isinstance(data_id, str):
            continue
        try:
            hashes[data_id] = canonical_data_hash(record.get("canonical_value"))
        except (TypeError, ValueError):
            hashes[data_id] = None
    return hashes


def compute_freshness(
    ledger: JsonObject,
    *,
    base_dir: Path | None = None,
    documents: Mapping[str, Path] | None = None,
    state_output: JsonObject | None = None,
    mode: str = "INTERMEDIATE",
    human_review_digest: str | None = None,
    pptx_sha256: str | None = None,
) -> JsonObject:
    """Deterministically recompute CURRENT/STALE for every data record and artifact.

    ``documents`` maps each source-binding role to the actual file; a missing
    role is a verification failure upstream, never silently ignored. Results
    depend only on ledger content, actual file bytes, and the supplied state
    output; sorted memoized traversal keeps them order-independent.
    """
    documents = dict(documents) if documents is not None else {}
    data_by_id = {record["data_id"]: record for record in _records(ledger, "data_records") if isinstance(record.get("data_id"), str)}
    artifact_by_id = {record["artifact_id"]: record for record in _records(ledger, "artifacts") if isinstance(record.get("artifact_id"), str)}
    state_stale = stale_entity_records(state_output) if state_output is not None else {}

    document_hashes = {role: (_file_sha256(path) if path else None) for role, path in sorted(documents.items())}
    data_reasons: dict[str, set[str]] = {data_id: set() for data_id in data_by_id}
    for data_id in sorted(data_by_id):
        record = data_by_id[data_id]
        binding = record.get("source_binding") or {}
        role = binding.get("document_role")
        document_path = documents.get(role) if isinstance(role, str) else None
        if not isinstance(role, str) or document_path is None:
            data_reasons[data_id].add("SOURCE_DOCUMENT_CHANGED")
            continue
        if document_hashes.get(role) != binding.get("document_sha256"):
            data_reasons[data_id].add("SOURCE_DOCUMENT_CHANGED")
            continue
        found, extracted = _resolve_pointer(load_json_object(Path(document_path)), str(binding.get("json_pointer", "")))
        if not found or not _value_matches(extracted, record.get("canonical_value")) or canonical_data_hash(extracted) != record.get("canonical_sha256"):
            data_reasons[data_id].add("SOURCE_BINDING_MISMATCH")
            continue
        if canonical_data_hash(record.get("canonical_value")) != record.get("canonical_sha256"):
            data_reasons[data_id].add("DATA_VALUE_CHANGED_UNBOUND")
        if state_output is not None:
            for entity_id in record.get("state_entity_ids", []) or []:
                if isinstance(entity_id, str) and entity_id in state_stale:
                    data_reasons[data_id].add("STATE_CHAIN_STALE")
                    break

    data_edges: dict[str, set[str]] = {}
    for data_id, record in data_by_id.items():
        for upstream_id in record.get("stale_if", []) or []:
            if isinstance(upstream_id, str):
                data_edges.setdefault(data_id, set()).add(upstream_id)
    pending = [data_id for data_id in sorted(data_reasons) if data_reasons[data_id]]
    while pending:
        stale_id = pending.pop(0)
        for downstream_id in sorted(data_edges):
            if stale_id in data_edges[downstream_id] and "UPSTREAM_DATA_STALE" not in data_reasons[downstream_id]:
                data_reasons[downstream_id].add("UPSTREAM_DATA_STALE")
                pending.append(downstream_id)

    current_hashes = _current_data_hashes(ledger)
    artifact_reasons: dict[str, set[str]] = {}

    def artifact_stale_reasons(artifact_id: str) -> set[str]:
        if artifact_id in artifact_reasons:
            return artifact_reasons[artifact_id]
        artifact_reasons[artifact_id] = set()  # cycle guard; validation rejects cycles first
        record = artifact_by_id[artifact_id]
        reasons: set[str] = set()
        relative_path = record.get("relative_path")
        if isinstance(relative_path, str):
            if base_dir is None:
                reasons.add("FILE_MISSING")
            else:
                actual = _file_sha256(base_dir / relative_path)
                if actual is None:
                    reasons.add("FILE_MISSING")
                elif actual != record.get("content_sha256"):
                    reasons.add("CONTENT_HASH_CHANGED")
                if record.get("artifact_kind") == "svg_manifest" and not reasons & {"FILE_MISSING"}:
                    reasons |= _manifest_asset_errors(base_dir, record)
        if record.get("deterministic"):
            reasons |= _provenance_errors(base_dir, record, current_hashes)
        built_from = record.get("built_from") or {}
        for upstream_id in built_from.get("artifact_ids", []) or []:
            if isinstance(upstream_id, str) and artifact_stale_reasons(upstream_id):
                reasons.add("UPSTREAM_ARTIFACT_STALE")
                break
        for bound_id in built_from.get("data_ids", []) or []:
            if data_reasons.get(bound_id):
                reasons.add("UPSTREAM_DATA_STALE")
                break
        artifact_reasons[artifact_id] = reasons
        return reasons

    for artifact_id in sorted(artifact_by_id):
        artifact_stale_reasons(artifact_id)

    input_file_hashes = [
        {"role": role, "sha256": digest}
        for role, digest in sorted(document_hashes.items())
        if digest is not None
    ]
    copy_digest = canonical_copy_bindings_digest(ledger)
    graph_nodes = sorted(data_by_id)
    graph_digest = canonical_data_hash({
        "data": {data_id: sorted(data_reasons[data_id]) for data_id in graph_nodes},
        "artifacts": {artifact_id: sorted(artifact_reasons[artifact_id]) for artifact_id in sorted(artifact_by_id)},
    })
    data_entries = [
        {
            "data_id": data_id,
            "maturity": data_by_id[data_id].get("maturity"),
            "freshness": "STALE" if data_reasons[data_id] else "CURRENT",
            "reasons": sorted(data_reasons[data_id]),
        }
        for data_id in sorted(data_by_id)
    ]
    artifact_entries = [
        {
            "artifact_id": artifact_id,
            "artifact_kind": artifact_by_id[artifact_id].get("artifact_kind"),
            "freshness": "STALE" if artifact_reasons[artifact_id] else "CURRENT",
            "reasons": sorted(artifact_reasons[artifact_id]),
        }
        for artifact_id in sorted(artifact_by_id)
    ]
    receipt: JsonObject = {
        "receipt_version": RECEIPT_VERSION,
        "mode": mode,
        "ledger_canonical_sha256": canonical_ledger_hash(ledger),
        "computed_with_state_output": state_output is not None,
        "input_file_hashes": input_file_hashes,
        "dependency_graph_digest": graph_digest,
        "copy_bindings_digest": copy_digest,
        "data": data_entries,
        "artifacts": artifact_entries,
        "stale_data_count": sum(1 for entry in data_entries if entry["freshness"] == "STALE"),
        "stale_artifact_count": sum(1 for entry in artifact_entries if entry["freshness"] == "STALE"),
    }
    if human_review_digest is not None:
        receipt["human_review_digest"] = human_review_digest
    if pptx_sha256 is not None:
        receipt["pptx_sha256"] = pptx_sha256
    return receipt


def _value_matches(extracted: Any, canonical_value: Any) -> bool:
    if isinstance(extracted, float) and isinstance(canonical_value, (int, float)) and not isinstance(canonical_value, bool):
        return float(extracted) == float(canonical_value)
    return extracted == canonical_value


def human_review_digest(review: JsonObject) -> str:
    """Exact digest the verifier binds into receipts for this review receipt."""
    return hashlib.sha256(
        json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def verify_human_review(review: JsonObject | None, ledger: JsonObject) -> tuple[bool, list[LedgerError], str]:
    """Verify the independent human review receipt against the current ledger.

    The review file digest is returned so receipts and delivery verdicts can
    bind it; any ledger, frozen-value, wording-binding, or artifact-binding
    change voids the review through its hash bindings.
    """
    errors: list[LedgerError] = []
    if review is None:
        return False, [_error("HUMAN_REVIEW_REQUIRED", "/human_review", "delivery requires an independent human review receipt")], ""
    try:
        errors.extend(_schema_errors(review, _human_review_schema()))
    except (OSError, ValueError, SchemaError, RuntimeError) as error:
        return False, [_error("RUNTIME_ERROR", "", str(error))], ""
    review_digest = human_review_digest(review)
    if review.get("status") != "APPROVED":
        errors.append(_error("HUMAN_REVIEW_NOT_APPROVED", "/status", f"review status {review.get('status')!r} cannot enter delivery", []))
    if not is_human_reviewer_label(review.get("reviewed_by")):
        errors.append(_error("HUMAN_REVIEWER_LABEL_REJECTED", "/reviewed_by", "reviewed_by must identify a human, not an agent, model, or system label", []))
    if review.get("ledger_canonical_sha256") != canonical_ledger_hash(ledger):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/ledger_canonical_sha256", "the review does not cover the current ledger", []))
        return (not errors), errors, review_digest

    data_by_id = {record["data_id"]: record for record in _records(ledger, "data_records") if isinstance(record.get("data_id"), str)}
    covered = {entry.get("data_id"): entry for entry in review.get("frozen_data_bindings", []) or [] if isinstance(entry, Mapping)}
    for data_id in sorted(data_by_id):
        record = data_by_id[data_id]
        if record.get("maturity") not in {"COORDINATED", "FROZEN_FOR_DELIVERY"}:
            continue
        binding = covered.get(data_id)
        if binding is None:
            errors.append(_error("REVIEW_HASH_MISMATCH", "/frozen_data_bindings", f"confirmed data {data_id} is missing from the human review", [data_id]))
        elif binding.get("canonical_sha256") != record.get("canonical_sha256") or binding.get("public_wording") != record.get("public_wording"):
            errors.append(_error("REVIEW_HASH_MISMATCH", f"/frozen_data_bindings/{data_id}", f"confirmed value or wording for {data_id} changed after the review", [data_id]))
    expected_wording_digest = canonical_copy_bindings_digest(ledger)
    if review.get("public_wording_bindings_sha256") != expected_wording_digest:
        errors.append(_error("REVIEW_HASH_MISMATCH", "/public_wording_bindings_sha256", "copy bindings changed after the review", []))
    artifact_by_id = {record["artifact_id"]: record for record in _records(ledger, "artifacts") if isinstance(record.get("artifact_id"), str)}
    current_hashes = _current_data_hashes(ledger)
    artifact_covered = {entry.get("artifact_id"): entry for entry in review.get("artifact_bindings", []) or [] if isinstance(entry, Mapping)}
    for artifact_id in sorted(artifact_by_id):
        record = artifact_by_id[artifact_id]
        # R2: every delivery artifact needs the independent human binding — a
        # deterministic artifact can no longer skip it, because its
        # caller-owned provenance sidecar alone cannot prove that the builder
        # actually ran or that the artifact was regenerated from the current
        # inputs.
        binding = artifact_covered.get(artifact_id)
        input_digest = artifact_input_bindings_digest(ledger, artifact_id)
        if binding is None:
            errors.append(_error("REVIEW_ARTIFACT_BINDING_MISSING", "/artifact_bindings", f"delivery artifact {artifact_id} needs independent human confirmation of its input/output binding", [artifact_id]))
        elif binding.get("content_sha256") != record.get("content_sha256") or binding.get("input_bindings_sha256") != input_digest:
            errors.append(_error("REVIEW_HASH_MISMATCH", f"/artifact_bindings/{artifact_id}", f"artifact {artifact_id} input/output binding changed after the review", [artifact_id]))
    findings_payload = {"findings": review.get("findings", []), "findings_resolutions": review.get("findings_resolutions", [])}
    if review.get("findings_sha256") != canonical_data_hash(findings_payload):
        errors.append(_error("REVIEW_HASH_MISMATCH", "/findings_sha256", "findings hash does not bind the findings record", []))
    return (not errors), errors, review_digest


def verify_delivery_freshness(
    ledger: JsonObject,
    receipt: JsonObject | None,
    *,
    base_dir: Path | None = None,
    documents: Mapping[str, Path] | None = None,
    state_output: JsonObject | None = None,
    human_review: JsonObject | None = None,
    expected_bindings: Sequence[tuple[str, str]] = (),
    require_human_review: bool = False,
    verify_copy_bindings: bool = False,
) -> tuple[bool, list[LedgerError], JsonObject]:
    """Recompute freshness and bind it to the delivery; never trust a stored verdict.

    DELIVERY semantics: the independent human review is mandatory, copy
    bindings are verified against the actual presentation handoff, and the
    supplied receipt must equal the recomputation byte-for-byte in canonical
    form. ``expected_bindings`` lists (artifact_kind, content_sha256) pairs
    that must exist among CURRENT artifacts.
    """
    errors: list[LedgerError] = []
    ok, validation_errors = validate_ledger(ledger)
    if not ok:
        return False, validation_errors, {}
    review_digest: str | None = None
    if require_human_review or human_review is not None:
        review_ok, review_errors, review_digest = verify_human_review(human_review, ledger)
        errors.extend(review_errors)
        if not review_ok:
            return False, errors, {}
    handoff = documents.get(HANDOFF_PRESENTATION_ROLE) if documents else None
    copy_errors: list[LedgerError] = []
    if verify_copy_bindings:
        if handoff is None:
            errors.append(_error("DOCUMENT_ROLE_MISSING", f"/documents/{HANDOFF_PRESENTATION_ROLE}", f"copy binding verification requires the actual {HANDOFF_PRESENTATION_ROLE} document", [HANDOFF_PRESENTATION_ROLE]))
            return False, errors, {}
        copy_errors, _digest = _copy_binding_errors(ledger, load_json_object(Path(handoff)))
        errors.extend(copy_errors)
        if copy_errors:
            return False, errors, {}
    recomputed = compute_freshness(
        ledger,
        base_dir=base_dir,
        documents=documents,
        state_output=state_output,
        mode="DELIVERY" if (require_human_review or verify_copy_bindings) else "INTERMEDIATE",
        human_review_digest=review_digest,
    )
    if receipt is not None and canonical_data_hash(receipt) != canonical_data_hash(recomputed):
        errors.append(_error("RECEIPT_MISMATCH", "/receipt", "the supplied freshness receipt does not match the recomputed ledger state", []))
    for entry in recomputed["data"]:
        if entry["freshness"] == "STALE":
            errors.append(_error("RECEIPT_NOT_CURRENT", f"/data/{entry['data_id']}", f"data {entry['data_id']} is stale: {', '.join(entry['reasons'])}", [entry["data_id"]]))
    for entry in recomputed["artifacts"]:
        if entry["freshness"] == "STALE":
            errors.append(_error("RECEIPT_NOT_CURRENT", f"/artifacts/{entry['artifact_id']}", f"artifact {entry['artifact_id']} is stale: {', '.join(entry['reasons'])}", [entry["artifact_id"]]))
    artifact_by_id = {record["artifact_id"]: record for record in _records(ledger, "artifacts") if isinstance(record.get("artifact_id"), str)}
    fresh_artifacts = {entry["artifact_id"] for entry in recomputed["artifacts"] if entry["freshness"] == "CURRENT"}
    current_bindings = {
        (artifact_by_id[artifact_id].get("artifact_kind"), artifact_by_id[artifact_id].get("content_sha256"))
        for artifact_id in fresh_artifacts
    }
    for kind, content_sha256 in expected_bindings:
        if (kind, content_sha256) not in current_bindings:
            errors.append(_error("RECEIPT_BINDING_MISSING", "/expected_bindings", f"no CURRENT {kind} artifact bound to content hash {str(content_sha256)[:12]}…", [kind]))
    return (not errors), errors, recomputed


def verify_release(
    ledger: JsonObject,
    receipt: JsonObject | None,
    human_review: JsonObject | None,
    *,
    base_dir: Path,
    documents: Mapping[str, Path],
    state_output: JsonObject | None = None,
    pptx_path: Path,
    expected_pptx_sha256: str,
) -> tuple[bool, list[LedgerError], JsonObject]:
    """Authoritative release verdict (mode DELIVERY) consumed by the Node entry.

    Re-reads every actual file: source documents through their bindings, the
    handoff copy slots, artifact bytes and provenance sidecars, and the actual
    PPTX bytes, which must match both the ledger deck binding and the caller's
    independently computed hash.
    """
    errors: list[LedgerError] = []
    actual_pptx_sha256 = _file_sha256(pptx_path)
    if actual_pptx_sha256 is None:
        return False, [_error("FRESHNESS_PPTX_UNREADABLE", "/pptx", "the actual PPTX file could not be read")], {}
    if actual_pptx_sha256 != expected_pptx_sha256:
        errors.append(_error("FRESHNESS_PPTX_HASH_MISMATCH", "/pptx", "the actual PPTX hash does not match the release request binding", []))
    deck_artifacts = [
        record for record in _records(ledger, "artifacts")
        if record.get("artifact_kind") == "pptx_deck" and record.get("content_sha256") == actual_pptx_sha256
    ]
    if not deck_artifacts:
        errors.append(_error("RECEIPT_BINDING_MISSING", "/pptx_deck", "no pptx_deck artifact in the ledger binds the actual PPTX bytes", [actual_pptx_sha256[:12]]))
    ok, verification_errors, verdict = verify_delivery_freshness(
        ledger,
        receipt,
        base_dir=base_dir,
        documents=documents,
        state_output=state_output,
        human_review=human_review,
        expected_bindings=[],
        require_human_review=True,
        verify_copy_bindings=True,
    )
    errors.extend(verification_errors)
    verdict = dict(verdict)
    verdict["mode"] = "DELIVERY"
    verdict["validator_contract_version"] = VALIDATOR_CONTRACT_VERSION
    verdict["pptx_sha256"] = actual_pptx_sha256
    verdict["ledger_sha256"] = verdict.get("ledger_canonical_sha256")
    if errors:
        return False, errors, verdict
    return True, [], verdict


def _value_strings(value: Any) -> list[str]:
    """Surface forms one canonical value may take in copy text (value-level, no word scans)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool):
        return ["true" if value else "false"]
    if isinstance(value, (int, float)):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
        forms = [raw]
        formatted = f"{value:,}"
        if formatted != raw:
            forms.append(formatted)
        return forms
    return [json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)]


def check_public_copy(ledger: JsonObject, copy_document: JsonObject) -> tuple[bool, list[LedgerError]]:
    """Ad-hoc maturity/wording gate for free copy text; the binding-based verifier is authoritative for delivery."""
    data_by_id = {record["data_id"]: record for record in _records(ledger, "data_records") if isinstance(record.get("data_id"), str)}
    errors: list[LedgerError] = []
    pages = copy_document.get("pages")
    if not isinstance(pages, list):
        return False, [_error("RUNTIME_ERROR", "/pages", "copy document requires a pages array")]
    for position, page in enumerate(pages):
        if not isinstance(page, Mapping):
            continue
        base = f"/pages/{position}"
        page_id = page.get("page_id", str(position))
        text = page.get("visible_text")
        if not isinstance(text, str):
            errors.append(_error("RUNTIME_ERROR", f"{base}/visible_text", f"page {page_id} requires visible_text text", [str(page_id)]))
            continue
        for ref_position, data_id in enumerate(page.get("data_ids", []) or []):
            path = f"{base}/data_ids/{ref_position}"
            if not isinstance(data_id, str) or data_id not in data_by_id:
                errors.append(_error("COPY_DATA_REF_NOT_FOUND", path, f"referenced data ID {data_id!r} not found", [str(data_id)]))
                continue
            record = data_by_id[data_id]
            if record.get("maturity") == "UNRESOLVED":
                errors.append(_error("UNRESOLVED_DATA_IN_VISIBLE_COPY", path, f"UNRESOLVED data {data_id} must not appear in visible copy", [data_id]))
                continue
            forms = _value_strings(record.get("canonical_value"))
            if not any(form and form in text for form in forms):
                continue
            wording = record.get("public_wording")
            if wording == "NOT_PUBLIC":
                errors.append(_error("NOT_PUBLIC_VALUE_VISIBLE", path, f"NOT_PUBLIC data {data_id} value appears in visible copy", [data_id]))
            elif wording == "QUALIFIED_ESTIMATE":
                template = record.get("public_wording_template", "")
                required_phrase = str(template).replace(VALUE_TEMPLATE_PLACEHOLDER, _value_strings(record.get("canonical_value"))[0])
                if required_phrase not in text:
                    errors.append(_error("UNQUALIFIED_ESTIMATE_VISIBLE", path, f"estimate data {data_id} appears without its qualified estimate wording", [data_id]))
            elif wording == "CURRENT_DESIGN_VALUE":
                template = record.get("public_wording_template", "")
                required_phrase = str(template).replace(VALUE_TEMPLATE_PLACEHOLDER, _value_strings(record.get("canonical_value"))[0])
                if required_phrase not in text:
                    errors.append(_error("CURRENT_DESIGN_VALUE_VISIBLE_MISMATCH", path, f"visible copy for data {data_id} does not express its current canonical value through the declared wording template", [data_id]))
    return (not errors), errors


def _parse_document_args(pairs: Sequence[str]) -> tuple[dict[str, Path], list[LedgerError]]:
    documents: dict[str, Path] = {}
    errors: list[LedgerError] = []
    for pair in pairs:
        role, separator, value = pair.partition("=")
        if not separator or not role or not value:
            errors.append(_error("RUNTIME_ERROR", "", f"--document requires role=path, got {pair!r}"))
            continue
        documents[role] = Path(value)
    return documents, errors


def main(argv: Sequence[str]) -> int:
    """Run one ledger mode and emit machine-readable JSON without touching inputs."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", nargs="?")
    parser.add_argument("ledger_path", nargs="?")
    parser.add_argument("second_path", nargs="?")
    parser.add_argument("third_path", nargs="?")
    parser.add_argument("--mode", dest="delivery_mode", choices=["intermediate", "delivery"])
    parser.add_argument("--document", action="append", default=[], help="role=path actual input document")
    parser.add_argument("--state-output", type=str)
    parser.add_argument("--write-receipt", type=str)
    parser.add_argument("--human-review", type=str)
    parser.add_argument("--handoff", type=str)
    parser.add_argument("--pptx", type=str)
    parser.add_argument("--expect-pptx-sha256", type=str)
    parser.add_argument("--expect", action="append", default=[], help="artifact_kind:content_sha256 binding")
    arguments = parser.parse_args(argv[1:])
    modes_with_one_path = {"validate", "freshness"}
    valid = (
        (arguments.mode in modes_with_one_path and bool(arguments.ledger_path) and not arguments.second_path)
        or (arguments.mode == "check-public-copy" and bool(arguments.ledger_path) and bool(arguments.second_path))
        or (arguments.mode == "verify-delivery" and bool(arguments.ledger_path) and bool(arguments.second_path))
        or (arguments.mode == "verify-release" and bool(arguments.ledger_path) and bool(arguments.second_path) and bool(arguments.third_path))
    )
    if not valid:
        print(json.dumps({"ok": False, "errors": [_error(
            "RUNTIME_ERROR", "",
            "usage: design_data_staleness.py validate <ledger> | "
            "freshness <ledger> --mode intermediate|delivery [--document role=path]... [--human-review r.json --handoff h.json] "
            "[--state-output out.json] [--write-receipt receipt.json] | "
            "check-public-copy <ledger> <copy.json> | "
            "verify-delivery <ledger> <receipt> --mode delivery --human-review r.json --handoff h.json [--document role=path]... | "
            "verify-release <ledger> <receipt> <human-review> --handoff h.json --pptx deck.pptx --expect-pptx-sha256 <sha> [--document role=path]...",
        )]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 3
    try:
        ledger = load_json_object(Path(arguments.ledger_path))
        state_output = load_json_object(Path(arguments.state_output)) if arguments.state_output else None
        documents, document_errors = _parse_document_args(arguments.document)
        base_dir = Path(arguments.ledger_path).resolve().parent

        def _emit(payload: object, code: int) -> int:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
            return code

        if arguments.mode == "validate":
            ok, errors = validate_ledger(ledger)
            return _emit({"ok": ok, "errors": errors}, 0 if ok else 1)
        if arguments.mode == "freshness":
            if arguments.delivery_mode is None:
                return _emit({"ok": False, "errors": [_error("MODE_REQUIRED", "", "freshness requires an explicit --mode intermediate|delivery")]}, 3)
            ok, errors = validate_ledger(ledger)
            if not ok:
                return _emit({"ok": False, "errors": errors}, 1)
            if document_errors:
                return _emit({"ok": False, "errors": document_errors}, 3)
            review = load_json_object(Path(arguments.human_review)) if arguments.human_review else None
            review_digest = None
            if arguments.delivery_mode == "delivery":
                if review is None:
                    return _emit({"ok": False, "errors": [_error("HUMAN_REVIEW_REQUIRED", "", "delivery freshness requires --human-review")]}, 1)
                review_ok, review_errors, review_digest = verify_human_review(review, ledger)
                if not review_ok:
                    return _emit({"ok": False, "errors": review_errors}, 1)
            receipt = compute_freshness(
                ledger,
                base_dir=base_dir,
                documents=documents,
                state_output=state_output,
                mode="DELIVERY" if arguments.delivery_mode == "delivery" else "INTERMEDIATE",
                human_review_digest=review_digest,
            )
            if arguments.write_receipt:
                Path(arguments.write_receipt).write_text(
                    json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
                    encoding="utf-8",
                )
            return _emit(receipt, 0)
        if arguments.mode == "check-public-copy":
            ok, ledger_errors = validate_ledger(ledger)
            if not ok:
                return _emit({"ok": False, "errors": ledger_errors}, 1)
            copy_document = load_json_object(Path(arguments.second_path))
            ok, errors = check_public_copy(ledger, copy_document)
            return _emit({"ok": ok, "errors": errors}, 0 if ok else 1)
        if arguments.mode == "verify-delivery":
            if arguments.delivery_mode != "delivery":
                return _emit({"ok": False, "errors": [_error("MODE_REQUIRED", "", "verify-delivery runs only in --mode delivery")]}, 3)
            receipt = load_json_object(Path(arguments.second_path))
            review = load_json_object(Path(arguments.human_review)) if arguments.human_review else None
            bindings: list[tuple[str, str]] = []
            for expectation in arguments.expect:
                kind, separator, digest = expectation.partition(":")
                if not separator or not kind or not digest:
                    return _emit({"ok": False, "errors": [_error("RUNTIME_ERROR", "", f"--expect requires kind:sha256, got {expectation!r}")]}, 3)
                bindings.append((kind, digest))
            ok, errors, _verdict = verify_delivery_freshness(
                ledger,
                receipt,
                base_dir=base_dir,
                documents=documents,
                state_output=state_output,
                human_review=review,
                expected_bindings=bindings,
                require_human_review=True,
                verify_copy_bindings=True,
            )
            return _emit({"ok": ok, "errors": errors}, 0 if ok else 1)
        # verify-release
        receipt = load_json_object(Path(arguments.second_path))
        review = load_json_object(Path(arguments.third_path)) if arguments.third_path else None
        if not arguments.pptx or not arguments.expect_pptx_sha256 or not arguments.handoff:
            return _emit({"ok": False, "errors": [_error("RUNTIME_ERROR", "", "verify-release requires --handoff, --pptx, and --expect-pptx-sha256")]}, 3)
        documents[HANDOFF_PRESENTATION_ROLE] = Path(arguments.handoff)
        ok, errors, verdict = verify_release(
            ledger,
            receipt,
            review,
            base_dir=base_dir,
            documents=documents,
            state_output=state_output,
            pptx_path=Path(arguments.pptx),
            expected_pptx_sha256=arguments.expect_pptx_sha256,
        )
        payload = dict(verdict) if verdict else {}
        payload["ok"] = ok
        payload["errors"] = errors
        payload.setdefault("mode", "DELIVERY")
        payload.setdefault("pptx_sha256", arguments.expect_pptx_sha256)
        return _emit(payload, 0 if ok else 1)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return _emit({"ok": False, "errors": [_error("RUNTIME_ERROR", "", str(error))]}, 3)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
