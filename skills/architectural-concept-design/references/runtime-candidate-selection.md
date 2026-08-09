# Runtime candidate cards and human selection

## Purpose and authority

This reference implements the six-candidate and one-to-three human-selection gates in ADR-0005 §§1–2. The machine contract is [runtime-candidate-card.schema.json](runtime-candidate-card.schema.json); the deterministic local check is `scripts/validate_runtime_candidates.py`.

It governs an ephemeral per-project research set. It is not a `CARD-xxx` entry, does not amend the ADR-0003 eight-field built-in card contract, and does not place a source in the local case corpus.

## Preconditions

Before creating any runtime candidate record:

1. Complete the brief/evidence ledger.
2. Read `source-access-registry.json` and `runtime-source-access-gate.md`.
3. Run `scripts/check_source_access.py <request-plan.json>`.
4. Make an automated request only after its local result is `REQUEST_READY`.

This reference and its validator never make a network request. They cannot authorize Firecrawl, Scrapling, browser impersonation, redirects, HTML extraction, media download, asset scraping, bulk download, anti-bot bypass, or any unregistered source.

## Candidate-card boundary

- Use `RC-xxx` for runtime candidates and `RCR-xxx` for the finite run. Never use `CARD-xxx`.
- A candidate is an unselected, provisional research record. It is not an ADR-0001 `SRC-xxx` or `E-xxx` object, and it must not contain an ADR-0001 evidence label.
- Keep the exact registry version, registered domain, registered access method, canonical locator, and RFC 3339 access time.
- `structured_metadata_only` records require the actual `REQUEST_READY` gate result and its non-secret `gate_receipt`: registered operation, endpoint, and JSON response kind only. The receipt must not contain query values, request bodies, credentials, provider content, or media locators. `manual_title_and_locator_only` records use `MANUAL_ONLY`, preserve only a manually supplied title and locator, set `gate_receipt` to `null`, and set `spatial_operation` to `null`.
- A non-null spatial operation is a team-authored candidate hypothesis. It must give preconditions, expected effects, limitations, and a falsification condition. It is not copied source text, a source claim, or a VERIFIED conclusion.
- Use `team_original_diagram_only` as the visual strategy. Do not embed, download, package, or render third-party media at this gate.

## Six-candidate gate

Return no more than six conforming candidates.

- When six conforming candidates are available, return exactly six and omit `insufficiency_report`.
- When zero through five conforming candidates are available, return only those candidates and include an `insufficiency_report` whose `available_count` is exact, `no_fabrication` is `true`, and next actions remain within the source-access policy.
- Never pad the set, invent a project, reuse the same candidate under a second `RC-xxx`, or convert a local corpus card into a runtime candidate.

Candidate relevance must state project-brief-linked reasons. Search rank, popularity, publication, visual similarity, or source reputation is not an architectural-quality score.

## Explicit human selection gate

Present the validated set with `selection.state: AWAITING_HUMAN_SELECTION`. Do not transfer a candidate operation into the architectural chain while this state remains.

After a person makes an explicit choice, replace that state with `HUMAN_SELECTED` and record:

- one to three unique IDs from the presented `RC-xxx` set;
- a non-agent human-record label in `selected_by`;
- an RFC 3339 timezone-qualified `selected_at`; and
- `selection_method: explicit_human_selection`.

The model must not select, rank, recommend as a decision, or infer this field. The validator rejects unknown IDs, zero or more than three selections, duplicate selections, and model/agent identities as the selector.

Only after this gate may a later task register sources and used claims in the ADR-0001 state package as `SRC-xxx` and `E-xxx`, subject to the state contract. Selection alone does not make a source claim VERIFIED and does not grant media rights.

## Validation and stop boundary

Run:

```text
uv run python skills/architectural-concept-design/scripts/validate_runtime_candidates.py <candidate-set.json>
```

The validator is deterministic and read-only: it reads the fixed in-package Schema and source registry, emits machine-readable JSON, and never writes the candidate set, changes the registry, or performs I/O beyond local reads.

Stop and report the returned errors if the candidate set, registry trace, six-candidate rule, insufficiency report, or human-selection rule is invalid. This task does not implement discovery clients, persist runtime data, register `SRC-xxx`/`E-xxx`, transfer operations, create a presentation handoff, install external Skills, or generate a PPTX.
