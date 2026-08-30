# Student Manual Spatial Design Handoff Card Renderer

## Contents

- [Scope](#scope)
- [Input](#input)
- [Output](#output)
- [Fixed Markdown structure](#fixed-markdown-structure)
- [Fidelity rules](#fidelity-rules)
- [Boundaries](#boundaries)
- [Error codes](#error-codes)
- [Explicit non-claims](#explicit-non-claims)
- [Determinism and safety](#determinism-and-safety)

## Scope

This reference governs one local, offline, read-only renderer: it turns one
valid, untampered ARCH-111 spatial transition state handoff whose human
review continued to manual spatial design into one deterministic
Simplified-Chinese Markdown handoff card for the student. The ARCH-111
builder output remains JSON; this renderer is a separate, independent
stdout-only projection. It is not an automatic designer, recommender, option
generator, drawing tool, web page, PPT generator, or state-package
generator.

## Input

The renderer consumes the complete ARCH-097~111 source chain: the twenty
ARCH-097~107 chain documents, the ARCH-108 review record and state handoff,
the ARCH-109 main-space-support draft and framework, the ARCH-110 spatial
transition draft and framework, the ARCH-111 review record, and the ARCH-111
state handoff itself.

Its sole upstream entry is ARCH-111 public
`validate_spatial_transition_state_handoff`, which re-runs the full
ARCH-097~111 chain. Upstream error codes propagate unchanged and are never
renamed as renderer errors. The renderer never trusts the handoff document
alone and never uses a hand-assembled shortcut chain.

Only a handoff whose human review outcome is
`continue_to_manual_spatial_design` is rendered. An invalid handoff, a
tampered handoff, an invalid or non-continued review record, upstream
unresolved items, or any upstream chain error fails closed; the renderer
never produces half a card, reopens the review, continues or withdraws on
the human's behalf, or introduces a new human choice, confirmation, hash, or
state transition.

## Output

The renderer writes UTF-8 Markdown to stdout only. It offers no `--output`
flag and creates no file, cache, log, receipt, or selection record.
Identical inputs produce byte-identical cards, and every input file stays
byte-unchanged.

## Fixed Markdown structure

Every card carries exactly these sections in this exact order:

1. `# 已确认的空间设计起点`
2. `## 空间层级`
3. `## 空间过渡意图`
4. `## 本轮人工审阅意见`
5. `## 现在可以手工继续什么`
6. `## 还需要你确认的问题`
7. `## 不应擅自推断什么`

## Fidelity rules

Space names, roles, notes, transition patterns, transition notes, human
review notes, and clarification questions are projected verbatim in the
upstream human order. The renderer never sorts, adds, drops, merges,
renames, rewrites, or supplies missing human facts. Fixed role and
transition enums may be displayed as clear Chinese labels, but the labels
never change their meaning. The next-step section only states that the
student may continue their own manual spatial design from the confirmed
facts.

## Boundaries

The card carries no coordinate, dimension, rectangle, entrance, corridor,
wall, door, column, stair, toilet, site plan, massing, orientation,
structure, regulation, cost, performance, constructibility, or scheme
conclusion. It emits no winner, best option, ranking, score,
recommendation, or automatic-selection language, and it never claims to
generate a plan, drawing, image, HTML, PPTX, model, or professional
conclusion.

## Error codes

| Code | Meaning |
| --- | --- |
| `MANUAL_DESIGN_HANDOFF_CARD_NOT_CONTINUED` | The supplied handoff does not record a human continuation to manual spatial design; no card is rendered. |
| `DOCUMENT_LOAD_FAILED` | One input document could not be loaded; nothing is rendered. |

ARCH-097~111 errors propagate unchanged and are never renamed as renderer
errors.

## Explicit non-claims

The renderer decides nothing. It writes no selection record, reopens no
review, and performs no state transition. It creates no network access,
browser, database, frontend, subprocess, system-clock dependency, PPT,
image, OCR, or format-parsing capability, and it does not call
`assemble_project_state.py` or any generic project-state package.

## Determinism and safety

Identical inputs produce byte-identical cards. The renderer is a pure
projection of the validated ARCH-111 handoff plus fixed contract sentences;
it opens input files read-only, writes only to stdout, and never modifies
an input document.
