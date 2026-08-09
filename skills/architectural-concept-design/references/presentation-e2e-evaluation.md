# Presentation end-to-end evaluation

> **Single authority** for the fixed, local end-to-end evaluation from an anonymous synthetic brief through a validated state package, six runtime candidates, explicit human precedent selection, a presentation handoff, and (when supplied) an editable PPTX package. It does not search, fetch, install, invoke `ppt-master`, create a PPTX, or mutate an input.

## Contents

- [Purpose and fixed fixture boundary](#purpose-and-fixed-fixture-boundary)
- [1. Evaluation inputs](#1-evaluation-inputs)
- [2. Cross-package trace checks](#2-cross-package-trace-checks)
- [3. Renderer receipt and PPTX audit](#3-renderer-receipt-and-pptx-audit)
- [4. Outcomes and stop conditions](#4-outcomes-and-stop-conditions)
- [5. Command](#5-command)

## Purpose and fixed fixture boundary

This Phase 4 evaluator proves contract interoperability; it is not a design generator or a presentation renderer. The committed invariant fixture is anonymous and synthetic. It fixes these evaluation facts:

- exactly six `RC-xxx` runtime candidates;
- an explicit human selection of one to three candidates (the baseline selects `RC-001` and `RC-002`);
- an eleven-page `PH-xxx` deck framework; and
- only `team_original_diagram_only` local visual strategy.

Use the evaluator only after `scripts/validate_state.py validate`, `scripts/validate_runtime_candidates.py`, and `scripts/validate_presentation_handoff.py` pass for the same reviewed artifacts. It reads all supplied files without modifying them.

## 1. Evaluation inputs

The evaluator accepts four required local JSON files:

1. schema-valid input brief;
2. schema-valid output state package;
3. runtime candidate set; and
4. presentation handoff.

The state package remains the architectural authority. The candidate set remains the candidate-selection authority. The handoff remains an immutable pre-render plan: its `rendering_boundary` must continue to say `EXTERNAL_RENDERER_NOT_INVOKED` and all prohibited action flags must remain `false`.

`state_package.input_hash` is checked against ADR-0001 canonical input hashing. `state_package.output_hash` is checked against the evaluator's canonical output serialization: UTF-8 JSON, `ensure_ascii=false`, sorted object keys, compact separators, finite values only, and SHA-256. This gives a deterministic file-content identity without adding a new state-schema field.

## 2. Cross-package trace checks

The evaluation fails when any of these checks fails:

| Check | Required relationship |
| --- | --- |
| State | `validate_state.py validate` accepts the supplied input/output pair. |
| Candidate gate | Candidate set is schema-valid, has exactly six candidates, and records `HUMAN_SELECTED`; selection must identify a human and one to three existing IDs. |
| Selection transfer | Handoff run ID, registry version, selected ID order, selected names, locators, timestamps, operations, and visual strategies equal the selected candidate records. |
| State transfer | Handoff project ID and input/output hashes equal the supplied state package. |
| Architectural chain | Every carried `E/C/S/R/H/O/K-xxx` resolves in the supplied output package. |
| Design decision | Handoff remains `AWAITING_EXPLICIT_HUMAN_DESIGN_DECISION`; it must not bypass the state package with a deck-only `D-xxx`. |

The evaluator does not rank options, select an architectural option, create a `D-xxx`, register source evidence, or execute stale propagation.

## 3. Renderer receipt and PPTX audit

`ppt-master` is an independently installed, pinned Skill. The evaluator never calls its `SKILL.md`, bootstrap installer, shell commands, package manager, or network. If a reviewer supplies `--ppt-master-root`, the evaluator verifies only the local installation receipt:

- `.architecture-pre-design-external-dependency.json` exactly matches the `ppt-master` entry in `external-dependency-lock.json`;
- `SKILL.md` and `UPSTREAM_LICENSE` exist in that supplied root.

If a reviewer also supplies `--pptx`, the evaluator performs an OOXML package audit only. It requires the package to contain `ppt/presentation.xml`, exactly eleven slide XML parts, an editable native shape or graphic frame on each slide, and no external relationship target. This structural audit is not visual QA and does not prove that a particular renderer produced the file.

Do not pass a third-party image, downloaded media, source page, browser session, API response, or an automatically fetched case into this evaluator. A source locator is attribution only; it is never opened here.

## 4. Outcomes and stop conditions

| Outcome | Meaning |
| --- | --- |
| `HANDOFF_READY` | All four local contracts cross-validate. No renderer or PPTX was requested. |
| `PPTX_VALIDATED` | `HANDOFF_READY` plus a supplied locked renderer receipt and structurally editable, local eleven-slide PPTX. |
| `RENDERER_DEPENDENCY_UNAVAILABLE` | `--require-pptx` was requested but the supplied renderer receipt is unavailable or invalid. Stop; do not install automatically. |
| `PPTX_VALIDATION_FAILED` | A supplied PPTX is missing, malformed, contains external relationships, has a wrong slide count, or lacks editable shapes. Stop; do not repair or render automatically. |
| `CONTRACT_VALIDATION_FAILED` | Any upstream state, candidate, handoff, hash, or cross-package trace check failed. Stop and repair the authoritative input. |

## 5. Command

```text
uv run python skills/architectural-concept-design/scripts/evaluate_presentation_e2e.py \
  <input.json> <output.json> <candidate-set.json> <handoff.json>
```

For a supplied, independently rendered deck, add both local paths:

```text
uv run python skills/architectural-concept-design/scripts/evaluate_presentation_e2e.py \
  <input.json> <output.json> <candidate-set.json> <handoff.json> \
  --ppt-master-root <installed-ppt-master-directory> --pptx <editable-deck.pptx> --require-pptx
```

The command emits one machine-readable JSON result and writes no files.
