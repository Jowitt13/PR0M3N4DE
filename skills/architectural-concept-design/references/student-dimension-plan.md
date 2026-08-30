# Student Dimension Candidates and Plan Framework

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain and confirmation](#upstream-chain-and-confirmation)
- [Candidate and coverage rules](#candidate-and-coverage-rules)
- [Area arithmetic](#area-arithmetic)
- [Student view](#student-view)
- [What this slice never does](#what-this-slice-never-does)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Organize the long-by-short dimension rectangles the student has already
written, check them arithmetically against the confirmed areas, and project a
coordinate-free plan framework. Candidates are human-authored, machine-checked
candidates, never machine decisions: the builder computes footprint area,
area delta, area delta percentage, and aspect ratio with exact decimal
arithmetic, and the next action only asks the human to select or revise
candidates. It sits after the confirmed assignment brief digest, the
validated start board, and the confirmed student spatial program, and before
any human selection of candidates.

## Contracts

- Draft input: [`student-dimension-plan-draft.schema.json`](student-dimension-plan-draft.schema.json)
- Plan output: [`student-dimension-plan.schema.json`](student-dimension-plan.schema.json)
- Builder: [`build_student_dimension_plan.py`](../scripts/build_student_dimension_plan.py) with `confirm`, `build`, and `validate` subcommands.

`build` and `validate` both accept and verify the full upstream chain: the
confirmed ARCH-097 digest, the ARCH-098 start board, the confirmed ARCH-099
spatial program draft, and the ARCH-099 spatial program, verified by reusing
the committed ARCH-099 `validate_program`, so the spatial program must remain
the exact deterministic projection of its own upstream documents. The fifth
input is one confirmed dimension plan draft.

## Upstream chain and confirmation

The draft carries `source_program_sha256`, the canonical JSON plus newline
SHA-256 of the confirmed spatial program it answers; a mismatched binding
fails closed. Confirmation binds one explicit human record with exactly four
keys: `action` (`CONFIRM_STUDENT_DIMENSION_PLAN_DRAFT`), `confirmed_by`,
`confirmed_at`, and `pending_dimension_draft_sha256`. The recorded hash must
equal the canonical JSON plus newline SHA-256 of the whole pending draft
document; the confirmed draft preserves that binding, and any later tamper of
the confirmed draft fails closed. Agent or model labels, wrong actions,
non-timezone-qualified timestamps, and malformed hashes are rejected. No
system clock is read and no confirmer, time, or content is generated.

## Candidate and coverage rules

- A candidate set may target only a confirmed spatial program space whose name
  is unique and whose area value is known. An unresolved-area space cannot
  carry candidates; the plan lists it among unresolved-area spaces and states
  that no dimension candidates can be formed for it yet.
- Every numeric space is covered exactly once: one candidate set, or one
  entry in `deferred_numeric_spaces` with a human reason. A numeric space
  must not disappear, be covered twice, or appear in both lists.
- Each candidate set carries a dynamic count of two to six candidates, never
  a fixed two. `candidate_count_reason` is human-authored and explains why
  this space needs two, three, four, five, or six candidates.
- `option_key` values are consecutive and unique from `A` through `F` with no
  gaps and no repeats.
- `long_side_m` and `short_side_m` are exact decimal strings with at most two
  decimal places; `long_side_m >= short_side_m > 0`.
- The same long-by-short rectangle may not repeat within one space.
- The builder never corrects, reorients, fills in, adds, orders, or selects a
  candidate.

## Area arithmetic

All arithmetic uses exact `Decimal` values. The five-percent gate compares
the raw, unrounded values: footprint area (`long_side_m * short_side_m`),
area delta (confirmed area minus footprint), and area delta percentage. A
candidate passes only when the raw deviation is at most five percent; an
exactly five percent deviation is allowed, and any true value above five
percent fails closed. Displayed rounding of the area delta percentage and
aspect ratio is presentation precision applied only after the gate has
passed; it never changes the pass or fail outcome. Footprint area and area
delta keep their exact finite decimal results. That threshold is a
candidate-checking gate only; it is not a design, code, or constructibility
judgment. Brief-stated and human-working area sources are carried through
unchanged and stay distinct; a human working figure is never presented as a
brief fact.

## Student view

The output is JSON data only: no PPTX, image, HTML, coordinate drawing, or
plan drawing. `student_view` carries:

- the project title and the fixed stage
  `dimension_candidates_ready_for_human_selection`;
- `spaces_by_zone`, preserving the spatial program's functional zone order,
  space names, activity profiles, area source, and area values;
- for each included space, its `A`–`F` candidates with long side, short
  side, computed footprint area, area delta, area delta percentage, aspect
  ratio, and the human note;
- deferred numeric spaces and unresolved-area spaces;
- a coordinate-free `plan_framework` that projects only the confirmed zones,
  confirmed space names, and the confirmed relations, with no position,
  orientation, adjacency distance, road, entrance, floor, or geometric
  layout;
- the draft's clarification questions, at most three, carried verbatim;
- one deterministic next action: `resolve_dimension_gaps` while any deferred
  numeric space or unresolved-area space remains, otherwise
  `human_select_dimension_candidates`, which only asks the human to select or
  revise candidates;
- fixed boundaries stating that candidates are no final decision.

The student view exposes no internal identifier or SHA-256, and carries no
recommendation, winner, preference, ranking, or selection.

## What this slice never does

This slice parses no DOC, DOCX, PDF, HTML, image, or OCR content and claims
no format extraction support. It opens no socket and no browser, and it uses
no Crawl4AI, Playwright, or PowerPoint. It generates no automatic space,
area, relation, dimension, floor stack, plan layout, massing, grid,
orientation, coordinate, level, height, environmental conclusion, option, or
recommendation, and it selects no candidate.

## Error codes

| Code | Meaning |
| --- | --- |
| `DIMENSION_DRAFT_SCHEMA_INVALID` | The dimension draft fails its closed schema. |
| `DIMENSION_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `DIMENSION_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not a valid human record. |
| `DIMENSION_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `DIMENSION_SOURCE_PROGRAM_HASH_MISMATCH` | The draft's `source_program_sha256` does not bind the supplied program. |
| `DIMENSION_SOURCE_SPACE_UNKNOWN` | A candidate set or deferral names a space absent from the confirmed program. |
| `DIMENSION_AREA_UNRESOLVED` | A candidate set or deferral targets a space with no confirmed area value. |
| `DIMENSION_CANDIDATE_INVALID` | A candidate fails the side, key, duplicate, or raw five-percent gate. |
| `DIMENSION_COVERAGE_INVALID` | A numeric space disappears or is covered more than once. |
| `STUDENT_DIMENSION_PLAN_SCHEMA_INVALID` | A built or supplied plan fails the plan schema. |
| `STUDENT_DIMENSION_PLAN_CONTENT_MISMATCH` | The source chain is valid but the supplied plan is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097/098/099 stable error codes propagate unchanged and are
never masked as this slice's errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified. Validate re-derives the complete expected
output with the same build logic and compares canonical JSON plus newline
bytes exactly; any student-visible or binding change fails closed with
`STUDENT_DIMENSION_PLAN_CONTENT_MISMATCH`. Output is written only after full
validation, through a temporary file with `fsync` and atomic replace; a
failed write never creates or overwrites the destination. The script opens
no socket and starts no subprocess, and imports no `urllib`, `requests`,
browser, Crawl4AI, Playwright, PowerPoint, or system-clock module.
