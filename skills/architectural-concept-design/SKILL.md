---
name: architectural-concept-design
description: Help architecture students analyze supplied precedents, prepare fieldwork, synthesize site records, develop architectural concepts or deepen an adopted design. Use for new-build, renovation and mixed projects needing traceable spatial reasoning, program and area checks, alternatives and human design decisions.
---

# Architectural Concept Design

Help the student do the architectural work requested now: study a precedent, prepare or interpret research, propose a concept, or deepen an adopted direction. Produce something they can draw from, revise, or discuss. The human designer makes the final design decisions.

## Start with the current request

Read the request and accessible project material. Identify the immediate question, desired result, whether the project is new construction, renovation or mixed, and what information affects this work. These distinctions are not a menu, a new task file, or forms for the student to complete.

An assignment's eventual full-design requirement does not override a request to study one case today. Reuse material already provided. Ask only consequential questions, at most three together, and continue the parts not dependent on answers. Do not demand budgets, opening dates, JSON or all formal ledgers for an unrelated task.

For “I don't know where to start”, use [brief-analysis.md](references/brief-analysis.md): explain the assignment in architectural language, separate known conditions from immediate gaps and later questions, suggest a worthwhile small task, and begin its first draft where possible. Missing dimensions can prevent a measured plan without preventing functional relationships or research preparation.

Read only the references needed now. These are independent entry points, not sequential gates.

| Current work | Reference | Useful completion point |
| --- | --- | --- |
| Understand a brief / first step | [brief-analysis.md](references/brief-analysis.md) | Task, consequential gaps, first useful work |
| Analyze a supplied/selected precedent | [concept-options-and-decisions.md](references/concept-options-and-decisions.md) | Spatial operations, source/interpretation, transfer conditions and costs |
| Prepare fieldwork / synthesize records | [site-context-analysis.md](references/site-context-analysis.md) | Executable visit plan or traceable analysis and follow-up |
| Organize functions, areas and circulation | [program-area-and-circulation.md](references/program-area-and-circulation.md) | Checked quantities, adjacencies and movement |
| Generate or deepen a concept | [concept-options-and-decisions.md](references/concept-options-and-decisions.md); [grid/core/height](references/grid-core-height-hypotheses.md) when needed | Drawable relationships and trade-offs |
| Compare, revise or adopt parts | [option-comparison-decision-handoff.md](references/option-comparison-decision-handoff.md) | Comparison and a coherent revision preserving actual choices |

[output-contract.md](references/output-contract.md) distinguishes task delivery from formal-package assembly. Ordinary work can finish as a reply, editable report, record table or diagram. Generate files when useful or requested, not empty boilerplate or a state package merely to finish a case study.

## Make the architectural content specific

New construction relates site conditions to program, entry, circulation, volume and space. Renovation identifies existing objects, the source/certainty of retention requirements, candidate interventions, functional fit and old/new interfaces. Mixed projects need both object sets and their shared access, spaces or services. A “new-build” label cannot erase a retention requirement. The research and working-concept references explain these differences.

The model may propose, compare, recommend with reasons and deepen architectural ideas. Adapt quantity, structure and expression to the request; do not invent scores. Distinguish alternatives through placement, massing, organization, circulation, structure, sequence or environmental response, not names, colors or materials alone. Aesthetic/spatial-experience discussions are allowed; they do not prove dimensional fit or engineering performance.

Use [brief-and-evidence.md](references/brief-and-evidence.md) to distinguish `PROVIDED`, `VERIFIED`, `INFERRED`, `ASSUMED`, `PROPOSED`. Prose can show sources and conditions readably; structured Source/Evidence records still obey [evidence.schema.json](references/evidence.schema.json) exactly. Never invent sources, surveyed dimensions, regulatory permission, buildability or verification.

Use [area-schedule.schema.json](references/area-schedule.schema.json) and `scripts/check_area_schedule.py` for area totals. Show quantities, units and sources. Check other arithmetic explicitly, including site area and a supplied floor-area ratio; its counting rule is a stated premise, not planning approval. Missing geometry calls for relationships, not a pretend measured site plan. Treat grids, cores and heights as revisable hypotheses; photographs cannot establish safe demolition or structural safety.

## Continue after a human revision

Reuse the current materials and latest draft. For “entrance from A, reading spaces from B, no canopy, everything else pending”, adopt only those named parts, reject the canopy and keep the rest pending. Recheck the combination's access, adjacencies and area conflicts before deepening; a simple splice is not proof it works. Do not mark all of A/B selected or restart an option competition by default.

Bind the actual instruction to the specific draft/version in existing reports or project records, without a second fact store. When an area or retention condition changes, identify affected calculations, arrangements, diagrams and text, retain unaffected research, and update the requested work. Registered state uses the existing [maturity/staleness](references/design-data-maturity-and-staleness.md) tools. Unregistered prose must list needed revisions; do not claim machine freshness, automatic propagation or edits not performed.

Human adoption of an AI-authored draft is not human authorship. Ordinary work does not need a signature for every file. Formal persistence follows the applicable Decision path below, without invented upstream objects or false human-authored declarations.

## Formal state and guided teaching are explicit paths

Formal-ledger prerequisites, stage boundaries, quantities and mappings govern their named records, not every working sketch. Do not loosen a validator or turn a formal assessment into an automatic decision.

- For an explicitly requested normalized thirteen-field ledger, read [normalized-brief-ledger.md](references/normalized-brief-ledger.md) and use `scripts/normalize_project_brief.py`. It records field status, not design; `PROVIDED` is not `VERIFIED` evidence.
- For a formal full-chain package, read [output-contract.md](references/output-contract.md), [input.schema.json](references/input.schema.json) and [output.schema.json](references/output.schema.json). When a normalized ledger is used, run `scripts/build_normalized_brief_human_assembly_handoff.py` as described in [human-authored draft gate](references/human-authored-project-state-draft.md). Its chapters must actually be human-authored; no agent may fill its chapters or make false attestations. Then `scripts/validate_human_authored_project_state_draft.py` checks the declaration and supplied documents without generating a state package. If that route cannot represent adoption of an AI draft, explain the limitation and continue ordinary work without claiming a formal package exists.
- The normalized-brief handoff is not a direct assembly input. Once its prerequisites are met, [project-state-assembly.md](references/project-state-assembly.md) routes to `scripts/assemble_project_state.py`, which copies supplied content and computes bindings, not design. Run `scripts/validate_state.py validate <input.json> <output.json>` before claiming formal validation. Explicit changes use `propagate-stale` with the supplied event/time and a new output package, never a system-clock event or overwriting the validated source.
- For user-selected guided teaching read [student-workflow-routing.md](references/student-workflow-routing.md). Its builders validate/project human-written designs, with no automated design. Confirmed-state choices use [student-guided-decision-interaction.md](references/student-guided-decision-interaction.md); its card and selection requirements remain intact. This is not the default route for all work.

## Precedent access and media

Analyze supplied material directly with its provenance/limitations. [attribution-only-case-cards.json](references/attribution-only-case-cards.json) contains local attributed prompts, not VERIFIED facts or runtime evidence; do not follow its source links merely to display cards. Notes/visuals use [case-research-supplements.md](references/case-research-supplements.md), [case-card-presentation.md](references/case-card-presentation.md) and [case-media-assets.md](references/case-media-assets.md) when needed. Never add media to the eight-field card or fetch a source at render time.

New external research requires the [source registry](references/source-access-registry.json) and [source-access gate](references/runtime-source-access-gate.md) before requests; unregistered domains are blocked. Controlled access additionally requires the exact [crawl plan](references/controlled-crawl-plan.md) and [live transport](references/controlled-crawl4ai-live-transport.md) contracts, current human confirmation, robots/path/budget checks and explicit execution flags. A local PASS or installed runtime is not access permission. On denial, login, paywall, CAPTCHA, 401/403/429 or an out-of-scope redirect, stop that source. Never bypass access controls with stealth, impersonation, proxies, custom/random user agents, cookies, injected scripts, fallback fetchers, CAPTCHA/Cloudflare solving or `curl-impersonate`.

The formal [runtime discovery](references/runtime-candidate-selection.md) chain retains six conforming candidates when available (otherwise an insufficiency report), validation and human selection of one to three before transfer. Its [selection handoff](references/runtime-candidate-selection-handoff.md) creates no evidence and cannot unlock transfer alone. Do not impose that chain on an already supplied single case. Per-run third-party media never enters the corpus or a release package; human publishability confirmation is not a license or VERIFIED rights.

## Optional diagrams and presentation

Editable diagrams use [svg-dual-asset-pipeline.md](references/svg-dual-asset-pipeline.md): editable text source, audit, compiled glyph paths, preview and manifest. Report renderers actually checked; untested Microsoft PowerPoint or Qwen Office compatibility is not verified.

PPT, WPS round-trip, presentation usability and Human Pilot are optional/experimental and non-blocking. Normal architectural work needs no deck, rehearsal, client installation or Human Pilot approval. Explicit presentation work uses [presentation-handoff.md](references/presentation-handoff.md) and [audience-copy-contract.md](references/audience-copy-contract.md); that deck's review, freshness and DELIVERY rules still apply. The [state-only](references/state-only-presentation-handoff.md) and [synthetic teaching](references/synthetic-teaching-presentation-handoff.md) routes keep separate gates. External `ppt-master` handles layout, not changes to sources, quantities or decisions. ADR-0007's [media contract](references/user-authorized-presentation-media.md) records direction, not a license/access permission; validate already-local records only until all activation gates exist. Engineering checks are not Human Pilot execution.

Install external tools only on an explicit request through the reviewed-plan [dependency bootstrap](references/external-dependency-installation.md); ordinary use never triggers extra installation or a crawler environment.

## Maintainer operations

[release-installation.md](references/release-installation.md) is the archive/checksum/isolated-install contract. The archive does not install or invoke external sibling Skills. Temporary verification is not release authorization. Final PPTX publication uses source-repository maintenance contract `docs/standards/verified-pptx-release.md` and repository-root `node scripts/release-verified-pptx.mjs --request <request.json>`. These maintainer resources are absent from an installed Skill; ordinary design work needs no source checkout. Do not invent an installed wrapper or claim an unavailable command ran.

Keep landscape as architectural context only. Standalone landscape/interior/exhibition work, construction documents, authoritative code approval, structural construction calculations and professional approval are outside this Skill.
