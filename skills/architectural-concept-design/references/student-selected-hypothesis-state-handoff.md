# Student Selected Hypothesis State Package and Controlled Handoff

## Contents

- [Purpose](#purpose)
- [Contracts](#contracts)
- [Upstream chain](#upstream-chain)
- [Why not the generic project state package](#why-not-the-generic-project-state-package)
- [Source binding](#source-binding)
- [Selected state](#selected-state)
- [Student handoff](#student-handoff)
- [Handoff contract](#handoff-contract)
- [Guidance display rule](#guidance-display-rule)
- [Next stage and explicit non-claims](#next-stage-and-explicit-non-claims)
- [Error codes](#error-codes)
- [Determinism and safety](#determinism-and-safety)

## Purpose

Wrap the human-selected massing, grid, and height hypothesis of one selected
ARCH-104 comparison document into a closed, deterministic, traceable state
package, and hand it to the next separately reviewed stage under an explicit
contract. The machine verifies and binds; it never re-selects, re-ranks,
re-scores, recommends, or derives a design from the selection. Design is not
an answer but a sequence of decisions: this slice records one human decision
and states exactly what may and may not be built on it.

## Contracts

- State package: [`student-selected-hypothesis-state.schema.json`](student-selected-hypothesis-state.schema.json)
- Builder: [`build_student_selected_hypothesis_state.py`](../scripts/build_student_selected_hypothesis_state.py) with `build` and `validate` subcommands.

## Upstream chain

`build` and `validate` reuse the committed ARCH-104 `validate_comparison`
public entry, which re-runs the complete ARCH-097~104 chain: the confirmed
ARCH-097 digest, the exact ARCH-098 start board, the confirmed ARCH-099
spatial program draft and its exact spatial program, the confirmed ARCH-100
dimension draft, its exact dimension plan, the human dimension selection,
the confirmed ARCH-101 floor zoning draft and its exact framework, the
confirmed ARCH-102 circulation-environment draft and its exact framework,
the confirmed ARCH-103 massing-grid-height draft and its exact framework,
the confirmed ARCH-104 comparison draft, and the comparison document. Any
upstream tamper or failure propagates the existing ARCH-097~104 stable error
codes unchanged; this slice never masks or remaps them.

Only the `selected` comparison state is accepted. A `pending_selection`
document fails closed with `SELECTED_STATE_NOT_SELECTED`, and the recorded
human selection is re-verified by the upstream entry: its candidate key must
be exactly one existing hypothesis, and its hash must bind the whole pending
comparison document. The builder takes no selection record of its own, so a
selection can never be replaced or derived from guidance here.

## Why not the generic project state package

This slice does not call `assemble_project_state.py` and does not modify
`output.schema.json`. The generic package requires `skill_version`,
`project_id` (`P-xxx`), `generated_at`, plus `sources`, `evidence`,
`options`, `decisions`, and `deliverables` ledgers; none of those can be
produced from the student chain without fabrication, and its assembly entry
expects a validated ADR-0001 input plus a separately authored assembly
draft. The student selected-hypothesis package is therefore an independent,
closed contract and is never presented as equivalent to the generic project
state package.

## Source binding

The machine-only `source_binding` carries:

- the complete ARCH-097~104 hash chain inherited from the selected
  comparison document;
- the canonical JSON plus newline SHA-256 of the whole selected comparison
  document;
- the human selection binding: fixed action, candidate key, human label,
  timezone-qualified RFC 3339 time, and the pending comparison document
  hash bound by the record.

`source_binding` never appears in the student-facing handoff.

## Selected state

The machine-only `selected_state` carries the selected hypothesis key and
the selection record, marked `machine_verification_binding_only`. It exists
only for later controlled verification and is not an automatic design
instruction.

## Student handoff

The human-readable `student_handoff` carries:

- the project title and the fixed stage
  `selected_hypothesis_confirmed`;
- the selected candidate's readable label plus its confirmed massing groups
  with level and zone names, grid intent, per-level vertical intervals and
  subtotal, and note;
- the selected candidate's human-written assessment: applicable
  preconditions, advantages, costs or risks, and reconsider conditions;
- the student's own guidance basis only when the selected candidate appears
  in its focus, always with the fixed sentence
  `This is decision guidance, not an automatic architectural decision.`;
- a readable human selection summary (label, who, when);
- the fixed next action `author_selected_plan_framework_draft`;
- a fixed boundaries statement.

The student handoff exposes no internal id (`MGH-`, `MG-`, `Z-`, `LV-`,
`CR-`, `S-`), no SHA-256, and no winner, rank, score, best, or automatic
selection wording.

## Handoff contract

The `handoff_contract` states:

- `confirmed_available`: what the next stage may rely on — the confirmed
  selected hypothesis facts, the student's own assessment, the explicit
  human selection binding, and the confirmed upstream levels and zones;
- `must_not_infer`: what must still not be inferred — plan coordinates,
  room rectangles, entrances, circulation drawings, total plans, extra
  floor counts, massing shape, orientation, site position, grid values
  beyond the written bays, structural conclusions, regulation, cost,
  performance, or constructibility;
- `invalidated_by_upstream_change`: any ARCH-097~104 upstream change, a
  changed or re-selected comparison document, or a document that stops
  being the exact deterministic projection of its chain invalidates the
  handoff and requires rebuild plus revalidation;
- `prohibited_outputs`: automatic plan generation, drawing, image, PPTX,
  or three-dimensional model; automatic selection, ranking, scoring, or
  recommendation; any machine-made design conclusion.

## Guidance display rule

Guidance is shown only when the selected candidate is inside the student's
own guidance focus, and always with the fixed boundary sentence. Showing
that guidance never turns it into a selection: the package records the
human selection record verbatim and derives nothing from guidance. A
guidance focus that names another candidate has no effect on this package.

## Next stage and explicit non-claims

The next action is `author_selected_plan_framework_draft`: the human authors
the next stage's plan-framework draft over this confirmed selected
hypothesis. This slice decides no plan coordinate, room rectangle, floor
count beyond the written levels, entrance, total plan, massing shape,
orientation, column grid value beyond the written bays, structural system,
regulation, cost, performance, or constructibility. It generates no
drawing, image, PPTX, or three-dimensional model, parses no DOC, DOCX, PDF,
HTML, image, or OCR content, opens no socket and no browser, and uses no
Crawl4AI, Playwright, or PowerPoint.

## Error codes

| Code | Meaning |
| --- | --- |
| `SELECTED_STATE_NOT_SELECTED` | Build or validate received a pending comparison document; only the selected state is accepted. |
| `STUDENT_SELECTED_HYPOTHESIS_STATE_SCHEMA_INVALID` | A built or supplied state package fails the closed output schema. |
| `STUDENT_SELECTED_HYPOTHESIS_STATE_CONTENT_MISMATCH` | The chain is valid but the supplied state package is not its exact deterministic projection. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written; no output is created or overwritten. |

Upstream ARCH-097~104 stable error codes propagate unchanged and are never
remapped or disguised as ARCH-105 errors.

## Determinism and safety

The builder is deterministic: the same inputs yield byte-identical output,
and inputs are never modified or reordered. `validate` re-runs the complete
upstream chain, re-derives the expected package with the same build logic,
and compares canonical JSON plus newline bytes exactly; any candidate fact,
assessment, guidance, handoff, next action, boundary, contract, or binding
change fails closed with
`STUDENT_SELECTED_HYPOTHESIS_STATE_CONTENT_MISMATCH`. Output is written
only after full validation, through a temporary file with `fsync` and
atomic replace; a failed write never creates or overwrites the destination.
The script opens no socket and starts no subprocess, reads no system clock,
and imports no `urllib`, `requests`, browser, Crawl4AI, Playwright,
PowerPoint, or system-clock module.
