# Student Schematic Plan Blocks and Local Coordinates

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Schematic plan draft](#schematic-plan-draft)
- [Human confirmation record](#human-confirmation-record)
- [Local containers](#local-containers)
- [Space placements](#space-placements)
- [Dimension mapping](#dimension-mapping)
- [Geometric consistency](#geometric-consistency)
- [Relation handling](#relation-handling)
- [Output contract](#output-contract)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Let the student write, one small structured draft per confirmed level, a
local rectangular container and one local rectangle per confirmed space,
before any drawing happens. The machine checks consistency, coverage,
selected dimensions, containment, non-overlap, and part of the declared
relationships; it never arranges, optimizes, draws, or generates an
architectural proposal. These are rectangle blocks in local schematic
coordinates, not a formal drawing.

## Contracts

- Draft input: [`student-schematic-plan-blocks-draft.schema.json`](student-schematic-plan-blocks-draft.schema.json)
- Blocks output: [`student-schematic-plan-blocks.schema.json`](student-schematic-plan-blocks.schema.json)
- Builder: [`build_student_schematic_plan_blocks.py`](../scripts/build_student_schematic_plan_blocks.py) with `confirm`, `build`, and `validate` subcommands.

## Upstream chain

`build` and `validate` reuse the committed ARCH-106
`validate_plan_framework` public entry, which re-runs the complete
ARCH-097~106 chain through the selected hypothesis state package, the
confirmed plan-framework draft, and the plan framework itself. Any
upstream tamper or failure propagates the existing ARCH-097~106 stable
error codes unchanged; this slice never masks or remaps them.

Only a valid, untampered plan framework is accepted, and it must carry no
unresolved plan items. A framework whose `student_view.unresolved_plan_items`
is non-empty fails closed with `SCHEMATIC_PLAN_UPSTREAM_UNRESOLVED` before
any output is written, and points to `resolve_plan_framework_gaps`. The
builder never re-selects a hypothesis, and never changes the
human-selected dimension options, levels, zones, space names, or confirmed
relations.

## Schematic plan draft

The student writes one closed pending draft:

- one `levels` entry per confirmed level, each carrying a local container
  and the level's space placements;
- `clarification_questions`: at most three, carried verbatim.

The draft binds the whole ARCH-106 plan framework by its canonical JSON
plus newline SHA-256 (`source_plan_framework_sha256`). Confirmation uses
exactly four keys: `action` (`CONFIRM_STUDENT_SCHEMATIC_PLAN_DRAFT`),
`confirmed_by`, `confirmed_at` (timezone-qualified RFC 3339), and
`pending_student_schematic_plan_draft_sha256`, which must equal the
canonical JSON plus newline SHA-256 of the whole pending draft with
`human_confirmation` restored to `{"status": "pending"}`. Agent and model
labels fail closed. No system clock is read; no confirmer, time, or
content is generated.

## Local containers

Each level carries one local rectangular container with `width_m` and
`depth_m`, both finite and strictly positive (greater than zero). A
zero-area container is not a valid local plan frame and fails closed in
both the closed schema and the semantic container check. The container is
a local sketch frame for that level only: it is not a site boundary, a
total plan, a final massing outline, a regulation conclusion, or a
constructibility claim. The coordinate origin is the level sketch's local
`(0, 0)`; it carries no latitude, longitude, north direction, site
coordinate, or elevation.

## Space placements

Every confirmed space must be placed exactly once; no space may be
deferred, missing, duplicated, moved to another level or zone, or newly
invented. Each placement carries:

- a real upstream `space_name`;
- `x_m` and `y_m` written by the student (finite non-negative decimals);
- `rotation_degrees`, exactly `0` or `90`.

The placement stays inside its confirmed level and zone: the machine
checks that the space appears under the level where the confirmed floor
zoning framework put it, and the zone follows from the space itself.

## Dimension mapping

The rectangle width and depth are never written by the student. They come
from the ARCH-100 human-selected long and short sides of the space's
selected dimension option:

- `0` degrees: width = long side, depth = short side;
- `90` degrees: width = short side, depth = long side.

Manual width/depth rewriting and arbitrary scaling are impossible in the
closed schema and fail closed if attempted.

## Geometric consistency

Container dimensions are finite and strictly positive; placement
coordinates are finite and non-negative. The machine checks:

1. every space rectangle lies inside its level container;
2. no two rectangles on the same level overlap with positive area;
3. every pair declared `adjacent` in the confirmed plan framework shares
   a boundary segment of positive length on the same level;
4. every pair declared `separate` must neither touch nor overlap;
5. `near`, `buffered_transition`, and `flexibly_divisible` pairs stay
   human intent: no distance threshold or performance judgment is
   invented by the machine.

## Relation handling

The output carries the plan framework's relations verbatim with their
notes. Pairs declared `adjacent` or `separate` are checked geometrically
as above and marked `geometrically_verified`; all other categories are
kept and marked `human_authored_intent_only`, preserving the
human-authored intent boundary without fabricating distances, adjacency,
or performance conclusions.

## Output contract

One closed output schema covers the blocks.

- `source_binding` (machine-only): the complete ARCH-097~106 hash chain
  inherited from the plan framework, the canonical JSON plus newline
  SHA-256 of the whole plan framework, and the pending and confirmed
  schematic-plan draft hashes.
- `student_view`: the readable projection below.

`validate` re-runs the complete upstream chain, re-derives the expected
blocks with the same build logic, and compares canonical JSON plus newline
bytes exactly.

## Student view

The output is JSON data only: no PPTX, web page, image, drawing, or
three-dimensional model. `student_view` carries:

- the project title and the fixed stage `schematic_plan_blocks_confirmed`;
- the explicit marker `local_schematic_coordinates_only`;
- per level, in the student's own order: the level label, the student's
  container, and the confirmed zones with each space's local placement,
  rotation, and option-determined width and depth;
- the plan framework's relations with their notes and their verification
  status (`geometrically_verified` or `human_authored_intent_only`);
- the draft's clarification questions, at most three, carried verbatim;
- the fixed next action `human_review_schematic_plan_blocks`;
- a fixed boundaries statement.

The student view exposes no internal id (`S-`, `Z-`, `LV-`, `MG-`, `MGH-`,
`CR-`, `PR-`, `SQ-`, `UP-`), no SHA-256, no scoring or ranking algorithm,
no winner, no rank, no score, no best option, no recommendation, and no
upstream machine field.

## Explicit non-claims

This slice decides no site plan, orientation, building outline, wall,
door, column, stair, toilet, or entrance, and no massing shape, structure,
regulation, cost, performance, or constructibility. It never moves a
rectangle, resolves a conflict, fills a gap, or optimizes area efficiency,
and it derives no daylight, wind, view, noise, fire, or code conclusion.
It does not call `assemble_project_state.py`, does not modify
`output.schema.json`, and claims no equivalence with the generic project
state package. It parses no DOC, DOCX, PDF, HTML, image, or OCR content
and claims no format extraction support. It opens no socket and no
browser, and it uses no Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `SCHEMATIC_PLAN_UPSTREAM_UNRESOLVED` | The validated plan framework still carries unresolved plan items; resolve them first (`resolve_plan_framework_gaps`). |
| `SCHEMATIC_PLAN_DRAFT_SCHEMA_INVALID` | The draft fails its closed schema (including an invalid rotation, an attempted manual width/depth, or a malformed decimal). |
| `SCHEMATIC_PLAN_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `SCHEMATIC_PLAN_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not one valid human record with the fixed action, a human label, a timezone-qualified RFC 3339 time, and a well-formed hash. |
| `SCHEMATIC_PLAN_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `SCHEMATIC_PLAN_SOURCE_FRAMEWORK_MISMATCH` | The draft does not bind the supplied plan framework. |
| `SCHEMATIC_PLAN_SPACE_INVALID` | A placement names a space that is not a real confirmed space. |
| `SCHEMATIC_PLAN_LEVEL_INVALID` | A level is unknown, duplicated, or missing, or a space is placed under a level other than its confirmed level. |
| `SCHEMATIC_PLAN_COVERAGE_INVALID` | A confirmed space is placed more than once or not placed at all. |
| `SCHEMATIC_PLAN_CONTAINER_INVALID` | A container dimension is zero, negative, or non-finite, or a space rectangle extends outside its level container. |
| `SCHEMATIC_PLAN_OVERLAP_INVALID` | Two rectangles on one level overlap with positive area. |
| `SCHEMATIC_PLAN_ADJACENCY_INVALID` | A pair declared adjacent does not share a positive-length boundary segment on one level. |
| `SCHEMATIC_PLAN_SEPARATION_INVALID` | A pair declared separate touches or overlaps. |
| `STUDENT_SCHEMATIC_PLAN_BLOCKS_SCHEMA_INVALID` | A built or supplied blocks document fails the output schema. |
| `STUDENT_SCHEMATIC_PLAN_BLOCKS_CONTENT_MISMATCH` | The chain is valid but the supplied blocks document is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097~106 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-107 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. `validate` re-runs the complete
upstream chain, re-derives the expected blocks with the same build logic,
and compares canonical JSON plus newline bytes exactly; any container,
placement, rotation, relation, next action, boundary, binding, or stage
change fails closed with `STUDENT_SCHEMATIC_PLAN_BLOCKS_CONTENT_MISMATCH`.
Output is written only after full validation, through a temporary file
with `fsync` and atomic replace; a failed write never creates or
overwrites the destination. The script opens no socket and starts no
subprocess, and imports no `urllib`, `requests`, browser, Crawl4AI,
Playwright, PowerPoint, or system-clock module.
