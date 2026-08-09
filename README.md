# PR0M3N4DE

**[简体中文](README.zh-CN.md)**

> **A promenade through architectural reasoning.**

Architecture is not encountered all at once. It is discovered through movement,
sequence, threshold, return, and revision. PR0M3N4DE applies that idea to the
work that happens before a building can be drawn with confidence: the design
reasoning itself should unfold in view.

**Design is not an answer. It is a sequence of decisions.**

**Machine for order. Human for meaning.**

**Trace before trust.**

PR0M3N4DE does not try to replace the architect's decision. It tries to
preserve the path that makes the decision intelligible.

**The final option is not the whole design. The evolution is part of the
design.**

> **Naming note.** The implemented Skill in this source tree is still named
> `architectural-concept-design`. PR0M3N4DE is the intended public product
> identity for a future distribution; this README does not silently rename the
> existing contracts, package identifiers, or release manifests.

## Why the name

`PR0M3N4DE` borrows its name from the architectural idea of the *promenade
architecturale*: a building is understood through movement, sequence, changing
viewpoints, thresholds, and time rather than as a single static image. The
`0`, `3`, and `4` substitute for `O`, `E`, and `A` to make the name digitally
distinct without turning it into generic AI branding.

The same metaphor guides the product. A design should not jump from prompt to
form. It should unfold through a sequence of states, reasons, operations,
decisions, and revisions.

```text
State → Operation → State → Operation → State
```

PR0M3N4DE is an independent open-source project; it is not affiliated with Le
Corbusier, Fondation Le Corbusier, or any architecture software vendor.

## The promenade: current core and future direction

### Implemented reasoning core

```text
Brief → Evidence → Constraints → Hypotheses → Options → Comparison
      → Human Decision → Deliverables
```

Each step is deliberately inspectable. A missing survey is not turned into a
fact. A promising option is not treated as a decision. A decision does not
erase the evidence, dependencies, or uncertainties from which it emerged.

### Target evolution — not implemented

The intended product direction is **Architectural Reasoning + Design Evolution
+ Design Operations**:

```text
Brief → Evidence → Constraints → Hypotheses → Design Operations → Options
      → Comparison → Human Decision → Deliverables
```

The future Design Operations layer would make a transformation specific enough
to inspect: what changed, why, which evidence and constraint triggered it, the
hypothesis behind it, affected systems, trade-offs, stale downstream objects,
and whether the architect accepted, rejected, or revised it.

For example, an operation might state an intent, a `Carve` or `Terrace` move,
its reason, and effects on massing, circulation, programme, facade, structure,
or landscape. This is **not** a claim that the current repository has a
state-to-state operation history, geometry engine, or CAD/BIM integration. Its
current option contract records a `spatial_operation` description; the general
operation/evolution model remains vision.

This is an installable, local-first architecture **pre-design Skill** for
architectural prosumers: students with design literacy, advanced and AI-native
architecture students, young architects, independent designers, small studios,
and early-stage design teams. It organizes explicit inputs, evidence labels,
constraints, spatial hypotheses, options, comparisons, and human decisions
into traceable early-design records. It is not a web application, a
construction-document system, an automatic approval engine, or a substitute for
professional judgement.

## What is implemented now

The following capabilities are present in the current repository and are backed
by contracts, deterministic scripts, or fixed evaluations.

| Capability | Current implementation | Repository evidence |
| --- | --- | --- |
| Brief normalization | A loose human brief becomes thirteen explicitly labelled fields. `PROVIDED`, `UNKNOWN`, and `MISSING` remain distinct; the normalizer creates neither design content nor new evidence. | [normalized brief ledger](skills/architectural-concept-design/references/normalized-brief-ledger.md) · [input schema](skills/architectural-concept-design/references/normalized-brief-ledger.input.schema.json) · [normalizer](skills/architectural-concept-design/scripts/normalize_project_brief.py) |
| Evidence discipline | Records carry `PROVIDED`, `VERIFIED`, `INFERRED`, `ASSUMED`, or `PROPOSED` labels. Contracts prevent an assumption or inference from silently being presented as verified fact. | [evidence schema](skills/architectural-concept-design/references/evidence.schema.json) · [brief/evidence protocol](skills/architectural-concept-design/references/brief-and-evidence.md) |
| Site, programme, and circulation reasoning | References structure site observations, programme, areas, adjacency, zoning, circulation, grid/core/height hypotheses, and missing information. Area arithmetic is handled by a deterministic local script. | [site/context](skills/architectural-concept-design/references/site-context-analysis.md) · [programme/area/circulation](skills/architectural-concept-design/references/program-area-and-circulation.md) · [area-schedule checker](skills/architectural-concept-design/scripts/check_area_schedule.py) |
| Substantively different options | The output contract records hypotheses, options, criteria, comparisons, dependencies, and deliverables. Options must differ in spatial operations, not merely in style. The present `spatial_operation` field is an option description, not a generic evolution-history engine. | [concept options and decisions](skills/architectural-concept-design/references/concept-options-and-decisions.md) · [comparison/decision handoff](skills/architectural-concept-design/references/option-comparison-decision-handoff.md) · [state-package schema](skills/architectural-concept-design/references/output.schema.json) |
| Human decision gate and state package | A deterministic assembler accepts a schema-valid brief plus **already human-authored** hypotheses, options, and criteria; it leaves the package awaiting an explicit human decision. The validator tracks dependencies and stale downstream state. | [project-state assembly](skills/architectural-concept-design/references/project-state-assembly.md) · [assembler](skills/architectural-concept-design/scripts/assemble_project_state.py) · [state validator](skills/architectural-concept-design/scripts/validate_state.py) |
| State-only presentation handoff | For a validated real-project state with one explicit human selection and no reviewed runtime-candidate set, the Skill can create a bounded ten-page state-only handoff using team-original diagrams only. It does not render a PPTX or transfer external precedents. | [state-only handoff](skills/architectural-concept-design/references/state-only-presentation-handoff.md) · [builder](skills/architectural-concept-design/scripts/build_state_only_presentation_handoff.py) |
| Controlled source-access boundaries | A local registry, request-plan checks, synthetic replay, runtime dry-run, and explicitly gated canary contracts enforce exact sources, budgets, and stop-on-denial behaviour. They are not a general web-search or scraping facility. | [source registry](skills/architectural-concept-design/references/source-access-registry.json) · [source-access gate](skills/architectural-concept-design/references/runtime-source-access-gate.md) · [controlled plan](skills/architectural-concept-design/references/controlled-crawl-plan.md) |
| Release integrity | The repository includes deterministic Skill archive build/verify/clean-install logic, plus separate gates that validate supplied PPTX visual-QA evidence and publish a verified candidate without clobbering protected inputs. | [release installation](skills/architectural-concept-design/references/release-installation.md) · [release packager](skills/architectural-concept-design/scripts/release_skill_package.py) |
| Regression and governance provenance | The source-development workflow uses Python evaluations, Node governance tests, strict preflight, repository checks, and GitHub Actions. Those development-only test and governance sources are intentionally absent from this public distribution. | [public-distribution manifest](PUBLIC-DISTRIBUTION-MANIFEST.json) |

## A local, traceable working route

The source-development workflow uses anonymous synthetic fixtures to test the
chain; they are examples of structure, **not** architectural conclusions to
reuse, and are intentionally absent from this public distribution. A real
project begins with human-provided material and retains its unknowns.

```text
1. Normalize the human brief.
2. Register sources and label evidence.
3. Record site, programme, relations, and constraints.
4. Write comparable hypotheses and genuinely different options.
5. Compare against explicit criteria.
6. Ask a human to select, reject, or revise.
7. Assemble and validate the state package.
8. Create only the handoff or deliverable that the available evidence authorizes.
```

For local development, the core deterministic checks use the pinned Python
environment:

```bash
uv sync --project skills/architectural-concept-design --frozen --group test

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/normalize_project_brief.py \
  <human-brief.json> --output <normalized-brief-ledger.json>

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/check_area_schedule.py \
  <area-schedule.json>

```

Development-only fixtures and evaluations are intentionally omitted from this
public distribution; the public package retains the deterministic local
operations shown above.

## Architectural specificity

PR0M3N4DE should avoid architectural clichés without architectural
consequences. “Respond to the site,” “create rich spatial layers,” “follow the
contours,” or “strengthen the relationship with nature” are intentions, not
enough information to test a design move.

Whenever an operation is described, it should be connected—where the evidence
allows—to a concrete chain:

```text
Evidence → Constraint → Operation → Consequence
```

For example, a site observation may lead to an access constraint, then to a
proposed split, terrace, or carved passage, with explicit circulation,
structure, landscape, programme, and trade-off implications. The repository
does not claim to automate that geometric work today; this is the standard of
architectural precision the future product should preserve.

## What PR0M3N4DE deliberately does not claim

- It does not verify a human-provided document merely because it was supplied.
- It does not turn an `ASSUMED`, `INFERRED`, or `PROPOSED` record into a
  `VERIFIED` fact.
- It does not make code-compliance, planning-permission, constructibility,
  cost, schedule, structural, fire-safety, or professional-approval claims.
- It does not scrape the web freely, bypass access controls, retain raw page
  content, download media, or use anti-bot evasion.
- It does not select a design option in place of a human.
- It does not make an editable PPTX, a visual-QA receipt, or a published file
  proof of design quality, authorship, rights clearance, legal compliance, or
  human approval.

## Experimental / partial

These parts exist only with the limits stated below. They should not be
represented as a complete autonomous design pipeline.

| Area | Current limitation |
| --- | --- |
| Design Operations and evolution | The repository records reasoning state, dependencies, stale state, and option-level `spatial_operation` descriptions. It does not yet provide a general state-to-state operation ledger, operation semantics, or geometry execution layer. |
| Runtime source observation | Access is registry-, plan-, runtime-, and human-confirmation-gated. It remains source-specific and fail-closed; the repository does not provide unrestricted discovery, search, or crawling. |
| External presentation rendering | The presentation handoff specifies a boundary to an independently pinned external renderer. That renderer is not bundled or invoked by the state-only handoff itself. |
| PPTX release gates | The gates validate an already-produced candidate and supplied render evidence. They do not generate architectural content, judge visual quality, or replace a human slide review. |
| Public distribution | This candidate PR0M3N4DE public export carries its own `LICENSE`, `NOTICE`, and deterministic export manifest. It is not itself a GitHub Release, repository-visibility change, or final publication authorization. |
| Case and media material | Local research and media policies are bounded by their ADRs. This candidate export enforces the policy to **exclude all third-party media**; it does not infer rights for any omitted content. |

## Future direction — not implemented

The public vision is a more legible design workspace, not an assertion that the
following systems already exist:

- a visual workspace in which every decision can be followed back through its
  evidence, assumptions, dependencies, and alternatives;
- a **Design Grammar** for describing and comparing spatial operations without
  collapsing them into stylistic labels;
- option evolution: explicit forks, revisions, rejected paths, and decision
  history rather than a single opaque “final answer”;
- a Design Operations vocabulary and records that bridge evidence, constraints,
  hypotheses, spatial transformations, consequences, and trade-offs;
- focused Domain Packs for selected building types, each with its own programme
  grammar, circulation grammar, spatial relationships, service logic, site
  logic, and evaluation criteria;
- geometry operations that translate a human-authored spatial proposition into
  inspectable diagrams and testable relationships;
- carefully bounded SketchUp MCP, Rhino, CAD, and BIM integrations that
  preserve the same evidence and human-decision boundaries;
- richer human review surfaces for comparison, uncertainty, and handoff.

The strategy is **domain depth before domain breadth**: deepen one beachhead
building type before widening scope. It is not a promise to train a separate
model for every building type. The intended sequence is shared foundation-model
APIs, structured output, deterministic tools, schema validation, retrieval,
domain rules, Domain Packs, evaluation, real user corrections, repeated failure
data, and fine-tuning only when justified. Premature training would only make an
undefined workflow's errors more stable.

Any one of these directions would require its own approved scope, contracts,
tests, and release review. None is enabled merely by appearing here.

## Who it is for

PR0M3N4DE is not a one-click answer generator for people with no design
judgment. It should amplify existing architectural judgment:

```text
Student → makes reasoning explicit
Young architect → accelerates analysis, comparison, and iteration
Experienced architect → project memory, consistency checking, and reasoning trace
```

The product should become more useful as the user's judgment improves, not
less. Today's GitHub/Codex/Skill form naturally serves AI-native architects,
architecture students, and developers; a future Web workspace could have a
broader audience, but is not implemented here.

## Future architecture — not implemented

```text
Architecture State
        ↓
Design Grammar
        ↓
Hypotheses
        ↓
Design Operations
        ↓
Options
        ↓
Human Decision
        ↓
Geometry Operations
        ↓
SketchUp / Rhino / CAD / BIM
```

This diagram is product direction only. It does not grant current support for
Design Grammar, Design Operations, Geometry Operations, or any authoring-tool
integration.

## Project map

```text
LICENSE                           # Apache-2.0 text for this public package
NOTICE                            # public-package notices
PUBLIC-DISTRIBUTION-MANIFEST.json # deterministic public export record

skills/architectural-concept-design/
├── SKILL.md                 # concise workflow and routing
├── references/              # contracts, schemas, and architectural guidance
├── scripts/                 # deterministic local operations
├── assets/                  # packageable local assets
├── pyproject.toml           # pinned Python runtime metadata (0.1.0)
└── uv.lock                  # locked runtime dependencies
```

The concise operational entry point is
[`skills/architectural-concept-design/SKILL.md`](skills/architectural-concept-design/SKILL.md).
Detailed rules belong in the linked references and scripts rather than in this
README.

## Development and release discipline

Before a source-development change is considered complete, the development
workflow expects strict preflight, repository checks, governance tests,
relevant Skill evaluations, clean diffs, and the applicable review/release
evidence. Development-only governance documents and test sources are
intentionally omitted from this public distribution; the retained release
installation boundary is documented in
[`skills/architectural-concept-design/references/release-installation.md`](skills/architectural-concept-design/references/release-installation.md).

The current repository package metadata is version `0.1.0`. Archive creation,
verification, and clean installation are deterministic local operations; a
release archive records its source commit, build time, manifest, and per-file
hashes. See
[`release_skill_package.py`](skills/architectural-concept-design/scripts/release_skill_package.py).

## Public-distribution intent

The intended public repository identity is **PR0M3N4DE**. For that future
distribution:

- **Code license:** The code included in this candidate export is accompanied by the canonical Apache-2.0 `LICENSE`. That license does not grant rights to excluded third-party content, project inputs, or generated deliverables.
- **Media policy:** exclude all third-party media from the public package.
- **Privacy boundary:** do not publish private project files, human-provided
  source material, credentials, local configuration, runtime receipts, or
  test-only fixtures as production examples.

## Naming transition to review later

This README intentionally makes no mechanical rename. A later, separately
reviewed migration should inventory at least:

1. the GitHub repository name, public URLs, release names, and issue/PR
   templates;
2. root package metadata (`package.json`) and any release/repository labels;
3. the Skill directory, `SKILL.md` frontmatter/name, `pyproject.toml`
   distribution metadata, and archive manifest `skill_id`;
4. documentation headings, cross-links, examples, and public installation
   instructions;
5. release artifacts, checksums, verification commands, and compatibility
   rules for already-installed `architectural-concept-design` Skills;
6. automation, governance, Feishu, and CI text that names the former project.

Renaming these identifiers is a compatibility and release decision, not a
cosmetic search-and-replace. It should preserve a clear migration path for
existing installs and recorded evidence.

---

PR0M3N4DE is a place to make architectural reasoning visible: not to make the
architect disappear, but to make the work of deciding easier to inspect,
challenge, and carry forward.

**Not only what architecture became, but how and why it became that way.**
