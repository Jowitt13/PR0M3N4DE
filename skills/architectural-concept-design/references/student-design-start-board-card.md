# Student Design Start Board Card Renderer

## Contents

- [Scope](#scope)
- [Input](#input)
- [Output](#output)
- [Fixed card structure](#fixed-card-structure)
- [Fidelity and boundaries](#fidelity-and-boundaries)
- [Error codes](#error-codes)
- [Explicit non-claims](#explicit-non-claims)
- [Determinism and safety](#determinism-and-safety)

## Scope

This reference governs one local, offline, read-only renderer: it turns one
valid ARCH-098 student design start board, backed by its confirmed ARCH-097
digest, into one deterministic Simplified-Chinese Markdown card. The card
presents the confirmed brief requirements, the unresolved items, the
clarification questions, and the single program-and-area next step. It
creates no space, allocates no area, and decides no floor count, entrance,
circulation, massing, or scheme.

## Input

The renderer consumes two documents: one confirmed ARCH-097 digest and one
ARCH-098 start board. Its sole upstream entry is ARCH-098's public
`validate_board`, which re-validates the confirmed digest binding chain and
requires the supplied board to be the exact deterministic projection of that
digest. Upstream error codes propagate unchanged; the renderer defines no
substitute error codes. The renderer never rebuilds, repairs, or
reinterprets the digest or the board.

## Output

The renderer writes UTF-8 Markdown to stdout only. It offers no `--output`
flag and creates no file, cache, log, receipt, confirmation record, or JSON
artifact. Identical inputs produce byte-identical cards, and both input
files stay byte-unchanged.

## Fixed card structure

Every card carries exactly these sections in this exact order:

1. `# 已确认的任务书起点`
2. `## 已明确的任务书要求`
3. `## 还未解决、不能替你决定的内容`
4. `## 进入功能与面积编排前的问题`
5. `## 下一步：功能与面积编排`
6. `## 你可以先写什么`
7. `## 现在不要自动决定什么`

## Fidelity and boundaries

Confirmed requirements are grouped by the nine categories in their fixed
canonical order; empty categories are omitted. Within each group the board's
original order is preserved, and every item keeps its requirement wording and
source locator.

Unresolved items appear in board order, item by item: `conflict`, `missing`,
`unreadable`, and `deferred_with_reason`. A conflict keeps its description
and every conflicting locator and states that the machine chooses no winner.
Missing, unreadable, and deferred items keep their original wording; no
value is ever filled in and no reason is ever removed.

Clarification questions stay verbatim, in order, at most three; with zero
questions the card shows only the fixed no-pending-question sentence and
never invents questions.

The next-step section projects only the existing `program_and_area` action
and its description. The preparation section lists only the fixed,
non-design preparation work a human does alone: organizing functional
spaces, provided or unresolved areas, users, access levels, active and
quiet needs, and adjacency or separation relationships. It never creates a
space name, an area value, a priority, or architectural advice.

The no-automatic-decision section states that no area, dimension, floor
count, entrance, circulation, massing, column grid, environmental
conclusion, or scheme is decided, and restates the board's own boundaries.

The card exposes no machine-only hash, no internal identifier, and no
winner, best, rank, score, recommendation, or automatic-selection language.
It generates no coordinate, rectangle, wall, door, column, plan, drawing,
HTML, PPTX, image, or model.

## Error codes

All rejection codes are ARCH-097/ARCH-098 authoritative codes propagated
unchanged: `SOURCE_DIGEST_SCHEMA_INVALID`, `SOURCE_DIGEST_NOT_CONFIRMED`,
`SOURCE_DIGEST_CONFIRMATION_INVALID`, `SOURCE_DIGEST_HASH_MISMATCH`,
`START_BOARD_SCHEMA_INVALID`, `START_BOARD_CONTENT_MISMATCH`, plus
`DOCUMENT_LOAD_FAILED` for unreadable inputs.

## Explicit non-claims

The renderer decides nothing. It introduces no network access, browser,
subprocess, system-clock dependency, database, scanned-content parsing,
PPTX, or generic state-package capability, and it does not call
`assemble_project_state.py`.

## Determinism and safety

Identical inputs produce byte-identical cards. The renderer is a pure
projection of the validated board plus fixed contract sentences; it opens
the input files read-only, writes only to stdout, and never modifies an
input document.
