# Precedent space operations, concept directions, and decision boundary

> **Single authoritative source** for precedent/precedent operation extraction, concept-direction generation, concept differentiation, and the stop boundary before comparison and decision. This reference is not a Skill, not a workflow, and not a concept generator. It is a Phase 3 segment 5 procedure anchored in ADR-0001 and the upstream ledger chain.

## Contents

- [Prerequisites and authority boundary](#prerequisites-and-authority-boundary)
- [Evidence record authority](#evidence-record-authority)
- [Precedent space operations](#precedent-space-operations)
  - [Optional input, not a blocking prerequisite](#optional-input-not-a-blocking-prerequisite)
  - [Source registration](#source-registration)
  - [Observation and extraction workflow](#observation-and-extraction-workflow)
  - [Proceeding without precedent input](#proceeding-without-precedent-input)
  - [High-impact question ceiling](#high-impact-question-ceiling)
- [Three concept directions](#three-concept-directions)
  - [Generation prerequisites](#generation-prerequisites)
  - [O-xxx concept-direction format](#o-xxx-concept-direction-format)
  - [Direction quantity](#direction-quantity)
  - [Substantive differentiation](#substantive-differentiation)
  - [Prohibited pseudo-differentiations](#prohibited-pseudo-differentiations)
- [Output mapping and boundary](#output-mapping-and-boundary)
  - [O-xxx → output.schema.json options[]](#o-xxx--outputschemajson-options)
  - [Evidence records](#evidence-records)
  - [What must not be written](#what-must-not-be-written)
- [Human-readable output and stop boundary](#human-readable-output-and-stop-boundary)
  - [Precedent and concept ledger](#precedent-and-concept-ledger)
  - [Stop boundary](#stop-boundary)

---

## Prerequisites and authority boundary

### Upstream ledger dependencies

This reference must only be used after all four upstream ledgers are complete:

1. A completed **brief ledger** produced by [brief-analysis.md](brief-analysis.md).
2. A completed **site ledger** produced by [site-context-analysis.md](site-context-analysis.md).
3. A completed **program-and-area ledger** produced by [program-area-and-circulation.md](program-area-and-circulation.md).
4. A completed **grid/core/height ledger** produced by [grid-core-height-hypotheses.md](grid-core-height-hypotheses.md).

### Inherited data

Use only the following from the upstream ledgers — do not redefine them as a second authority:

| Data | Source | Description |
| --- | --- | --- |
| Program spaces (S-xxx) | program-and-area ledger | Space IDs, names, areas |
| Relations (R-xxx) | program-and-area ledger | Adjacency relations |
| Site constraints and observations | site ledger | Boundaries, access, orientation, climate, context |
| Grid/core/height hypotheses (H-xxx) | grid/core/height ledger | Structural and height hypotheses |
| Constraints (C-xxx) | input/output state | Design constraints with evidence IDs and status |
| Evidence (E-xxx) | all four ledgers | PROVIDED, VERIFIED, INFERRED, ASSUMED records |
| Sources (SRC-xxx) | brief ledger | External source references |

### Authority boundary

- The four upstream ledgers are the sole authorities for their respective facts.
- This reference must not reclassify, re-source, or upgrade any upstream fact into a new confirmed fact.
- New interpretations may only use complete INFERRED Evidence Records with `inference_basis` and `inference_rule`.
- New design proposals may only use complete PROPOSED Evidence Records with `proposal_rationale` and exactly one of `basis_evidence_ids` or `basis_absent_reason`.
- This reference must not generate VERIFIED evidence.
- Do not present PROPOSED, INFERRED, or ASSUMED records as facts or compliance conclusions.
- Do not silently re-read the brief or upstream ledgers to fill information gaps.

---

## Evidence record authority

The complete Evidence Record field contracts are defined by [brief-and-evidence.md](brief-and-evidence.md) and [evidence.schema.json](evidence.schema.json). Those two files are the single authoritative source. This reference must not weaken, omit, or alter any contract defined there.

| Label | Minimum required fields |
| --- | --- |
| PROVIDED | `source_id` — must reference a registered source from the brief ledger. |
| VERIFIED | `source_id`, `claim_type`, `verification_status`, `verified_at`. This reference must not create VERIFIED evidence. |
| INFERRED | `inference_basis` (array of E-xxx evidence IDs) and `inference_rule`. |
| ASSUMED | All four resolution fields: `missing_information`, `impact`, `owner`, `validation_action`. |
| PROPOSED | `proposal_rationale` and exactly one of `basis_evidence_ids` (min 1 E-xxx) or `basis_absent_reason`. Both must not be provided together; neither must be absent. |

### PROPOSED one-of contract

Every PROPOSED Evidence Record created by this reference must satisfy:

- `proposal_rationale` — architectural reasoning behind the proposal.
- Exactly one of:
  - `basis_evidence_ids` — one or more evidence IDs supporting the proposal, **OR**
  - `basis_absent_reason` — why no prior evidence exists for this proposal.

Both together is invalid. Neither is invalid. This is a strict one-of contract enforced by evidence.schema.json.

---

## Precedent space operations

### Optional input, not a blocking prerequisite

Precedent/reference sources are an **optional user input**. They are not required for this segment and must not block concept-direction generation.

The repository must only contain anonymous, synthetic fixtures. It must never contain:
- real project names, addresses, or identifiable client information;
- copyrighted images, drawings, or photographs;
- lengthy protected text from published case studies or books.

### Source registration

When the user provides precedent or reference material, register each piece as a Source before recording observations:

```text
Source: SRC-xxx
  locator: URI, file path, or descriptive reference (anonymous in fixtures)
  retrieved_at: RFC3339 date-time with timezone
```

### Observation and extraction workflow

When precedent input is available, for each reference source:

1. **Register** the source as SRC-xxx.
2. **Record raw observations** as PROVIDED Evidence Records with `source_id`:
   - Spatial operation observed (e.g. "courtyard as climate moderator", "split-level entry sequence").
   - Dimensional or proportional relationships when explicitly stated in the source.
   - Environmental strategy when described in the source.
3. **Extract transferable spatial operations**, not visual style:
   - What spatial move was made?
   - Under what preconditions did it succeed?
   - What is the expected spatial or environmental effect?
   - What is the applicable boundary (building type, climate, scale)?
   - What failure condition would make this operation unsuitable?
4. **Do not extract**:
   - Visual style, colour, material palette, or façade language.
   - Formal composition, proportion systems, or aesthetic judgments.
   - The architect's name, project title, or copyrighted narrative text beyond what is needed for traceable reference.

### Proceeding without precedent input

When the user provides no precedent or reference material:

1. **Explicitly record "No precedent input provided"** in the precedent section of the ledger.
2. **Do not fabricate** sources, observations, or "precedent-inspired" claims.
3. **Do not generate** precedent-derived spatial operations.
4. **Do not block** concept-direction generation. Concept directions may be generated solely from the completed brief, site, program, and grid/core/height upstream evidence.
5. Any design direction not based on precedent must be recorded as a PROPOSED Evidence Record with the required one-of contract, and must not claim precedent derivation.

### High-impact question ceiling

If the absence of precedent input would materially change the concept directions, the agent may ask at most **one** high-impact question requesting the user to provide or confirm a reference source. This question counts against the overall three-question limit inherited from the brief intake phase.

---

## Three concept directions

### Generation prerequisites

Concept directions may only be generated when:

1. All four upstream ledgers (brief, site, program-area, grid-core-height) are complete.
2. Precedent input has been processed (or its absence explicitly recorded).
3. Sufficient traceable evidence exists to support at least three substantively different spatial strategies.

### O-xxx concept-direction format

Each concept direction carries the identifier `O-xxx` (where `xxx` is a three-or-more-digit number). Before generating directions, scan the entire state package `options[]` array and allocate the next unused O-xxx. Must not reuse upstream O IDs or existing O-xxx from prior ledger generations. Every concept direction must state:

- **O-xxx identifier** — globally unique, matching `^O-[0-9]{3,}$`.
- **Name** — a clear, descriptive name that distinguishes the spatial idea (not a poetic label or branding).
- **spatial_operation** — a drawable, measurable, and falsifiable statement of the primary spatial move. What moves? Where does it apply? Which spaces or sequences are affected?
- **Differentiation axes** — at least three from: `site`, `massing`, `organization`, `circulation`, `structure`, `sequence`, `environment`.
- **Location and object of operation** — where in the site/program the operation acts and what it affects.
- **Expected spatial or environmental consequence** — what the direction aims to achieve spatially or environmentally.
- **Falsifiability condition** — a specific observation that would disprove the usefulness of this direction. What would make this the wrong choice?
- **Evidence trace** — `evidence_ids` linking to the Evidence Records (PROVIDED, VERIFIED, INFERRED, PROPOSED) that support this direction.

### Direction quantity

| Condition | Action |
| --- | --- |
| Sufficient traceable evidence exists for at least three substantively different spatial strategies | Produce **exactly three** O-xxx concept directions |
| Only two substantively different strategies are supported by available evidence | Produce two O-xxx directions and explicitly record why a third cannot be formed |
| Fewer than two strategies are supported | **Do not fabricate.** Record the insufficiency, flag missing information, and request human guidance |
| Exactly three cannot be differentiated substantively | **Do not pad.** Do not create a third direction that differs only in name, colour, material, or façade — flag the limitation for human review |

### Substantive differentiation

Three concept directions must differ in their actual spatial operations, not in wording alone.

Each pair of directions must show substantive differences in at least **three differentiation axes** out of:

| Axis | Meaning | What differs |
| --- | --- | --- |
| `site` | Site strategy | Building placement, entry side, relationship to boundaries, open-space role |
| `massing` | Massing or section | Volume distribution, number of storeys, sectional organisation, building footprint shape — as falsifiable spatial hypotheses only; never as construction-level, regulatory-compliance, or confirmed volumetric conclusions |
| `organization` | Program organisation | Space grouping, zoning logic, departmental adjacency, stacking order |
| `circulation` | Circulation and sequence | Primary movement path, entry sequence, vertical circulation strategy |
| `structure` | Grid, span, core, or structural logic | Column grid choice, core position, structural system, span direction |
| `sequence` | Spatial sequence | Progression from entry to destination, compression and release, served/servant logic |
| `environment` | Daylight, ventilation, shade, or environmental response | Orientation strategy, passive environmental move, acoustic zoning |

A substantive difference means the option proposes a measurably different spatial arrangement — not the same arrangement described with different words. Two directions that share the same spatial organisation but narrate it differently are not substantively different.

`massing` is a differentiation axis for concept directions only. Massing descriptions are falsifiable spatial hypotheses; they are not construction-level, regulatory-compliance, or confirmed volumetric conclusions.

### Prohibited pseudo-differentiations

The following do **not** count as substantive differentiation and must not be used to satisfy the three-axis requirement or to create a third direction:

- Changing the name, label, or title of a direction while keeping the same spatial operation.
- Changing the colour palette, material selection, or façade style.
- Changing the architectural language, historical reference, or metaphorical framing.
- Re-stating the same spatial move with different prose.

If three directions cannot be substantively differentiated, **do not create a third**. Record the limitation and request human guidance.

---

## Output mapping and boundary

### O-xxx → output.schema.json options[]

Each concept direction maps to the existing `options[]` array in [output.schema.json](output.schema.json):

| O-xxx field | output.schema.json field | Notes |
| --- | --- | --- |
| O-xxx identifier | `options[].id` | Must match pattern `^O-[0-9]{3,}$` |
| Name | `options[].name` | Clear descriptive name |
| spatial_operation | `options[].spatial_operation` | Primary spatial move |
| Differentiation axes | `options[].differentiation_axes` | Array, min 3, from the enum `["site","massing","organization","circulation","structure","sequence","environment"]` |
| Evidence IDs | `options[].evidence_ids` | Array of E-xxx identifiers, min 1 |

The following content is recorded in the human-readable ledger only — it does not map to JSON fields in `options[]`:

- Location and object of the spatial operation.
- Expected spatial or environmental consequence.
- Falsifiability condition.
- Preconditions and applicable boundary.
- Failure conditions for precedent-derived operations.
- Differentiation fingerprint between directions.

Do not invent JSON fields for these. Do not write `location`, `consequence`, `falsifiability`, `precondition`, `boundary`, `failure_condition`, or `fingerprint` into the JSON.

### Evidence records

- **INFERRED** Evidence Records created during this segment are added to the `evidence[]` array in output.schema.json with `inference_basis` and `inference_rule`.
- **PROPOSED** Evidence Records are added to `evidence[]` with `proposal_rationale` and exactly one of `basis_evidence_ids` or `basis_absent_reason`.
- **ASSUMED** Evidence Records are added to `evidence[]` with all four resolution fields when information is missing.
- **PROVIDED** and **VERIFIED** records must originate from the input; they are inherited, not created here.

### What must not be written

This segment must not write:

- `criteria[]` (K-xxx) — criteria definition belongs to later segments.
- `assessments[]` on options — assessment against criteria belongs to later segments.
- `decisions[]` (D-xxx) — decision-making belongs to later segments.
- `dependencies[]` (DEP-xxx) — dependency edges belong to later segments.
- `stale` metadata on any object — stale propagation belongs to later segments.
- Any new JSON field not defined in output.schema.json.
- Any writing to `spaces[]`, `relations[]`, `constraints[]`, or `hypotheses[]` — these are inherited or produced by other segments.
- Any scoring, ranking, selection, or recommendation among O-xxx directions.

A **differentiation fingerprint table** comparing the three directions across the differentiation axes is permitted in the human-readable ledger. This table may only state what differs — it must not assign scores, rankings, recommendations, or preferences. It must not generate a D-xxx decision.

---

## Human-readable output and stop boundary

### Precedent and concept ledger

Produce a human-readable ledger with the following structure:

```markdown
# Precedent and Concept Ledger: [project name]

## 1. Precedent input
### 1.1 Registered precedent sources
...
### 1.2 Precedent observations and extracted operations
...
### 1.3 No precedent input (when applicable)
...

## 2. Upstream evidence summary
### 2.1 Key constraints from upstream ledgers
...
### 2.2 Key hypotheses from grid/core/height
...

## 3. Concept directions (O-xxx)

### `<next available O-xxx>`: [name]
- Spatial operation: ...
- Location and object: ...
- Expected spatial or environmental consequence: ...
- Falsifiability condition: ...
- Differentiation axes: [axis1, axis2, axis3, ...]
- Evidence trace: [E-xxx, E-xxx, ...]
- Precedent basis (if any): [SRC-xxx operations]

### `<next available O-xxx>`: [name]
...

### `<next available O-xxx>`: [name]
...

## 4. Differentiation fingerprint

| Axis | O-xxx | O-xxx | O-xxx |
| --- | --- | --- | --- |
| site | ... | ... | ... |
| massing | ... | ... | ... |
| organization | ... | ... | ... |
| circulation | ... | ... | ... |
| structure | ... | ... | ... |
| sequence | ... | ... | ... |
| environment | ... | ... | ... |

The differentiation fingerprint table states what differs. It does not score, rank, recommend, or select. It does not form a D-xxx decision. It does not imply preference or superiority.

## 5. Missing information
...

## 6. Questions for human review (maximum three)
1. [Question 1, if any]
2. [Question 2, if any]
3. [Question 3, if any]
```

Questions are limited to at most three items across all upstream ledgers and this segment combined. Omit the entire section when no questions arise. Do not add a fourth item.

### Stop boundary

When the precedent and concept ledger is complete — precedent input processed or its absence recorded, exactly three concept directions generated with substantive differentiation across at least three axes, falsifiability conditions stated, evidence traces recorded, missing information flagged, and at most three high-impact questions raised — **stop**. Do not continue into:

- criteria definition (K-xxx);
- option assessment against criteria;
- option comparison or scoring;
- human decision request or D-xxx;
- dependency modelling or stale propagation;
- deterministic comparison scripts;
- real precedent database construction, batch precedent collection, or Rubric;
- fixed regression or forward evaluation suites — these belong to Phase 4.

This reference is not a Skill, not a workflow, and not a concept generator. It is the single authoritative precedent operation and concept-direction framework for Phase 3 segment 5.

---

**Tasks explicitly reserved for later ARCH segments:**

| Reserved task | Description | Target phase |
| --- | --- | --- |
| Criteria definition (K-xxx) | Define comparison criteria with evidence traces | Phase 3 later segment |
| Option assessment | Rate each O-xxx against K-xxx criteria | Phase 3 later segment |
| Option comparison | Compare O-xxx options and present findings | Phase 3 later segment |
| Decision-making (D-xxx) | Record human design decision with rationale | Phase 3 later segment |
| Dependency and stale propagation | Establish DEP-xxx edges; mark downstream objects stale | Phase 3 later segment |
| Deterministic comparison scripts | Script-based option fingerprinting and comparison | Phase 3 later segment |
| Real precedent database | Batch collection, Rubric, regression and forward evaluation suites | Phase 4 |
