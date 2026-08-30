# Student Spatial Programming

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain and confirmation](#upstream-chain-and-confirmation)
- [Human-authored draft rules](#human-authored-draft-rules)
- [Area framework](#area-framework)
- [Student view](#student-view)
- [What this slice never does](#what-this-slice-never-does)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Organize what the student has already written about the program: functional
spaces, area statements, functional zones, activity profiles, and adjacency or
separation relations. The output is a verifiable state, not a design. The
builder never invents a space, area, relation, zone, activity profile, or
design content. It sits after the confirmed assignment brief digest and the
validated start board, and before any dimension-candidate work.

## Contracts

- Draft input: [`student-spatial-program-draft.schema.json`](student-spatial-program-draft.schema.json).
- Program output: [`student-spatial-program.schema.json`](student-spatial-program.schema.json).
- Script: [`../scripts/build_student_spatial_program.py`](../scripts/build_student_spatial_program.py).
- Upstream contracts, read-only: the ARCH-097 digest and the ARCH-098
  [`student-design-start-board.schema.json`](student-design-start-board.schema.json).

Subcommands:

- `confirm <pending-program-draft.json> <human-record.json> --output <confirmed-program-draft.json>`
- `build <confirmed-digest.json> <start-board.json> <confirmed-program-draft.json> --output <student-spatial-program.json>`
- `validate <confirmed-digest.json> <start-board.json> <confirmed-program-draft.json> <student-spatial-program.json>`

## Upstream chain and confirmation

`build` and `validate` accept only this chain:

1. a confirmed ARCH-097 digest, verified with the existing digest gates;
2. a start board verified with the existing ARCH-098 logic as the exact
   deterministic projection of that digest;
3. a confirmed student spatial program draft.

The draft starts with `human_confirmation.status: "pending"`. `confirm`
binds a human record with exactly four keys: `action` equal to
`CONFIRM_STUDENT_SPATIAL_PROGRAM_DRAFT`, a human record label (agent and
model labels are rejected with the existing human-label guard), a
timezone-qualified RFC 3339 date-time, and `pending_draft_sha256`: the
SHA-256 of the canonical JSON plus newline bytes of the whole pending draft
document. Any field change to a confirmed draft breaks the recomputed
binding hash and fails closed with `PROGRAM_DRAFT_HASH_MISMATCH`. No system
clock is read and no confirmer, time, or user content is generated.

The output carries a machine-only `source_binding` with the digest
`input_hash`, the confirmed digest SHA-256, the pending digest SHA-256, the
start board SHA-256, the confirmed program draft SHA-256, and the pending
program draft SHA-256. `validate` re-derives the expected output from the
three upstream documents and requires exact canonical JSON plus newline byte
equality; any output tampering fails with
`STUDENT_SPATIAL_PROGRAM_CONTENT_MISMATCH`, never as a source hash mismatch.

## Human-authored draft rules

The draft carries only what the human explicitly wrote. Each space declares a
stable `space_id`, a name, one functional zone (`public`, `internal_staff`,
`service_support`, `shared`, `unresolved`), one activity profile (`active`,
`quiet`, `mixed`, `unresolved`), an origin, and an area:

- origin `brief_stated` requires a locator visible in the confirmed start
  board; origin `human_working` requires the human's own reason;
- area `brief_stated` requires a positive square-metre value plus a confirmed
  program locator from the start board; area `human_working` requires a
  positive value plus a working note and stays visibly a working figure;
  area `unresolved` carries no value and must state what is missing.

Space names must be unique across different `space_id` values: the student
view shows names only and exposes no internal identifier, so distinct names
are the readability and traceability requirement. The builder never
auto-numbers, rewrites, or guesses a difference; the human must provide clear
unique names in the draft. Each `unresolved_program_input` record_id must
also be unique; a reused record id is rejected with
`PROGRAM_DRAFT_SCHEMA_INVALID`.

Relations carry a stable identifier, two distinct declared spaces, one kind
(`must_be_near`, `prefer_be_near`, `must_be_separate`, `shared_support`), and
a brief locator or a human working reason. One unordered pair of spaces keeps
exactly one relation: any second relation for the same pair fails closed with
`PROGRAM_RELATION_INVALID`, whatever its kind, basis, direction, or
relation_id; the builder never merges relations, picks a priority, drops one
silently, or suggests a replacement. The builder also rejects self-relations,
unknown spaces, and any brief claim whose locator is not visible in the
confirmed start board.

Confirmed program locators never disappear silently: every confirmed
`program` locator of the start board must be referenced by at least one
`brief_stated` space (origin or area), or kept visible by an explicit human
`unresolved_program_input` record with a reason. A locator can never be both
mapped and unresolved, and an unresolved record can never cite a locator that
does not exist in the confirmed board.

## Area framework

Area arithmetic reuses the deterministic calculation logic of
[`check_area_schedule.py`](../scripts/check_area_schedule.py) by direct module import;
no subprocess is started. The output keeps the figures separate:

- `brief_stated_area_subtotal_m2`: brief figures only;
- `human_working_area_subtotal_m2`: working figures only, never disguised as
  brief facts;
- `scheduled_area_m2`: the sum of the two;
- `unresolved_area_spaces`: spaces without a value, counted in no total;
- `area_status`: `partial` while any space lacks a value; `complete` only
  when every current space has a number. `complete` is never a final,
  approval, or constructibility conclusion.

No grossing factor, efficiency ratio, gross-area inference, floor count,
dimension, side length, area ratio, or buildability conclusion is produced.

## Student view

`student_view` contains the project title; the fixed stage
`program_confirmed_ready_for_next_step`; spaces grouped in the fixed zone
order `public`, `internal_staff`, `service_support`, `shared`, `unresolved`,
each with name, activity profile, area status and value when present, and a
human-readable origin or working note; the separated area summary; relations
expressed by space names; unresolved brief items carried from the start
board; unresolved program and area items; at most three human questions; one
deterministic next action; and explicit boundaries.

The next action is `resolve_program_gaps` whenever any unresolved brief,
program, or area item exists, and `dimension_candidates` otherwise. The
student view contains no internal identifier, hash, recommendation, winner,
option, concept, massing, floor count, entrance, dimension, side length,
grid, height, site plan, circulation scheme, environmental conclusion,
source URL, HTML, media, or real-project path.

## What this slice never does

This slice does not parse DOC, DOCX, PDF, HTML, or image content and performs
no OCR; it uses no browser, network, external case, Crawl4AI, Playwright, or
PowerPoint. It generates no space, area, relation, zone, or activity profile
automatically; it performs no automatic area extraction or semantic
validation; it gives no design advice, dimension candidate, floor stack, plan
layout, massing, grid, or option comparison. The output is JSON data: no
HTML, web page, PPTX, image, plan, or massing diagram.

## Error codes

| Code | Meaning |
| --- | --- |
| `PROGRAM_DRAFT_SCHEMA_INVALID` | The draft fails the closed draft schema, or duplicates a space id, space name, relation id, or unresolved record id. |
| `PROGRAM_DRAFT_NOT_CONFIRMED` | The draft is pending instead of confirmed. |
| `PROGRAM_DRAFT_CONFIRMATION_INVALID` | The confirmation action, human label, time, or bound hash field is invalid. |
| `PROGRAM_DRAFT_HASH_MISMATCH` | The recorded confirmation hash does not bind the supplied draft's pre-confirmation document. |
| `PROGRAM_SOURCE_LOCATOR_UNKNOWN` | A brief claim cites a locator absent from the confirmed start board, or a confirmed program locator disappeared without an explicit unresolved record. |
| `PROGRAM_RELATION_INVALID` | A relation is self-referential, references an unknown space, or is a second relation for the same unordered pair. |
| `STUDENT_SPATIAL_PROGRAM_SCHEMA_INVALID` | A built or supplied program fails the program schema. |
| `STUDENT_SPATIAL_PROGRAM_CONTENT_MISMATCH` | The upstream documents are valid but the supplied program is not their exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written atomically; no existing file is overwritten. |

Upstream digest and start-board error codes propagate unchanged.

## Determinism and safety

- The script opens no socket and starts no subprocess; it imports no browser,
  presentation, or crawler module.
- Identical inputs produce byte-identical output; no system clock is read and
  no input document is modified.
- With `--output`, the destination is written through a temporary file with
  `fsync` and atomic replace, and only after full validation, so a failed run
  leaves any existing file unchanged.
- Failed gates emit no output and return a non-zero exit code with
  machine-readable error codes.
