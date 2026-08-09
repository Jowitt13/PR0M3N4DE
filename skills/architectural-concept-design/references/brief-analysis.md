# Brief Analysis: intake, evidence labeling, and missing-information identification

This reference covers the first segment of Phase 3 (Architectural Chain): receiving a raw design brief or attachment summary, building a traceable brief ledger, classifying every claim with an evidence label, surfacing conflicts and missing information, and asking at most three high-impact questions before anything else.

## Scope and prohibitions

### Required inputs

- One or more raw brief texts, attachment summaries, or stakeholder statements.
- Every input piece MUST be registered as a Source before any claim is classified.

### What this reference does

- Guides the agent through receiving, registering, and labeling brief statements.
- Defines the mandatory sections of a brief ledger.
- Enforces the three-question limit for missing information.
- Specifies the ASSUMED Evidence Record contract when proceeding without answers.
- Provides a mapping from the ledger into input.schema.json.

### Prohibitions

- **No regulatory conclusions.** Never claim compliance, calculate fire ratings, or derive code-mandated dimensions.
- **No site analysis, area calculation, function/adjacency/flow/structural-grid/concept generation, option comparison, or stale propagation.** Those belong to later Phase 3 segments.
- **No VERIFIED without source_id, claim_type, verification_status, and verified_at. For regulatory claims, also require jurisdiction, edition, and clause.**
- **No ingestion of real user briefs, client names, addresses, contacts, or private documents into the repository.** All fixtures must be anonymous.
- **Do not generate a concept option, proposal, or design move.** This is intake only.

## Receiving a brief

### Source registration

For each piece of input (original brief, attachment summary, email excerpt, meeting notes):

```text
Source: SRC-xxx
  locator: file name, URL, or oral summary description
  retrieved_at: RFC3339 date-time with timezone (e.g. 2026-07-12T08:00:00Z or 2026-07-12T16:00:00+08:00); date-only or offset-less timestamps are not accepted
```

Multiple sources are allowed. `scope` (what this source covers) is a human-readable ledger annotation only; it is NOT a field in `sources[]` JSON. Source JSON contains only `id`, `locator`, and `retrieved_at`.

Evidence claims link to sources by label:
- PROVIDED: must have `source_id`.
- VERIFIED: must have `source_id`, `claim_type`, `verification_status`, and `verified_at` (RFC3339 date-time with timezone).
- INFERRED: must have `inference_basis` and `inference_rule`; `source_id` is NOT required.
- ASSUMED: must have `missing_information`, `impact`, `owner`, `validation_action`; `source_id` is NOT required.
- PROPOSED: not generated during intake; when generated later, must have `proposal_rationale` and either `basis_evidence_ids` or `basis_absent_reason`.

### Initial classification

Statements taken verbatim or paraphrased from the source:

- **Direct statements → PROVIDED.** Quote or paraphrase. Must include `source_id`.
- **Publicly verifiable fact with recorded retrieval → VERIFIED.** Must include `source_id`, `claim_type`, `verification_status`, and `verified_at` (RFC3339 date-time with timezone; date-only or offset-less timestamps are not accepted). For regulatory claims (`claim_type` = `"regulatory"`), must additionally include `jurisdiction`, `edition`, and `clause`. When `clause` is `null`, `clause_not_applicable_reason` is required. The string `"N/A"` is never accepted as a `clause` value. This is a Schema field contract — do not derive regulatory compliance conclusions from it.
- **Reasoned conclusion from existing evidence → INFERRED.** Must state `inference_basis` (array of evidence IDs) and `inference_rule` (the reasoning). `source_id` is NOT required.
- **Working assumption because information is missing → ASSUMED.** Must state `missing_information`, `impact`, `owner`, and `validation_action`. `source_id` is NOT required.
- **Design suggestion → PROPOSED.** Not used in the intake segment; reserved for later stages. When used later, requires `proposal_rationale` and either `basis_evidence_ids` (one or more evidence IDs) or `basis_absent_reason` (why no prior evidence exists).

Never silently promote an INFERRED or ASSUMED claim to PROVIDED or VERIFIED. Changing a label requires recording the reason.

## Brief ledger sections

Produce a ledger with these fixed sections. Omitted sections where no data exists are acceptable; do not fabricate.

### 1. Project purpose

- One-sentence purpose statement.
- Intended users and their key activities.
- Building type classification (matching input.schema.json `building_type`).
- Required deliverables and decision timeline.

### 2. Known facts

A table mapping each discrete claim to its evidence label and source:

| ID | Claim | Label | Trace / 来源或推断依据 |
| --- | --- | --- | --- |
| E-001 | ... | PROVIDED | SRC-001 |
| E-002 | ... | PROVIDED | SRC-001 |

Each entry includes a stable evidence ID (E-xxx) and a label. The trace column records the source (for PROVIDED/VERIFIED), the inference chain (for INFERRED), or the assumption context (for ASSUMED).

### 3. Hard constraints

Requirements the design cannot violate. Each constraint maps to `constraints[]` in input.schema.json and requires four fields:

- `id`: stable C-xxx ID.
- `description`: constraint text.
- `evidence_ids`: at least one E-xxx evidence ID.
- `status`: must be `candidate` in the intake segment (never `confirmed` without human action).

### 4. Soft goals

Desirable but not mandatory outcomes. Document as text with evidence references. Do not assign constraint IDs.

### 5. Conflicts and inconsistencies

Explicit contradictions between sources or statements. Record:

- The conflicting claims.
- Their sources.
- Whether resolution is possible without external input.

### 6. Missing information

| ID | Missing Item | Design Impact | Priority |
| --- | --- | --- | --- |
| M-001 | ... | ... | High / Medium / Low |

Only items marked **High** are eligible for a direct question. Other items remain in the ledger for the designer to address at their discretion.

### 7. Assumed entries

Complete ASSUMED Evidence Records, one per missing item that the agent cannot resolve and for which work must proceed:

```text
Evidence: E-xxx
  label: ASSUMED
  claim: <the working assumption>
  missing_information: <what is unknown>
  impact: <what design decision this affects>
  owner: <who must provide or validate this information>
  validation_action: <concrete step to resolve before the assumption hardens>
```

Do not add more ASSUMED entries than High-priority missing items. If more than three High items exist, flag the excess for the designer.

### 8. Next actions

A numbered list. The first three are the high-impact questions (if any). Remaining items are ledger-level next steps (e.g., "confirm jurisdiction before site analysis").

## Missing-information protocol

### Three-question limit

Ask at most **three** questions that would change a major design decision. Examples of high-impact questions:

- "What is the maximum allowable building height?" (changes massing strategy)
- "Does the site include protected heritage features?" (changes site strategy)
- "Is the building serving a single owner or multiple tenants?" (changes organization)

Questions about finish materials, furniture count, or non-structural detailing are not high-impact for pre-design.

### Proceeding without answers

When a High-priority item cannot be resolved:

1. Create a complete ASSUMED Evidence Record with all four resolution fields.
2. Record the assumption in the ledger's Assumed entries section.
3. Proceed with the assumption as a clearly labeled temporary premise.
4. Never present the assumption as fact, and never label it VERIFIED or PROVIDED.

### Escalation

If more than three High-priority missing items exist and no answer is available, flag them in the ledger and present them to the human designer for prioritization. Do not silently pick three.

## Output format

### Human-readable ledger

A Markdown document with the eight sections above. A template:

```markdown
# Brief Ledger: [project name]

## 1. Project purpose
...

## 2. Known facts
...

## 3. Hard constraints
...

## 4. Soft goals
...

## 5. Conflicts and inconsistencies
...

## 6. Missing information
...

## 7. Assumed entries
...

## 8. Next actions
1. [Question 1]
2. [Question 2]
3. [Question 3]
4. ...
```

### Structured input mapping

The ledger maps to input.schema.json as follows. This table is precise and executable: every row states exactly what may be written into JSON and what must not be written.

| Ledger content | Legal structured destination | Prohibitions |
| --- | --- | --- |
| Project identity (id, name) | `project.id`, `project.name` | — |
| Building type, jurisdiction, deliverables | `project.building_type`, `project.jurisdiction`, `project.requested_deliverables` | Do not write `project.purpose`, `project.users`, or any field not in the Schema |
| Project purpose, users, activities, decision timeline | Human-readable ledger text OR an Evidence Record with the correct label | Do not add new `project` fields |
| Source registration | `sources[].id`, `sources[].locator`, `sources[].retrieved_at` | Do not write `sources[].scope` |
| PROVIDED facts | `evidence[]` with `source_id` | — |
| VERIFIED facts | `evidence[]` with `source_id`, `claim_type`, `verification_status`, `verified_at` (RFC3339 date-time with timezone); regulatory → additionally `jurisdiction`, `edition`, `clause`; `clause` is `null` → require `clause_not_applicable_reason` | Never write `"N/A"` for `clause`; do not fabricate VERIFIED claims or use non-existent `verification_scope`; Schema contract only — not a compliance conclusion |
| INFERRED conclusions | `evidence[]` with `inference_basis`, `inference_rule` | Do not require `source_id` |
| ASSUMED working assumptions | `evidence[]` with `missing_information`, `impact`, `owner`, `validation_action` | Do not require `source_id` |
| Raw site statements | Evidence Record only | Do not create a `site` JSON property; `input.schema.json` has no `site` field |
| Hard constraints | `constraints[].id`, `constraints[].description`, `constraints[].evidence_ids`, `constraints[].status` | status must be `candidate` (intake never confirms); `confirmed` only by human action; `evidence_ids` requires at least one E-xxx ID |

`input.schema.json` has `program` and `relations` fields that may be absent in intake; do not fabricate program spaces or adjacency relations. There is no `site` field in `input.schema.json`.

## Stop boundary

When the ledger is complete and any high-impact questions are formulated, **stop**. Do not continue into site analysis, program organization, adjacency, circulation, grid, core, height, environmental response, concept generation, option comparison, or stale propagation. Those are the responsibility of later references and segments of Phase 3.

This reference itself is not a Skill, not a workflow, and not a concept generator. It is an intake procedure only.
