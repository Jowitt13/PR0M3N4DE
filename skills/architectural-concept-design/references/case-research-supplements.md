# Case Research Supplements

> **Single authority** for reading the ADR-0004 research note beside an existing attribution-only case card. It does not alter the eight-field card or create runtime evidence.

## Use and authority

Read `attribution-only-case-cards.json` first, then read `case-research-supplements.json` only when a user asks to inspect an audit note, a possible correction, or a linked source page for one existing `CARD-xxx`.

- The card JSON remains the sole published card record and has exactly eight fields.
- Each supplement is a separate review record keyed by one existing `card_id`.
- `review_status` is always `agent_checked_needs_human_confirmation`; it is not an ADR-0001 evidence label and does not make a source claim VERIFIED.
- A non-null `proposed_operation_summary` is a team-authored proposal only. Do not change the card until a human curator confirms it in a separately reviewed change.
- Register a source as `SRC-xxx` and a claim as `E-xxx` only inside a concrete runtime state package. The static supplement never substitutes for that registration.

## Data contract

The root object in `case-research-supplements.json` contains `format`, `card_source`, and `supplements`. Every supplement contains exactly:

| Field | Rule |
| --- | --- |
| `card_id` | An existing `CARD-xxx` in the local card set. |
| `reviewed_source_locator` | One individually reviewed page; it may be more direct than the card attribution link. |
| `reviewed_source_accessed_on` | Calendar date of the manual review in `YYYY-MM-DD`. |
| `fact_note` | Concise, original team paraphrase relevant to the card operation. |
| `review_status` | Exact value `agent_checked_needs_human_confirmation`. |
| `proposed_operation_summary` | `null`, or a concise team-authored replacement proposal awaiting human confirmation. |

## Boundaries

- Do not add a ninth field to any `CARD-xxx` object.
- Do not copy a source description or add a quotation in this v1 review set.
- Do not package, embed, cache, or thumbnail source photographs or drawings here. A media-selection task must apply ADR-0004's individual-selection gate separately.
- Do not browse, query, or re-check a source merely to render or use a card. This file records a completed manual review; it is not a runtime research workflow.
