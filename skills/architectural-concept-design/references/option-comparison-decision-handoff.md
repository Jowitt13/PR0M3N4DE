# Option comparison, human decision, dependency, and stale-propagation handoff

> **Single authoritative source** for comparison criteria (K-xxx), option assessment, comparison-matrix presentation, human-design-decision request (D-xxx), dependency-edge modelling (DEP-xxx), and stale-propagation handoff within Phase 3. This reference does not implement `propagate-stale` or `validate_state.py` — it models the human-readable handoff for a subsequent Phase 4 automation task. This is Phase 3 segment 6; it does not complete Phase 3 or Phase 4.

## Contents

- [Prerequisites and upstream-authority boundary](#prerequisites-and-upstream-authority-boundary)
- [K-xxx comparison criteria](#k-xxx-comparison-criteria)
- [O-xxx assessments](#o-xxx-assessments)
- [Comparison matrix and quantitative-verification gates](#comparison-matrix-and-quantitative-verification-gates)
- [Human decision request and D-xxx](#human-decision-request-and-d-xxx)
- [DEP-xxx dependency modelling](#dep-xxx-dependency-modelling)
- [Stale-propagation handoff](#stale-propagation-handoff)
- [Output mapping](#output-mapping)
- [Human-readable ledger](#human-readable-ledger)
- [Stop boundary](#stop-boundary)

---

## Prerequisites and upstream-authority boundary

### Upstream ledger dependencies

This reference must only be used after all upstream ledgers and concept-direction generation are complete:

1. A completed **brief ledger** produced by [brief-analysis.md](brief-analysis.md).
2. A completed **site ledger** produced by [site-context-analysis.md](site-context-analysis.md).
3. A completed **program-and-area ledger** produced by [program-area-and-circulation.md](program-area-and-circulation.md).
4. A completed **grid/core/height ledger** produced by [grid-core-height-hypotheses.md](grid-core-height-hypotheses.md).
5. A completed **precedent-and-concept ledger** produced by [concept-options-and-decisions.md](concept-options-and-decisions.md), including exactly two or three concept directions (O-xxx) with substantive differentiation.

### Inherited data

Use only the following from the upstream ledgers — do not redefine them:

| Data | Source | Description |
| --- | --- | --- |
| Concept options (O-xxx) | precedent-and-concept ledger / `options[]` | Exactly 2–3 substantively different concept directions |
| Evidence (E-xxx) | all five ledgers | PROVIDED, VERIFIED, INFERRED, ASSUMED, PROPOSED records |
| Constraints (C-xxx) | input/output state | Design constraints with evidence IDs and status |
| Hypotheses (H-xxx) | grid/core/height ledger | Structural and height hypotheses |
| Spaces (S-xxx) | program-and-area ledger | Space IDs, names, areas |
| Relations (R-xxx) | program-and-area ledger | Adjacency relations |

### Authority boundary

- All five upstream ledgers are the sole authorities for their respective facts.
- This reference must not reclassify, re-source, or upgrade any upstream fact.
- This reference must not generate new evidence labels beyond the existing five.
- New criteria, assessments, decisions, and dependencies must reference only existing evidence IDs.
- This reference must not write `stale` JSON metadata on any object.
- Do not present ASSUMED or PROPOSED records as facts.
- Do not re-read the brief or upstream ledgers to fill gaps.

---

## K-xxx comparison criteria

### ID allocation

Before creating any criterion, scan the entire state package `criteria[]` array and allocate the **next unused K-xxx** identifier. Each K-xxx must be globally unique and must not reuse any K-xxx from any prior ledger or generation.

### Field requirements

Every criterion must have:

| Field | Required | Description |
| --- | --- | --- |
| `id` | Yes | Globally unique K-xxx identifier matching `^K-[0-9]{3,}$` |
| `name` | Yes | Clear, concise name describing the comparison dimension |
| `description` | Yes | Precise description of what the criterion evaluates and how it relates to the design brief. Must reference registered goals, constraints, site conditions, functional requirements, or structural/height hypotheses. |
| `evidence_ids` | Yes | Array of E-xxx identifiers supporting this criterion. **Only E-xxx IDs are permitted** — C-xxx, R-xxx, H-xxx, S-xxx, or any other non-E identifiers must NOT appear in this array. Non-E identifiers may appear in human-readable `Derived from` / `Context` prose only. Must resolve to existing evidence records. |

### Derivation rules

- Each criterion must be derived from at least one of: registered project goals (from the brief ledger), confirmed constraints (C-xxx with status `confirmed`), site evidence (PROVIDED or VERIFIED), functional requirements (from the program-and-area ledger), or structural/height hypotheses (H-xxx).
- **Machine-readable `evidence_ids` must contain only E-xxx identifiers.** When a criterion is based on a constraint (C-xxx), hypothesis (H-xxx), space (S-xxx), or relation (R-xxx), the `evidence_ids` array must reference the supporting E-xxx evidence records that underpin those C/R/H/S objects — not the C/R/H/S IDs themselves.
- C-xxx, R-xxx, H-xxx, and S-xxx identifiers may appear in human-readable `Derived from` / `Context` prose, but must never enter the machine-readable `evidence_ids` array.
- Criteria must be architectural — they must evaluate spatial, functional, environmental, or structural qualities.
- Criteria must **not** be based on:
  - Aesthetic slogans, style preferences, material colour, or façade language.
  - Unverified regulations, fabricated code clauses, or assumed legal requirements.
  - Weighted scores, numeric formulas, or automatic ranking algorithms.
  - A claim that any single option is "the only correct answer".
- Criteria must be specific enough that a reasonable architect could independently assess an option against them.

### Prohibited operations

Do **not**:

- Assign numeric weights to criteria.
- Sum, average, or aggregate ratings across criteria.
- Auto-rank, auto-score, or auto-select an option.
- Claim that a criterion "obviously" favours one option.
- Fabricate regulatory, code, or compliance criteria.
- Use aesthetic preference as a criterion.

---

## O-xxx assessments

### Assessment format

Each Concept Option (O-xxx) may carry zero or more assessments in its `assessments[]` array. Every assessment maps one O-xxx against one K-xxx:

```json
{
  "criterion_id": "K-001",
  "rating": "strong" | "adequate" | "weak" | "not_applicable",
  "rationale": "Free-text architectural reasoning",
  "evidence_ids": ["E-005"]
}
```

### Rating definitions

| Rating | Meaning |
| --- | --- |
| `strong` | The option addresses this criterion particularly well, with evidence to support the claim. |
| `adequate` | The option satisfies the criterion; no significant deficiency. |
| `weak` | The option has a known deficiency against this criterion. |
| `not_applicable` | The criterion does not apply to this option. Must explain **why** it does not apply. Must not be used to evade comparison. |

### Assessment rules

- Every option must be assessed against every applicable criterion. Missing assessments are not permitted.
- Each assessment must include `rationale` — free-text architectural reasoning that explains the rating.
- Each assessment must include `evidence_ids` — at least one evidence ID supporting the rating.
- `not_applicable` must state the reason the criterion does not apply. It must not be used to avoid comparing a weak option.
- Assessments must not sum, weight, or aggregate ratings across criteria.
- Assessments must not auto-generate a "winner" or recommendation.

### Assessment evidence

- `rationale` may reference spatial operations, differentiation axes, site conditions, constraint compliance, hypothesis implications, or program requirements.
- `evidence_ids` must reference existing E-xxx records from the state package. **Only E-xxx IDs are permitted** — same rule as criteria `evidence_ids`: C-xxx, R-xxx, H-xxx, S-xxx must not appear in this array.
- Do not create new evidence records solely to support an assessment rating. If existing evidence is insufficient, flag missing information rather than fabricate.

---

## Comparison matrix and quantitative-verification gates

### Comparison matrix

Present the comparison as a human-readable matrix:

| Criterion | O-xxx (name) | O-xxx (name) | O-xxx (name, if three exist) |
| --- | --- | --- | --- |
| K-001 (name) | rating + rationale | rating + rationale | rating + rationale |
| K-002 (name) | rating + rationale | rating + rationale | rating + rationale |

### Content requirements

The matrix must include:

1. **Evidence column**: For each criterion, list the key evidence IDs that support it.
2. **Strengths summary**: For each option, list the criteria where it rates `strong`.
3. **Risks summary**: For each option, list the criteria where it rates `weak` or `not_applicable`.
4. **Missing information**: List evidence gaps that affect the comparison — what is not yet known and how it could change the assessment.
5. **Verification conditions**: List any assumptions (ASSUMED records) that must be validated before a decision is final.

### Assessment record mapping

The **Assessment matrix** is for human readability. A separate **Assessment record mapping** provides the precise mapping to `options[].assessments[]` per output.schema.json:

| option_id | criterion_id | rating | rationale | evidence_ids | contextual_ids |
|---|---|---|---|---|---|
| O-001 | K-001 | strong/adequate/weak/not_applicable | architectural reasoning | [E-xxx, ...] | [C-xxx, R-xxx, H-xxx, ...] |

- **evidence_ids**: Non-empty; only E-xxx; must resolve to registered evidence records.
- **contextual_ids**: Optional; C-xxx, R-xxx, H-xxx for human traceability. Must NOT appear in `evidence_ids`.
- Two options × three criteria must produce exactly 6 assessment mappings.
- This table is the authoritative source for constructing `options[].assessments[]`; the human-readable matrix in the ledger is derived from it for presentation.

### Quantitative gates

When a criterion involves area, count, or numeric comparison:

- Use only [check_area_schedule.py](../scripts/check_area_schedule.py) for area totals — do not hand-calculate.
- Script results are comparison inputs only. They do not auto-conclude any option.
- When an area threshold is stated in a constraint (C-xxx), present the script result alongside the constraint value.
- Do not convert numeric comparison into automatic "pass" or "fail".

### Prohibitions

Do **not**:

- Produce a weighted scorecard, radar chart, or numeric ranking.
- Auto-select or auto-recommend an option.
- Claim one option is "best" or "superior".
- Hide weak assessments by marking them `not_applicable`.
- Use the matrix to imply a foregone conclusion.

---

## Human decision request and D-xxx

### Decision-request boundary

The agent must present a clear, structured **human decision request** with:

- A summary of the comparison matrix.
- The key trade-offs between options.
- Any missing information that could change the assessment.
- A stop point where the human must explicitly respond.

The agent must **not**:

- Generate a D-xxx decision autonomously.
- Fill `decided_by` with "AI", "Codex", "DeepSeek", "Agent", or any non-human identity.
- Pretend the human has chosen when no explicit human response has been given.

### D-xxx creation protocol

A D-xxx decision is written **only** after the human explicitly states one of:

- `select` — "I choose O-xxx"
- `revise` — "Revise O-xxx with this change"
- `request-new` — "Give me another option that differs in these axes"
- `defer` — "I'll decide later when this condition is met"

Before allocating a D-xxx, scan the entire state package `decisions[]` array and allocate the next unused D-xxx.

### Decision fields by type

All D-xxx carry `id`, `decision_type`, `rationale`, and `decided_by`:

| Type | Additional required fields |
| --- | --- |
| `select` | `chosen_option_id` (O-xxx), `criteria_ids` (array of K-xxx) |
| `revise` | `target_option_id` (O-xxx), `revision_instructions` |
| `request-new` | `requested_differentiation_axes`, `reason` |
| `defer` | `defer_reason`, `revisit_trigger` |

The field contracts are defined by [output.schema.json](output.schema.json) and enforced by JSON Schema. This reference must not add, remove, or alter any decision field.

### decided_by requirement

`decided_by` must contain a **real human identity** — a name, GitHub handle, or role designation that identifies a person. It must never be "AI", "Agent", "Codex", "DeepSeek", "Qoder", "System", "Auto", or any synthetic identity.

### Decision authority

- The human designer is the sole decision-maker. The agent presents options and comparisons; it does not select.
- A single D-xxx records one design decision. Multiple decisions require multiple D-xxx records.
- Once a decision is written, downstream dependencies that reference the affected entities are subject to stale propagation (see [Stale-propagation handoff](#stale-propagation-handoff)).

---

## DEP-xxx dependency modelling

### ID allocation

Before creating any dependency, scan the existing `dependencies[]` array and allocate the next unused DEP-xxx.

### Dependency format

Every dependency in `dependencies[]` follows:

```json
{
  "id": "DEP-001",
  "upstream_id": "C-003",
  "downstream_id": "O-001",
  "rationale": "Option O-001 massing depends on height constraint C-003"
}
```

Semantics: `downstream_id` depends on `upstream_id`. When the upstream changes, the downstream should be marked stale.

### Allowed upstream/downstream pairs

Only the following pairs are permitted, per ADR-0001 §9:

| Upstream type | Downstream type |
| --- | --- |
| Constraint (C-xxx) | Option (O-xxx), Decision (D-xxx), Hypothesis (H-xxx) |
| Space (S-xxx) | Option (O-xxx), Relation (R-xxx) |
| Hypothesis (H-xxx) | Option (O-xxx), Decision (D-xxx) |
| Evidence Record (E-xxx) | Constraint (C-xxx), Hypothesis (H-xxx), Option (O-xxx), Decision (D-xxx) |
| Option (O-xxx) | Decision (D-xxx) |
| Criterion (K-xxx) | Decision (D-xxx) |
| Decision (D-xxx) | Deliverable (A-xxx) |

### Explicitly disallowed

The direction **Decision → Option**, **Decision → Hypothesis**, and **Decision → Criterion** is disallowed. A decision depends on the option, hypothesis, and criterion it references — not the reverse.

### Dependency creation rules

- Each DEP-xxx must carry `rationale` explaining why the dependency exists.
- Dependencies must reflect actual architectural relationships — not generic "everything depends on everything".
- Dependencies are written to the top-level `dependencies[]` array only. No embedded `depends_on` or per-entity dependency arrays are permitted.
- Do not create duplicate dependencies. Before writing, verify the pair `(upstream_id, downstream_id)` does not already exist.

### D-xxx dependency timing rule

**Dependencies whose upstream or downstream is a D-xxx (Decision) must NOT be written before the human decision exists.**

- O/K/H/C/E → D dependencies are allowed per the pair table, but only after the human has explicitly responded and a D-xxx record has been created.
- While the decision is pending ("Awaiting explicit human response"), the `dependencies[]` array must contain only dependencies between existing entities (e.g. C-xxx → O-xxx, H-xxx → O-xxx).
- Never write a dependency edge whose downstream or upstream references a `<placeholder>` Decision ID that does not yet exist in the state package.
- Template (for use AFTER human confirmation):

```
### DEP-xxx: <downstream> depends on <upstream>
- **Rationale**: ...
- **Note**: This dependency is only valid after D-xxx is confirmed by human response.
```

### Decision and Dependency evidence-ids boundary

**Decision (D-xxx) and Dependency (DEP-xxx) objects do NOT carry `evidence_ids` in the current Schema.** This reference must not add `evidence_ids` to either object type.

- D-xxx `rationale` may reference existing object IDs (C-xxx, E-xxx, H-xxx, K-xxx, O-xxx) and evidence context in human-readable prose.
- DEP-xxx `rationale` may reference existing object IDs and evidence context in human-readable prose.
- Do not introduce machine-readable `evidence_ids` arrays on D-xxx or DEP-xxx — this is a Schema change requiring an ADR.

---

## Stale-propagation handoff

### What this reference does

This reference models the **human-readable stale-propagation handoff** — it identifies which downstream objects would become stale when a specific upstream entity changes. It does **not** implement the propagation mechanism.

### What this reference does NOT do

This reference must **not**:

- Write `stale` JSON metadata on any object.
- Traverse the dependency graph algorithmically.
- Read or use the system clock.
- Implement `scripts/validate_state.py` or `propagate-stale` mode.
- Implement any new deterministic script.

### Stale-propagation request format

For each identified stale-propagation scenario, produce a human-readable request in the ledger with all three explicit inputs required by ADR-0001 §10:

```text
**Stale-propagation request: <description>**

- trigger_id: <C-003 / H-001 / etc.>
- trigger_change_event: ARCH-xxx:decision-confirmed:<commit>
- occurred_at: <ISO 8601 timestamp of the change event, not system clock>

Affected downstream (根据已声明 dependencies[] 边列出预期受影响对象；本模块不执行算法遍历):
- <existing downstream object ID>: rationale

Expected stale reason: <human-readable reason text, not JSON>
```

### Handoff contract

These requests are the input contract for a future Phase 4 `propagate-stale` implementation. The implementation will:

1. Receive `trigger_id`, `trigger_change_event`, `occurred_at`.
2. Traverse `dependencies[]` from `trigger_id` downstream.
3. Write `stale` metadata on every reachable object.
4. Output a new state package or JSON Patch.

This reference produces the human-readable request. The Phase 4 script performs the actual traversal and writing. The handoff is complete when the ledger contains at least one stale-propagation request per decision or constraint change that triggers downstream invalidation.

---

## Output mapping

### Mapping to output.schema.json

All outputs of this reference map to existing fields in [output.schema.json](output.schema.json):

| This reference | output.schema.json field | Notes |
| --- | --- | --- |
| Criteria (K-xxx) | `criteria[]` | Each criterion as a top-level array item |
| Assessments | `options[].assessments[]` | Live on the option, not on the criterion |
| Decisions (D-xxx) | `decisions[]` | Each decision as a top-level array item |
| Dependencies (DEP-xxx) | `dependencies[]` | Each dependency as a top-level array item |

### What must not be written to JSON

This reference must not write to JSON:

- K-xxx description prose beyond the existing `description` field.
- Any scoring, weighting, ranking, or selection metadata.
- `stale` JSON metadata on any object.
- New JSON fields not defined in output.schema.json.
- Modifications to upstream `options[]` fields (`spatial_operation`, `differentiation_axes`, `evidence_ids` — these belong to [concept-options-and-decisions.md](concept-options-and-decisions.md)).

### Existing schema fields used

| Schema field | Write permission | Authority |
| --- | --- | --- |
| `criteria[].id` | Write | This reference |
| `criteria[].name` | Write | This reference |
| `criteria[].description` | Write | This reference (now mandatory) |
| `criteria[].evidence_ids` | Write | This reference |
| `options[].assessments[].criterion_id` | Write | This reference |
| `options[].assessments[].rating` | Write | This reference (enum: `strong`/`adequate`/`weak`/`not_applicable`) |
| `options[].assessments[].rationale` | Write | This reference |
| `options[].assessments[].evidence_ids` | Write | This reference |
| `decisions[]` (all fields) | Write | This reference (human-confirmed only) |
| `dependencies[]` (all fields) | Write | This reference |

---

## Human-readable ledger

Produce a human-readable ledger with the following structure:

```markdown
# Option Comparison, Decision, and Stale-Propagation Handoff: [project name]

## 1. Comparison criteria (K-xxx)

### K-xxx: [name]
- Description: ...
- Derived from: [goals, constraints, site evidence, functional requirements, hypotheses]
- Evidence trace: [E-xxx, E-xxx, ...]

## 2. Assessment matrix

| Criterion | O-xxx (name) | O-xxx (name) | [O-xxx (name)] |
| --- | --- | --- | --- |
| K-001 | strong/adequate/weak/not_applicable — rationale | ... | ... |

## 3. Evidence and risk summary

### O-xxx strengths
- Criteria rated strong: ...
- Key evidence: ...

### O-xxx risks
- Criteria rated weak/not_applicable: ...
- Missing information: ...

### Cross-cutting concerns
- Assumptions requiring validation before decision: ...
- Information gaps: ...

## 4. Quantitative verification

[When area or count criteria exist, present check_area_schedule.py results]

## 5. Human decision request (D-xxx)

**Decision required**: [select / revise / request-new / defer]

- Options considered: [O-xxx, O-xxx]
- Key trade-offs: ...
- Recommendation: NONE — the human designer selects.

**Awaiting explicit human response.**

[After human response, record:]
### D-xxx: [decision_type]
- decided_by: [human identity]
- [type-specific fields]

## 6. Dependency model (DEP-xxx)

### DEP-xxx: downstream_id depends on upstream_id
- Rationale: ...

## 7. Stale-propagation handoff

**Stale-propagation request: <description>**

- trigger_id: <C-xxx / H-xxx / O-xxx>
- trigger_change_event: ARCH-xxx:decision-confirmed:<commit>
- occurred_at: <ISO 8601>

Affected downstream:
- <existing downstream object ID>: rationale (D-xxx only when confirmed by human and present in decisions[])

Expected stale reason: <human-readable text>

## 8. Missing information and next steps
```

---

## Stop boundary

When the comparison matrix, human decision request, dependency model, and stale-propagation handoff are complete — criteria defined and assessed, matrix presented, decision requested, dependencies established, and stale requests documented — **stop**. This is Phase 3 segment 6; it does not complete Phase 3 or Phase 4. Do not continue into:

- Implementing `scripts/validate_state.py` or `propagate-stale` mode.
- Creating a real case database, card library, or case-operation corpus.
- Building a Web application, database, API, or online interface.
- Auto-generating Rubric, regression tests, or forward evaluations.
- Implementing any new deterministic script.
- Implementing stale graph traversal, JSON Patch generation, or system-clock usage.
- Creating real case cards, batch curation, or Phase 4 automation.
- Starting a new ARCH task.

This reference is the single authoritative option-comparison, decision, dependency, and stale-handoff framework for Phase 3 segment 6. It models the architectural reasoning; it does not implement the automation.

---

**Tasks explicitly reserved for Phase 4:**

| Reserved task | Description |
| --- | --- |
| `validate_state.py` validate mode | Schema conformance, ID uniqueness, cross-ref integrity, hash verification, dependency-pair validation, existing stale-metadata integrity |
| `validate_state.py` propagate-stale mode | Dependency-graph traversal from trigger_id, per-object stale metadata writing, new state package or JSON Patch output |
| Real case card curation | Human-curated case-operation cards with provenance_class, traceability, and license status |
| Local filter logic | Label-based filtering/browsing of the controlled case corpus |
| Rubric and regression evaluations | Fixed evaluation set, regression cases, forward evaluations |
| Fixture migration | Update fixtures and expected invariants for Phase 4 automation |
