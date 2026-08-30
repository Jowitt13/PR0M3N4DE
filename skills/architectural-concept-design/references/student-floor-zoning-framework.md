# Student Floor and Functional Zoning Framework

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain and human dimension selection](#upstream-chain-and-human-dimension-selection)
- [Floor zoning draft rules](#floor-zoning-draft-rules)
- [Student view](#student-view)
- [What this slice never does](#what-this-slice-never-does)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Organize what the student has already written about floors and functional
zoning on top of human-selected dimension candidates: level labels and
sequence, zones, access and activity attributes, non-geometric
public-internal boundaries, and unresolved zoning items. Humans select
dimensions; humans write levels and zones; the machine only validates,
traces, projects, and rejects incomplete or tampered input. The builder
never adds, removes, reorders, or infers a level, assigns no space, and
resolves no item.

## Contracts

- Selection record: [`student-dimension-selection.schema.json`](student-dimension-selection.schema.json)
- Draft input: [`student-floor-zoning-draft.schema.json`](student-floor-zoning-draft.schema.json)
- Framework output: [`student-floor-zoning.schema.json`](student-floor-zoning.schema.json)
- Builder: [`build_student_floor_zoning.py`](../scripts/build_student_floor_zoning.py) with `confirm`, `build`, and `validate` subcommands.

## Upstream chain and human dimension selection

`build` and `validate` verify the full upstream chain by reusing the
committed ARCH-100 `validate_dimension_plan`: the confirmed ARCH-097 digest,
the exact ARCH-098 start board, the confirmed ARCH-099 spatial program draft
and its exact spatial program, and the confirmed ARCH-100 dimension draft and
its exact dimension plan. Any upstream tamper or failure propagates the
existing stable error codes unchanged; this slice never masks them.

The dimension selection is a direct human record with exactly one action
(`SELECT_STUDENT_DIMENSION_CANDIDATES`), one human label, one
timezone-qualified RFC 3339 time, and the exact canonical JSON plus newline
SHA-256 of the confirmed dimension plan it answers. Agent and model labels
are rejected. For every candidate set the human picks exactly one existing
option key; unknown spaces, unknown options, duplicate spaces, missing
candidate sets, and selections for deferred or candidate-less spaces fail
closed. The record carries no geometry, rationale, alternative, derived
area, or design field, and it can never inject or rewrite candidate
dimensions.

The floor zoning draft binds the complete selection record by canonical
SHA-256. Confirmation uses exactly four keys: `action`
(`CONFIRM_STUDENT_FLOOR_ZONING_DRAFT`), `confirmed_by`, `confirmed_at`, and
`pending_floor_zoning_draft_sha256`, which must equal the canonical JSON plus
newline SHA-256 of the whole pending draft. The confirmed draft preserves the
binding; any later tamper fails closed. No system clock is read and no
confirmer, time, or content is generated.

## Floor zoning draft rules

- Level count, labels, and sequence are all human input; the builder never
  adds, removes, reorders, or infers levels such as "two or three storeys".
- Level ids, orders, and labels are unique; zone ids and names are unique
  across the draft; boundary ids and unresolved record ids are unique.
- Every dimension-selected space enters exactly one zone or exactly one
  explicit unresolved zoning item with a human reason. A space must not
  disappear, repeat, or appear in both.
- Zone space names and unresolved space names must be dimension-selected
  spaces; unknown names fail closed.
- Boundaries are student-declared non-geometric relations between two
  existing zones with different access scopes. They never express doors,
  entrances, stairs, corridors, gates, coordinates, or plan layouts. One
  unordered zone pair keeps at most one boundary; self-boundaries fail
  closed.
- `access_scope` (`public` / `internal` / `shared`) and
  `activity_character` (`active` / `quiet` / `mixed`) copy student input
  only; the builder never moves "active" zones to lower levels or "quiet"
  zones to higher ones.

## Student view

The output is JSON data only: no PPTX, web page, image, or drawing.
`student_view` carries:

- the project title and the fixed stage
  `floor_zoning_confirmed_ready_for_next_step`;
- the human-written levels in human-written sequence, each zone with its
  access and activity attributes and each space with its human-selected
  option key and confirmed dimension values;
- the student-declared boundaries, expressed by zone names;
- unresolved zoning items with human reasons;
- the draft's clarification questions, at most three, carried verbatim;
- one deterministic next action: `resolve_floor_zoning_gaps` while any
  unresolved zoning item remains, otherwise
  `circulation_and_environment_framework`;
- a fixed boundaries statement.

The machine-only `source_binding` keeps the confirmed dimension plan hash,
the selection hash, the pending floor zoning draft binding hash, and the
upstream trace hashes. The student view exposes no internal identifier or
SHA-256.

## What this slice never does

This slice decides no level count and assigns no space to a level or zone.
It decides no entrance, exit, lobby, stair, elevator, evacuation, or
circulation. It produces no coordinate, dimension placement, orientation,
site plan, massing, grid, elevation, height, or environmental conclusion. It
recommends, ranks, selects, and judges no zone. It parses no DOC, DOCX, PDF,
HTML, image, or OCR content and claims no format extraction support. It opens
no socket and no browser, and it uses no Crawl4AI, Playwright, or
PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `DIMENSION_SELECTION_SCHEMA_INVALID` | The selection record fails its closed schema. |
| `DIMENSION_SELECTION_RECORD_INVALID` | The selection is not one valid human record with the fixed action, label, and time. |
| `DIMENSION_SELECTION_SOURCE_MISMATCH` | The selection does not bind the supplied confirmed dimension plan. |
| `DIMENSION_SELECTION_OPTION_INVALID` | A selection names an unknown space, unknown option, or repeats a space; deferred or candidate-less spaces cannot be selected. |
| `DIMENSION_SELECTION_COVERAGE_INVALID` | A candidate set has no human selection. |
| `FLOOR_ZONING_DRAFT_SCHEMA_INVALID` | The floor zoning draft fails its closed schema. |
| `FLOOR_ZONING_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `FLOOR_ZONING_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not a valid human record. |
| `FLOOR_ZONING_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `FLOOR_ZONING_SOURCE_SELECTION_MISMATCH` | The draft does not bind the supplied selection record. |
| `FLOOR_ZONING_SPACE_UNKNOWN` | A zone or unresolved item names a space absent from the bound selection. |
| `FLOOR_ZONING_COVERAGE_INVALID` | A selected space disappears, repeats, or is both zoned and unresolved. |
| `FLOOR_ZONING_LEVEL_INVALID` | Level ids, orders, or labels repeat. |
| `FLOOR_ZONING_ZONE_INVALID` | Zone ids or names repeat. |
| `FLOOR_ZONING_BOUNDARY_INVALID` | A boundary is unknown-zone, self, duplicate, or same-scope. |
| `FLOOR_ZONING_UNRESOLVED_INVALID` | Unresolved record ids repeat. |
| `STUDENT_FLOOR_ZONING_SCHEMA_INVALID` | A built or supplied framework fails the output schema. |
| `STUDENT_FLOOR_ZONING_CONTENT_MISMATCH` | The chain is valid but the supplied framework is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097/098/099/100 stable error codes propagate unchanged and are
never masked as this slice's errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified. Validate re-verifies the full upstream chain
and selection, re-derives the complete expected framework with the same
build logic, and compares canonical JSON plus newline bytes exactly; any
level sequence, zone, scope, boundary, text, next action, or binding change
fails closed with `STUDENT_FLOOR_ZONING_CONTENT_MISMATCH`. Output is written
only after full validation, through a temporary file with `fsync` and atomic
replace; a failed write never creates or overwrites the destination. The
script opens no socket and starts no subprocess, and imports no `urllib`,
`requests`, browser, Crawl4AI, Playwright, PowerPoint, or system-clock
module.
