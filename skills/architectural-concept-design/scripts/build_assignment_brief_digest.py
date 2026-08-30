"""Build one literal-only assignment brief digest from a structured intake.

This deterministic, local-only gate turns a human or reader-agent authored
intake record (file inventory, pre-extracted segments, source locators,
readability status, declared conflicts and unknowns) into an
AssignmentBriefDigest. Every accepted literal requirement keeps its file and
source locator; partial, unreadable, missing, duplicate, conflicting, and
deferred input is represented without invention; every readable or partial
input file must be represented by at least one extracted segment; at most
three clarification questions are carried; and the digest stays pending until
an explicit human confirmation record is bound by the confirm subcommand. The
confirmation record must carry the exact SHA-256 of the supplied pending
digest document, so any later edit to that document is rejected. The builder
parses no DOC, DOCX, PDF, HTML, or image content and claims no format
extraction support. It opens no socket and starts no subprocess, records no
wall-clock time, and writes a destination only after full validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from _human_record import is_human_record_label
from _rfc3339 import is_rfc3339_datetime

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover - exercised only in an incomplete runtime install.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    Registry = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]

JsonObject = Mapping[str, Any]

REFERENCES = Path(__file__).resolve().parents[1] / "references"
INTAKE_SCHEMA_PATH = REFERENCES / "assignment-brief-intake.schema.json"
DIGEST_SCHEMA_PATH = REFERENCES / "assignment-brief-digest.schema.json"

CANDIDATE_STATUSES: tuple[str, ...] = ("included", "duplicate_merged", "conflict", "deferred_with_reason")
ALL_STATUSES: tuple[str, ...] = (
    "included",
    "duplicate_merged",
    "conflict",
    "missing",
    "unreadable",
    "deferred_with_reason",
)
PENDING_DIGEST_HASH_RE = re.compile(r"[0-9a-f]{64}")

DOWNSTREAM = {
    "consumable_by": "human authoring of the normalized brief ledger and the ADR-0001 input brief, only after human confirmation",
    "mapping_note": (
        "Confirmed digest requirements become candidate facts a human authors as sourced evidence; "
        "unknowns become the missing-information register. The digest authors no evidence, source, "
        "design interpretation, option, area allocation, or decision itself."
    ),
}

NOT_GENERATED: tuple[str, ...] = (
    "design_options",
    "recommendations",
    "area_allocation",
    "floor_count_decisions",
    "entrance_decisions",
    "massing_recommendations",
    "design_interpretations",
    "hypotheses",
    "decisions",
    "SRC",
    "Evidence",
    "CARD",
    "VERIFIED",
)


class DigestError(TypedDict):
    """One deterministic rejection without a partial digest."""

    code: str
    path: str
    message: str


class DigestResult(TypedDict):
    """The public result of building or confirming one digest."""

    ok: bool
    errors: list[DigestError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> DigestError:
    return {"code": code, "path": path, "message": message}


def _registry(intake_schema: JsonObject, digest_schema: JsonObject) -> Any:
    resources = []
    for schema in (intake_schema, digest_schema):
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(dict(schema))))
    return Registry().with_resources(resources)


def _schema_errors(instance: object, schema: JsonObject, registry: Any, code: str) -> list[DigestError]:
    """Validate an instance against a committed Draft 2020-12 schema."""

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str):
        return [_error("SCHEMA_INVALID", "", "schema is missing a string $id")]
    if Draft202012Validator is None or Registry is None or Resource is None:  # pragma: no cover - runtime guard.
        return [_error("SCHEMA_TOOLING_MISSING", "", "jsonschema and referencing are required")]
    try:
        Draft202012Validator.check_schema(dict(schema))
        validator = Draft202012Validator(dict(schema), registry=registry)
    except Exception as error:  # pragma: no cover - the committed schemas are checked separately.
        return [_error("SCHEMA_INVALID", "", str(error))]
    errors: list[DigestError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(map(str, item.absolute_path)), item.message)):
        pointer = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error(code, pointer, f"schema rule failed: {error.validator}"))
    return errors


def _unique_id_errors(ids: Sequence[str], path: str, code: str, label: str) -> list[DigestError]:
    seen: set[str] = set()
    errors: list[DigestError] = []
    for item_id in ids:
        if item_id in seen:
            errors.append(_error(code, path, f"duplicate {label}: {item_id}"))
        seen.add(item_id)
    return errors


def _locator_for(segment: JsonObject) -> str:
    return f"{segment['source_file']} :: {segment['source_locator']}"


def build_digest(
    intake: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
) -> tuple[dict[str, Any] | None, DigestResult]:
    """Return one literal-only digest, or no digest on any failed gate."""

    registry = _registry(intake_schema, digest_schema)
    schema_errors = _schema_errors(intake, intake_schema, registry, "INTAKE_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    files: list[JsonObject] = list(intake.get("input_files", []))
    segments: list[JsonObject] = list(intake.get("extracted_segments", []))
    conflicts: list[JsonObject] = list(intake.get("declared_conflicts", []))
    unknowns: list[JsonObject] = list(intake.get("declared_unknowns", []))
    candidates: list[JsonObject] = list(intake.get("requirement_candidates", []))

    errors: list[DigestError] = []
    errors.extend(_unique_id_errors([str(f["path_label"]) for f in files], "/input_files", "DUPLICATE_FILE_LABEL", "path_label"))

    segment_ids = [str(s["segment_id"]) for s in segments]
    errors.extend(_unique_id_errors(segment_ids, "/extracted_segments", "DUPLICATE_SEGMENT_ID", "segment_id"))
    errors.extend(_unique_id_errors([str(c["conflict_id"]) for c in conflicts], "/declared_conflicts", "DUPLICATE_CONFLICT_ID", "conflict_id"))
    errors.extend(_unique_id_errors([str(u["unknown_id"]) for u in unknowns], "/declared_unknowns", "DUPLICATE_UNKNOWN_ID", "unknown_id"))
    errors.extend(_unique_id_errors([str(c["candidate_id"]) for c in candidates], "/requirement_candidates", "DUPLICATE_CANDIDATE_ID", "candidate_id"))
    errors.extend(_unique_id_errors([str(n["note_id"]) for n in intake.get("human_notes", [])], "/human_notes", "DUPLICATE_NOTE_ID", "note_id"))

    file_labels = {str(f["path_label"]): f for f in files}
    segment_by_id: dict[str, JsonObject] = {}
    for index, segment in enumerate(segments):
        segment_id = str(segment["segment_id"])
        segment_by_id.setdefault(segment_id, segment)
        source_file = str(segment["source_file"])
        pointer = f"/extracted_segments/{index}"
        if source_file not in file_labels:
            errors.append(_error("SEGMENT_SOURCE_FILE_UNKNOWN", pointer, f"segment {segment_id} references unknown file label: {source_file}"))
            continue
        if file_labels[source_file]["readability"] == "unreadable":
            errors.append(_error("SEGMENT_SOURCE_UNREADABLE_FILE", pointer, f"segment {segment_id} cannot be extracted from unreadable file: {source_file}"))

    represented_files: set[str] = {
        str(segment["source_file"]) for segment in segments if str(segment["source_file"]) in file_labels
    }
    for path_label, file in file_labels.items():
        if file["readability"] in ("readable", "partial") and path_label not in represented_files:
            errors.append(
                _error(
                    "INPUT_FILE_UNREPRESENTED",
                    "/input_files",
                    f"readable or partial file has no extracted segment and would silently disappear: {path_label}",
                )
            )

    conflict_by_id: dict[str, JsonObject] = {}
    for index, conflict in enumerate(conflicts):
        conflict_id = str(conflict["conflict_id"])
        conflict_by_id.setdefault(conflict_id, conflict)
        for segment_id in conflict["segment_ids"]:
            if str(segment_id) not in segment_by_id:
                errors.append(_error("CONFLICT_SEGMENT_UNKNOWN", f"/declared_conflicts/{index}", f"conflict {conflict_id} references unknown segment: {segment_id}"))

    covered_segments: set[str] = set()
    for index, candidate in enumerate(candidates):
        pointer = f"/requirement_candidates/{index}"
        candidate_id = str(candidate["candidate_id"])
        candidate_segments = [str(s) for s in candidate["source_segment_ids"]]
        merged_segments = [str(s) for s in candidate.get("merged_from_segment_ids", [])]
        for segment_id in candidate_segments + merged_segments:
            if segment_id not in segment_by_id:
                errors.append(_error("CANDIDATE_SEGMENT_UNKNOWN", pointer, f"candidate {candidate_id} references unknown segment: {segment_id}"))
            else:
                covered_segments.add(segment_id)
        if candidate["status"] == "duplicate_merged" and not set(candidate_segments) <= set(merged_segments):
            errors.append(_error("MERGED_SEGMENTS_INCONSISTENT", pointer, f"candidate {candidate_id} source segments must be contained in merged_from_segment_ids"))
        if candidate["status"] == "conflict":
            referenced = [str(c) for c in candidate.get("conflict_ids", [])]
            conflict_segment_sets: list[set[str]] = []
            for conflict_id in referenced:
                conflict = conflict_by_id.get(conflict_id)
                if conflict is None:
                    errors.append(_error("CANDIDATE_CONFLICT_UNKNOWN", pointer, f"candidate {candidate_id} references unknown conflict: {conflict_id}"))
                else:
                    conflict_segment_sets.append({str(s) for s in conflict["segment_ids"]})
            if conflict_segment_sets:
                union_segments = set().union(*conflict_segment_sets)
                if not set(candidate_segments) <= union_segments:
                    errors.append(
                        _error(
                            "CANDIDATE_CONFLICT_MISMATCH",
                            pointer,
                            f"candidate {candidate_id} source segments must all belong to the segments of its declared conflicts",
                        )
                    )

    uncovered = sorted(set(segment_ids) - covered_segments)
    if uncovered:
        errors.append(_error("UNCOVERED_SEGMENT", "/extracted_segments", f"every extracted segment needs a status: uncovered {', '.join(uncovered)}"))

    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    requirements: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: str(item["candidate_id"])):
        status = str(candidate["status"])
        supporting = [str(s) for s in candidate.get("merged_from_segment_ids", candidate["source_segment_ids"])]
        locator = " + ".join(_locator_for(segment_by_id[segment_id]) for segment_id in sorted(supporting))
        requirement: dict[str, Any] = {
            "category": candidate["category"],
            "concise_text": candidate["concise_text"],
            "status": status,
            "literal_only": True,
            "source_locator": locator,
            "source_segment_ids": sorted(str(s) for s in candidate["source_segment_ids"]),
        }
        if status == "duplicate_merged":
            requirement["merged_from_segment_ids"] = sorted(str(s) for s in candidate["merged_from_segment_ids"])
        if status == "conflict":
            requirement["conflict_ids"] = sorted(str(c) for c in candidate["conflict_ids"])
        if status == "deferred_with_reason":
            requirement["deferred_reason"] = candidate["deferred_reason"]
        requirements.append(requirement)

    for unknown in sorted(unknowns, key=lambda item: str(item["unknown_id"])):
        unknown_id = str(unknown["unknown_id"])
        requirements.append(
            {
                "category": unknown["expected_category"],
                "concise_text": unknown["description"],
                "status": "unreadable" if unknown["kind"] == "unreadable" else "missing",
                "literal_only": True,
                "source_locator": f"declared-unknown:{unknown_id}",
                "source_segment_ids": [],
                "unknown_id": unknown_id,
            }
        )

    for number, requirement in enumerate(requirements, start=1):
        requirement_id = f"REQ-{number:03d}"
        requirements[number - 1] = {"requirement_id": requirement_id, **requirement}

    digest_conflicts = []
    for conflict in sorted(conflicts, key=lambda item: str(item["conflict_id"])):
        digest_conflicts.append(
            {
                "conflict_id": conflict["conflict_id"],
                "description": conflict["description"],
                "segment_ids": [str(s) for s in conflict["segment_ids"]],
                "locators": [_locator_for(segment_by_id[str(s)]) for s in conflict["segment_ids"]],
            }
        )

    digest_unknowns = [
        {
            "unknown_id": unknown["unknown_id"],
            "expected_category": unknown["expected_category"],
            "kind": unknown["kind"],
            "description": unknown["description"],
        }
        for unknown in sorted(unknowns, key=lambda item: str(item["unknown_id"]))
    ]

    status_counts = {status: 0 for status in ALL_STATUSES}
    for requirement in requirements:
        status_counts[str(requirement["status"])] += 1

    digest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "digest_kind": "assignment_brief_digest",
        "input_hash": compute_input_hash(intake),
        "project_title": intake["project_title"],
        "input_files": [dict(file) for file in files],
        "requirements": requirements,
        "conflicts": digest_conflicts,
        "unknowns": digest_unknowns,
        "clarification_questions": [str(q) for q in intake.get("clarification_questions", [])],
        "human_notes": [dict(note) for note in intake.get("human_notes", [])],
        "coverage_summary": {
            "input_file_count": len(files),
            "unreadable_file_count": sum(1 for f in files if f["readability"] == "unreadable"),
            "segment_count": len(segments),
            "covered_segment_count": len(covered_segments),
            "uncovered_segments": [],
            "requirement_count_by_status": status_counts,
        },
        "human_confirmation": {"status": "pending"},
        "downstream": dict(DOWNSTREAM),
        "not_generated": list(NOT_GENERATED),
    }

    digest_errors = _schema_errors(digest, digest_schema, registry, "DIGEST_SCHEMA_INVALID")
    if digest_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": digest_errors}
    return digest, {"ok": True, "errors": []}


def confirm_digest(
    digest: JsonObject,
    human_record: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
) -> tuple[dict[str, Any] | None, DigestResult]:
    """Bind one explicit human confirmation record to a pending digest.

    The record must carry the exact SHA-256 of the supplied pending digest
    document. The hash is recomputed over the whole pending document and any
    mismatch is rejected, so a digest edited after review cannot be confirmed.
    """

    registry = _registry(intake_schema, digest_schema)
    schema_errors = _schema_errors(digest, digest_schema, registry, "DIGEST_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = digest.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("DIGEST_ALREADY_CONFIRMED", "/human_confirmation", "only a pending digest can be confirmed")]}

    errors: list[DigestError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_digest_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("HUMAN_RECORD_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != "CONFIRM_BRIEF_DIGEST":
            errors.append(_error("CONFIRMATION_ACTION_INVALID", "/action", "action must be CONFIRM_BRIEF_DIGEST"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("HUMAN_RECORD_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("CONFIRMATION_TIME_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_digest_sha256")
        if not isinstance(bound_hash, str) or PENDING_DIGEST_HASH_RE.fullmatch(bound_hash) is None:
            errors.append(_error("HUMAN_RECORD_INVALID", "/pending_digest_sha256", "pending_digest_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_digest_sha256(digest):
            errors.append(
                _error(
                    "PENDING_DIGEST_HASH_MISMATCH",
                    "/pending_digest_sha256",
                    "recorded hash does not match the supplied pending digest document",
                )
            )
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(digest))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": "CONFIRM_BRIEF_DIGEST",
        "pending_digest_sha256": human_record["pending_digest_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, digest_schema, registry, "DIGEST_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def compute_input_hash(intake: JsonObject) -> str:
    """Return the SHA-256 of the canonical raw intake."""

    return hashlib.sha256(_canonical_json(intake)).hexdigest()


def compute_pending_digest_sha256(digest: JsonObject) -> str:
    """Return the SHA-256 of one whole pending digest document.

    The hash covers the canonical JSON plus trailing newline bytes of the
    complete pending document, every field from ``schema_version`` through
    ``not_generated``, including the pending ``human_confirmation`` object and
    the intake-derived ``input_hash``. It is the human-confirmation binding;
    ``input_hash`` alone is only the intake provenance hash.
    """

    return hashlib.sha256(_canonical_json(digest) + b"\n").hexdigest()


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write the fully validated digest as UTF-8, replacing only at the end."""

    encoded = _canonical_json(payload) + b"\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise
    return hashlib.sha256(encoded).hexdigest()


def _load_failure(code: str, message: str) -> DigestResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, DigestResult]:
    if output is None:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0, {"ok": True, "errors": []}
    try:
        output_hash = _write_atomically(output, payload)
    except OSError as error:
        return 2, _load_failure("OUTPUT_WRITE_FAILED", str(error))
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0, {"ok": True, "errors": []}


def main(argv: Sequence[str]) -> int:
    """Build a pending digest or bind one human confirmation record."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build one pending digest from a structured intake")
    build_parser.add_argument("intake", type=Path, help="structured assignment brief intake JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending digest")
    confirm_parser.add_argument("digest", type=Path, help="pending assignment brief digest JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema = load_json_object(INTAKE_SCHEMA_PATH)
        digest_schema = load_json_object(DIGEST_SCHEMA_PATH)
        if arguments.command == "build":
            intake = load_json_object(arguments.intake)
        else:
            digest_document = load_json_object(arguments.digest)
            human_record = load_json_object(arguments.human_record)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "build":
        digest, result = build_digest(intake, intake_schema, digest_schema)
    else:
        digest, result = confirm_digest(digest_document, human_record, intake_schema, digest_schema)

    if digest is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    exit_code, _ = _emit(digest, arguments.output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
