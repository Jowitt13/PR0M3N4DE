# State-only presentation handoff

Use this route only when a validated **real-project** state package already
records exactly one explicit human `D-xxx` selection, but no valid reviewed
runtime-candidate (`RC`/`RCR`) set is available. It is a bounded local fallback
under ADR-0005; it does not loosen the ordinary
[presentation handoff](presentation-handoff.md).

## What it permits

- Transfer only IDs and supplied project-state content needed to frame a
  team-original concept presentation.
- Carry an optional local, team-original diagram record bound to an existing
  `A-xxx` deliverable by relative path and SHA-256.
- Hand an independently installed renderer a ten-page framework after the
  later rendering boundary has separately been authorized.

## What it never permits

- Creating, inferring, or substituting `RC`, `RCR`, `SRC`, source locators,
  URLs, `VERIFIED` claims, external precedent operations, or third-party media.
- Treating state-only validation as a source/evidence, rights, licensing,
  visual-quality, regulatory, constructibility, or human-approval conclusion.
- Installing or invoking `ppt-master`, producing a PPTX, opening a browser,
  or accessing a network.

## Required input and validation

Run `scripts/build_state_only_presentation_handoff.py` only with an input/output
pair that passes `validate_state.py`. The builder refuses stale state, absent
evidence/constraints/spaces/hypotheses/options/criteria/deliverables, an absent
or non-human explicit decision, a decision that does not resolve to a state
option and criteria, or a malformed timestamp. It computes state hashes itself;
callers do not supply them.

The output must conform to
[state-only-presentation-handoff.schema.json](state-only-presentation-handoff.schema.json)
and pass `scripts/validate_state_only_presentation_handoff.py`. Its ten pages
are fixed as `SOP-01` through `SOP-10`, and each must visibly state:

`STATE-ONLY HANDOFF — NO EXTERNAL PRECEDENT OR THIRD-PARTY MEDIA`

Use `team_original_diagram_only` as the only visual strategy. `local_assets`
may be empty. If non-empty, every record must be a safe relative local path,
an SHA-256, and a reference to a listed state `A-xxx` deliverable.

## Boundary to later rendering

This is a handoff only. A valid result sets renderer, network, external
precedent transfer, third-party media packaging, and PPTX generation to false.
It cannot by itself authorize renderer installation, file access, or release.
