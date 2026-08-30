# Student Plan Relationship and Placement Framework

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Plan framework draft](#plan-framework-draft)
- [Human confirmation record](#human-confirmation-record)
- [Placements](#placements)
- [Space relations](#space-relations)
- [Movement gradients](#movement-gradients)
- [Unresolved plan items](#unresolved-plan-items)
- [Output contract](#output-contract)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Let the student write, in one small readable structured draft, which confirmed
space sits on which confirmed level and zone, which spaces are adjacent,
near, separate, buffered, or flexibly divisible, which movement gradients
run from active to quiet or open to private, and which relationships remain
undecided. The machine only verifies, traces, and projects what the student
writes; it never generates a plan, a coordinate, or an architectural
proposal. This is a relationship table, not a coordinate drawing.

## Contracts

- Draft input: [`student-plan-framework-draft.schema.json`](student-plan-framework-draft.schema.json)
- Framework output: [`student-plan-framework.schema.json`](student-plan-framework.schema.json)
- Builder: [`build_student_plan_framework.py`](../scripts/build_student_plan_framework.py) with `confirm`, `build`, and `validate` subcommands.

## Upstream chain

`build` and `validate` reuse the committed ARCH-105 `validate_state` public
entry, which re-runs the complete ARCH-097~105 chain: the confirmed
ARCH-097 digest, the exact ARCH-098 start board, the confirmed ARCH-099
spatial program draft and its exact spatial program, the confirmed ARCH-100
dimension draft, its exact dimension plan, the human dimension selection,
the confirmed ARCH-101 floor zoning draft and its exact framework, the
confirmed ARCH-102 circulation-environment draft and its exact framework,
the confirmed ARCH-103 massing-grid-height draft and its exact framework,
the confirmed ARCH-104 comparison draft, the selected comparison document,
and the selected hypothesis state package. Any upstream tamper or failure
propagates the existing ARCH-097~105 stable error codes unchanged; this
slice never masks or remaps them.

Only a valid, untampered selected hypothesis state package is accepted. A
pending comparison document, a tampered state package, a tampered selection,
or any changed upstream hash fails closed with its original error code. The
builder takes no selection record of its own, never re-selects, re-ranks,
or re-derives the hypothesis, and never turns ARCH-104 guidance into a plan
conclusion.

## Plan framework draft

The student writes one closed pending draft over the selected state package:

- `placements`: one readable placement per confirmed space, each naming the
  space, its confirmed level, its confirmed zone, a placement note, and an
  optional role.
- `deferred_placements`: spaces whose placement stays undecided, each with
  an explicit reason; a deferred space is never also placed.
- `relations`: a finite set of space pair relations with fixed categories.
- `sequences`: ordered movement gradients whose elements are real spaces or
  confirmed zones.
- `unresolved_plan_items`: relations or placements the student explicitly
  leaves undecided.
- `clarification_questions`: at most three, carried verbatim.

The draft binds the whole selected hypothesis state package by its canonical
JSON plus newline SHA-256
(`source_selected_hypothesis_state_sha256`). Confirmation uses exactly four
keys: `action` (`CONFIRM_STUDENT_PLAN_FRAMEWORK_DRAFT`), `confirmed_by`,
`confirmed_at` (timezone-qualified RFC 3339), and
`pending_student_plan_framework_draft_sha256`, which must equal the
canonical JSON plus newline SHA-256 of the whole pending draft with
`human_confirmation` restored to `{"status": "pending"}`. Agent and model
labels fail closed. No system clock is read; no confirmer, time, or content
is generated.

## Placements

Every confirmed space must be covered exactly once, either by one placement
or by one deferred record. The machine never adds, deletes, moves, or
renames a space.

Each placement must:

- name a real, confirmed space;
- place it on a real confirmed level label and inside a real confirmed zone
  of that level, exactly where the confirmed floor zoning framework already
  put the space;
- carry a human-readable `placement_note` and an optional `role`
  (`primary`, `secondary`, or `service`).

A placement for a space whose confirmed level or zone does not match, or
for a space the student zoned elsewhere, fails closed. Deferred placements
must carry a non-empty reason and may not overlap any placement.

## Space relations

Each relation names two distinct real spaces and one fixed category:
`adjacent`, `near`, `separate`, `buffered_transition`, or
`flexibly_divisible`. The pair is undirected: the same unordered pair may
appear at most once, self-loops are invalid, and the same pair may never be
resolved twice with different categories. The machine checks only that the
pair and category do not contradict the confirmed spatial program
relations: `must_be_separate` rejects `adjacent`, `near`, and
`buffered_transition`; `must_be_near` rejects `separate`. It generates no
corridor, wall, door, stair, toilet position, or any geometry.

## Movement gradients

Each sequence is an ordered list of at least two elements, each either a
real confirmed space or a real confirmed zone. The order is the student's
own; the machine never sorts, scores, or recommends a sequence. Gradient
intentions such as active-to-quiet or open-to-private are carried as
student text and are never upgraded into noise, daylight, wind, view,
regulation, or performance facts.

## Unresolved plan items

The student may explicitly leave a placement or a space relation
undecided. Each unresolved item references a real space, a real pair of
spaces, or an existing sequence, and carries a reason. Confirmed spaces and
relations never disappear: every confirmed space is still covered by
placements plus deferred records, and an unresolved pair may never also be
resolved. While any unresolved item remains, the next action is
`resolve_plan_framework_gaps`; the machine never resolves it for the
student.

## Output contract

One closed output schema covers the framework.

- `source_binding` (machine-only): the complete ARCH-097~105 hash chain
  inherited from the selected state package, the canonical JSON plus
  newline SHA-256 of the whole selected state package, and the pending and
  confirmed plan-framework draft hashes.
- `student_view`: the readable projection below.

`validate` re-runs the complete upstream chain, re-derives the expected
framework with the same build logic, and compares canonical JSON plus
newline bytes exactly.

## Student view

The output is JSON data only: no PPTX, web page, image, drawing, or
three-dimensional model. `student_view` carries:

- the project title and the fixed stage `plan_framework_confirmed`;
- the placed spaces grouped by confirmed level order and confirmed zone
  order, each with the student's placement note and optional role;
- the deferred placements with their reasons;
- every relation in the student's own order with its category and note;
- every movement gradient in the student's own order;
- the unresolved plan items with a readable subject and the student's
  reason;
- the draft's clarification questions, at most three, carried verbatim;
- the next action: `resolve_plan_framework_gaps` while unresolved items
  remain, otherwise `human_review_plan_framework`;
- a fixed boundaries statement.

The student view exposes no internal id (`S-`, `Z-`, `LV-`, `MG-`, `MGH-`,
`CR-`, `PR-`, `SQ-`, `UP-`), no SHA-256, no scoring or ranking algorithm,
no winner, no rank, no score, no best option, no recommendation, and no
upstream machine field.

## Explicit non-claims

This slice decides no plan coordinate, room rectangle, wall, door, column,
entrance, circulation drawing, or total plan, and no floor count beyond the
written levels, orientation, massing shape, structural system, regulation,
cost, performance, or constructibility. It generates no placement,
relation, sequence, or architectural conclusion of its own, ranks and
scores nothing, and selects nothing. Placement and sequence text are human
judgment, never verified facts. It does not call
`assemble_project_state.py`, does not modify `output.schema.json`, and
claims no equivalence with the generic project state package. It parses no
DOC, DOCX, PDF, HTML, image, or OCR content and claims no format
extraction support. It opens no socket and no browser, and it uses no
Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `PLAN_FRAMEWORK_DRAFT_SCHEMA_INVALID` | The draft fails its closed schema. |
| `PLAN_FRAMEWORK_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `PLAN_FRAMEWORK_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not one valid human record with the fixed action, a human label, a timezone-qualified RFC 3339 time, and a well-formed hash. |
| `PLAN_FRAMEWORK_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `PLAN_SOURCE_STATE_MISMATCH` | The draft does not bind the supplied selected hypothesis state package. |
| `PLAN_SPACE_INVALID` | A placement, deferred record, relation endpoint, sequence element, or unresolved subject names a space that is not a real confirmed space. |
| `PLAN_PLACEMENT_INVALID` | A placement names an unknown level or zone, or places a space outside its confirmed level and zone. |
| `PLAN_COVERAGE_INVALID` | A confirmed space is covered more than once, placed and deferred together, or not covered at all. |
| `PLAN_RELATION_INVALID` | A relation is a self-loop, repeats a relation id, or repeats an unordered pair. |
| `PLAN_RELATION_CONFLICT` | A relation contradicts a confirmed spatial program relation (`must_be_separate` or `must_be_near`). |
| `PLAN_SEQUENCE_INVALID` | A sequence repeats an id, carries fewer than two elements, repeats an element, or names an element that is neither a real space nor a confirmed zone. |
| `PLAN_UNRESOLVED_INVALID` | An unresolved item repeats a record id, references an unknown space, pair, or sequence, or repeats a pair that is already resolved. |
| `STUDENT_PLAN_FRAMEWORK_SCHEMA_INVALID` | A built or supplied framework fails the output schema. |
| `STUDENT_PLAN_FRAMEWORK_CONTENT_MISMATCH` | The chain is valid but the supplied framework is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097~105 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-106 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. `validate` re-runs the complete
upstream chain, re-derives the expected framework with the same build
logic, and compares canonical JSON plus newline bytes exactly; any
placement, relation, sequence, unresolved item, next action, boundary,
binding, or stage change fails closed with
`STUDENT_PLAN_FRAMEWORK_CONTENT_MISMATCH`. Output is written only after
full validation, through a temporary file with `fsync` and atomic replace;
a failed write never creates or overwrites the destination. The script
opens no socket and starts no subprocess, and imports no `urllib`,
`requests`, browser, Crawl4AI, Playwright, PowerPoint, or system-clock
module.
