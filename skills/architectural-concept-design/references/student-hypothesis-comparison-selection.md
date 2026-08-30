# Student Hypothesis Comparison and Human Selection

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Comparison draft](#comparison-draft)
- [Criteria](#criteria)
- [Candidate assessments](#candidate-assessments)
- [Guidance rules](#guidance-rules)
- [Human selection record](#human-selection-record)
- [Two output states](#two-output-states)
- [Student view](#student-view)
- [Explicit non-claims](#explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Turn the two to six student-written massing, grid, and height hypotheses of
one confirmed ARCH-103 framework into one clear, comparable, guided but
never machine-decided selection interface, plus one machine-readable human
selection record. The machine organizes, verifies, compares, and explains
what the student and human have written; the human makes the final
selection. Design is not an answer but a sequence of decisions: this slice
supplies order and traceability, never the meaning.

## Contracts

- Draft input: [`student-hypothesis-comparison-draft.schema.json`](student-hypothesis-comparison-draft.schema.json)
- Comparison output: [`student-hypothesis-comparison.schema.json`](student-hypothesis-comparison.schema.json)
- Builder: [`build_student_hypothesis_comparison.py`](../scripts/build_student_hypothesis_comparison.py) with `confirm`, `build`, `select`, and `validate` subcommands.

## Upstream chain

`build`, `select`, and `validate` verify the complete ARCH-103 chain by
reusing the committed `validate_massing_grid_height`: the confirmed
ARCH-097 digest, the exact ARCH-098 start board, the confirmed ARCH-099
spatial program draft and its exact spatial program, the confirmed
ARCH-100 dimension draft, its exact dimension plan, the human dimension
selection, the confirmed ARCH-101 floor zoning draft and its exact
framework, the confirmed ARCH-102 circulation-environment draft and its
exact framework, and the confirmed ARCH-103 massing-grid-height draft and
its exact framework. Any upstream tamper or failure propagates the existing
ARCH-097~103 stable error codes unchanged; this slice never masks or remaps
them. When the ARCH-103 upstream unresolved gate is blocked, this slice
fails closed with the same `MASSING_GRID_HEIGHT_UPSTREAM_UNRESOLVED`; it
never bypasses, filters, fills, or recommends around unresolved items.

The comparison draft binds the complete massing-grid-height framework by
its canonical JSON plus newline SHA-256
(`source_massing_grid_height_framework_sha256`). Confirmation uses exactly
four keys: `action` (`CONFIRM_STUDENT_HYPOTHESIS_COMPARISON_DRAFT`),
`confirmed_by`, `confirmed_at` (timezone-qualified RFC 3339), and
`pending_student_hypothesis_comparison_draft_sha256`, which must equal the
canonical JSON plus newline SHA-256 of the whole pending draft with
`human_confirmation` restored to `{"status": "pending"}`. Agent and model
labels fail closed. No system clock is read; no confirmer, time, or content
is generated.

## Comparison draft

The student writes one comparison draft over the confirmed framework:

- `criteria`: zero or more ordered, human-authored comparison criteria.
- `candidate_assessments`: exactly one assessment per existing hypothesis,
  so every real candidate appears and no candidate is added or dropped.
- `clarification_questions`: at most three, carried verbatim.
- `guidance`: optional human-authored, non-binding guidance.

The dynamic candidate count comes only from the confirmed framework's
actual hypotheses (two to six). The machine never forces a two-option A/B
layout, never merges candidates, and never invents one. Candidate order
always equals the student's own hypothesis order.

## Criteria

Each criterion carries a `CR-xxx` id, a `name`, and a `description`. The
array order is the human's priority order; the machine keeps it and uses it
for guidance traceability only. Criteria may be empty, but empty criteria
can never support a single-candidate recommendation: any guidance claiming
a focus while no criteria exist fails closed as untraceable. The machine
never adds, reorders, reinterprets, or weighs a criterion.

## Candidate assessments

Each assessment is bound to one existing `MGH-xxx` hypothesis key and
carries the student's own words:

- `applicable_preconditions`: when this candidate applies;
- `advantages`: what the candidate would gain;
- `costs_or_risks`: what it would cost or risk;
- `reconsider_when`: when it should not be chosen or must be reconsidered;
- `criterion_judgments`: optional per-criterion judgments, each referencing
  one existing criterion id.

Every hypothesis keeps exactly one assessment; unknown, duplicated, or
missing candidate keys fail closed. All assessment text is human judgment
shown verbatim; the machine verifies nothing about its architectural merit
and labels none of it as verified fact.

## Guidance rules

Guidance is a projection of the student's own draft, never a machine
opinion. The draft guidance carries `focus_candidate_keys` (zero, one, or
several), a `basis` text, `basis_criterion_ids` (every id must exist in
`criteria`), `advantages`, `costs_or_risks`, and `reconsider_when`.

- Exactly one focus key becomes `recommended_to_consider_first`; two or
  more become a `suggested_focus` list. The machine never breaks a tie or
  resolves a conflict on its own.
- No guidance, or guidance with zero focus keys, projects
  `unable_to_suggest_single_candidate` with factual reasons; a winner is
  never fabricated.
- Focus keys or basis criterion ids that do not exist, or duplicated,
  fail closed as `COMPARISON_GUIDANCE_INVALID`.
- Every projected guidance carries the fixed boundary sentence:
  `This is decision guidance, not an automatic architectural decision.`
- Guidance is never binding: the human may select any existing candidate,
  including one outside the guidance focus.

## Human selection record

The final selection can only be completed by one explicit, valid human
record. The `select` subcommand and the `validate` path accept a record
with exactly these five keys and nothing else:

- `action`: exactly `SELECT_STUDENT_MASSING_GRID_HEIGHT_HYPOTHESIS`;
- `selected_by`: a human label; agent and model labels are rejected;
- `selected_at`: a timezone-qualified RFC 3339 date-time supplied by the
  human; no system clock is read;
- `selected_candidate_key`: exactly one existing `MGH-xxx` hypothesis key;
  a list, an unknown key, or a duplicated selection fails closed;
- `source_comparison_document_sha256`: the canonical JSON plus newline
  SHA-256 of the whole pending comparison document being answered, so any
  tamper of the pending document is rejected.

There is no default selection, no automatic acceptance of guidance, no
score-based selection, and no selected output without a valid human record.
A document that already carries a selection cannot be selected again.

## Two output states

One closed output schema covers both states.

- `pending_selection`: `human_selection` is `null`; the next action is
  `human_select_massing_grid_height_hypothesis`.
- `selected`: `human_selection` carries the bound record; the next action
  is `handoff_selected_massing_grid_height_hypothesis`, a controlled
  handoff to the next separately reviewed stage. It does not enter PPTX
  generation, automatic plan drawing, or any machine-made design
  conclusion.

## Student view

The output is JSON data only: no PPTX, web page, image, drawing, or
three-dimensional model. `student_view` carries:

- the project title and the fixed stage
  `massing_grid_height_hypothesis_comparison`;
- a natural-language `decision_prompt` stating which confirmed upstream
  conditions and which student criteria apply, and that exactly N
  candidates are available for human selection;
- every candidate, in the student's own order, each showing its label, its
  confirmed massing groups with level and zone names, grid intent,
  per-level vertical intervals and subtotal, note, and the human-written
  assessment (preconditions, advantages, costs or risks, reconsider
  conditions, per-criterion judgments by criterion name);
- the ordered comparison criteria by name and description;
- the projected guidance with its basis, advantages, costs, reconsider
  conditions, and fixed non-binding boundary sentence, or the honest
  inability statement with reasons;
- the draft's clarification questions, at most three, carried verbatim;
- the human selection view (label, who, when) once a valid record exists;
- the fixed next action and boundaries statement.

The machine-only `source_binding` keeps the full upstream hash chain plus
the pending and confirmed comparison draft hashes, and the selected state
binds the whole pending document through the human record's hash. The
student view exposes no internal id (`MGH-`, `MG-`, `Z-`, `LV-`, `CR-`,
`S-`), no SHA-256, no scoring or ranking algorithm, no winner, no rank, no
score, no best option, and no upstream machine field. Candidate keys exist
only in the student's own authored documents and machine records.

## Explicit non-claims

This slice decides no level count, entrance, plan coordinate, orientation,
site plan, massing shape, structural system, regulation, cost, performance,
or constructibility. It generates no candidate, criterion, assessment, or
architectural conclusion, ranks and scores nothing, and selects nothing.
Assessment and guidance text are human judgment, never verified facts. It
parses no DOC, DOCX, PDF, HTML, image, or OCR content and claims no format
extraction support. It opens no socket and no browser, and it uses no
Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `COMPARISON_DRAFT_SCHEMA_INVALID` | The draft fails its closed schema (including a candidate count outside two to six or an empty guidance basis). |
| `COMPARISON_DRAFT_NOT_CONFIRMED` | Build, select, or validate received a pending draft. |
| `COMPARISON_DRAFT_CONFIRMATION_INVALID` | The confirmation record is not a valid human record. |
| `COMPARISON_DRAFT_HASH_MISMATCH` | The recorded hash does not bind the draft's pre-confirmation document. |
| `COMPARISON_SOURCE_MASSING_MISMATCH` | The draft does not bind the supplied confirmed massing-grid-height framework. |
| `COMPARISON_CRITERION_INVALID` | A criterion id repeats. |
| `COMPARISON_ASSESSMENT_INVALID` | An assessment names an unknown or duplicated candidate key. |
| `COMPARISON_ASSESSMENT_COVERAGE_INVALID` | A hypothesis has no assessment; every candidate keeps exactly one. |
| `COMPARISON_JUDGMENT_INVALID` | A judgment references an unknown or duplicated criterion id. |
| `COMPARISON_GUIDANCE_INVALID` | Guidance references unknown or duplicated focus candidates or basis criteria, and can never rest on criteria that do not exist. |
| `COMPARISON_SELECTION_RECORD_INVALID` | The selection record is not one valid human record with the fixed action, a human label, a timezone-qualified RFC 3339 time, and a well-formed hash. |
| `COMPARISON_SELECTION_CANDIDATE_INVALID` | The selected key is not exactly one existing hypothesis key. |
| `COMPARISON_SELECTION_SOURCE_MISMATCH` | The recorded hash does not bind the whole pending comparison document. |
| `COMPARISON_ALREADY_SELECTED` | A selection is recorded exactly once; re-selection is refused. |
| `STUDENT_HYPOTHESIS_COMPARISON_SCHEMA_INVALID` | A built or supplied document fails the output schema. |
| `STUDENT_HYPOTHESIS_COMPARISON_CONTENT_MISMATCH` | The chain is valid but the supplied pending or selected document is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097~103 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-104 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. `validate` re-runs the complete
upstream chain, re-derives the expected pending document with the same
build logic, re-applies the recorded selection for selected documents, and
compares canonical JSON plus newline bytes exactly; any candidate text,
assessment, guidance, decision prompt, next action, selection view, or
binding change fails closed with
`STUDENT_HYPOTHESIS_COMPARISON_CONTENT_MISMATCH`. Output is written only
after full validation, through a temporary file with `fsync` and atomic
replace; a failed write never creates or overwrites the destination. The
script opens no socket and starts no subprocess, and imports no `urllib`,
`requests`, browser, Crawl4AI, Playwright, PowerPoint, or system-clock
module.
