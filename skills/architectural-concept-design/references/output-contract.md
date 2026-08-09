# Output contract and final early-design package assembly

> **Single authoritative source** for Step 8: assembling the completed architectural-chain ledgers into one final, traceable early-design package. This reference defines presentation and alignment, and routes to the separate state validator. It does not alter upstream facts, curate case cards, or release the Skill.

## Contents

- [Purpose, prerequisites, and authority](#purpose-prerequisites-and-authority)
- [Two aligned artifacts](#two-aligned-artifacts)
- [1. Project identity and delivery boundary](#1-project-identity-and-delivery-boundary)
- [2. Evidence, unknowns, and assumptions](#2-evidence-unknowns-and-assumptions)
- [3. Brief and site/context summary](#3-brief-and-sitecontext-summary)
- [4. Program, area, adjacency, zoning, and circulation](#4-program-area-adjacency-zoning-and-circulation)
- [5. Grid, structure, core, and height hypotheses](#5-grid-structure-core-and-height-hypotheses)
- [6. Precedent spatial operations and concept directions](#6-precedent-spatial-operations-and-concept-directions)
- [7. Comparison and assessment](#7-comparison-and-assessment)
- [8. Human decision request](#8-human-decision-request)
- [9. Dependencies and stale-propagation handoff](#9-dependencies-and-stale-propagation-handoff)
- [10. Deliverable register](#10-deliverable-register)
- [11. Next actions and professional boundaries](#11-next-actions-and-professional-boundaries)
- [12. Machine-readable package mapping and alignment](#12-machine-readable-package-mapping-and-alignment)
- [Assembly check and stop boundary](#assembly-check-and-stop-boundary)

---

## Purpose, prerequisites, and authority

Use this reference only after the following ledgers are complete for the same project state:

1. brief and evidence intake;
2. site and context analysis;
3. program, area, adjacency, zoning, and circulation;
4. grid, structural-system, core, and height hypotheses;
5. precedent spatial operations and differentiated concept directions; and
6. option comparison, human decision request, dependency model, and stale-propagation handoff.

Those upstream references remain the sole authority for their facts, evidence classification, architectural rules, calculations, and identifiers. This reference assembles their results; it must not reclassify, re-source, upgrade, or silently repair them. When an upstream ledger is incomplete, make the gap visible in Sections 2 and 11 rather than inventing content.

The package is an architectural pre-design deliverable. It is not construction documentation, a regulatory-compliance conclusion, a structural calculation, a cost estimate, a professional approval, or a final design decision.

## Two aligned artifacts

Produce both artifacts together:

1. **Human-readable early-design package.** A reviewable narrative and ledger that makes the design reasoning, trade-offs, unknowns, decision request, and next actions understandable to the human designer.
2. **Machine-readable state package.** A JSON document conforming to [output.schema.json](output.schema.json), containing only fields defined by that Schema.

The human-readable package may explain how conclusions were reached. The state package preserves stable IDs, sources, evidence, entities, dependencies, and deliverables for machine validation. Neither artifact may contradict the other.

For every evidence-bearing statement, show the relevant `E-xxx` identifier and retrieve its label from the Evidence Record. For every source reference, use the registered `SRC-xxx` identifier. Do not copy an Evidence Record label onto a Constraint, Hypothesis, Option, Criterion, Decision, Dependency, or Deliverable as if it were that entity's own label.

Every numeric quantity in the state package uses a separate `value` and `unit` structure where the Schema provides one. Narrative text may render a quantity for readability only when it names the corresponding source field or deterministic script result. Do not hand-calculate area totals; use [check_area_schedule.py](../scripts/check_area_schedule.py) where an area total is needed.

## 1. Project identity and delivery boundary

Open the human-readable package with:

- project name and `project_id`;
- package purpose and current early-design status;
- source-package identity: `schema_version`, `skill_version`, input hash, generated-at timestamp, and model identity when available;
- a concise list of included deliverables (`A-xxx`); and
- an explicit boundary statement that the package remains provisional and subject to human and professional review.

Do not manufacture a project identifier, model identity, input hash, timestamp, or delivery status. If a value is unavailable, state that it is unavailable and identify the action needed to obtain it.

## 2. Evidence, unknowns, and assumptions

Provide a compact evidence and uncertainty ledger that:

- groups relevant `E-xxx` records by their existing labels: `PROVIDED`, `VERIFIED`, `INFERRED`, `ASSUMED`, and `PROPOSED`;
- connects each summarized claim to its `SRC-xxx`, inference basis, proposal basis, or validation action as applicable;
- highlights conflicts, unresolved evidence, and information that could change an option assessment or decision; and
- names the responsible owner and validation action for every `ASSUMED` record.

`ASSUMED` Evidence Records are the sole machine-readable authority for assumptions. Do **not** create a free-text `assumptions` field or array in the state package. An assumption is a missing-information record and a validation plan, not an observed, measured, confirmed, or quantified fact.

## 3. Brief and site/context summary

Summarize the brief and site/context ledger as traceable architectural inputs:

- project objectives, users, requested deliverables, and programme priorities;
- source-described site observations, context, access, orientation, and documented restrictions;
- candidate or confirmed constraints, including their `C-xxx` status and supporting `E-xxx`; and
- missing site information that prevents a stronger claim.

Keep observation separate from interpretation. A site statement supplied by the brief is `PROVIDED`; an authority-confirmed statement is `VERIFIED`; an interpretation is `INFERRED`; an unresolved gap is `ASSUMED` or missing information. Do not introduce unsupported climate, survey, regulatory, access, or setback facts.

## 4. Program, area, adjacency, zoning, and circulation

Present the program-and-area ledger using existing `S-xxx`, `R-xxx`, and `C-xxx` identifiers:

- required spaces and their area values and units;
- adjacency priorities, zoning intent, and circulation relationships;
- the latest deterministic area-schedule result, when available; and
- any candidate constraints or missing information that affect spatial organization.

Area totals and grossing results must cite the output of `check_area_schedule.py`; they are comparison inputs, not proof that an option is compliant, buildable, or selected. Do not add an `area_schedule`, `zoning`, or `circulation` field to the state package when [output.schema.json](output.schema.json) has no such field. Explain those items in the human-readable package and map only their existing entities to `spaces[]`, `relations[]`, and `constraints[]`.

## 5. Grid, structure, core, and height hypotheses

Present each `H-xxx` as a revisable architectural hypothesis, with its supporting `E-xxx` records and required verification action. Explain possible programme, circulation, environmental, or spatial consequences without presenting a hypothesis as a construction-ready structural solution.

Do not provide load calculations, member sizes, foundations, fire-capacity conclusions, accessibility compliance, cost conclusions, regulatory approval, final massing selection, or a quantified value supported only by `ASSUMED` evidence. If only missing-information evidence exists, record the risk and next validation action; do not substitute a numeric value.

## 6. Precedent spatial operations and concept directions

For every concept direction, present:

- `O-xxx`, name, and spatial operation;
- the substantive differentiation axes and the spatial consequences of the operation;
- its supporting `E-xxx` records and relevant upstream `C-xxx`, `H-xxx`, `S-xxx`, or `R-xxx` context; and
- a falsifiability or failure condition that indicates when the direction must be reconsidered.

Precedent material is optional input, not a normative answer. Use only user-provided or registered sources. Do not create real case cards, claim that a built-in case corpus has been searched, or package copyrighted text, images, or drawings.

## 7. Comparison and assessment

Present a human-readable comparison matrix derived from existing `K-xxx` criteria and `options[].assessments[]` records. For each option, show:

- strengths, risks, and trade-offs;
- evidence IDs and rationale behind each assessment;
- missing information and `ASSUMED` records that could change the comparison; and
- relevant deterministic area-check results where an area criterion exists.

Assessment ratings (`strong`, `adequate`, `weak`, `not_applicable`) support architectural discussion; they are not numeric weights, aggregate scores, rankings, recommendations, or an automatic selection. `not_applicable` must include its reason and must not conceal a weak option.

## 8. Human decision request

End the comparison with a visible stop point for the human designer. State the alternatives, trade-offs, unresolved information, and the permitted response types: `select`, `revise`, `request-new`, or `defer`.

Create a `D-xxx` record only after an explicit human response. Before that response, present a pending decision request only; do not pre-fill `decided_by`, a chosen option, a recommendation disguised as a decision, or a placeholder Decision in the state package. A confirmed Decision must use exactly the existing [output.schema.json](output.schema.json) decision fields and include a real human `decided_by` value.

## 9. Dependencies and stale-propagation handoff

Present existing top-level `DEP-xxx` edges with their direction and rationale. State that the downstream object depends on the upstream object. Do not add embedded dependency arrays to entities.

For a possible upstream change, provide a human-readable stale-propagation request containing:

- `trigger_id`;
- `trigger_change_event`;
- `occurred_at`, supplied by the change event rather than a system clock;
- affected existing downstream object IDs, listed from declared `dependencies[]` edges; and
- an expected human-readable stale reason.

Use the existing state tool only after the upstream change is explicit:

```text
scripts/validate_state.py propagate-stale <input.json> <output.json> <trigger_id> <trigger_change_event> <occurred_at> > <new-output.json>
```

The command validates before traversal, marks every reachable declared downstream object in a new output package, and emits that package to stdout. `occurred_at` must be the supplied change-event time, never a system-clock value. Do not overwrite the validated source package, add embedded dependency arrays, or infer an undeclared dependency.

## 10. Deliverable register

List each package artifact as an `A-xxx` Deliverable with its existing `type`, concise description, current availability, and human review need. The register must make clear whether an item is present, provisional, awaiting human decision, or awaiting validation.

The machine-readable counterpart is `deliverables[]`. Do not invent an `A-xxx`, mark an absent artifact as delivered, or make a Deliverable stand in for a human decision.

## 11. Next actions and professional boundaries

Separate the next actions into:

1. user-provided missing information;
2. human design decisions;
3. site, consultant, authority, or other professional verification; and
4. later project work.

Clearly identify work that remains outside this package, including real case-card curation, local case filtering, Rubric design, fixed/regression/forward evaluations, packaging, and release. Do not state that later work is complete, and do not create a Web application, database, API, or online service.

## 12. Machine-readable package mapping and alignment

Map the human-readable package to existing Schema fields only:

| Human-readable package content | Existing `output.schema.json` field | Alignment rule |
| --- | --- | --- |
| Identity and provenance | `schema_version`, `skill_version`, `project_id`, `state` | Preserve the validated input hash and generated-at value; model is optional only where the Schema permits it. |
| Source and evidence ledger | `sources[]`, `evidence[]` | Use `SRC-xxx` and `E-xxx`; labels remain on Evidence Records. |
| Candidate or confirmed limits | `constraints[]` | Preserve `C-xxx`, status, and E-only `evidence_ids`. |
| Programme, area, and adjacency | `spaces[]`, `relations[]` | Keep space area as `value` plus `unit`; present area totals as narrative/script results only. |
| Structural and height hypotheses | `hypotheses[]` | Preserve `H-xxx`, description, and E-only `evidence_ids`. |
| Concept directions | `options[]` | Preserve O-xxx spatial operation, differentiation axes, and E-only `evidence_ids`. |
| Comparison assessments | `criteria[]`, `options[].assessments[]` | Keep assessments on options; use ratings and evidence IDs without scores or ranking. |
| Confirmed human decision | `decisions[]` | Write only after explicit human response and a real human `decided_by`. |
| Dependency model | `dependencies[]` | Keep one top-level source of directed `DEP-xxx` edges. |
| Package artifacts | `deliverables[]` | One `A-xxx` record per actual deliverable. |

The following are **human-readable narrative only** and must not be added as new JSON fields: explanatory prose, layout order, comparison commentary, unresolved-question wording, professional-review notices, and stale-propagation requests. In particular, do not add free-text `assumptions`, scores, rankings, recommendations, case-library search results, or implementation metadata that the Schema does not define.

## Assembly check and stop boundary

Before delivering, check that:

- all twelve package sections are present or explicitly marked unavailable with a next action;
- every cited `E-xxx`, `SRC-xxx`, `C-xxx`, `S-xxx`, `R-xxx`, `H-xxx`, `O-xxx`, `K-xxx`, `D-xxx`, `DEP-xxx`, and `A-xxx` resolves in the relevant state package or is visibly a pending template rather than a record;
- narrative claims and the machine-readable package agree;
- all assumptions, conflicts, missing information, human choices, and professional boundaries are visible; and
- the state package is validated separately against [output.schema.json](output.schema.json).

Run `../scripts/validate_state.py validate <input.json> <output.json>` before delivery. The read-only `validate` mode checks the JSON Schemas plus ADR-0001 semantic requirements: stable-ID uniqueness, cross-object references, input hash, allowed dependency pairs, dependency cycles, existing stale metadata, and input-output consistency. It emits machine-readable JSON and never modifies either file. For an explicit upstream change, use the separate `propagate-stale` mode described in Section 9, then validate its new output package before delivery.

When stale propagation is needed, use only the `propagate-stale` mode described in Section 9; do not recreate its traversal or stale-writing logic in package assembly.

Stop after assembling the two aligned artifacts and making the human decision request. Do not implement case-card curation, local filtering, Rubric work, fixed or forward evaluations, packaging, or release work in this reference. Those are separate later tasks.
