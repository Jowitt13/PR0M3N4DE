# Read-only checks for an ordinary D1 SVG

`scripts/check_concept_layout.py` reads an AI-authored rectangular working SVG,
reuses existing rectangle predicates and area calculation, prints JSON and exits
nonzero on failure. It never designs, moves blocks, rewrites sources or produces
a teaching state. No new solver, dependency or persistent state format is added.

## Supported slice

- SVG namespace, `data-unit="m"`, `viewBox="0 0 W D"` matching independently supplied
  layout width/depth. SVG y increases downwards. For northward-increasing brief
  coordinates, `svg_y = D - design_y - block_height`; explain the frame and north
  direction. Local drawing coordinates are not surveyed positions.
- Every checked block is an axis-aligned `<rect>` with stable `id`, numeric `x`,
  `y`, positive `width`/`height`, a name in `<title>`, and `data-role="space"` or
  `data-role="circulation"`. Use existing `S-xxx` space identifiers.
- Drawing-only rectangles can omit role; identified decorations can use
  `data-role="decoration"`. Required spaces cannot be disguised as decorations.
  Ordinary editable text/lines can show labels, dimensions, north and legend.
- Nested SVG viewports and `defs`, `symbol`, `clipPath`, `mask`, `marker`,
  `pattern` and `switch` containers are unsupported, even when empty. Transforms,
  `display`, `visibility` and `opacity` overrides (including inline CSS), CSS
  geometry, rounded checked blocks, indirect `use`, scripts,
  animation, external media, DTD and entities are unsupported and fail closed.
  Visibility overrides are rejected even for visible values; inline CSS comments
  and escapes are also rejected, including in otherwise harmless styles.
  Numbers must be finite metre coordinates within 1e9 in magnitude.

## Use and interpret the check

```text
python <skill>/scripts/check_concept_layout.py <project>/revision.svg --width 24 --depth 18 --required S-001,S-002
```

Use the available Python 3.13 interpreter. Ordinary use needs no source checkout.
Pass the complete actual required ID list and brief bounds, not requirements
invented from the candidate. The checker verifies coverage, finite dimensions,
bounds, positive-area overlap and each space's positive-length contact with real
traffic rectangles. It derives actual functional, circulation and unassigned
area and the existing area-schedule result from the SVG.

Compare individual areas against the brief's targets/ranges; a geometry PASS does
not establish those requirements automatically. Inspect labels/clipping and
architectural quality separately. Shared edges are not doors or verified access/
evacuation routes; net allocation is not gross building area.
The checker is not a renderer and does not certify that paint, colors or labels
are visible; review an actual rendered output separately.

Add `--expect-sha256 <recorded-sha256>` to bind the saved source. A mismatch returns
`CONCEPT_LAYOUT_SOURCE_CHANGED` and does not touch the file.

The typed Python entry also accepts `adjacent_pairs=[(first,second)]`,
`previous_svg=old_source` and `locked={space_id:["x","y","width","height"]}`.
Other arguments are `svg_source`, `container=(W,D)`, `required_spaces=[...]` and
optional `expected_sha256`. Pass only explicitly locked fields: a location-only
lock allows size changes. Missing previous source, unknown fields or missing
locked IDs fail rather than silently unlock. Bind the prior source hash in the
project record before comparison. Performance/quiet intent needs design review.

Use `source_sha256` for same-version tables and record bindings. Changed SVG bytes
require a new check and affected outputs; a failure preserves the last valid set.
Formal state/teaching keep their actual upstream gates. This check certifies no
authorship, regulatory/fire/structural/cost/construction conclusion, client
compatibility or real student use.
