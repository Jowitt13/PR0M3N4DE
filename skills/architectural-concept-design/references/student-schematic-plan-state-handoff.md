# Student Schematic Plan Review and Controlled State Handoff

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Human review record](#human-review-record)
- [Continue or revise](#continue-or-revise)
- [State handoff](#state-handoff)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Record one explicit human review of already validated ARCH-107 local schematic
plan blocks. The human may either continue the reviewed local schematic into a
controlled state handoff or require a revision. The machine never treats the
prior draft confirmation as an implicit review, and it never turns a local
rectangle arrangement into a site plan, drawing, architectural decision, or
presentation.

## Contracts

- Review record: [`student-schematic-plan-review.schema.json`](student-schematic-plan-review.schema.json)
- State handoff: [`student-schematic-plan-state-handoff.schema.json`](student-schematic-plan-state-handoff.schema.json)
- Builder: [`build_student_schematic_plan_state_handoff.py`](../scripts/build_student_schematic_plan_state_handoff.py) with `build` and `validate` subcommands.

## Upstream chain

Both commands use ARCH-107 `validate_schematic_plan_blocks` as their only
upstream entry. It re-runs the complete ARCH-097~107 chain, including the
confirmed human schematic-plan draft, selected dimension sides, plan
framework, and its local geometry checks. Existing upstream error codes pass
through unchanged.

The reviewed blocks must therefore be schema-valid and the exact deterministic
projection of their complete upstream chain. This stage neither rechecks by
approximation nor repairs a prior result.

## Human review record

The human authors one closed record with exactly these fields:

- fixed action `REVIEW_STUDENT_SCHEMATIC_PLAN_BLOCKS`;
- `reviewed_by`, which must identify a human rather than an agent or model;
- timezone-qualified RFC 3339 `reviewed_at`;
- `source_schematic_plan_blocks_sha256`, the canonical JSON plus newline
  SHA-256 of the entire blocks document actually reviewed;
- one outcome, `continue_to_handoff` or `revise_schematic_plan`;
- at most three human-authored `review_notes` carried verbatim.

No system clock, reviewer name, note, decision, rectangle, or geometry is
invented. A record with an unknown key, an agent label, an invalid time, or a
different source hash fails closed.

## Continue or revise

`continue_to_handoff` is an explicit human authorization to create the local
state handoff. It is not an architectural quality, code, construction,
performance, or approval claim.

`revise_schematic_plan` is a valid human decision but deliberately yields no
handoff. The student must revise and re-confirm a new ARCH-107 schematic
draft, rebuild its blocks, then submit a new review record bound to those new
blocks. The machine never applies review notes, moves rectangles, chooses a
revision, or reuses a review record against changed blocks.

## State handoff

On `continue_to_handoff`, the builder produces one closed state handoff. Its
machine-only `source_binding` binds the reviewed blocks document and the
whole review record. The bound blocks document itself carries the complete
ARCH-097~107 hash chain and is revalidated on every build and validate call.

The handoff exposes a readable, local-only projection of level containers,
zone-grouped placements, relation verification status, clarification
questions, and the human review summary. It also states what is available,
what must not be inferred, which upstream changes invalidate the handoff, and
which outputs remain prohibited.

## Student view

The student view is JSON data only. It preserves the fixed coordinate marker
`local_schematic_coordinates_only`; all x/y/width/depth values are local
schematic values, not survey, site, north, elevation, or building coordinates.
It exposes no internal identifier, SHA-256, ranking, score, winner, best
option, recommendation, or hidden upstream field.

Its next action is `human_continue_manual_schematic_design`: the human may
continue manual design from the reviewed record. This route does not silently
activate a later drawing, image, PPTX, or presentation workflow.

## Explicit non-claims

This stage decides no site plan, orientation, building outline, wall, door,
column, stair, toilet, entrance, corridor, massing shape, structural system,
regulation, cost, performance, or constructibility. It does not evaluate
visual quality, move or optimize a rectangle, derive lighting, wind, view,
noise, fire, or code conclusions, or resolve any review note.

It does not call `assemble_project_state.py`, modify `output.schema.json`,
or claim compatibility with the generic project-state package. It parses no
DOC, DOCX, PDF, HTML, image, or OCR content; opens no socket or browser; and
uses no Crawl4AI, Playwright, PowerPoint, or PPTX library.

## Error codes

| Code | Meaning |
| --- | --- |
| `SCHEMATIC_REVIEW_RECORD_SCHEMA_INVALID` | The closed review record is malformed. |
| `SCHEMATIC_REVIEW_RECORD_INVALID` | The review action, human label, or timestamp is invalid. |
| `SCHEMATIC_REVIEW_SOURCE_BLOCKS_MISMATCH` | The review record does not bind the supplied exact blocks document. |
| `SCHEMATIC_REVIEW_NOT_CONTINUED` | The human requested revision, so no handoff may be produced. |
| `STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_SCHEMA_INVALID` | A built or supplied handoff violates its closed output schema. |
| `STUDENT_SCHEMATIC_PLAN_STATE_HANDOFF_CONTENT_MISMATCH` | The chain and review are valid but the supplied handoff is not their exact projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

ARCH-097~107 errors propagate unchanged and are never renamed as ARCH-108
errors.

## Determinism and safety

Identical documents produce byte-identical handoffs. `validate` re-runs the
complete upstream chain, revalidates the review record, rebuilds the expected
handoff, and compares canonical JSON plus newline bytes exactly. Input
documents retain their order and content. A destination is written only after
every check passes, through a temporary file with `fsync` and atomic replace;
a failed write never creates or overwrites a destination.
