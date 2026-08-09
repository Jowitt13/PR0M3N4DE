# Synthetic teaching presentation handoff

> **Single authority** for the `SYNTHETIC_NO_PRECEDENT_DEMO` teaching route
> accepted by ADR-0008. This contract is deliberately incompatible with the
> real-project [presentation handoff](presentation-handoff.md).

## Preconditions

Use this route only for an explicit human-confirmed fictional exercise. The
same run needs a schema-valid input/output state pair accepted by
`validate_state.py validate`, one explicit human `D-xxx` selection recorded in
that output state, and all three labels:

- `HUMAN_AUTHORIZED_ASSUMPTION`;
- `DEMO_ONLY`; and
- `NOT_A_REAL_SITE_OR_BUILDABILITY_CONCLUSION`.

`UNKNOWN` stays visible. It is not converted into `PROVIDED`, `VERIFIED`, or a
real-world claim.

## Contract boundary

Use [synthetic-teaching-presentation-handoff.schema.json](synthetic-teaching-presentation-handoff.schema.json)
and validate the result with:

```text
scripts/validate_synthetic_teaching_presentation_handoff.py <handoff.json>
```

The handoff is local and versioned. It transfers only validated state hashes,
allowed state IDs, the human design decision, the teaching labels, unresolved
input names, concise team-authored page purposes, and team-original vector
diagrams. It must never carry `RC-xxx`, `RCR-xxx`, `SRC-xxx`, `E-xxx`, source
locators, URLs, third-party media, media authorization, copied source text, or
`VERIFIED` claims.

## Eight-page teaching framework

The framework has exactly eight ordered pages: teaching boundary; assumed
brief; program; assumed spatial relationships; options; human-selected option;
unresolved inputs; and teaching next actions. Every page visibly says
`TEACHING DEMO — NOT A REAL PROJECT VALIDATION` and uses only
`team_original_vector_diagram_only` visuals.

## Renderer and output boundary

`render_synthetic_teaching_pptx.py` validates this handoff, verifies the local
locked `ppt-master` receipt, authors only local SVG vector pages, and invokes
the locked exporter. It neither searches, fetches, installs, adds sources,
changes quantities, resolves unknowns, or changes the human decision.

Rendering and structure checks run in a short-path temporary staging area outside the requested
output directory; only after every check passes are the deck, manifest, and report atomically
delivered to the final directory, and a failed run leaves no half-finished artifacts behind.

The resulting deck is a teaching-chain artifact only. Its manifest, every
slide, and its validation report retain all three labels. The deck must have
eight native editable slides, no macros, no external OOXML relationship, no
third-party media, and no remote asset.
