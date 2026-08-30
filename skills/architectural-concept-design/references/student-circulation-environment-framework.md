# Student Circulation and Environmental Intent Framework

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Horizontal relations](#horizontal-relations)
- [Vertical movement intentions](#vertical-movement-intentions)
- [Environmental intentions](#environmental-intentions)
- [Unresolved coverage](#unresolved-coverage)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Organize what the student has already written about movement and
environmental intention on top of one confirmed floor zoning framework:
which zones relate to which, how movement crosses levels, and which zones or
spaces the student wants to prefer or avoid for daylight, view, noise, or
ventilation. This is a traceable intent framework, not a site analysis, and
it never upgrades a preference into a fact. The builder validates, traces,
and projects student-written content; it infers nothing.

## Contracts

- Draft input: [`student-circulation-environment-draft.schema.json`](student-circulation-environment-draft.schema.json)
- Framework output: [`student-circulation-environment.schema.json`](student-circulation-environment.schema.json)
- Builder: [`build_student_circulation_environment.py`](../scripts/build_student_circulation_environment.py) with `confirm`, `build`, and `validate` subcommands.

## Upstream chain

`build` and `validate` verify the complete ARCH-101 chain by reusing the
committed `validate_floor_zoning`: the confirmed ARCH-097 digest, the exact
ARCH-098 start board, the confirmed ARCH-099 spatial program draft and its
exact spatial program, the confirmed ARCH-100 dimension draft, its exact
dimension plan, the human dimension selection, the confirmed floor zoning
draft, and its exact floor zoning framework. The tenth input is one
human-confirmed circulation-environment draft. Any upstream tamper or
failure propagates the existing stable error codes unchanged; this slice
never masks or remaps them.

The draft binds the complete floor zoning framework by its canonical JSON
plus newline SHA-256 (`source_floor_zoning_sha256`). Confirmation uses
exactly four keys: `action`
(`CONFIRM_STUDENT_CIRCULATION_ENVIRONMENT_DRAFT`), `confirmed_by`,
`confirmed_at` (timezone-qualified RFC 3339), and
`pending_circulation_environment_draft_sha256`, which must equal the
canonical JSON plus newline SHA-256 of the whole pending draft with
`human_confirmation` restored to `{"status": "pending"}`. Agent and model
labels fail closed. No system clock is read; no confirmer, time, or content
is generated.

## Horizontal relations

Each `circulation_relations` entry carries a unique `CR-xxx` relation id,
two different real zone ids from the confirmed floor zoning draft, a
`flow_scope` (`public` / `internal` / `shared`), a `directionality`
(`one_way` / `two_way`), and a student note. Rules:

- Both ends must be real, different zones; self-loops fail closed.
- One unordered zone pair keeps at most one horizontal relation; both
  directions are expressed with `two_way`, never with a reversed duplicate.
- A relation expresses only the student-declared connection. It is not a
  corridor, door, entrance, width, length, coordinate, fire, or
  constructibility claim.
- The builder infers no path, priority, efficiency, shortest distance, or
  activity gradient.

Every zone must appear in at least one horizontal relation or carry an
explicit unresolved item with `subject_kind: "circulation_relation"`
targeting that zone; otherwise the build fails closed with
`CIRCULATION_COVERAGE_INVALID`, so no zone can quietly disappear at the
circulation stage.

## Vertical movement intentions

Each `vertical_movement_intents` entry carries a unique `VT-xxx` transition
id, two real zone ids on different levels, a `mode` (`stair` / `lift` /
`ramp` / `other`), a `flow_scope`, and a student note. Rules:

- Both ends must be real zones belonging to different levels; same-level
  pairs fail closed.
- One unordered zone pair keeps at most one vertical movement intent.
- An intent is a student-written movement intention, not a system
  recommendation. The builder never infers or validates stair, lift, or ramp
  counts, sizes, positions, clearances, code compliance, accessibility,
  fire protection, or structure.
- When the confirmed floor zoning draft has more than one level, every level
  must participate in at least one vertical movement intent or carry an
  unresolved item with `subject_kind: "vertical_movement"` targeting that
  level; otherwise the build fails closed with
  `VERTICAL_MOVEMENT_COVERAGE_INVALID`.

## Environmental intentions

Each `environmental_intents` entry carries a unique `EI-xxx` intent id, a
`target_kind` (`zone` / `space`), a real `target_id` (a zone id from the
confirmed floor zoning draft, or a unique dimension-selected space name), a
`topic` (`daylight` / `view` / `noise` / `ventilation`), a `preference`
(`prefer` / `avoid` / `neutral`), and a student note. Rules:

- Intents record only student preferences or intentions awaiting
  verification.
- Structured fields such as orientation, north, sun path, wind direction,
  site condition, view fact, noise measurement, code reference, or
  performance value have no representation in the closed schema and fail
  closed.
- Environmental intentions may be empty; the builder never generates them
  because information is scarce.

环境意图不是场地事实、日照分析、风环境结论、噪声测量或性能证明。它只是学生写下、待后续以场地证据核验的空间偏好。

## Unresolved coverage

Each unresolved item carries a unique `UCE-xxx` record id, a `subject_kind`
(`circulation_relation` / `vertical_movement` / `environmental_intent`), a
matching `target_kind` and real `target_id`, and a student-written reason:

- a zone without any horizontal relation is covered only by a
  `circulation_relation` unresolved item with `target_kind: "zone"`
  targeting that zone id;
- in a multi-level framework, a level that participates in no vertical
  intent is covered only by a `vertical_movement` unresolved item with
  `target_kind: "level"` targeting that level id;
- an `environmental_intent` unresolved item targets a zone id or a space
  name and records only a gap the student explicitly raised; it never
  triggers auto-filling, a recommendation, or a design conclusion.

Unresolved items are never a vehicle for automatic completion.

## Student view

The output is JSON data only: no PPTX, web page, image, or drawing.
`student_view` carries:

- the project title and the fixed stage
  `circulation_environment_intent_confirmed`;
- the student-declared horizontal relations, shown by zone names in
  student-written order with student-written notes;
- the student-declared vertical movement intentions, shown by zone names and
  level labels;
- the student-declared environmental intentions, shown by readable zone or
  space names;
- unresolved items with readable targets and student reasons;
- the draft's clarification questions, at most three, carried verbatim;
- one deterministic next action: `resolve_circulation_environment_gaps`
  while any unresolved item remains, otherwise
  `massing_grid_height_hypotheses`;
- a fixed boundaries statement.

The machine-only `source_binding` keeps the full upstream hash chain,
including the floor zoning framework hash and the pending and confirmed
draft hashes. The student view exposes no internal identifier, SHA-256,
recommendation, winner, score, rank, automatic selection, or geometry.

## Explicit non-claims

This slice decides no level count, entrance, core, stair, lift, or ramp
position, count, size, or clearance. It decides no orientation, wind
direction, sun path, site conclusion, coordinate, plan, site plan, massing,
grid, elevation, or height. It recommends, ranks, scores, selects, and
generates nothing. It parses no DOC, DOCX, PDF, HTML, image, or OCR content
and claims no format extraction support. It opens no socket and no browser,
and it uses no Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `CIRCULATION_ENVIRONMENT_DRAFT_SCHEMA_INVALID` | The draft fails its closed schema. |
| `CIRCULATION_ENVIRONMENT_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `CIRCULATION_ENVIRONMENT_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not a valid human record. |
| `CIRCULATION_ENVIRONMENT_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `CIRCULATION_ENVIRONMENT_SOURCE_ZONING_MISMATCH` | The draft does not bind the supplied confirmed floor zoning framework. |
| `CIRCULATION_RELATION_INVALID` | A horizontal relation is duplicate, self, unknown-zone, or a repeated unordered pair. |
| `CIRCULATION_COVERAGE_INVALID` | A zone has no horizontal relation and no circulation unresolved item. |
| `VERTICAL_MOVEMENT_INVALID` | A vertical intent is duplicate, self, same-level, unknown-zone, or a repeated unordered pair. |
| `VERTICAL_MOVEMENT_COVERAGE_INVALID` | A level participates in no vertical intent and has no vertical unresolved item. |
| `ENVIRONMENTAL_INTENT_INVALID` | An environmental intent has a duplicate id or an unknown zone or space target. |
| `CIRCULATION_ENVIRONMENT_UNRESOLVED_INVALID` | An unresolved item has a duplicate id, a mismatched subject/target kind, or an unknown target. |
| `STUDENT_CIRCULATION_ENVIRONMENT_SCHEMA_INVALID` | A built or supplied framework fails the output schema. |
| `STUDENT_CIRCULATION_ENVIRONMENT_CONTENT_MISMATCH` | The chain is valid but the supplied framework is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097～101 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-102 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. Validate re-runs the complete
upstream chain, re-derives the expected framework with the same build logic,
and compares canonical JSON plus newline bytes exactly; any relation,
movement, intent, unresolved, next action, text, or binding change fails
closed with `STUDENT_CIRCULATION_ENVIRONMENT_CONTENT_MISMATCH`. Output is
written only after full validation, through a temporary file with `fsync`
and atomic replace; a failed write never creates or overwrites the
destination. The script opens no socket and starts no subprocess, and
imports no `urllib`, `requests`, browser, Crawl4AI, Playwright, PowerPoint,
or system-clock module.
