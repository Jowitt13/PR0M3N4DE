# Attribution-only Case-card Presentation

> **Single authoritative source** for turning one existing ADR-0003 attribution-only simplified card into a local editorial HTML or PNG presentation. It may place one already-selected local asset beside the card; it does not alter a card, research its source, or create a research supplement.

## Inputs and authority

Read `attribution-only-case-cards.json` before presenting a card. The card input is exactly one existing `CARD-xxx` object and only its eight fields:

`card_id`, `building_name`, `source_locator`, `source_accessed_on`, `attribution_mode`, `content_origin`, `operation_summary`, and `building_tags`.

Keep the card JSON as the only authoritative card record. A rendered HTML file or PNG is a derived, local presentation artifact; it must not add a field, correct a fact, or become runtime ADR-0001 evidence. When a local visual is requested, read [case-media-assets.md](case-media-assets.md) and its manifest separately; the manifest is an asset-selection record, not card data.

## Rendering boundary

- Select one existing card by `card_id`; do not invent cards or collect another source.
- Preserve `building_name` as the title and display `operation_summary` verbatim as the team's original abstraction.
- Display `building_tags` as local filtering labels, not as factual assertions.
- Display `source_locator` as a visible attribution link and `source_accessed_on` as its supplied calendar date. Do not open, follow, query, or validate the link while rendering.
- Escape all substituted text and URLs before inserting them into HTML. Render tags as separately escaped text nodes.
- Do not add quotations, source descriptions, research notes, `SRC-xxx`, `E-xxx`, evidence labels, a permission claim, or a static `VERIFIED` status.
- Do not add a photograph, drawing, image URL, iframe, remote stylesheet, remote font, script, fetch call, crawler, database, Web interface, or API to the card object.
- An already-selected local asset may be rendered only through the local `case-media-manifest.json` mapping. Do not open, follow, query, or validate its source while rendering.

ADR-0004 research supplements remain separate records. They may be created only in their own reviewed task and never expand this eight-field visual input contract.

## Editorial layout

Use the repository-owned [3:4 template](../assets/attribution-only-case-card-3x4.html) for the default portrait card. If a local asset is selected, substitute its local package path and team-authored alt text into `{{media_asset_path}}` and `{{media_alt_text}}`.

- Canvas: `1500 x 2000` pixels (`3:4`).
- Style: calm hybrid editorial / Swiss-international hierarchy, warm paper ground, one strong title zone, one primary operation module, and lighter tag and attribution bands.
- Density: medium. The title, original operation summary, tags, and attribution have distinct visual weights; do not turn them into equal tiles.
- The large background identifier is decorative only. It must not obscure the title or body copy.
- Keep the HTML screenshot-ready at the fixed canvas size and readable at narrow widths through the template's media fallback.

## Local infocard tool

`editorial-card-screenshot` from `shaom/infocard-skills` is an optional local rendering aid. Its MIT-licensed editorial workflow informed this template's density, hierarchy, ratio, and screenshot checks; it is not bundled into this Skill and is not a runtime dependency.

When that local tool is installed, give it the selected card's eight fields and, only when present, the separate local asset mapping. Use these constraints:

```text
Create one 3:4 editorial HTML card from this existing attribution-only CARD-xxx.
Use the supplied building_name unchanged as the title and operation_summary unchanged as the body.
Include tags and a visible source_locator attribution line with source_accessed_on.
Do not browse, follow the source link, fetch media, add a quote, add facts, or imply permission or VERIFIED status.
If a supplied local media mapping exists, use only its local asset path and alt text; do not add any other image.
Use local fallbacks; do not depend on remote fonts.
```

Use the template when the external local tool is unavailable. A local browser may capture the resulting self-contained HTML as PNG, but do not commit generated previews unless a later task explicitly defines a generated-artifact contract.

## Completion check

Before returning a presentation, verify that:

1. The selected `CARD-xxx` still has exactly eight fields.
2. The title, summary, tags, source locator, and supplied date map directly to those fields.
3. No source link was opened; any media came only from the separate local manifest and no quotation was added.
4. The output contains no evidence label, runtime identifier, permission claim, or new card field.
5. The fixed 3:4 composition has no cropped text, overlapping modules, or unexplained blank region.
