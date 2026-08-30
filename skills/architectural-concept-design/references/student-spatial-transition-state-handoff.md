# Student Spatial Transition Review and Controlled State Handoff

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

Record one explicit human review of an already validated ARCH-110 spatial
transition framework. The human may either continue the reviewed hierarchy
and transition intentions into a controlled state handoff or require a
revision. The machine never treats the prior draft confirmation as an implicit
review, never generates or applies a review, and never turns a human-written
hierarchy or transition intention into geometry, a drawing, an architectural
decision, or a presentation.

## Contracts

- State handoff: [`student-spatial-transition-state-handoff.schema.json`](student-spatial-transition-state-handoff.schema.json)
- Builder: [`build_student_spatial_transition_state_handoff.py`](../scripts/build_student_spatial_transition_state_handoff.py) with `build` and `validate` subcommands.
- Review record: validated inside the builder as one closed eight-key record; no separate schema file exists for this stage.

## Upstream chain

Both commands use ARCH-110 `validate_spatial_transition_framework` as their
only upstream entry. It re-runs the complete ARCH-097~110 chain, including the
ARCH-108 state handoff, the confirmed main-space-support draft and framework,
and the confirmed spatial transition draft. Existing upstream error codes pass
through unchanged and are never renamed as ARCH-111 errors.

The reviewed framework must therefore be schema-valid and the exact
deterministic projection of its complete upstream chain. A framework whose
`student_view` still carries unresolved transition items fails closed with
`SPATIAL_TRANSITION_HANDOFF_UPSTREAM_UNRESOLVED` before any review validation
or output. This stage neither rechecks by approximation nor repairs a prior
result.

## Human review record

The human authors one closed record with exactly these fields:

- fixed action `REVIEW_STUDENT_SPATIAL_TRANSITION_FRAMEWORK`;
- `reviewed_by`, which must identify a human rather than an agent or model;
- timezone-qualified RFC 3339 `reviewed_at`;
- `source_spatial_transition_framework_sha256`, the canonical JSON plus
  newline SHA-256 of the entire ARCH-110 framework actually reviewed;
- one outcome, `continue_to_manual_spatial_design` or
  `revise_spatial_transition`;
- at most three human-authored `review_notes` carried verbatim.

No system clock, reviewer name, note, decision, hierarchy role, or transition
pattern is invented. A record with an unknown key, an agent label, an invalid
time, a malformed hash, or a different source hash fails closed.

## Continue or revise

`continue_to_manual_spatial_design` is an explicit human authorization to
create the state handoff. It is not an architectural quality, code,
construction, performance, or approval claim.

`revise_spatial_transition` is a valid human decision but deliberately yields
no handoff. The student must revise and re-confirm a new ARCH-110 transition
draft, rebuild its framework, then submit a new review record bound to that
new framework. The machine never applies review notes, chooses a pattern,
completes or inverts a transition, or reuses a review record against a changed
framework.

## State handoff

On `continue_to_manual_spatial_design`, the builder produces one closed state
handoff. Its machine-only `source_binding` binds the reviewed framework
document and the whole review record. The bound framework itself carries the
complete upstream hash binding and is revalidated on every build and validate
call.

The handoff exposes a readable projection of the confirmed human space
hierarchy, transition patterns, clarification questions, and the human review
summary. It also states what is available, what must not be inferred, which
upstream changes invalidate the handoff, and which outputs remain prohibited.

## Student view

The student view is JSON data only. It exposes no internal identifier,
SHA-256, ranking, score, winner, best option, recommendation, coordinate, or
hidden upstream field.

Its next action is `human_continue_manual_spatial_design`: the human may
continue manual spatial design from the reviewed record. This route does not
silently activate a later drawing, image, PPTX, or presentation workflow.

## Explicit non-claims

This stage decides no coordinate, rectangle, size, distance, orientation,
entrance, corridor, wall, door, column, stair, toilet, plan layout, massing,
site conclusion, structural system, regulation, cost, performance, or
constructibility. It does not evaluate visual quality, select or modify a
transition pattern, derive lighting, wind, view, noise, fire, or code
conclusions, or resolve any review note.

It does not call `assemble_project_state.py`, modify `output.schema.json`,
or claim compatibility with the generic project-state package. It parses no
DOC, DOCX, PDF, HTML, image, or OCR content; opens no socket or browser; and
uses no Crawl4AI, Playwright, PowerPoint, or PPTX library.

## Error codes

| Code | Meaning |
| --- | --- |
| `SPATIAL_TRANSITION_HANDOFF_UPSTREAM_UNRESOLVED` | The reviewed framework still carries unresolved transition items, so no review or handoff may proceed. |
| `SPATIAL_TRANSITION_REVIEW_RECORD_INVALID` | The closed review record structure, action, human label, timestamp, outcome, notes, or hash format is invalid. |
| `SPATIAL_TRANSITION_REVIEW_SOURCE_FRAMEWORK_MISMATCH` | The review record does not bind the supplied exact framework document. |
| `SPATIAL_TRANSITION_REVIEW_NOT_CONTINUED` | The human requested revision, so no handoff may be produced. |
| `STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_SCHEMA_INVALID` | A built or supplied handoff violates its closed output schema. |
| `STUDENT_SPATIAL_TRANSITION_STATE_HANDOFF_CONTENT_MISMATCH` | The chain and review are valid but the supplied handoff is not their exact projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

ARCH-097~110 errors propagate unchanged and are never renamed as ARCH-111
errors.

## Determinism and safety

Identical documents produce byte-identical handoffs. `validate` re-runs the
complete upstream chain, revalidates the review record, rebuilds the expected
handoff, and compares canonical JSON plus newline bytes exactly. Input
documents retain their order and content. A destination is written only after
every check passes, through a temporary file with `fsync` and atomic replace;
a failed write never creates or overwrites a destination.

## Read-only manual design handoff card renderer

The ARCH-111 builder output remains JSON; this section only routes to a
separate read-only renderer. For one validated, untampered handoff whose
human review continued to manual spatial design, read
[student-manual-spatial-design-handoff-card.md](student-manual-spatial-design-handoff-card.md)
and use `scripts/render_student_manual_spatial_design_handoff_card.py` to
render one deterministic Simplified-Chinese Markdown handoff card to stdout
only. The renderer re-validates the complete ARCH-097~111 chain through this
stage's public `validate_spatial_transition_state_handoff` entry, propagates
upstream error codes unchanged, fails closed on any invalid, tampered, or
non-continued input, and never writes a file, a selection record, or a design
conclusion.
