# Program, area, adjacency, zoning, and circulation

## Contents

- [Scope and prohibitions](#scope-and-prohibitions)
- [Evidence record authority](#evidence-record-authority)
- [Input boundaries](#input-boundaries)
- [Area handling](#area-handling)
- [Adjacency relations](#adjacency-relations)
- [Zoning and circulation hypotheses](#zoning-and-circulation-hypotheses)
- [Schema mapping](#schema-mapping)
- [Output format](#output-format)
- [Stop boundary](#stop-boundary)

This reference covers the third segment of Phase 3 (Architectural Chain): after the brief ledger and site ledger are complete, receive the structured program and relations from input.schema.json, build a traceable program-and-area ledger, validate adjacency, form zoning and circulation hypotheses, and stop before any grid, core, or concept work.

## Scope and prohibitions

### Required inputs

- A completed brief ledger produced by [brief-analysis.md](brief-analysis.md).
- A completed site ledger produced by [site-context-analysis.md](site-context-analysis.md).
- A validated `program` object and optional `relations[]` from input.schema.json.

### What this reference does

- Validates program spaces against the area-schedule schema contract.
- Calls `scripts/check_area_schedule.py` for deterministic area calculation.
- Validates adjacency relations against existing space IDs.
- Surfaces missing information, conflicts, and ambiguous relationships.
- Forms zoning and circulation hypotheses with traceable evidence.
- Produces a program-and-area ledger with candidate adjacency proposals and a stop boundary.

### Prohibitions

- **No grid, structural-system, core, or height hypotheses.** Those are the responsibility of [grid-core-height-hypotheses.md](grid-core-height-hypotheses.md).
- **No site strategy, mass placement, arrival sequence, or service access.** Those belong to later Phase 3 segments.
- **No concept generation, precedent operation, option comparison, or stale propagation.**
- **No hand-calculation of area totals.** Use `check_area_schedule.py`.
- **No regulatory conclusions.** Never claim compliance, calculate fire ratings, or derive code-mandated dimensions.
- **No writing of Schema-undefined fields into structured JSON.**
- **Do not present zoning or circulation hypotheses as confirmed facts, regulatory compliance, or final design.**

## Evidence record authority

The complete Evidence Record field contracts are defined by [brief-and-evidence.md](brief-and-evidence.md) and [evidence.schema.json](evidence.schema.json). Those two files are the single authoritative source. This reference must not weaken, omit, or alter any contract defined there.

| Label | Minimum required fields |
| --- | --- |
| PROVIDED | `source_id` — the source must be a registered source from the brief ledger. |
| VERIFIED | `source_id`, `claim_type`, `verification_status`, `verified_at`. When `claim_type` is `regulatory`: `jurisdiction`, `edition`, and `clause` are additionally required. When `clause` is `null`, `clause_not_applicable_reason` is additionally required. `"N/A"` is not accepted as a `clause` value. `clause_not_applicable_reason` does not replace `clause` — `clause` is always required for regulatory claims. |
| INFERRED | `inference_basis` (array of E-xxx evidence IDs) and `inference_rule`. |
| ASSUMED | All four resolution fields: `missing_information`, `impact`, `owner`, `validation_action`. |
| PROPOSED | `proposal_rationale` and exactly one of `basis_evidence_ids` or `basis_absent_reason`. |

For zoning and circulation inferences in this reference specifically, `inference_basis` must reference only PROVIDED or VERIFIED evidence — hypotheses must be grounded in recorded facts, not in other inferences.

## Input boundaries

### Program structure

`program` uses the existing structure defined in [input.schema.json](input.schema.json) and [area-schedule.schema.json](area-schedule.schema.json). The only legal structured fields for each space are:

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `id` | yes | string `^S-[0-9]{3,}$` | Stable space identifier. |
| `name` | yes | string | Human-readable space name. |
| `area.value` | yes | number ≥ 0 | Numeric area value. |
| `area.unit` | yes | const `"m2"` | Area unit (square metres). |

No other fields may be written into the `program` JSON. Specifically, the Schema does not define `user_group`, `opening_hours`, `privacy`, `zone`, `department`, `floor`, or `ceiling_height` within the `program` spaces.

### Grossing factor

`grossing_factor` is an optional object within `program`:

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `grossing_factor.value` | yes | number > 0 | Grossing factor multiplier. |
| `grossing_factor.unit` | yes | const `"ratio"` | Unit must always be `ratio`. |

### Relations location

`relations[]` is located at the input root level — **not** inside `program`. Each relation has:

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `id` | yes | string `^R-[0-9]{3,}$` | Stable relation identifier. |
| `from_space_id` | yes | string `^S-[0-9]{3,}$` | Source space ID. |
| `to_space_id` | yes | string `^S-[0-9]{3,}$` | Target space ID. |
| `priority` | yes | enum `required`, `preferred`, `avoid` | Adjacency priority. |
| `rationale` | no | string | Architectural reasoning. |

### Handling extra-programmatic information

Information from the brief that relates to spaces but is not covered by the Schema — such as user groups, opening hours, privacy expectations, or preliminary zoning ideas — must **not** be written into the structured JSON. Instead, retain it in:

- The human-readable program ledger (see [Output format](#output-format)).
- An Evidence Record with the appropriate label (PROVIDED, INFERRED, or ASSUMED).

If this information is missing and needed for design decisions, flag it in the missing-information table following the protocol in [brief-analysis.md](brief-analysis.md).

## Area handling

### Script-based calculation

Area totals must be calculated by the existing deterministic script. Call:

```text
python scripts/check_area_schedule.py <program.json>
```

Or use the Python function `calculate_area_schedule(payload)` directly. The script returns:

```json
{
  "space_count": 3,
  "net_area": {"value": 680.0, "unit": "m2"},
  "gross_area": {"value": 816.0, "unit": "m2"},
  "grossing_factor": {"value": 1.2, "unit": "ratio"}
}
```

**Do not hand-calculate totals.** The script is the single source of truth for arithmetic. Do not re-implement its logic in prose or code.

### Interpreting script results

The script checks arithmetic only. It does **not**:

- establish whether a target area is architecturally suitable;
- compare net or gross area against a brief target;
- flag over- or under-provision;
- validate whether the grossing factor is appropriate for the building type.

These interpretations are the agent's responsibility, supported by evidence and labelled as INFERRED.

### Area conflicts and missing data

When the brief states an area target that conflicts with the script result, or when area data is missing:

1. **Conflict**: Record the conflict explicitly in the program ledger. Cite both the brief claim (PROVIDED) and the script result. Do not silently resolve the discrepancy. Flag it for human review.
2. **Missing area**: Do not fabricate areas. If a space lacks an area value and work must proceed, create a full ASSUMED Evidence Record with `missing_information`, `impact`, `owner`, and `validation_action`.
3. **Unknown grossing factor**: Default to `{"value": 1.0, "unit": "ratio"}` only when no factor is provided and work must continue. Record this as an ASSUMED Evidence Record, not a neutral default.
4. **Maximum three high-impact questions** for area targets, grossing method, or program quantities that would change a major design decision.

## Adjacency relations

### Validating existing relations

For each relation in `relations[]`:

1. Verify that both `from_space_id` and `to_space_id` reference existing space IDs from `program.spaces[]`.
2. Verify that `priority` is one of `required`, `preferred`, or `avoid`.
3. Check for relations where `from_space_id == to_space_id` (self-relation) — these are invalid.
4. Identify duplicate relations (same pair of space IDs with different priorities) — flag as conflicting.

### Missing and incomplete relations

| Condition | Action |
| --- | --- |
| `relations[]` is absent or empty | Flag as "relations missing — requires clarification." Do not fabricate R-xxx. |
| `from_space_id` or `to_space_id` does not match any existing S-xxx | Record the orphan relation as invalid. Do not guess which space was intended. |
| Priority conflict (two relations between same spaces, different priorities) | Flag both and record the conflict. Do not pick one silently. |
| Relation exists with no `rationale` | Accept as valid but note the absence of reasoning. |

### Candidate adjacency proposals

When adjacency needs are apparent from the brief but no relation exists in the input, the agent may propose a candidate adjacency:

1. Create a PROPOSED Evidence Record with:
   - `proposal_rationale`: architectural reasoning for the adjacency.
   - EITHER `basis_evidence_ids` (one or more E-xxx) OR `basis_absent_reason` (why no prior evidence exists).
2. Add the proposed relation to the program ledger's candidate-relations table.
3. Mark it clearly as **pending human confirmation**.

Candidate relations must **never**:

- be written into the structured `relations[]` JSON without human approval;
- be presented as confirmed task requirements;
- be mixed with existing input relations without clear labelling.

### The one-of contract for PROPOSED

Per [evidence.schema.json](evidence.schema.json), every PROPOSED Evidence Record must satisfy exactly one of:

- `basis_evidence_ids` (minimum one E-xxx), **OR**
- `basis_absent_reason` (why no prior evidence exists).

Both must not be provided together. Neither must be absent. This is a strict one-of contract.

## Zoning and circulation hypotheses

### Zoning terms are assumptions, not facts

Terms such as `public`, `semi-public`, `staff`, `service`, `accessible`, and `emergency` describe spatial organisation conditions that require verification. They are not:

- default facts about any space;
- regulatory compliance conclusions;
- fixed zoning labels that can be assigned without evidence.

### Forming zoning hypotheses

When interpreting spatial organisation from PROVIDED or VERIFIED evidence:

1. Create an INFERRED Evidence Record with:
   - `inference_basis`: the PROVIDED or VERIFIED evidence IDs from which zoning is reasoned.
   - `inference_rule`: the logical basis (e.g., "spaces described as public-facing are tentatively grouped into a public zone based on program adjacency to the entry sequence").
2. Record the hypothesis in the program ledger's zoning table with its evidence trace.
3. Present as a revisable hypothesis, not a fixed fact or design instruction.

### Proceeding with insufficient information

When zoning or circulation information is insufficient but work must continue:

- Create a full ASSUMED Evidence Record with all four resolution fields: `missing_information`, `impact`, `owner`, `validation_action`.
- Never present the assumption as fact.
- Never label it VERIFIED or PROVIDED.

### Circulation hypotheses

Circulation (horizontal and vertical) may be hypothesised based on:

- PROVIDED or VERIFIED evidence about user flows, numbers, or operational patterns;
- adjacency relations that imply movement between spaces;
- site constraints (from the site ledger).

Circulation hypotheses are provisional only. They must not:

- pre-determine grid, core, or structural decisions;
- claim fire-escape or accessibility compliance;
- be presented as a final circulation plan.

### Limits

- Zone and circulation hypotheses remain at the level of **discussable, falsifiable propositions**.
- They may be informed by site constraints but must not become site strategy, massing, or entrance design.
- Maximum three high-impact questions may already have been asked in earlier segments. Do not silently exceed the three-question ceiling.

## Schema mapping

| Content | Legal structured destination | Prohibitions |
| --- | --- | --- |
| Program spaces (id, name, area) | `program.spaces[]` per area-schedule.schema.json | Do not add `user_group`, `opening_hours`, `privacy`, `zone`, `department`, `floor`, or `ceiling_height` |
| Grossing factor | `program.grossing_factor` with `unit: "ratio"` | Do not use units other than `ratio` |
| Adjacency relations | `relations[]` at root level | Do not nest inside `program`; do not fabricate R-xxx for missing relations |
| Area totals | Human-readable program ledger only; output.schema.json has no structured area field | Do not hand-calculate; do not create undocumented structured area fields |
| Extra-programmatic information (user groups, privacy, hours) | Human-readable ledger OR Evidence Record (PROVIDED, INFERRED, or ASSUMED) | Do not write into structured JSON |
| Zoning interpretations | INFERRED Evidence Record with `inference_basis` + `inference_rule`, then hypothesis in ledger | Do not present as confirmed facts, regulatory compliance, or final design |
| Circulation hypotheses | INFERRED Evidence Record → `hypotheses[]` (H-xxx) | Do not pre-determine grid, core, or structure; do not claim code compliance |
| Candidate adjacencies | PROPOSED Evidence Record with `proposal_rationale` and one-of `basis_evidence_ids` / `basis_absent_reason` | Do not mix with input relations without labelling; do not claim as confirmed |
| Working assumptions (missing program/circulation data) | ASSUMED Evidence Record with `missing_information`, `impact`, `owner`, `validation_action` | Do not present as fact; do not label VERIFIED or PROVIDED |

## Output format

### Human-readable program-and-area ledger

```markdown
# Program and Area Ledger: [project name]

## 1. Program summary
...

## 2. Area schedule
...

## 3. Area verification (script output)
...

## 4. Adjacency relations
### 4.1 Existing relations
...
### 4.2 Missing, invalid, or conflicting relations
...
### 4.3 Candidate adjacency proposals (pending human confirmation)
...

## 5. Zoning and circulation hypotheses
...

## 6. Missing information
...

## 7. Next actions
1. [Question 1, if any]
2. [Question 2, if any]
3. [Question 3, if any]
```

Questions are limited to at most three items. Omit the entire section when no questions arise. Do not add a fourth item.

### Integration with structured output

The output.schema.json state package has no `area_summary`, `area_totals`, or equivalent structured area field. Area results from `check_area_schedule.py` are reported in the human-readable program ledger only; do not create undocumented structured area fields in JSON.

The output may legally carry:
- input `spaces[]` and `relations[]` (inherited, not modified);
- `hypotheses[]` (H-xxx) backed by INFERRED Evidence Records;
- PROPOSED Evidence Records (for candidate adjacency proposals).

Candidate adjacency proposals remain in the human-readable ledger only. They must not be written into the structured `relations[]` JSON without explicit human approval. This segment does not create C-xxx constraints — `constraints[]` in output.schema.json is not populated by program-area-and-circulation.

All IDs (S-xxx, R-xxx, H-xxx, E-xxx) must be unique across the combined state. Do not create separate output artifacts for program content.

## Stop boundary

When the program-and-area ledger is complete — spaces validated, area calculated by script, relations checked for validity, gaps and conflicts flagged, candidate adjacencies recorded for human confirmation, and zoning/circulation hypotheses traced to evidence — **stop**. Do not continue into:

- floor-plan resolution or spatial layout;
- massing, entrance strategy, or volumetric design;
- grid, structural-system, core, or height hypotheses;
- precedent operation, concept generation, or option comparison;
- regulatory compliance, fire-escape, or accessibility conclusions.

Those are the responsibility of later references and segments of Phase 3.

This reference is not a Skill, not a workflow, and not a concept generator. It is a program, area, adjacency, zoning, and circulation procedure only.
