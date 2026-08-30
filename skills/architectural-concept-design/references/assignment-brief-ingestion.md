# Assignment Brief Ingestion

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [What this slice accepts](#what-this-slice-accepts)
- [Literal layer and design layer](#literal-layer-and-design-layer)
- [Categories and statuses](#categories-and-statuses)
- [Coverage rules](#coverage-rules)
- [Clarification questions](#clarification-questions)
- [Human confirmation gate](#human-confirmation-gate)
- [Abnormal input representation](#abnormal-input-representation)
- [Downstream boundary](#downstream-boundary)
- [Determinism and safety](#determinism-and-safety)
- [Student assignment brief digest card renderer](#student-assignment-brief-digest-card-renderer)

## Purpose

Make an assignment brief understandable before any design reasoning begins.
The digest is the first hard gate of the student workflow: it turns supplied
assignment material into a short, categorized, literal reading with one status
for every identified item, and it stops for human confirmation before any
site, program, concept, option, or spatial work.

## Contracts

- Intake input: [`assignment-brief-intake.schema.json`](assignment-brief-intake.schema.json).
- Digest output: [`assignment-brief-digest.schema.json`](assignment-brief-digest.schema.json).
- Script: [`../scripts/build_assignment_brief_digest.py`](../scripts/build_assignment_brief_digest.py).

Run `scripts/build_assignment_brief_digest.py build <intake.json> --output <digest.json>`
to assemble one pending digest. Run
`scripts/build_assignment_brief_digest.py confirm <digest.json> <human-record.json> --output <confirmed-digest.json>`
to bind one explicit human confirmation record.

## What this slice accepts

The intake is a structured record authored by the human or by a reading agent
that has already looked at the supplied material:

- a file inventory with declared file types and readability classifications;
- pre-extracted text segments, each with a source file label and an in-file locator;
- human-declared conflicts between segments;
- human-declared unknowns for information no readable source supplies;
- literal requirement candidates, each bound to its supporting segments;
- at most three clarification questions and optional human notes.

This slice parses no DOC, DOCX, PDF, HTML file, or image scan, and it claims
no binary or format-specific extraction support. A format becomes supported
only when a later, separately reviewed slice proves it with implementation and
tests. Until then, extraction is human or reader-agent work carried into the
intake, and an unreadable file is represented as unreadable, not bypassed.

## Literal layer and design layer

The digest answers only one question: what does the assignment brief literally
say? It must not answer how to design, how many floors to build, where to put
an entrance, or which massing to prefer.

Allowed in the literal layer:

- concise paraphrases of stated requirements, with source locators;
- stated hard constraints, program and areas, site conditions, relationship
  and circulation requirements, deliverable requirements, design goals, and
  scoring focus;
- declared conflicts, unknowns, and deferred items with reasons.

Forbidden in the literal layer:

- choosing floor counts, entrance positions, or massing;
- presenting experience-based judgement as a brief fact;
- promoting supplied information to a verified claim;
- hiding missing information behind a design proposal.

Requirement candidates therefore carry no design fields, every digest
requirement fixes `literal_only: true`, and the digest schema has no
representation for interpretations, hypotheses, options, or recommendations.
The schemas reject undefined structured fields, including structured design
fields, and the builder fails closed on them. They cannot prove that free
prose is literal: whether a `concise_text` truly paraphrases the brief is
checked by reading back the cited source locators and by the human
confirmation gate, not by schema validation alone.

## Categories and statuses

Categories follow the student workflow machine contract: `hard_constraint`,
`program`, `site`, `spatial_relationship`, `circulation`, `deliverable`,
`design_goal`, `scoring_focus`, and `reference_only`.

Requirement statuses are exactly six:

- `included`: a literal requirement with at least one supporting segment;
- `duplicate_merged`: duplicates merged into one record while every original
  location is preserved in `merged_from_segment_ids`;
- `conflict`: the item belongs to at least one declared conflict; no winner is chosen;
- `missing`: derived from a declared unknown that no source supplies;
- `unreadable`: derived from a declared unknown whose only possible source is an unreadable file;
- `deferred_with_reason`: not relevant to the current design stage, with the reason recorded.

A `conflict` candidate must draw every one of its source segments from the
segments of the conflicts it cites; a candidate that mixes in unrelated
segments is rejected.

## Coverage rules

Every extracted segment must be covered by at least one requirement
candidate; the builder emits no digest while any segment is uncovered
(`UNCOVERED_SEGMENT`). Every `readable` or `partial` input file must be
represented by at least one extracted segment; a readable or partial file
that contributes nothing fails the build (`INPUT_FILE_UNREPRESENTED`),
because its content would otherwise silently disappear. Unreadable files keep
their required `unreadable_reason` and never receive fabricated segments. The
coverage summary reports file, segment, and status counts. Never claim
complete understanding of a brief. The permitted claim is: every identified
segment, table item, and drawing requirement has a status, and every
unresolved item is listed explicitly.

## Clarification questions

The digest carries at most three focused clarification questions at a time.
Questions are authored in the intake by the reading agent; the builder only
enforces the limit. Ask only questions that would change a major decision.

## Human confirmation gate

`build` always emits `human_confirmation.status: "pending"`. No design
analysis, program table, area allocation, option, or spatial recommendation
may be presented while the digest is pending.

To confirm, a human supplies a record with exactly four keys:

```json
{
  "action": "CONFIRM_BRIEF_DIGEST",
  "confirmed_by": "<human name or label>",
  "confirmed_at": "<timezone-qualified RFC 3339 date-time>",
  "pending_digest_sha256": "<exact SHA-256 of the pending digest document>"
}
```

`pending_digest_sha256` is the SHA-256 of the canonical JSON plus trailing
newline bytes of the whole pending digest document exactly as built: every
field from `schema_version` through `not_generated`, including the pending
`human_confirmation` object and the intake-derived `input_hash`. `confirm`
recomputes that hash over the supplied digest document and rejects any
mismatch with `PENDING_DIGEST_HASH_MISMATCH`, writing no output, so a digest
edited after review can never be confirmed. The confirmed digest preserves
the bound hash for downstream state-package traceability. `input_hash` is
only the intake provenance hash; it is not the human-confirmation binding.

`confirm` binds that record to the pending digest document supplied to it.
Agent labels are rejected, an already confirmed digest cannot be confirmed
again, and any intake change requires a rebuild and a new confirmation with a
new hash.

## Abnormal input representation

| Condition | Representation |
| --- | --- |
| Unreadable file | inventory `readability: "unreadable"` with a reason; expected content recorded as a declared unknown of kind `unreadable`; nothing is guessed |
| Readable or partial file with no segments | build fails closed with `INPUT_FILE_UNREPRESENTED`; content is never allowed to disappear silently |
| Missing information | declared unknown of kind `missing`; becomes a `missing` requirement; absence is never inferred into a value |
| Conflicting values | declared conflict plus `conflict` requirements; both locations keep their locators and no winner is selected |
| Duplicated requirements | one `duplicate_merged` record preserving every original location |
| Not relevant now | `deferred_with_reason` with the recorded reason |
| Human-stated assumption | carried in `human_notes` verbatim; never promoted to a brief requirement |

## Downstream boundary

The digest is a reading layer only. It generates no `hypotheses`, `options`,
`decisions`, area allocation, massing, floor count, entrance position, floor
plan, `SRC`, `Evidence`, `CARD`, or `VERIFIED` content. After confirmation,
digest requirements become candidate facts a human authors into the
normalized brief ledger and the ADR-0001 input brief; unknowns become the
missing-information register. Concept direction remains a human decision.

## Determinism and safety

- The script opens no socket and starts no subprocess.
- Output is deterministic for identical input; the builder records no
  wall-clock time, and `input_hash` is the SHA-256 of the canonical intake.
- With `--output`, the destination is written atomically and only after full
  validation, so a failed run leaves any existing file unchanged.
- Failed gates emit no digest and return a non-zero exit code with
  machine-readable error codes.

## Student assignment brief digest card renderer

The digest builder output remains JSON; this section only routes to a
separate read-only renderer. For one schema-valid, pending digest, read
[student-assignment-brief-digest-card.md](student-assignment-brief-digest-card.md)
and use `scripts/render_student_assignment_brief_digest_card.py` to render one
deterministic Simplified-Chinese digest card to stdout only. The renderer
validates the supplied digest against this stage's authoritative digest
schema, fails closed on a confirmed digest or any schema violation, never
reads the intake, parses no DOC, DOCX, PDF, HTML, image, or OCR content, and
writes no file, confirmation record, or design content. Human confirmation
still happens only through the `confirm` contract above.
