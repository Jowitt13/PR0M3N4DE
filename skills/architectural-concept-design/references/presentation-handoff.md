# Presentation handoff and fixed deck framework

> **Single authority** for the local handoff package prepared after human precedent selection and before a separately installed presentation renderer. This reference defines traceable content, a fixed deck framework, and renderer boundaries. It does not install or invoke `ppt-master`, access any network source, download media, create a PPTX, or alter the architectural state package.

## Contents

- [Purpose and prerequisites](#purpose-and-prerequisites)
- [1. Authority and input boundary](#1-authority-and-input-boundary)
- [2. Precedent-selection gate](#2-precedent-selection-gate)
- [3. Handoff package contract](#3-handoff-package-contract)
- [4. Fixed deck framework](#4-fixed-deck-framework)
- [5. Local visual assets](#5-local-visual-assets)
- [6. Human design decision request](#6-human-design-decision-request)
- [7. Renderer boundary and stop condition](#7-renderer-boundary-and-stop-condition)

## Purpose and prerequisites

Prepare a local JSON handoff only after these prerequisites are available for the same project state:

1. a state package that passes `scripts/validate_state.py validate`;
2. a runtime candidate set that passes `scripts/validate_runtime_candidates.py`; and
3. an explicit human selection of one to three `RC-xxx` candidates.

The handoff is a presentation plan, not a new architectural authority. Its IDs must point to the already validated output package and the human-selected runtime candidates. It must not reclassify evidence, replace source registration, turn a team-authored operation into a source claim, or create a `D-xxx` decision.

## 1. Authority and input boundary

Use [presentation-handoff.schema.json](presentation-handoff.schema.json) for the handoff JSON and run:

```text
scripts/validate_presentation_handoff.py <handoff.json>
```

The validator is deterministic and read-only. It validates the handoff alone; it neither reads project files beyond its bundled Schema nor verifies that an external source is still available. `state_package.input_hash` and `state_package.output_hash` identify the reviewed state without inserting absolute local paths, private source responses, API keys, or renderer output.

The authoritative architectural content remains in `output.schema.json` and the upstream state package. Carry only existing `E-xxx`, `C-xxx`, `S-xxx`, `R-xxx`, `H-xxx`, `O-xxx`, and `K-xxx` IDs into the handoff. Never add free-text evidence labels to those entities.

## 2. Precedent-selection gate

The package requires one to three selected `RC-xxx` IDs. It must retain the runtime `candidate_run_id` (`RCR-xxx`) and source-registry version, then record all four fields from the runtime human-selection gate:

- `selection_method: explicit_human_selection`;
- a real human `selected_by` value;
- RFC 3339 `selected_at`; and
- matching `selected_candidate_ids` and `selected_precedents` records.

Each selected record retains a locator and retrieval time for attribution, but its `spatial_operation` remains a `team_authored_candidate_hypothesis`. It is not copied source text, a `VERIFIED` claim, a local `CARD-xxx`, or a media permission. Use only `team_original_diagram_only` visuals in this task.

Do not make this handoff while the candidate set says `AWAITING_HUMAN_SELECTION`. Do not let an agent, model, `Codex`, `DeepSeek`, or `ppt-master` appear as the selector.

## 3. Handoff package contract

Populate these sections exactly once:

| Contract area | Required content | Boundary |
| --- | --- | --- |
| Identity | `PH-xxx`, `P-xxx`, RFC 3339 creation time | No absolute path or generated PPTX path. |
| State reference | input/output SHA-256 and validation time | Does not replace or mutate the state package. |
| Selected precedents | one to three human-selected `RC-xxx` records | Locator is attribution, not a license or live-fetch instruction. |
| Architectural chain | existing E/C/S/R/H/O/K IDs plus pending design-decision state | Do not manufacture a `D-xxx`. |
| Deck framework | the eleven ordered pages below | Do not reorder, add, or remove pages. |
| Local assets | optional, relative, team-authored diagram paths only | No remote URL, source image, drawing, quotation, or downloaded media. |
| Rendering boundary | explicit no-install/no-network/no-PPTX flags | Keeps `ppt-master` independent until a later install task. |

## 4. Fixed deck framework

Use the following ordered pages. Every page names at least one existing entity ID, supplies a concise purpose and speaker note, and uses `team_original_diagram_only`.

| Order | Page ID | Required trace focus |
| --- | --- | --- |
| 1 | `P-01-cover` | project identity and one selected `RC-xxx` |
| 2 | `P-02-brief-evidence` | existing `E-xxx` brief evidence and uncertainty |
| 3 | `P-03-precedent-selection` | selected `RC-xxx` and explicit human selection |
| 4 | `P-04-precedent-operations` | selected `RC-xxx` team-authored spatial operation |
| 5 | `P-05-site-context` | existing `C-xxx` site constraint |
| 6 | `P-06-program-circulation` | existing `S-xxx` and `R-xxx` |
| 7 | `P-07-grid-core-height` | existing `H-xxx` hypothesis |
| 8 | `P-08-concept-directions` | at least two existing `O-xxx` options |
| 9 | `P-09-option-comparison` | existing `O-xxx` and `K-xxx` criteria |
| 10 | `P-10-human-decision-request` | existing `O-xxx` and `K-xxx`; no pre-filled `D-xxx` |
| 11 | `P-11-sources-risks-next-actions` | existing `E-xxx`, selected `RC-xxx`, risks, and next actions |

The framework supports a human review narrative. It does not score, rank, recommend, or automatically select concept options. Page 10 is an explicit stop point for a human design response (`select`, `revise`, `request-new`, or `defer`).

## 5. Local visual assets

An optional `local_assets` entry may point only to a project-relative `team_original_diagram` associated with a selected `RC-xxx`. Do not use a drive path, parent-directory traversal, HTTP(S) URL, a third-party photo, an externally sourced drawing, or a copied quotation. Keep source locators in the selected-precedent attribution record rather than the asset path.

## 6. Human design decision request

The presentation may frame the option comparison and ask the human to decide. Until the human gives an explicit response, set `decision_request_state` to `AWAITING_EXPLICIT_HUMAN_DESIGN_DECISION` and do not place a `D-xxx` identifier in the handoff. After a real human decision, update the validated architectural state package first; do not bypass `output.schema.json` with deck-only decision data.

## 7. Renderer boundary and stop condition

This contract finishes at an `EXTERNAL_RENDERER_NOT_INVOKED` handoff for `ppt-master`. It must assert all of the following as `false`: `pptx_generated`, `installation_attempted`, `network_accessed`, `third_party_media_packaged`, and `web_application_created`.

Installing, pinning, updating, or invoking `ppt-master`; producing an editable PPTX; downloading or embedding third-party media; browsing source locators; creating a Web application; and packaging or release verification remain separate reviewed tasks. This contract does not authorize any of them.
