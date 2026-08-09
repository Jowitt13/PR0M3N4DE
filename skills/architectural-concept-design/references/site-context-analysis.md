# Site and context analysis

## Contents

- [Scope and prohibitions](#scope-and-prohibitions)
- [Evidence classification for site information](#evidence-classification-for-site-information)
- [Site observation framework](#site-observation-framework)
- [Source-content guard for brief statements](#source-content-guard-for-brief-statements)
- [Hypothesis records](#hypothesis-records)
- [Candidate site constraints](#candidate-site-constraints)
- [Schema mapping](#schema-mapping)
- [Output format](#output-format)
- [Stop boundary](#stop-boundary)

This reference covers the second segment of Phase 3 (Architectural Chain): receiving a completed brief ledger, extracting and classifying every site-related statement, recording observations and interpretations with evidence labels, surfacing missing information, producing candidate site constraints, and stopping before any site strategy or massing decision.

## Scope and prohibitions

### Required inputs

- A completed brief ledger produced by [brief-analysis.md](brief-analysis.md) with registered Sources, labelled Evidence Records, and at most three high-impact questions.
- The original brief text and the registered source material referenced by the brief ledger.

### What this reference does

- Guides the agent through extracting site information from the brief ledger.
- Defines the fixed site-observation categories and their evidence classification.
- Enforces that "busy road", "standard setback", "6 metres", and similar brief statements remain brief-source content, never upgraded to survey, regulatory, or VERIFIED conclusions.
- Maps site observations and interpretations into evidence records and hypotheses.
- Produces candidate constraints that the design cannot violate.
- Specifies the stop boundary after site and context analysis.

### Prohibitions

- **No regulatory conclusions.** Never claim compliance, calculate fire ratings, or derive code-mandated dimensions from site observations.
- **No site survey or measurement claims.** "6 metres", "800 m²", "rectangular", "busy road", and "standard setback" are PROVIDED brief content only. Do not present them as surveyed, measured, or VERIFIED facts.
- **No VERIFIED without source_id, claim_type, verification_status, and verified_at.** For regulatory claims, also require jurisdiction, edition, and clause. When no applicable clause exists, `clause` must be `null` and `clause_not_applicable_reason` is required. Never use the string `"N/A"` as a clause placeholder. These are field contracts (data integrity), not regulatory compliance conclusions.
- **No site strategy, mass placement, open-space role, arrival sequence, service access, or concept generation.** These belong to later Phase 3 segments.
- **No program, area calculation, adjacency, circulation, grid, structural-system, core, or height work.** These belong to later segments.
- **No reset of ARCH-007's three high-impact question limit.** The intake phase may have already asked up to three questions. Do not silently add more; flag any new site-specific High-priority missing items without asking additional questions beyond the three-question ceiling.
- **No ingestion of real user briefs, client names, addresses, contacts, or private documents into the repository.** All fixtures must be anonymous.

## Evidence classification for site information

Site information follows the same five-label classification defined in [brief-analysis.md](brief-analysis.md):

| Label | Site use | Requirements |
| --- | --- | --- |
| `PROVIDED` | Site statements taken verbatim from the brief or source. | Must have `source_id`. |
| `VERIFIED` | Site facts confirmed against a recorded authoritative source (map, survey, regulation). | Must have `source_id`, `claim_type`, `verification_status`, `verified_at` (RFC3339 date-time with timezone). Regulatory claims also require `jurisdiction`, `edition`, `clause`. When no applicable clause exists, `clause` must be `null` and `clause_not_applicable_reason` is required. Never use the string `"N/A"` as a clause placeholder. These are field contracts (data integrity), not regulatory compliance conclusions. |
| `INFERRED` | Site interpretations reasoned from existing evidence. | Must have `inference_basis` and `inference_rule`; `source_id` is NOT required. |
| `ASSUMED` | Working premise when site information is missing. | Must have `missing_information`, `impact`, `owner`, `validation_action`; `source_id` is NOT required. |
| `PROPOSED` | Not generated during site and context analysis; reserved for later stages. | — |

Never silently promote an INFERRED or ASSUMED claim to PROVIDED or VERIFIED.

## Site observation framework

Record observations only when the source provides them. Do not fabricate observations for missing categories.

Site observations are classified by their source:

- **PROVIDED**: the brief or an attached source states a site fact verbatim → create a PROVIDED Evidence Record with `source_id`.
- **VERIFIED**: the site fact has been confirmed against a recorded authoritative source (map, survey, regulation) → create a VERIFIED Evidence Record with `source_id`, `claim_type`, `verification_status`, `verified_at`. Regulatory claims also require `jurisdiction`, `edition`, `clause`. When no applicable clause exists, `clause` must be `null` and `clause_not_applicable_reason` is required. Never use the string `"N/A"` as a clause placeholder. These are field contracts (data integrity), not regulatory compliance conclusions.

INFERRED and ASSUMED are not observation labels:

- **INFERRED**: an interpretation reasoned from existing evidence → create an INFERRED Evidence Record with `inference_basis` and `inference_rule`. Do not use INFERRED as an observation label.
- **ASSUMED**: site information is missing and work must proceed → create an ASSUMED Evidence Record with `missing_information`, `impact`, `owner`, `validation_action`, and state "没有观察事实". ASSUMED is not an observation—it is a placeholder for missing data.

### 1. Boundary and dimensions

- Site boundary description and approximate dimensions stated in the brief.
- Evidence label: PROVIDED for brief statements. Dimensions not stated are missing; do not estimate them as observations.

### 2. Orientation and access

- Compass orientation of the site and its edges if stated in the brief.
- Road access: which sides face roads, road classification as described in the brief.
- Evidence label: PROVIDED for brief statements. Orientation not stated is missing.

### 3. Surroundings and context

- Adjacent buildings and their character as described in the brief.
- Evidence label: PROVIDED for brief statements. Unstated surroundings are missing.

### 4. Levels and topography

- Site levels, slope, topography stated in the brief.
- Evidence label: PROVIDED for brief statements. Absent topography data is missing (ASSUMED only if work must continue, with "没有观察事实").

### 5. Existing conditions

- Previous use, demolished structures, contamination, trees stated in the brief.
- Evidence label: PROVIDED for brief statements. Unstated conditions are missing.

### 6. Noise and environmental conditions

- Noise sources (roads, industry, rail) stated in the brief.
- Wind, sun path, microclimate data when stated in the brief or a registered source.
- Evidence label: PROVIDED for climate data stated verbatim in the brief or an attached source. Climate data independently obtained and confirmed by the agent from an authoritative source (meteorological record, climate dataset, weather station) must use VERIFIED with the full VERIFIED field contract (`source_id`, `claim_type`, `verification_status`, `verified_at`). An INFERRED climate interpretation may only be created on top of an existing PROVIDED or VERIFIED climate evidence record, with `inference_basis` and `inference_rule`. Without any PROVIDED or VERIFIED climate evidence, climate data is missing. If work must proceed without observed environmental data, create a full ASSUMED Evidence Record and state "没有观察事实" (no observational facts).

### 7. Views and outlook

- Desirable or undesirable views stated in the brief.
- Evidence label: PROVIDED for brief statements. Unstated views are missing.

### 8. Shade and overshadowing

- Existing shading elements (adjacent buildings, trees, topography) stated in the brief.
- Evidence label: PROVIDED for brief statements. Unstated shading conditions are missing.

### 9. Hydrology and drainage

- Water bodies, flood zones, drainage patterns stated in the brief.
- Evidence label: PROVIDED for brief statements. Absent hydrology data is missing (ASSUMED only if work must continue, with "没有观察事实").

## Source-content guard for brief statements

Certain site-related phrases commonly appear in briefs without regulatory authority. The following must remain as PROVIDED brief content and **must not** be presented as survey, measurement, regulatory, or VERIFIED conclusions:

- **"busy road"** — a subjective description from the brief source. It is not a traffic count, noise measurement, or road classification.
- **"standard setback"** — the brief's wording. It is not a verified zoning or code requirement unless a specific regulation, jurisdiction, edition, and clause are recorded.
- **"6 metres"** — a dimension quoted from the brief. It is not a surveyed or code-verified measurement unless an authoritative source is recorded.
- **"800 m²", "rectangular"** — site area and shape from the brief. They are not surveyed dimensions.

When recording these as PROVIDED evidence, always attribute them to the original source. Do not write them as if the agent independently observed or verified them.

## Hypothesis records

When recording interpretations and derived conclusions about the site, use `hypotheses[]` from output.schema.json:

- `id`: stable H-xxx ID.
- `description`: the interpretive statement.
- `evidence_ids`: at least one E-xxx evidence ID supporting the hypothesis.

Examples of site hypotheses (interpretations only; conditional, falsifiable statements traced to INFERRED evidence—never stated as environmental facts or design instructions):

- "The source-described contrast between the busy southern road and quiet northern lane may indicate an acoustic difference that requires later measurement."
- "East and west residential adjacency may require later privacy and overshadowing verification."

Each hypothesis must reference at least one INFERRED Evidence Record. The referenced INFERRED record must declare `inference_basis` (the PROVIDED or VERIFIED evidence it reasons from) and `inference_rule` (the logical basis). Hypotheses without supporting INFERRED evidence are invalid.

Hypotheses are revisable interpretations, not fixed facts. They carry evidence IDs for traceability and must be clearly distinguished from raw observations.

## Candidate site constraints

Site observations and interpretations that impose requirements the design cannot violate must be recorded as candidate constraints. Each constraint maps to `constraints[]` in input.schema.json with four required fields:

- `constraints[].id`: stable C-xxx ID.
- `constraints[].description`: constraint text.
- `constraints[].evidence_ids`: at least one E-xxx evidence ID.
- `constraints[].status`: must be `candidate` in the site and context analysis segment. `confirmed` only by human action.

Example candidate constraint derived from the community-library intake:

- "Building must maintain minimum 6 m setback from east and west residential boundaries" → status `candidate`, evidence from PROVIDED brief statement only. The 6 m value is the brief author's stated requirement, not a survey measurement or VERIFIED regulation. It becomes a binding constraint only after human confirmation against an authoritative source (zoning code, title deed, or survey). Until confirmed, treat the 6 m value as a brief-source statement, never as a verified legal or physical fact.

No site-strategy, entry, façade, or service-access constraints are generated during site and context analysis; those belong to later Phase 3 segments.

Existing constraints from the brief intake phase (ARCH-007) carry forward; do not duplicate or silently overwrite them.

### Deduplication rule

- Only create a candidate constraint when no equivalent C-xxx with the same supporting evidence already exists in input `constraints[]`.
- If the brief intake phase (ARCH-007) already registered a constraint with the same evidence basis, carry it forward unchanged; do not create a duplicate C-xxx.
- The 6 m setback candidate constraint is a brief-source statement only. It is not enacted regulation, not a survey conclusion, and not a confirmed physical fact.

## Schema mapping

input.schema.json has no `site` top-level field. Site information maps as follows:

| Site content | Legal structured destination | Prohibitions |
| --- | --- | --- |
| Raw site observations (boundary, orientation, roads, surroundings, levels, existing, noise, views, shade, hydrology) | `evidence[]` with label PROVIDED (brief-derived) or VERIFIED (authority-confirmed). Both must trace to `source_id`. VERIFIED also requires `claim_type`, `verification_status`, `verified_at`. INFERRED and ASSUMED are not raw observation labels. | Do not create a `site` JSON property |
| Site interpretations and derived conclusions | First create an INFERRED Evidence Record with `inference_basis` and `inference_rule`. Then record in `hypotheses[]` (H-xxx) with `evidence_ids` pointing to that INFERRED evidence. | Do not claim hypotheses as fixed facts; do not write interpretations directly into `evidence[]` without the inference contract |
| Site-derived design requirements | `constraints[]` (C-xxx) with `id`, `description`, `evidence_ids`, `status` = `candidate` | Do not set status to `confirmed` without human action; do not fabricate regulatory constraints |
| Missing site information | Not an observation. Flag as missing. Only create an ASSUMED Evidence Record when work must continue: require `missing_information`, `impact`, `owner`, `validation_action`, and state "没有观察事实". | Do not present assumptions as observations |

VERIFIED regulatory evidence records require `jurisdiction`, `edition`, `clause`, `verification_status`, and `verified_at` as field contracts defined in `evidence.schema.json`. When `clause` is `null`, `clause_not_applicable_reason` is required. The string `"N/A"` must never appear as a clause value. These are data-integrity requirements of the Schema contract; they do not constitute or imply a regulatory compliance conclusion.

## Output format

### Human-readable site ledger

A Markdown document extending the brief ledger with site-specific sections:

```markdown
# Site Ledger: [project name]

## 1. Site observations
...

## 2. Site interpretations (hypotheses)
...

## 3. Candidate site constraints
...

## 4. Missing site information
...

## 5. Site next actions
...
```

### Integration with structured output

Site evidence and hypotheses integrate into the same output.schema.json state package as the brief ledger. All IDs (E-xxx, H-xxx, C-xxx) must be unique across the combined state. Do not create separate output artifacts for site content.

## Stop boundary

When the site ledger is complete—observations classified, interpretations recorded as hypotheses, candidate constraints listed, and missing information flagged—**stop**. Do not continue into:

- site strategy or mass placement;
- open-space role or landscape design;
- arrival sequence or service access;
- program organization or area allocation;
- adjacency, circulation, or zoning analysis;
- grid, structural-system, core, or height hypotheses;
- concept generation, option comparison, or stale propagation.

Those are the responsibility of later references and segments of Phase 3.

This reference itself is not a Skill, not a workflow, and not a concept generator. It is a site and context analysis procedure only.
