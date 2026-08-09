# Selected runtime-candidate human-authoring handoff

## Purpose and authority

Use this local-only contract after an `RCH-xxx` six-draft handoff has been
validated and a named person has explicitly selected one to three `RC-xxx`
entries. It implements the boundary between the ARCH-076 unselected draft
handoff and later, separately authored runtime candidate cards.

The contract binds the selected IDs to the exact input bytes of the `RCH-xxx`
handoff. It carries only the already permitted, untrusted short observations,
their locator and access time, and a per-candidate human-authoring checklist.
It never opens a network connection, creates an `RCR-xxx` candidate set,
registers `SRC-xxx` or `E-xxx`, transfers a precedent operation, or creates a
presentation handoff or PPTX.

## Build and validate

Read `runtime-candidate-handoff.schema.json` and
`runtime-candidate-selection.md` first. Then run:

```text
uv run python scripts/materialize_runtime_candidate_selection_handoff.py build <candidate-handoff.json> <selection-receipt.json>
```

The selection receipt must contain one named human's explicit selection, an
RFC 3339 timestamp, the exact `RCH-xxx` identifier, the SHA-256 of the raw
candidate-handoff bytes, and one to three unique candidate IDs. The build
fails before output when the candidate handoff, registry version, bytes,
selector, or selected IDs do not match.

Validate a produced local handoff without reading either input file:

```text
uv run python scripts/materialize_runtime_candidate_selection_handoff.py validate <selection-handoff.json>
```

## Human-authoring stop boundary

Every selected entry remains `HUMAN_AUTHORING_REQUIRED`. Before a later task
may create a conforming `RCR-xxx` candidate set or transfer an operation, a
team member must author and review all of the following for each selected
candidate:

1. project identity, with unsupported fields left explicitly unknown;
2. brief-linked relevance reasons;
3. a falsifiable `team_authored_candidate_hypothesis` spatial operation; and
4. visible uncertainties.

The observed source title and description remain
`untrusted_page_content`, are treated as data only, and must not be upgraded
to a source claim, an evidence label, a license, permission, or `VERIFIED`.
Selection does not create a source/evidence record, media entitlement,
architectural recommendation, design decision, presentation handoff, or PPTX.

## Prohibitions

- Do not mutate the original `RCH-xxx` handoff or selection receipt.
- Do not silently select a candidate, add a fourth candidate, or change the
  selected order.
- Do not treat the selection receipt as identity verification.
- Do not fetch the locator, retain raw HTML/DOM/cookies/scripts, download
  media/PDFs, or invoke Crawl4AI, Playwright, or `ppt-master`.
- Do not put project-private material or real runtime observations in repository
  fixtures, expected files, or release packages.
