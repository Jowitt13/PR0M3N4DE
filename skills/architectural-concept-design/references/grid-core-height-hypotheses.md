# Grid, structural-system, core, and height hypotheses

> **Single authoritative source** for grid, structural-system, core, and height hypotheses within Phase 3 (Architectural Chain). This reference is not a Skill, not a workflow, and not a concept generator.

## Contents

- [Prerequisites and inputs](#prerequisites-and-inputs)
- [Hypotheses, not fixed solutions](#hypotheses-not-fixed-solutions)
- [Evidence and uncertainty](#evidence-and-uncertainty)
- [Hypothesis dimensions](#hypothesis-dimensions)
  - [Grid and structural system](#grid-and-structural-system)
  - [Core and vertical circulation](#core-and-vertical-circulation)
  - [Height and storeys](#height-and-storeys)
- [Schema mapping](#schema-mapping)
- [Human-readable output and stop boundary](#human-readable-output-and-stop-boundary)

---

## Prerequisites and inputs

### Upstream ledgers

This reference must only be used after all three upstream ledgers are complete:

1. A completed **brief ledger** produced by [brief-analysis.md](brief-analysis.md).
2. A completed **site ledger** produced by [site-context-analysis.md](site-context-analysis.md).
3. A completed **program-and-area ledger** produced by [program-area-and-circulation.md](program-area-and-circulation.md).

### Inherited data

Use only the following from the upstream ledgers — do not redefine them as a second authority:

| Data | Source | Description |
| --- | --- | --- |
| Program spaces (S-xxx) | program-and-area ledger | Space IDs, names, areas from input.schema.json |
| Relations (R-xxx) | program-and-area ledger | Adjacency relations at input root level |
| Site constraints | site ledger | Site boundaries, access, orientation, climate, context observations |
| Constraints (C-xxx) | input.schema.json | Design constraints with evidence IDs and status |
| Evidence (E-xxx) | all three ledgers | PROVIDED, VERIFIED, INFERRED, ASSUMED Evidence Records |
| Sources (SRC-xxx) | brief ledger | External source references |

### Authority boundary

- The brief ledger is the sole authority for task-brief facts.
- The site ledger is the sole authority for site observations and context.
- The program-and-area ledger is the sole authority for spaces, areas, relations, zoning, and circulation.
- This reference must not reclassify, re-source, or upgrade any upstream fact into a new confirmed fact.
- It may use existing PROVIDED / VERIFIED evidence from upstream ledgers as the basis for generating explicitly labelled INFERRED Evidence Records.
- Every INFERRED must carry a valid `inference_basis` and `inference_rule`.
- Do not silently re-read the brief to fill information gaps, and do not make this reference a second authoritative source for brief, site, or program facts.
- If upstream information is insufficient for grid/core/height reasoning, flag it as missing — do not silently fill gaps by re-reading the brief.

---

## Hypotheses, not fixed solutions

### Hypothesis rules

Grid, structural-system, core, height, and vertical-circulation choices are **comparable, revisable hypotheses**. They are not:

- fixed design decisions;
- construction-ready structural solutions;
- confirmed facts about the building;
- regulatory compliance conclusions.

### H-xxx hypothesis format

Each hypothesis carries the identifier `H-xxx` (where `xxx` is a three-or-more-digit number). Before generating hypotheses, scan the entire state package `hypotheses[]` array and allocate the next unused H-xxx. Must not reuse upstream H IDs or existing H-xxx from prior ledger generations. Every hypothesis must state:

- **geometric rule and dimensions with units** — grid spacing, bay logic, core footprint, floor-to-floor height, total storeys;
- **program and circulation consequences** — how the hypothesis affects space organisation, adjacency satisfaction, vertical movement;
- **spatial and environmental opportunity** — daylight/ventilation implications, site-fit logic, and environmental consequences of the hypothesis for the site context;
- **risks, dependencies, and unknowns** — what upstream facts are uncertain, what downstream work depends on this hypothesis;
- **evidence trace** — linked through `evidence_ids` to the Evidence Records that support this hypothesis.

### Quantity of hypotheses

| Condition | Action |
| --- | --- |
| Sufficient traceable input exists for at least two distinct structural/core/height configurations | Produce **two or more H-xxx hypotheses** with substantive differences in grid logic, core position, or height strategy |
| Only one configuration is supported by available evidence | Produce one H-xxx hypothesis and explicitly record why alternatives cannot be formed |
| Input is insufficient for even one complete hypothesis | **Do not fabricate.** Create an ASSUMED Evidence Record documenting what is missing, and flag the insufficiency for human review |

Substantive difference means a hypothesis differs from another in at least one of: grid geometry or span logic, structural material or system, core position or configuration, floor-to-floor height, total storeys, or vertical circulation strategy. Superficial variations (label, wording, colour reference) do not count.

### Prohibitions

- **No O-xxx options.** This reference produces H-xxx hypotheses only. Concept options (O-xxx) belong to later segments.
- **No concept generation, option comparison, or decision-making.** H-xxx are hypotheses, not evaluated options.
- **No site strategy, mass placement, or entrance design.** Those belong to later Phase 3 segments.
- **No program, area, adjacency, zoning, or circulation work.** Those are the responsibility of [program-area-and-circulation.md](program-area-and-circulation.md).
- **No construction-ready structural detailing.** Do not present any hypothesis as a construction-ready structural solution.

---

## Evidence and uncertainty

### Evidence Record authority

The complete Evidence Record field contracts are defined by [brief-and-evidence.md](brief-and-evidence.md) and [evidence.schema.json](evidence.schema.json). Those two files are the single authoritative source. This reference must not weaken, omit, or alter any contract defined there.

### INFERRED Evidence Record

Structural, core, and height judgments derived from existing facts must each create an **INFERRED Evidence Record** with:

| Field | Requirement |
| --- | --- |
| `id` | Stable identifier `E-xxx` |
| `label` | `INFERRED` |
| `claim` | The structural, core, or height claim derived from evidence |
| `inference_basis` | Array of one or more E-xxx evidence IDs from which this claim is inferred |
| `inference_rule` | Logical rule used for the inference (e.g. "Given [source-traced site width] (E-xxx) and [source-traced programme depth] (E-yyy), test a documented grid range") |

`inference_basis` must reference evidence that exists in the upstream ledgers. Do not infer from other inferences when verifiable facts are available.

### ASSUMED Evidence Record

When input is insufficient but work must continue, create an **ASSUMED Evidence Record** with all four resolution fields:

| Field | Requirement |
| --- | --- |
| `missing_information` | What information is missing |
| `impact` | How the missing information affects grid/core/height decisions |
| `owner` | Person or role responsible for resolving the assumption |
| `validation_action` | Next step to validate or resolve the assumption |

### Numeric integrity

- **No fabricated precise values.** Span dimensions, bay sizes, storey counts, floor-to-floor heights, core dimensions, or structural depths without a source must not be presented as exact numbers.
- **Ranges are acceptable when reasoned from evidence.** A range is acceptable when derived from site dimensions and space requirements via documented inference with explicit source-traceable evidence IDs.
- **When no basis exists**, record the missing information, its impact, the responsible owner, and the validation action via an ASSUMED Evidence Record. Do not insert a substitute numeric value. Without sufficient evidence, do not form a quantified H-xxx.
- **Never present ASSUMED or INFERRED as VERIFIED or as a confirmed design decision.**
- **ASSUMED is not a channel for justifying baseless numeric values.** ASSUMED documents what is missing, its impact, and who must resolve it. It does not legitimise inserting a number where evidence is absent, and it must never be promoted to VERIFIED or a confirmed design decision.
- **When only ASSUMED evidence exists for a quantitative dimension**, do not write a numeric value for that dimension (core count, approximate footprint, span, floor-to-floor height, storey count). Record the missing information via an ASSUMED Evidence Record, but do not form a quantified H-xxx around that dimension. Quantified H-xxx content requires at minimum one PROVIDED, VERIFIED, or properly inferred INFERRED evidence record as its basis.

### H-xxx evidence linkage

Each H-xxx hypothesis links to its supporting evidence through `evidence_ids` — an array of one or more `E-xxx` identifiers. These must reference:

- **INFERRED Evidence Records** (with valid `inference_basis` and `inference_rule` traced to upstream PROVIDED/VERIFIED facts) as the quantification basis for spans, storeys, floor-to-floor heights, core dimensions, and other numeric H-xxx content;
- **ASSUMED Evidence Records** as risk/unknown documentation only (missing information, impact, owner, validation_action), not as a quantification basis for any numeric H-xxx content;
- or existing **PROVIDED/VERIFIED** records from upstream ledgers.

---

## Hypothesis dimensions

Each dimension is described separately but kept comparable across hypotheses.

### Grid and structural system

For each H-xxx hypothesis, describe:

- **Geometric logic** — grid shape (rectilinear, radial, irregular), primary and secondary span directions, typical bay dimensions with units, and column layout principle;
- **Span conditions** — how the grid responds to space depths from the program ledger, clear-span requirements for large spaces (reading rooms, multi-purpose halls), and column-free zones;
- **Structural system type** — material and system concept at schematic level (e.g. steel frame, RC frame, load-bearing masonry, timber), not detailed member design;
- **Spatial consequences** — how the grid affects space subdivision, flexibility, daylight penetration, and future adaptability;
- **Risks and verification actions** — dependencies on uncertain site conditions, unknown ground conditions, or unverified program areas.

### Core and vertical circulation

For each H-xxx hypothesis, describe:

- **Core position** — location relative to the plan (central, peripheral, split, distributed), reasoning from site access, program zoning, and circulation hypotheses from the program ledger;
- **Core content** — stair, lift, service riser, and shaft allocation at schematic level. Only write core count or approximate footprint when supported by PROVIDED, VERIFIED, or INFERRED evidence (with valid `inference_basis` and `inference_rule` traced to upstream PROVIDED/VERIFIED facts). ASSUMED records missing information, impact, owner, and validation_action; it cannot serve as the basis for a core count or approximate footprint. When the only evidence for core dimensions is ASSUMED, document the missing information but do not write a numeric core count or footprint. Do not extend to fire-escape capacity, mechanical shaft sizing, lift traffic analysis, or regulatory compliance conclusions;
- **Vertical circulation relationship** — how core position interacts with horizontal circulation, zoning, and adjacency priorities;
- **Unknown conditions** — ground conditions affecting core depth, site-level access constraints, unverified vertical transport requirements.

### Height and storeys

For each H-xxx hypothesis, describe:

- **Storey count and floor-to-floor height** — approximate values with reasoning from program areas, site constraints, and building type;
- **Height relationship to site** — how the proposed height relates to site boundaries, neighbouring context, access, and orientation observations from the site ledger;
- **Spatial and environmental consequences** — how height choice may affect daylight, overshadowing, and other environmental conditions supported by site context evidence, stated as hypotheses to verify, not as volumetric design outputs;
- **Constraints to verify** — height limits from planning context (if any observation exists in the site ledger), unverified brief requirements for single vs multi-storey organisation.

### Out of scope

This reference does **not** address:

- structural load calculations, member sizing, or foundation design;
- seismic, wind, or geotechnical engineering;
- fire-escape capacity, travel distances, or smoke-control strategy;
- accessibility compliance, barrier-free design, or inclusive-design calculations;
- construction sequencing, cost estimation, or procurement strategy;
- detailed core dimensioning, lift traffic analysis, or mechanical shaft sizing.

---

## Schema mapping

### H-xxx → output.schema.json hypotheses[]

Grid, core, and height hypotheses produced by this reference map to the existing `hypotheses[]` array in [output.schema.json](output.schema.json):

| H-xxx field | output.schema.json field | Notes |
| --- | --- | --- |
| H-xxx identifier | `hypotheses[].id` | Must match pattern `^H-[0-9]{3,}$` |
| Hypothesis description | `hypotheses[].description` | Free-text architectural description |
| Evidence IDs | `hypotheses[].evidence_ids` | Array of E-xxx identifiers; minimum one |

### Derived evidence → evidence[]

INFERRED and ASSUMED Evidence Records created during this segment are added to the `evidence[]` array in [output.schema.json](output.schema.json). PROVIDED and VERIFIED records must originate from the input; they are inherited, not created here.

### Prohibitions

- **No new JSON fields.** Do not create `grid`, `core`, `height`, `span`, `bay`, `structural_system`, `floor_count`, `floor_to_floor`, or any other field not defined in output.schema.json.
- **No writing to `spaces[]`.** Spaces are inherited from input; this segment does not add, modify, or remove spaces.
- **No writing to `relations[]`.** Relations are inherited from input; this segment does not add, modify, or remove relations.
- **No writing to `constraints[]`.** This segment does not create C-xxx constraints. The `constraints[]` array in output.schema.json is not populated by grid-core-height.
- **No writing to `options[]`, `criteria[]`, or `decisions[]`.** Those belong to later Phase 3 segments.
- **No presenting structural candidate hypotheses as confirmed constraints.** H-xxx is a hypothesis, not a C-xxx constraint.

---

## Human-readable output and stop boundary

### Grid/core/height ledger

Produce a human-readable ledger with the following structure:

```markdown
# Grid, Core, and Height Ledger: [project name]

## 1. Upstream facts and assumptions
### 1.1 Inherited from site ledger
...
### 1.2 Inherited from program-and-area ledger
...
### 1.3 Working assumptions
...

## 2. Comparable hypotheses (H-xxx)
### `<next available H-xxx>`: [name]
- Geometric rule and dimensions: ...
- Program and circulation consequences: ...
- Spatial and environmental opportunity: ...
- Risks, dependencies, and unknowns: ...
- Evidence trace: [E-xxx, E-xxx]

### `<next available H-xxx>`: [name]
...

## 3. Dimension comparison
| Dimension | `<H-xxx>` | `<H-xxx>` | ... |
| --- | --- | --- | --- |
| Grid geometry | ... | ... |
| Typical bay | ... | ... |
| Core position | ... | ... |
| Storeys | ... | ... |
| Spatial consequence | ... | ... |
| Key risk | ... | ... |

The comparison table is for descriptive cross-referencing only. Do not rank, score, select, or evaluate H-xxx against each other. Do not form D-xxx decisions from the comparison.

## 4. Missing information
...

## 5. Questions for human review (maximum three)
1. [Question 1, if any]
2. [Question 2, if any]
3. [Question 3, if any]
```

Questions are limited to at most three items. Omit the entire section when no questions arise. Do not add a fourth item.

### Stop boundary

When the grid/core/height ledger is complete — H-xxx hypotheses recorded with traceable evidence, INFERRED and ASSUMED Evidence Records attached, dimension comparison table populated, missing information flagged, and at most three high-impact questions raised — **stop**. Do not continue into:

- floor-plan resolution or spatial layout;
- massing, volumetric design, or entrance strategy;
- concept generation, precedent operation, or option comparison (O-xxx);
- decision-making (D-xxx), criteria definition (K-xxx), or stale propagation;
- structural load calculations, member sizing, or foundation design;
- fire-escape, accessibility, or regulatory compliance conclusions;
- case extraction, design narrative, or presentation material.

Those are the responsibility of later references and segments of Phase 3.

---

This reference is not a Skill, not a workflow, and not a concept generator. It is the single authoritative grid/core/height hypothesis framework for Phase 3.
