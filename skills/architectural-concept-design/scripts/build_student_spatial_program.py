"""Build one deterministic student spatial program from confirmed upstream records.

This deterministic, local-only slice accepts exactly three confirmed upstream
documents: an ARCH-097 AssignmentBriefDigest, its exact ARCH-098 start board
projection, and one human-confirmed student spatial program draft. It
organizes only what the human explicitly wrote: functional spaces, area
statements, zones, activity profiles, and adjacency or separation relations.
It never invents a space, area, relation, zone, activity profile, or design
content, and it emits no grossing factor, efficiency ratio, dimension, floor
count, entrance, circulation scheme, massing, grid, height, environmental
conclusion, option, or recommendation. The output is JSON data only: no HTML,
web page, PPTX, image, plan, or massing diagram. It opens no socket and starts
no subprocess, reads no system clock, never modifies an input document, and
writes a destination only after full validation. Validate re-derives the
expected output deterministically and requires exact byte equality.
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
from build_student_design_start_board import _verify_confirmed_digest, compute_confirmed_digest_sha256, validate_board
from check_area_schedule import calculate_area_schedule

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
BOARD_SCHEMA_PATH = REFERENCES / "student-design-start-board.schema.json"
DRAFT_SCHEMA_PATH = REFERENCES / "student-spatial-program-draft.schema.json"
PROGRAM_SCHEMA_PATH = REFERENCES / "student-spatial-program.schema.json"

ZONE_ORDER: tuple[str, ...] = ("public", "internal_staff", "service_support", "shared", "unresolved")
RELATION_KINDS: frozenset[str] = frozenset({"must_be_near", "prefer_be_near", "must_be_separate", "shared_support"})
CONFIRM_ACTION = "CONFIRM_STUDENT_SPATIAL_PROGRAM_DRAFT"
SHA256_RE = re.compile(r"[0-9a-f]{64}")

RESOLVE_GAPS_ACTION = {
    "action": "resolve_program_gaps",
    "description": (
        "Next, resolve the listed gaps: answer the unresolved brief items, the unresolved "
        "program inputs, and the spaces without an area value. This program does not fill them in for you."
    ),
}
DIMENSION_CANDIDATES_ACTION = {
    "action": "dimension_candidates",
    "description": (
        "Next, prepare dimension candidates for the confirmed spaces in a separately reviewed "
        "student spatial programming step. This program supplies no dimensions itself."
    ),
}

BOUNDARIES: tuple[str, ...] = (
    "This program decides no area value, area total, dimension, or size that the draft does not state.",
    "This program decides no floor count, entrance position, circulation scheme, massing, grid, or height.",
    "This program produces no design option, recommendation, winner, concept, or scheme.",
    "A complete area status means every current space has a number; it is not a final, approval, or constructibility conclusion.",
    "Human working figures stay working figures; they are never presented as brief facts.",
)


class ProgramError(TypedDict):
    """One deterministic rejection without a partial output."""

    code: str
    path: str
    message: str


class ProgramResult(TypedDict):
    """The public result of confirming, building, or validating one program."""

    ok: bool
    errors: list[ProgramError]


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one finite UTF-8 JSON object."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is not allowed: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _error(code: str, path: str, message: str) -> ProgramError:
    return {"code": code, "path": path, "message": message}


def _registry(*schemas: JsonObject) -> Any:
    resources = []
    for schema in schemas:
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(dict(schema))))
    return Registry().with_resources(resources)


def _schema_errors(instance: object, schema: JsonObject, registry: Any, code: str) -> list[ProgramError]:
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
    errors: list[ProgramError] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: (list(map(str, item.absolute_path)), item.message)):
        pointer = "/" + "/".join(str(token) for token in error.absolute_path)
        errors.append(_error(code, pointer, f"schema rule failed: {error.validator}"))
    return errors


def _canonical_json(payload: JsonObject) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _document_sha256(payload: JsonObject) -> str:
    """Return the SHA-256 of the canonical JSON plus newline bytes of one whole document."""

    return hashlib.sha256(_canonical_json(payload) + b"\n").hexdigest()


def compute_pending_draft_sha256(draft: JsonObject) -> str:
    """Return the SHA-256 binding the pre-confirmation draft document.

    The pre-confirmation document is the supplied draft with
    ``human_confirmation`` restored to its pending form, exactly as the
    confirm subcommand saw it before binding the human record.
    """

    pending_view = json.loads(json.dumps(draft))
    pending_view["human_confirmation"] = {"status": "pending"}
    return _document_sha256(pending_view)


def confirm_program_draft(
    draft: JsonObject,
    human_record: JsonObject,
    draft_schema: JsonObject,
) -> tuple[dict[str, Any] | None, ProgramResult]:
    """Bind one explicit human confirmation record to a pending program draft."""

    registry = _registry(draft_schema)
    schema_errors = _schema_errors(draft, draft_schema, registry, "PROGRAM_DRAFT_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": schema_errors}

    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return None, {"ok": False, "errors": [_error("PROGRAM_DRAFT_NOT_CONFIRMED", "/human_confirmation", "only a pending draft can be confirmed")]}

    errors: list[ProgramError] = []
    expected_keys = {"action", "confirmed_by", "confirmed_at", "pending_draft_sha256"}
    if set(human_record.keys()) != expected_keys:
        errors.append(_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "", f"human record must contain exactly the keys {sorted(expected_keys)}"))
    else:
        if human_record.get("action") != CONFIRM_ACTION:
            errors.append(_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "/action", f"action must be {CONFIRM_ACTION}"))
        if not is_human_record_label(human_record.get("confirmed_by")):
            errors.append(_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "/confirmed_by", "confirmed_by must name a human, not an agent"))
        if not is_rfc3339_datetime(human_record.get("confirmed_at")):
            errors.append(_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "/confirmed_at", "confirmed_at must be a timezone-qualified RFC 3339 date-time"))
        bound_hash = human_record.get("pending_draft_sha256")
        if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None:
            errors.append(_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "/pending_draft_sha256", "pending_draft_sha256 must be exactly 64 lowercase hex characters"))
        elif bound_hash != compute_pending_draft_sha256(draft):
            errors.append(_error("PROGRAM_DRAFT_HASH_MISMATCH", "/pending_draft_sha256", "recorded hash does not match the supplied pending draft document"))
    if errors:
        errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": errors}

    confirmed: dict[str, Any] = json.loads(json.dumps(draft))
    confirmed["human_confirmation"] = {
        "status": "confirmed",
        "confirmed_by": human_record["confirmed_by"],
        "confirmed_at": human_record["confirmed_at"],
        "action": CONFIRM_ACTION,
        "pending_draft_sha256": human_record["pending_draft_sha256"],
    }

    confirmed_errors = _schema_errors(confirmed, draft_schema, registry, "PROGRAM_DRAFT_SCHEMA_INVALID")
    if confirmed_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": confirmed_errors}
    return confirmed, {"ok": True, "errors": []}


def _verify_confirmed_draft(draft: JsonObject, draft_schema: JsonObject, registry: Any) -> list[ProgramError]:
    """Fail closed on any schema-invalid, unconfirmed, or mismatched program draft."""

    errors = _schema_errors(draft, draft_schema, registry, "PROGRAM_DRAFT_SCHEMA_INVALID")
    if errors:
        return errors
    confirmation = draft.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "confirmed":
        return [_error("PROGRAM_DRAFT_NOT_CONFIRMED", "/human_confirmation", "the program draft must be confirmed before a spatial program can be built")]
    if confirmation.get("action") != CONFIRM_ACTION or not is_human_record_label(confirmation.get("confirmed_by")) or not is_rfc3339_datetime(confirmation.get("confirmed_at")):
        return [_error("PROGRAM_DRAFT_CONFIRMATION_INVALID", "/human_confirmation", "the recorded confirmation is not a valid human record")]
    bound_hash = confirmation.get("pending_draft_sha256")
    if not isinstance(bound_hash, str) or SHA256_RE.fullmatch(bound_hash) is None or bound_hash != compute_pending_draft_sha256(draft):
        return [_error("PROGRAM_DRAFT_HASH_MISMATCH", "/human_confirmation/pending_draft_sha256", "the recorded confirmation hash does not bind this draft's pre-confirmation document")]
    return []


def _board_locator_sets(board: JsonObject) -> tuple[set[str], set[str]]:
    """Return (all confirmed locators, program-category locators) of one start board."""

    all_locators: set[str] = set()
    program_locators: set[str] = set()
    for group in board["student_view"]["confirmed_requirements"]:
        for item in group["items"]:
            locator = str(item["source_locator"])
            all_locators.add(locator)
            if group["category"] == "program":
                program_locators.add(locator)
    return all_locators, program_locators


def _draft_semantic_errors(draft: JsonObject, board: JsonObject) -> list[ProgramError]:
    """Check the human-authored draft against the confirmed start board, without inventing anything."""

    errors: list[ProgramError] = []
    all_locators, program_locators = _board_locator_sets(board)

    spaces: list[JsonObject] = list(draft["spaces"])
    space_ids = [str(space["space_id"]) for space in spaces]
    seen_space_ids: set[str] = set()
    for space_id in space_ids:
        if space_id in seen_space_ids:
            errors.append(_error("PROGRAM_DRAFT_SCHEMA_INVALID", "/spaces", f"duplicate space_id: {space_id}"))
        seen_space_ids.add(space_id)
    space_names: dict[str, str] = {}

    mapped_program_locators: set[str] = set()
    seen_space_names: set[str] = set()
    for index, space in enumerate(spaces):
        pointer = f"/spaces/{index}"
        space_id = str(space["space_id"])
        space_name = str(space["name"])
        space_names.setdefault(space_id, space_name)
        if space_name in seen_space_names:
            errors.append(
                _error(
                    "PROGRAM_DRAFT_SCHEMA_INVALID",
                    pointer,
                    f"duplicate space name: {space_name}; the student view shows names only, so every space needs a distinct name",
                )
            )
        seen_space_names.add(space_name)
        origin = space["origin"]
        if origin["kind"] == "brief_stated":
            if str(origin["locator"]) not in all_locators:
                errors.append(_error("PROGRAM_SOURCE_LOCATOR_UNKNOWN", pointer, f"space {space_id} claims a brief origin locator that is not in the confirmed start board"))
            else:
                if str(origin["locator"]) in program_locators:
                    mapped_program_locators.add(str(origin["locator"]))
        area = space["area"]
        if area["kind"] == "brief_stated":
            if str(area["locator"]) not in program_locators:
                errors.append(_error("PROGRAM_SOURCE_LOCATOR_UNKNOWN", pointer, f"space {space_id} claims a brief area locator that is not a confirmed program locator of the start board"))
            else:
                mapped_program_locators.add(str(area["locator"]))

    declared_unresolved: dict[str, str] = {}
    seen_record_ids: set[str] = set()
    for index, record in enumerate(draft["unresolved_program_input"]):
        pointer = f"/unresolved_program_input/{index}"
        record_id = str(record["record_id"])
        if record_id in seen_record_ids:
            errors.append(_error("PROGRAM_DRAFT_SCHEMA_INVALID", pointer, f"duplicate unresolved record id: {record_id}"))
        seen_record_ids.add(record_id)
        locator = str(record["locator"])
        if locator not in program_locators:
            errors.append(_error("PROGRAM_SOURCE_LOCATOR_UNKNOWN", pointer, f"unresolved record references a locator that is not a confirmed program locator of the start board: {locator}"))
            continue
        if locator in declared_unresolved:
            errors.append(_error("PROGRAM_DRAFT_SCHEMA_INVALID", pointer, f"duplicate unresolved record for locator: {locator}"))
        declared_unresolved.setdefault(locator, str(record["reason"]))

    for locator in sorted(mapped_program_locators & set(declared_unresolved)):
        errors.append(_error("PROGRAM_DRAFT_SCHEMA_INVALID", "/unresolved_program_input", f"locator is both mapped to a brief_stated space and kept unresolved: {locator}"))
    for locator in sorted(program_locators - mapped_program_locators - set(declared_unresolved)):
        errors.append(_error("PROGRAM_SOURCE_LOCATOR_UNKNOWN", "/spaces", f"confirmed program locator is neither mapped nor explicitly kept unresolved: {locator}"))

    relations: list[JsonObject] = list(draft["relations"])
    relation_ids = [str(relation["relation_id"]) for relation in relations]
    seen_relation_ids: set[str] = set()
    for relation_id in relation_ids:
        if relation_id in seen_relation_ids:
            errors.append(_error("PROGRAM_DRAFT_SCHEMA_INVALID", "/relations", f"duplicate relation_id: {relation_id}"))
        seen_relation_ids.add(relation_id)

    pair_kinds: dict[tuple[str, str], set[str]] = {}
    for index, relation in enumerate(relations):
        pointer = f"/relations/{index}"
        relation_id = str(relation["relation_id"])
        from_id = str(relation["from_space_id"])
        to_id = str(relation["to_space_id"])
        if from_id == to_id:
            errors.append(_error("PROGRAM_RELATION_INVALID", pointer, f"relation {relation_id} relates a space to itself"))
            continue
        if from_id not in seen_space_ids:
            errors.append(_error("PROGRAM_RELATION_INVALID", pointer, f"relation {relation_id} references unknown space: {from_id}"))
        if to_id not in seen_space_ids:
            errors.append(_error("PROGRAM_RELATION_INVALID", pointer, f"relation {relation_id} references unknown space: {to_id}"))
        basis = relation["basis"]
        if basis["kind"] == "brief_stated" and str(basis["locator"]) not in all_locators:
            errors.append(_error("PROGRAM_SOURCE_LOCATOR_UNKNOWN", pointer, f"relation {relation_id} claims a brief locator that is not in the confirmed start board"))
        pair = tuple(sorted((from_id, to_id)))
        if pair in pair_kinds:
            errors.append(
                _error(
                    "PROGRAM_RELATION_INVALID",
                    pointer,
                    f"relation {relation_id} repeats the same pair of spaces: {from_id} and {to_id}; one unordered pair keeps exactly one relation",
                )
            )
            continue
        pair_kinds[pair] = str(relation["kind"])

    return errors


def _subtotal_m2(entries: list[dict[str, Any]]) -> float:
    """Reuse the deterministic area-schedule calculation for one group of numeric spaces."""

    if not entries:
        return 0.0
    result = calculate_area_schedule({"spaces": entries})
    net_area = result["net_area"]
    return float(net_area["value"])


def build_program(
    digest: JsonObject,
    board: JsonObject,
    draft: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    draft_schema: JsonObject,
    program_schema: JsonObject,
) -> tuple[dict[str, Any] | None, ProgramResult]:
    """Return one deterministic student spatial program, or no output on any failed gate."""

    registry = _registry(intake_schema, digest_schema, board_schema, draft_schema, program_schema)
    digest_errors = _verify_confirmed_digest(digest, intake_schema, digest_schema, registry)
    if digest_errors:
        return None, {"ok": False, "errors": [dict(error) for error in digest_errors]}

    board_result = validate_board(digest, board, intake_schema, digest_schema, board_schema)
    if not board_result["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in board_result["errors"]]}

    draft_errors = _verify_confirmed_draft(draft, draft_schema, registry)
    if draft_errors:
        return None, {"ok": False, "errors": draft_errors}

    semantic_errors = _draft_semantic_errors(draft, board)
    if semantic_errors:
        semantic_errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
        return None, {"ok": False, "errors": semantic_errors}

    spaces: list[JsonObject] = list(draft["spaces"])
    space_names = {str(space["space_id"]): str(space["name"]) for space in spaces}

    zone_groups: dict[str, list[dict[str, Any]]] = {zone: [] for zone in ZONE_ORDER}
    brief_entries: list[dict[str, Any]] = []
    working_entries: list[dict[str, Any]] = []
    unresolved_area_names: list[str] = []
    unresolved_program_items: list[dict[str, Any]] = []
    for space in spaces:
        area = space["area"]
        view_space: dict[str, Any] = {
            "name": space["name"],
            "activity_profile": space["activity_profile"],
            "area_status": area["kind"],
        }
        if area["kind"] == "brief_stated":
            view_space["area_value_m2"] = area["value_m2"]
            view_space["origin_basis"] = f"brief: {space['origin']['locator'] if space['origin']['kind'] == 'brief_stated' else space['origin']['reason']} :: area {area['locator']}"
            brief_entries.append({"id": str(space["space_id"]), "area": {"value": area["value_m2"], "unit": "m2"}})
        elif area["kind"] == "human_working":
            view_space["area_value_m2"] = area["value_m2"]
            origin_text = space["origin"]["locator"] if space["origin"]["kind"] == "brief_stated" else space["origin"]["reason"]
            view_space["origin_basis"] = f"working figure ({area['working_note']}); origin: {origin_text}"
            working_entries.append({"id": str(space["space_id"]), "area": {"value": area["value_m2"], "unit": "m2"}})
        else:
            view_space["origin_basis"] = f"area unresolved: {area['unresolved_note']}"
            unresolved_area_names.append(str(space["name"]))
            unresolved_program_items.append({"kind": "area", "name": str(space["name"]), "note": str(area["unresolved_note"])})
        zone_groups[str(space["functional_zone"])].append(view_space)

    for record in draft["unresolved_program_input"]:
        unresolved_program_items.append({"kind": "program_input", "name": str(record["locator"]), "note": str(record["reason"])})

    brief_subtotal = _subtotal_m2(brief_entries)
    working_subtotal = _subtotal_m2(working_entries)
    scheduled_total = _subtotal_m2(brief_entries + working_entries)

    relations_view = []
    for relation in draft["relations"]:
        basis = relation["basis"]
        basis_text = f"brief: {basis['locator']}" if basis["kind"] == "brief_stated" else f"working note: {basis['reason']}"
        relations_view.append(
            {
                "from_space": space_names[str(relation["from_space_id"])],
                "to_space": space_names[str(relation["to_space_id"])],
                "kind": relation["kind"],
                "basis": basis_text,
            }
        )

    unresolved_brief_items = [
        {"kind": item["kind"], "description": item["description"]} for item in board["student_view"]["unresolved_items"]
    ]

    has_gaps = bool(unresolved_brief_items) or bool(unresolved_program_items)
    next_action = dict(RESOLVE_GAPS_ACTION) if has_gaps else dict(DIMENSION_CANDIDATES_ACTION)

    program: dict[str, Any] = {
        "schema_version": "1.0.0",
        "program_kind": "student_spatial_program",
        "source_binding": {
            "digest_input_hash": digest["input_hash"],
            "confirmed_digest_sha256": compute_confirmed_digest_sha256(digest),
            "pending_digest_sha256": digest["human_confirmation"]["pending_digest_sha256"],
            "start_board_sha256": _document_sha256(board),
            "confirmed_program_draft_sha256": _document_sha256(draft),
            "pending_program_draft_sha256": draft["human_confirmation"]["pending_draft_sha256"],
        },
        "student_view": {
            "project_title": digest["project_title"],
            "stage": "program_confirmed_ready_for_next_step",
            "spaces_by_zone": [{"zone": zone, "spaces": zone_groups[zone]} for zone in ZONE_ORDER],
            "area_summary": {
                "brief_stated_area_subtotal_m2": brief_subtotal,
                "human_working_area_subtotal_m2": working_subtotal,
                "scheduled_area_m2": scheduled_total,
                "unresolved_area_spaces": unresolved_area_names,
                "area_status": "partial" if unresolved_area_names else "complete",
            },
            "relations": relations_view,
            "unresolved_brief_items": unresolved_brief_items,
            "unresolved_program_items": unresolved_program_items,
            "clarification_questions": [str(question) for question in draft["clarification_questions"]],
            "next_action": next_action,
            "boundaries": list(BOUNDARIES),
        },
    }

    program_errors = _schema_errors(program, program_schema, registry, "STUDENT_SPATIAL_PROGRAM_SCHEMA_INVALID")
    if program_errors:  # pragma: no cover - defends the output contract against future drift.
        return None, {"ok": False, "errors": program_errors}
    return program, {"ok": True, "errors": []}


def validate_program(
    digest: JsonObject,
    board: JsonObject,
    draft: JsonObject,
    program: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
    draft_schema: JsonObject,
    program_schema: JsonObject,
) -> ProgramResult:
    """Re-derive the expected program from the three upstream inputs and compare it exactly."""

    registry = _registry(intake_schema, digest_schema, board_schema, draft_schema, program_schema)
    program_errors = _schema_errors(program, program_schema, registry, "STUDENT_SPATIAL_PROGRAM_SCHEMA_INVALID")
    if program_errors:
        return {"ok": False, "errors": program_errors}

    expected, build_result = build_program(digest, board, draft, intake_schema, digest_schema, board_schema, draft_schema, program_schema)
    if expected is None:
        return build_result
    if _canonical_json(program) + b"\n" != _canonical_json(expected) + b"\n":
        return {
            "ok": False,
            "errors": [
                _error(
                    "STUDENT_SPATIAL_PROGRAM_CONTENT_MISMATCH",
                    "",
                    "the supplied program is not the exact deterministic projection of its confirmed upstream documents",
                )
            ],
        }
    return {"ok": True, "errors": []}


def _write_atomically(path: Path, payload: JsonObject) -> str:
    """Write the fully validated document as UTF-8, replacing only at the end."""

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


def _load_failure(code: str, message: str) -> ProgramResult:
    return {"ok": False, "errors": [_error(code, "", message)]}


def _emit(payload: JsonObject, output: Path | None) -> tuple[int, ProgramResult]:
    if output is None:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0, {"ok": True, "errors": []}
    try:
        output_hash = _write_atomically(output, payload)
    except OSError as error:
        failure = _load_failure("OUTPUT_WRITE_FAILED", str(error))
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2, failure
    print(json.dumps({"ok": True, "output_sha256": output_hash}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0, {"ok": True, "errors": []}


def main(argv: Sequence[str]) -> int:
    """Confirm a pending draft, build a program, or validate one against its upstream documents."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    confirm_parser = subparsers.add_parser("confirm", help="bind one explicit human confirmation record to a pending program draft")
    confirm_parser.add_argument("draft", type=Path, help="pending student spatial program draft JSON")
    confirm_parser.add_argument("human_record", type=Path, help="human confirmation record JSON")
    confirm_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    build_parser = subparsers.add_parser("build", help="build one student spatial program from three confirmed upstream documents")
    build_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    build_parser.add_argument("board", type=Path, help="student design start board JSON")
    build_parser.add_argument("draft", type=Path, help="confirmed student spatial program draft JSON")
    build_parser.add_argument("--output", type=Path, help="optional UTF-8 destination written only after validation")

    validate_parser = subparsers.add_parser("validate", help="validate one student spatial program against its upstream documents")
    validate_parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    validate_parser.add_argument("board", type=Path, help="student design start board JSON")
    validate_parser.add_argument("draft", type=Path, help="confirmed student spatial program draft JSON")
    validate_parser.add_argument("program", type=Path, help="student spatial program JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema = load_json_object(INTAKE_SCHEMA_PATH)
        digest_schema = load_json_object(DIGEST_SCHEMA_PATH)
        board_schema = load_json_object(BOARD_SCHEMA_PATH)
        draft_schema = load_json_object(DRAFT_SCHEMA_PATH)
        program_schema = load_json_object(PROGRAM_SCHEMA_PATH)
        if arguments.command == "confirm":
            draft_document = load_json_object(arguments.draft)
            human_record = load_json_object(arguments.human_record)
        else:
            digest = load_json_object(arguments.digest)
            board = load_json_object(arguments.board)
            draft_document = load_json_object(arguments.draft)
            if arguments.command == "validate":
                program_document = load_json_object(arguments.program)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    if arguments.command == "confirm":
        confirmed, result = confirm_program_draft(draft_document, human_record, draft_schema)
        if confirmed is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(confirmed, arguments.output)
        return exit_code

    if arguments.command == "build":
        program, result = build_program(digest, board, draft_document, intake_schema, digest_schema, board_schema, draft_schema, program_schema)
        if program is None:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1
        exit_code, _ = _emit(program, arguments.output)
        return exit_code

    result = validate_program(digest, board, draft_document, program_document, intake_schema, digest_schema, board_schema, draft_schema, program_schema)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
