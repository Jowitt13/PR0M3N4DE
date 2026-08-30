# Student Design Start Board

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Input contract](#input-contract)
- [Source binding](#source-binding)
- [Student view](#student-view)
- [Unresolved items](#unresolved-items)
- [Next action and boundaries](#next-action-and-boundaries)
- [What this board never generates](#what-this-board-never-generates)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)
- [Student design start board card renderer](#student-design-start-board-card-renderer)

## Purpose

Give a student one readable starting point after a brief has been understood
and confirmed. The board restates what the confirmed assignment brief digest
says, lists what is still unresolved, carries the digest's clarification
questions, and names exactly one next action. It is data only: not a web UI,
not a PPTX, not an option generator, not an area calculator, and not a design
recommender. It does not replace the normalized brief ledger.

## Contracts

- Board output: [`student-design-start-board.schema.json`](student-design-start-board.schema.json).
- Script: [`../scripts/build_student_design_start_board.py`](../scripts/build_student_design_start_board.py).
- Source contract: the ARCH-097 [`assignment-brief-digest.schema.json`](assignment-brief-digest.schema.json), read-only.

Run `scripts/build_student_design_start_board.py build <confirmed-digest.json> --output <start-board.json>`
to derive one board, then
`scripts/build_student_design_start_board.py validate <confirmed-digest.json> <start-board.json>`
to re-check the board against its source digest.

## Input contract

The only accepted input is one ARCH-097 AssignmentBriefDigest that:

- validates against the committed digest schema;
- has `human_confirmation.status` equal to `confirmed`;
- carries a valid human confirmation: `CONFIRM_BRIEF_DIGEST` action, a human
  record label, a timezone-qualified RFC 3339 date-time, and a
  `pending_digest_sha256` that exactly matches the recomputed canonical hash
  of the digest's pre-confirmation document.

A pending or structurally invalid digest is rejected fail-closed with no
board emitted. A digest whose recorded binding hash does not match its
reconstructed pre-confirmation document is rejected with
`SOURCE_DIGEST_HASH_MISMATCH`. The board builder never reinterprets,
extends, repairs, or rewrites the input; every student-visible sentence is
copied from the confirmed digest.

## Source binding

`source_binding` is a machine traceability layer and is not default
student-facing content. It carries exactly three hashes:

- `input_hash`: the intake provenance hash carried by the digest (copied,
  never recomputed or invented);
- `confirmed_digest_sha256`: the SHA-256 of the canonical JSON plus newline
  bytes of the whole confirmed digest document as supplied;
- `pending_digest_sha256`: the human-confirmed binding hash preserved by the
  digest.

No hash is fabricated and no system clock is read. The builder re-derives the
digest's pre-confirmation document by restoring `human_confirmation` to its
pending form and requires the recomputed canonical hash to match the recorded
`pending_digest_sha256` exactly. `validate` recomputes the canonical hash of
the supplied confirmed digest and rebuilds the expected board with the same deterministic build logic and
requires the supplied board to match it byte-for-byte in canonical JSON plus
newline form; any student-visible or binding change fails with
`START_BOARD_CONTENT_MISMATCH`.

## Student view

`student_view` contains:

- `project_title`, copied from the digest;
- `stage`, fixed to `brief_confirmed_ready_for_programming`;
- `confirmed_requirements`: only digest requirements with status `included`
  or `duplicate_merged`, grouped by the nine categories in their fixed
  canonical order (`hard_constraint`, `program`, `site`,
  `spatial_relationship`, `circulation`, `deliverable`, `design_goal`,
  `scoring_focus`, `reference_only`). Each item copies the concise literal
  wording and the human-readable source locator; no internal `REQ`, `SEG`,
  `CONF`, `UNK`, or `CAND` identifier and no hash appears here;
- `unresolved_items`: conflicts, missing information, unreadable
  expectations, and deferred items, each with readable wording and locator;
- `clarification_questions`: carried verbatim from the digest, at most three,
  with no question ever added by the board;
- `next_action`: fixed to `program_and_area` with the student-facing wording
  that the next step is to organize the functional spaces, their provided or
  unresolved areas, users, access levels, active and quiet needs, and
  adjacency or separation relationships;
- `boundaries`: explicit statements of what the board does not decide.

## Unresolved items

- Conflict items list every distinct locator resolved from all of the
  requirement's declared conflicts, merged in stable conflict-identifier
  order with first occurrence kept, and never choose a winner;
- missing items state that no readable supplied source states the
  information and never fill in a value;
- unreadable items state that only an unreadable supplied source could state
  the information;
- deferred items preserve the recorded reason.

Unresolved items keep the deterministic requirement order of the source
digest. The board adds no resolution, priority, or recommendation.

## Next action and boundaries

The one next action is program-and-area work, which begins only after the
student has read this board. This slice does not generate the design-problem
translation or any design advice; that belongs to a later student spatial
programming slice. The board states explicitly that it decides no area value
or total, no dimension, no floor count, no entrance position, no circulation
scheme, no massing, no column grid, no environmental conclusion, and produces
no design option or scheme.

## What this board never generates

The board output contains no design option, recommendation, or selected
option; no floor count, entrance, massing, grid, or height; no invented
program, invented area, area total, or dimension; no hypothesis, spatial
operation, or human decision; no `SRC`, `Evidence`, `CARD`, or `VERIFIED`
record; no HTML, external link, media, or real-project path; and no hash or
internal identifier inside `student_view`.

## Error codes

| Code | Meaning |
| --- | --- |
| `SOURCE_DIGEST_SCHEMA_INVALID` | The supplied digest fails the committed digest schema. |
| `SOURCE_DIGEST_NOT_CONFIRMED` | The digest is pending or has no confirmed status. |
| `SOURCE_DIGEST_CONFIRMATION_INVALID` | The confirmation action, human label, time, or bound hash field is invalid. |
| `SOURCE_DIGEST_HASH_MISMATCH` | The recorded confirmation hash does not bind the supplied digest's pre-confirmation document, or the digest no longer matches the board's source binding. |
| `START_BOARD_SCHEMA_INVALID` | A built or supplied board fails the board schema. |
| `START_BOARD_CONTENT_MISMATCH` | The source digest is valid but the supplied board is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written atomically; no existing file is overwritten. |

## Determinism and safety

- The script opens no socket and starts no subprocess; it imports no browser,
  presentation, or crawler module.
- Identical input produces byte-identical output; the builder records no
  wall-clock time and never modifies the input digest.
- With `--output`, the destination is written through a temporary file with
  `fsync` and atomic replace, and only after full validation, so a failed run
  leaves any existing file unchanged.
- Failed gates emit no board and return a non-zero exit code with
  machine-readable error codes.

## Student design start board card renderer

The board builder output remains JSON; this section only routes to a
separate read-only renderer. For one confirmed digest and its validated
start board, read
[student-design-start-board-card.md](student-design-start-board-card.md)
and use `scripts/render_student_design_start_board_card.py` to render one
deterministic Simplified-Chinese start board card to stdout only. The
renderer validates the supplied digest and board through this stage's public
`validate_board` entry, propagates upstream error codes unchanged, never
rebuilds, repairs, or reinterprets the digest or board, and writes no file,
confirmation record, area value, or design content. Program-and-area work
still begins only through the student's own authoring.
