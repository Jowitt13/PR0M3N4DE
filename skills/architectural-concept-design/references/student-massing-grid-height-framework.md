# Student Massing, Grid and Height Hypotheses Framework

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Hypotheses and massing groups](#hypotheses-and-massing-groups)
- [Grid intent](#grid-intent)
- [Vertical intervals](#vertical-intervals)
- [Substantive differences and dynamic count](#substantive-differences-and-dynamic-count)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Organize two to six comparable massing, grid, and height hypotheses that the
student has already written on top of one confirmed circulation and
environmental intent framework. The machine only checks completeness,
numeric form, coverage, and traceability, and projects objective, fact-only
comparison rows. It never generates, ranks, scores, recommends, or selects a
hypothesis; the human compares and selects.

## Contracts

- Draft input: [`student-massing-grid-height-draft.schema.json`](student-massing-grid-height-draft.schema.json)
- Framework output: [`student-massing-grid-height.schema.json`](student-massing-grid-height.schema.json)
- Builder: [`build_student_massing_grid_height.py`](../scripts/build_student_massing_grid_height.py) with `confirm`, `build`, and `validate` subcommands.

## Upstream chain

`build` and `validate` verify the complete ARCH-102 chain by reusing the
committed `validate_circulation_environment`: the confirmed ARCH-097 digest,
the exact ARCH-098 start board, the confirmed ARCH-099 spatial program draft
and its exact spatial program, the confirmed ARCH-100 dimension draft, its
exact dimension plan, the human dimension selection, the confirmed ARCH-101
floor zoning draft and its exact framework, and the confirmed ARCH-102
circulation-environment draft and its exact framework. The twelfth input is
one human-confirmed massing-grid-height draft. Any upstream tamper or
failure propagates the existing stable error codes unchanged; this slice
never masks or remaps them.

When the upstream chain is valid but the circulation-environment framework
still carries `student_view.unresolved_items`, `build` and `validate` fail
closed with `MASSING_GRID_HEIGHT_UPSTREAM_UNRESOLVED` before any output is
formed. The upstream circulation or environmental gaps must be resolved via
`resolve_circulation_environment_gaps` first; the builder never auto-fills,
ignores, filters, migrates, or recommends unresolved items.

The draft binds the complete circulation-environment framework by its
canonical JSON plus newline SHA-256
(`source_circulation_environment_sha256`). Confirmation uses exactly four
keys: `action` (`CONFIRM_STUDENT_MASSING_GRID_HEIGHT_DRAFT`), `confirmed_by`,
`confirmed_at` (timezone-qualified RFC 3339), and
`pending_massing_grid_height_draft_sha256`, which must equal the canonical
JSON plus newline SHA-256 of the whole pending draft with
`human_confirmation` restored to `{"status": "pending"}`. Agent and model
labels fail closed. No system clock is read; no confirmer, time, or content
is generated.

## Hypotheses and massing groups

Each hypothesis carries a unique `MGH-xxx` id, a label, one or more massing
groups, one grid intent, one vertical interval per level, and a note. Each
massing group carries a hypothesis-unique `MG-xxx` id, one real level, a
non-empty list of real zones of that level, a role (`primary` / `secondary`
/ `service`), and a note. Rules:

- Within each hypothesis, every confirmed zone appears in exactly one massing
  group; a zone must not disappear, repeat, or join a group on the wrong
  level.
- A group is a student-declared functional combination. It is not a
  coordinate volume, a building shape, a plan drawing, or final massing.
- No `x`/`y`/`z`, width/depth, orientation, site position, outline,
  entrance, or form field has any representation in the closed schema.

## Grid intent

Each hypothesis carries one grid intent: a `grid_pattern` (`rectilinear` /
`hybrid` / `other`), a `primary_bay_m`, a `secondary_bay_m`, and a note.
Bay values are strict positive finite decimal strings. The machine checks
positivity and stable decimal representation only, and projects them
verbatim; it never judges structural safety, span reasonableness, material,
column size, load, seismic behavior, foundation, fire protection, or
constructibility.

## Vertical intervals

Each hypothesis carries exactly one `floor_to_floor_m` per confirmed level.
The machine checks the exactly-once level coverage and positive decimal
form, and computes the subtotal of the student-declared vertical intervals.
That subtotal is never called a building height, planning height, elevation,
structural height, or code conclusion.

## Substantive differences and dynamic count

The draft carries two to six hypotheses; the schema rejects one or seven.
Substantive difference must come from at least one of: the level–zone group
composition, the grid pattern or either bay value, or any level's
floor-to-floor value. Two hypotheses whose content is identical apart from
label or note fail closed as pseudo-options. The machine never ranks,
scores, recommends, or selects based on these differences.

## Student view

The output is JSON data only: no PPTX, web page, image, drawing, or
three-dimensional model. `student_view` carries:

- the project title and the fixed stage
  `massing_grid_height_hypotheses_confirmed`;
- the two to six student hypotheses, projected with readable level and zone
  names; each group shows its role, note, and a subtotal of the
  dimension-declared footprints of its spaces — accounting only for the
  dimension-declared footprints, never building area, gross area, or actual
  massing;
- each hypothesis's grid intent and per-level vertical intervals, plus the
  vertical interval subtotal;
- an automatically generated, fact-only comparison summary row per
  hypothesis: group count, grid pattern, both bay values, and the vertical
  interval subtotal;
- the draft's clarification questions, at most three, carried verbatim;
- the fixed next action
  `human_compare_and_select_massing_grid_height_hypotheses`;
- a fixed boundaries statement.

The machine-only `source_binding` keeps the full upstream hash chain plus the
pending and confirmed draft hashes. The student view exposes no internal id,
SHA-256, recommendation, winner, rank, score, best option, automatic
selection, entrance, coordinate, site plan, orientation, regulation,
structural conclusion, or constructibility conclusion.

## Explicit non-claims

This slice decides no entrance, plan coordinate, orientation, site
conclusion, structural system, regulation, or constructibility. It generates
no hypothesis and selects nothing, and it never auto-fills, ignores,
filters, migrates, or recommends upstream unresolved circulation or
environmental items. It parses no DOC, DOCX, PDF, HTML, image,
or OCR content and claims no format extraction support. It opens no socket
and no browser, and it uses no Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `MASSING_GRID_HEIGHT_DRAFT_SCHEMA_INVALID` | The draft fails its closed schema (including one or seven hypotheses). |
| `MASSING_GRID_HEIGHT_DRAFT_NOT_CONFIRMED` | Build or validate received a pending draft. |
| `MASSING_GRID_HEIGHT_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not a valid human record. |
| `MASSING_GRID_HEIGHT_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `MASSING_GRID_HEIGHT_SOURCE_CIRCULATION_MISMATCH` | The draft does not bind the supplied confirmed circulation-environment framework. |
| `MASSING_GRID_HEIGHT_UPSTREAM_UNRESOLVED` | The valid upstream circulation-environment framework still carries unresolved items; they must be resolved via `resolve_circulation_environment_gaps` first. |
| `MASSING_GROUP_INVALID` | A group has a duplicate id, an unknown level or zone, or a zone on the wrong level. |
| `MASSING_ZONE_COVERAGE_INVALID` | A confirmed zone disappears or repeats within one hypothesis. |
| `GRID_INTENT_INVALID` | A bay value is not a positive finite decimal string. |
| `VERTICAL_INTERVAL_INVALID` | A level is missing, repeated, unknown, or carries a non-positive interval. |
| `MASSING_GRID_HEIGHT_HYPOTHESIS_INVALID` | A hypothesis id repeats, or two hypotheses differ only in label or note. |
| `STUDENT_MASSING_GRID_HEIGHT_SCHEMA_INVALID` | A built or supplied framework fails the output schema. |
| `STUDENT_MASSING_GRID_HEIGHT_CONTENT_MISMATCH` | The chain is valid but the supplied framework is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097～102 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-103 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. Validate re-runs the complete
upstream chain, re-derives the expected framework with the same build logic,
and compares canonical JSON plus newline bytes exactly; any hypothesis,
group, grid, interval, comparison row, next action, text, or binding change
fails closed with `STUDENT_MASSING_GRID_HEIGHT_CONTENT_MISMATCH`. Output is
written only after full validation, through a temporary file with `fsync`
and atomic replace; a failed write never creates or overwrites the
destination. The script opens no socket and starts no subprocess, and
imports no `urllib`, `requests`, browser, Crawl4AI, Playwright, PowerPoint,
or system-clock module.
