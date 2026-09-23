# SVG dual asset pipeline

> **Single authority** for editable SVG source, compiled SVG, preview PNG,
> and the diagram manifest that binds them. This reference defines the
> source-before-compile order, scale semantics, cross-renderer visual QA,
> and the stable machine-readable error codes. It is additive to ARCH-122
> audience-copy rules and never replaces them.

## Contents

- [Purpose](#purpose)
- [1. Four asset roles](#1-four-asset-roles)
- [2. Pipeline order](#2-pipeline-order)
- [3. Editable SVG source contract](#3-editable-svg-source-contract)
- [4. Compiled SVG contract](#4-compiled-svg-contract)
- [5. Scale semantics](#5-scale-semantics)
- [6. Manifest contract](#6-manifest-contract)
- [7. Visual and cross-renderer QA](#7-visual-and-cross-renderer-qa)
- [8. Stable error codes](#8-stable-error-codes)
- [9. Synthetic teaching integration](#9-synthetic-teaching-integration)
- [10. Boundaries](#10-boundaries)

## Purpose

Human Pilot review found that SVG pages failed real presentation use because
of font substitution, wrapping, clipping, arrow scaling, and cross-renderer
drift. A file that merely exists, parses as XML, and contains no `<text>`
element is not a valid diagram asset. This pipeline requires a real editable
source, a real text-to-path compile step, a real preview, and a real
cross-renderer comparison bound in a machine-written manifest.

## 1. Four asset roles

Every diagram carries four required roles:

| Role | Recommended name | Content |
| --- | --- | --- |
| editable source | `<diagram-id>.editable.svg` | real `<text>`, explicit fonts, stable layer IDs |
| compiled SVG | `<diagram-id>.compiled.svg` | zero `<text>`/`<tspan>`; glyph paths only |
| preview PNG | `<diagram-id>.preview.png` | render of the compiled SVG |
| manifest | `<diagram-id>.manifest.json` | hashes, fonts, renderers, checks, scale |

Cross-renderer QA may produce additional temporary PNGs (Chrome and
PowerPoint). Those are evidence, not delivery assets: the manifest records
their purpose, hash, and `delivered: false`.

## 2. Pipeline order

The only valid order is:

```text
editable source authored
→ source structure and visual audit (PASS required)
→ text compiled to glyph paths
→ compiled SVG structure audit (PASS required)
→ preview PNG from compiled SVG
→ cross-renderer QA (Chrome + PowerPoint-compatible engine)
→ manifest written from real results
```

Never compile first and claim the source already passed. Never let a caller
supply `pass: true` fields that the tool did not compute.

## 3. Editable SVG source contract

An editable source must:

- keep real, editable `<text>` elements;
- declare UTF-8;
- set `width`, `height`, `viewBox`, and `preserveAspectRatio`;
- keep all coordinates finite and inside the canvas semantics;
- give every text run an explicit `font-family`, `font-size`, `font-weight`,
  and placement;
- wrap by measured glyph advance, never by character-count truncation;
- fail closed when copy does not fit — no silent truncation, no shrinking
  below the minimum font size, no overflow;
- use stable, readable `id` values on layers/groups;
- forbid external `href`, remote fonts, `foreignObject`, `script`, event
  handlers, and embedded bitmaps;
- declare arrow markers with explicit `viewBox`, `refX`/`refY`,
  `markerWidth`/`markerHeight`, `orient`, and `markerUnits`;
- keep line widths readable at the final display size;
- avoid browser-default CSS and implicit font fallback.

## 4. Compiled SVG contract

Compilation replaces each audited `<text>` run with real glyph outlines.
The compiled SVG must:

- keep the same canvas, `viewBox`, colors, line styles, and visual hierarchy
  as the source;
- contain zero `<text>`, `<tspan>`, and `foreignObject` elements;
- carry no font runtime dependency;
- contain no external links, images, scripts, or event handlers;
- keep path coordinates finite;
- keep glyph orientation faithful to the source text: outlines are parsed in
  font units (Y up) and converted to SVG Y-down coordinates exactly once, so
  every glyph transform keeps both scale factors positive and cap-height ink
  stays at or above its baseline;
- avoid clipping, negative sizes, illegal transforms, or canvas leakage;
- bind source hash and compiled hash in the manifest;
- be byte-deterministic for the same input, fonts, and compiler environment;
- **fail closed when a font cannot cover the text**: if no family in the
  declared `font-family` stack maps every visible character, the whole
  compilation fails with `SVG_GLYPH_MISSING` instead of emitting a partially
  rendered run. Coverage is decided only by the font's own `cmap` result
  (glyph id 0 is `.notdef`); no font name, script range, or character list is
  hard-coded, no undeclared system fallback is stitched onto the stack, a run
  with missing glyphs never counts as a successful text run, and no empty or
  partially filled `<g>` is produced.

Composite glyphs are resolved recursively. Component offsets follow the
OpenType flags: `SCALED_COMPONENT_OFFSET` transforms the offset by the 2×2
matrix, `UNSCALED_COMPONENT_OFFSET` adds it as-is, and setting both is treated
as contradictory and fails closed. A 2×2 is stored as
`(xscale, scale01, scale10, yscale)` and applied as
`x' = xscale·x + scale10·y + dx`, `y' = scale01·x + yscale·y + dy`.

Outline-format capability boundary — stated exactly, without over-claiming:

| font flavour | status |
| --- | --- |
| TrueType `glyf`/`loca` (`.ttf`) | supported |
| TrueType collection `.ttc` whose selected face has `glyf`/`loca` | supported |
| OpenType with CFF outlines (`CFF `) | **not supported — fails closed** with `SVG_FONT_FORMAT_UNSUPPORTED` |
| OpenType with CFF2 outlines (`CFF2`) | **not supported — fails closed** with `SVG_FONT_FORMAT_UNSUPPORTED` |

This is not a claim of support for "all `.otf`" or "all `.ttc`": the extension
says nothing about the outline format. A declared stack may still list a CFF
font first and a covering TrueType font later; the reader skips the CFF
candidate and uses the later one. If no candidate is usable but a CFF/CFF2
candidate was parsed, the reported error keeps that fact
(`SVG_FONT_FORMAT_UNSUPPORTED`) rather than reporting the font as absent or the
characters as missing. A CFF/CFF2 font is never rendered as an empty path and
never reported ready.

Text-to-path is implemented with a pure-stdlib TrueType/TTC outline reader.
It never downloads fonts, never copies system fonts into the repository, and
never claims font license or redistribution rights.

## 5. Scale semantics

Every asset declares exactly one of:

- `not_applicable`
- `not_to_scale`
- `declared_scale`

Rules:

- concept diagrams must not masquerade as measured drawings;
- `not_to_scale` must be visible on the face of the diagram or in an explicit
  legend;
- `declared_scale` must record the scale value, unit, and source;
- without a real dimensional basis, never invent `1:500` or `1:125`;
- a scale label that disagrees with the manifest fails closed.

## 6. Manifest contract

Use [svg-dual-asset-manifest.schema.json](svg-dual-asset-manifest.schema.json).
The manifest binds at least:

- contract and version;
- `diagram_id` and page role;
- canvas width/height, `viewBox`, aspect ratio, scale semantics;
- editable / compiled / preview paths and SHA-256 hashes;
- source→compiled input/output binding;
- compiler identity and version;
- actually used font family, file fingerprint when available, and source path
  class (system, not packaged);
- Chrome renderer identity, version, and result;
- PowerPoint-compatible renderer identity, version, and result;
- cross-renderer comparison metrics and thresholds;
- every machine check result computed by the tools;
- forbidden-content flags: external references, bitmaps, `foreignObject`,
  scripts, event handlers.

No absolute local paths, usernames, or temporary directories. PASS fields are
computed, never caller-supplied.

The manifest must never claim more than the bytes support:

- a preview that does not exist is recorded as `null`, **never** as an
  all-zero hash, and its absence fails the run with `SVG_PREVIEW_MISSING`;
- `hash_binding_ok` is recomputed from the bytes on disk — first before the
  manifest is written, then again by reading the manifest back and rehashing
  every bound asset; a mismatch fails with `SVG_HASH_BINDING_MISMATCH`;
- `delivered` reflects whether those bytes really exist; it is never
  hard-coded `true`;
- `asset_visual_delivery_ready` requires `hash_binding_ok`, `preview_ok`, and
  `cross_renderer_ok` together, so skipping the second client records
  `cross_renderer_ok: false` and `asset_visual_delivery_ready: false` — "the
  second client was not attempted" is *unverified*, never *ready*;
- a failed run rolls back the files it created, so it can neither leave a
  partial asset set behind nor overwrite a previously good one.

### 6.1 What `asset_visual_delivery_ready` does and does not say

It is an **asset-level visual** statement, and it is deliberately narrow: this
SVG four-asset set has real byte binding, a verified preview, and an acceptable
visual result from every renderer that was actually declared and run.

It is **not** a deck, package or client claim. It does not assert that:

- any PPTX consumes this SVG;
- a client will not render the PNG fallback instead;
- the SVG bytes survive a client save;
- the `svgBlip` relation survives a client save;
- a saved presentation round-trips with editable vectors;
- any office client is compatible;
- a human pilot passed;
- the final deck is deliverable.

`outcome` is named `ASSET_PACKAGE_READY` for the same reason: the four-asset
build finished. It is not a deck-delivery verdict. There is no second
"delivery" field and no compatibility alias for the old name: a manifest
carrying a field that claims deck or client readiness is rejected by the
schema.

### 6.2 Scope boundary against presentation round trips

Asset-level cross-renderer QA answers exactly one question: *does the same
compiled SVG produce an acceptable visual result in the two declared
renderers?*

It does not answer: *does a presentation containing that SVG still carry the
SVG after an office client saves it?*

Those are different questions with different evidence, and a PASS on the first
says nothing about the second. A client may play a page back correctly from a
bitmap fallback while deleting the extended SVG relationship on save, so an
asset-level visual PASS is not evidence of editable vector round-trip. A
saved-and-reopened presentation check, inspecting OOXML media, relationships
and extension lists after a real client save, is a separate gate with its own
evidence and belongs with the presentation package, not with this SVG contract.

No PPTX package is read, inferred, or modelled by this pipeline, and no field
in this manifest is derived from one.

## 7. Visual and cross-renderer QA

XML/regex checks alone are insufficient. After real rendering, check at least:

- `viewBox` versus output aspect;
- text ink bounds;
- text versus canvas bounds;
- text versus protected graphic regions;
- illegal overlaps;
- element clipping;
- minimum font size and minimum line width;
- arrow head proportions;
- long mixed Chinese/English/digit runs;
- multi-line wrapping;
- legend and annotation spacing;
- non-empty canvas;
- missing elements in Chrome and PowerPoint;
- overall scale, content bounds, and occupancy within explicit thresholds.

Do not require Chrome and PowerPoint PNGs to be byte-identical. Antialiasing
differs. The comparison must tolerate small antialiasing noise while catching
overall displacement, scale anomalies, missing text or shapes, clipping,
obvious font-size change, missing arrows/segments, and wrong canvas aspect.

### PowerPoint-compatible export methodology

`Slide.Export` renders the **entire slide**, not the picture bounds. A default
10"×7.5" slide that receives a small SVG picture exports that picture as a
corner thumbnail when the PNG size is set to the SVG canvas. The QA renderer
sets `PageSetup.SlideWidth/SlideHeight` to the SVG canvas, places the picture
to fill the slide, and only then exports. Sizing the picture alone is not
sufficient.

Engine identity is recorded honestly: `microsoft-powerpoint-com` only when
the real Microsoft PowerPoint executable is present; otherwise
`wps-presentation-powerpoint-com` (or another detected host). A WPS pass is
never reported as a Microsoft PowerPoint pass. Microsoft PowerPoint stays
`UNAVAILABLE_UNVERIFIED` on machines that do not have it installed.

Reading the comparison metrics: `powerpoint_png_sha256` names the **second
comparison slot** of the generic two-image comparator, not a PowerPoint render.
The comparator accepts any two images — for example a Chrome render of the
compiled SVG against a Chrome render of the editable source — so a populated
`powerpoint_png_sha256` is not evidence that PowerPoint or WPS produced
anything. The name is retained for interface compatibility only.

## 8. Stable error codes

| Code | Meaning |
| --- | --- |
| `SVG_SOURCE_INVALID` | editable source is not well-formed SVG |
| `SVG_VIEWBOX_INVALID` | missing or inconsistent viewBox/aspect |
| `SVG_FONT_UNDECLARED` | text without explicit font-family |
| `SVG_FONT_UNAVAILABLE` | required font file not available on this machine, or the path is not a usable font at all |
| `SVG_FONT_FORMAT_UNSUPPORTED` | the font exists and its sfnt tables are readable, but its outline format (CFF/CFF2) is outside this reader's TrueType `glyf`/`loca` capability |
| `SVG_GLYPH_UNSUPPORTED` | glyph outline cannot be compiled faithfully (point-matching composite, excessive nesting or components, contradictory scaled/unscaled offset flags) |
| `SVG_GLYPH_MISSING` | no family in the declared font stack covers every visible character; provide a font that covers the full character set |
| `SVG_TEXT_OVERFLOW` | measured text exceeds its box; fail-closed |
| `SVG_TEXT_COLLISION` | text collides with protected graphics or other text |
| `SVG_CLIPPING` | content clipped by canvas or viewport |
| `SVG_MIN_FONT_SIZE` | font size below the configured minimum |
| `SVG_MIN_LINE_WIDTH` | stroke width below the configured minimum |
| `SVG_SCALE_SEMANTICS_INVALID` | missing or inconsistent scale declaration |
| `SVG_EXTERNAL_REFERENCE` | forbidden external href/font/image/script |
| `SVG_COMPILED_TEXT_REMAINING` | compiled SVG still has text/tspan |
| `SVG_SOURCE_COMPILED_HASH_MISMATCH` | manifest binding does not match files |
| `SVG_PREVIEW_MISMATCH` | preview does not match compiled render |
| `SVG_RENDERER_EVIDENCE_INCOMPLETE` | a required renderer result is missing |
| `SVG_CROSS_RENDERER_MISMATCH` | Chrome and PowerPoint results diverge beyond thresholds |
| `SVG_PREVIEW_MISSING` | no preview bytes were produced; the asset is not reported as ready |
| `SVG_HASH_BINDING_MISMATCH` | manifest asset hashes do not match the bytes on disk |
| `SVG_MANIFEST_UNREADABLE` | the written manifest could not be read back for re-verification |

On error: non-zero exit, machine-readable stdout, no traceback on stderr, no
half-written bundle, no overwrite of existing outputs, inputs unchanged.

## 9. Synthetic teaching integration

The synthetic teaching renderer integrates this pipeline only:

1. author the existing 8-page editable SVGs;
2. run source QA;
3. compile to glyph paths;
4. run compiled QA;
5. build preview PNGs from compiled SVGs;
6. export PPTX from compiled SVGs only;
7. bind every page's four roles in the run manifest.

ARCH-122 visible copy, speaker notes, public-claim gate, page-local
provenance, and internal isolation stay unchanged. Design content, internal
trace, and speaker notes never enter SVG `<title>`, `<desc>`, shape names, or
alt text. The PPTX remains a native editable deck; path-compiling text does
not turn the slide into a full-page bitmap.

## 10. Boundaries

This pipeline does not:

- install or download fonts, browsers, or plugins;
- copy system fonts into the repository;
- claim font licenses or redistribution rights;
- modify presentation handoff schemas, audience-copy helper, or review hashes;
- rebuild the Qingtaili project;
- create product phases, top-level Skills, card types, Markdown renderers, or
  parallel state chains;
- treat CI fixtures as proof that a GitHub runner has Microsoft PowerPoint.

Local PowerPoint-compatible results and CI fixture results are recorded
separately.
