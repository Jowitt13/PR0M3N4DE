# Student Hypothesis Decision Card Renderer

## Contents

- [Scope](#scope)
- [Input](#input)
- [Output](#output)
- [Fixed Markdown structure](#fixed-markdown-structure)
- [Candidate rules](#candidate-rules)
- [Guidance rules](#guidance-rules)
- [Source boundaries](#source-boundaries)
- [Error codes](#error-codes)
- [Explicit non-claims](#explicit-non-claims)
- [Determinism and safety](#determinism-and-safety)

## Scope

This reference governs one local, offline, read-only renderer: it turns one
valid ARCH-104 student hypothesis comparison in the `pending_selection` state
into one deterministic Simplified-Chinese Markdown decision card that a
student can read and answer directly in chat. It is not an automatic
decision-maker, scorer, option generator, web UI, PPT generator, or new
top-level Skill. It implements the decision card contract of
[student-guided-decision-interaction.md](student-guided-decision-interaction.md)
for the ARCH-104 stage only.

## Input

The renderer consumes the complete ARCH-097~104 chain: the confirmed digest,
start board, spatial program draft and program, dimension draft, dimension
plan, human dimension selection, floor zoning draft and framework,
circulation-environment draft and framework, massing-grid-height draft and
framework, the confirmed hypothesis comparison draft, and the pending
comparison document itself.

Its sole upstream entry is ARCH-104 `validate_comparison`, which re-runs the
full ARCH-097~104 chain. Upstream error codes propagate unchanged and are
never renamed as renderer errors.

The renderer accepts only `pending_selection` comparisons. A `selected`
comparison fails closed with `DECISION_CARD_NOT_PENDING_SELECTION`: the human
selection has already happened and is never re-opened, re-rendered as a
choice, or overwritten.

## Output

The renderer writes UTF-8 Markdown to stdout only. It creates no file,
receipt, log, cache, or output path; it has no `--output` flag. It never
writes, replaces, or simulates the human selection record, and it never
modifies an input document.

## Fixed Markdown structure

Every card carries exactly these sections in this exact order:

1. `# 现在要决定什么` — the upstream decision prompt, verbatim.
2. `## 为什么现在要决定` — confirmed upstream state, the human-authored
   comparison criteria, and the real candidate count.
3. `## 可选方案` — every real candidate, in the upstream human order.
4. For each candidate: 它是什么; 适用前提; 优点; 代价/风险; 推翻条件.
5. `## 建议先重点考虑` — governed by the guidance rules below.
6. `## 你可以怎样回答` — reply paths under the existing ARCH-104 contract.

## Candidate rules

The candidate count is always the real, confirmed human-authored count from
the upstream comparison: two to six. The renderer never forces exactly two
options, never sorts, reorders, adds, drops, merges, splits, renames, or
invents a candidate, and never supplies a missing precondition, advantage,
cost, risk, or overturn condition on its own.

Every candidate must carry human-written, traceable facts for all five card
fields. When any required human fact is missing or blank, the renderer fails
closed with `DECISION_CARD_SOURCE_INCOMPLETE` and renders nothing; the
machine never authors architectural judgment to fill a gap.

## Guidance rules

`## 建议先重点考虑` names one candidate only when the confirmed comparison
carries a single, traceable human guidance focus
(`recommended_to_consider_first`). The card then restates the human-written
basis, basis criteria, advantages, costs or risks, and overturn conditions,
and always includes the fixed sentence:

`这是帮助你判断的决策引导，不是自动替你做建筑决定。`

When the comparison carries no guidance, an unable-to-suggest statement, or
multiple focus candidates, the card displays exactly:

`当前没有足够依据给出单一优先建议。`

and fabricates no recommendation, default, or preference.

`## 你可以怎样回答` offers only the ARCH-104 contract paths: choose one real
candidate by name, ask to revise or supplement the human candidates, or mark
the decision unresolved. The card is never a selection itself; the binding
decision still requires the existing explicit human selection record.

## Source boundaries

Every sentence of the card restates confirmed upstream content or one of the
fixed contract sentences in this reference. The renderer emits no model
preference, no winner, best option, ranking, score, or automatic-selection
language, and never presents a suggestion as an already-made choice.

## Error codes

| Code | Meaning |
| --- | --- |
| `DECISION_CARD_NOT_PENDING_SELECTION` | The supplied comparison is not in the pending_selection state; no card is rendered. |
| `DECISION_CARD_SOURCE_INCOMPLETE` | A human fact the card needs is missing or blank; nothing is rendered and nothing is invented. |
| `DOCUMENT_LOAD_FAILED` | One input document could not be loaded; nothing is rendered. |

ARCH-097~104 errors propagate unchanged and are never renamed as renderer
errors.

## Explicit non-claims

The renderer decides nothing. It selects no default, declares no winner or
best option, assigns no rank or score, and never turns model preference into
confirmed fact. It writes no selection record and does not bypass or weaken
the ARCH-104 selection and hash-binding contract.

It creates no network access, browser, database, frontend, subprocess,
system-clock dependency, PPT, image, OCR, or format-parsing capability, and
it does not call `assemble_project_state.py` or any generic project-state
package.

## Determinism and safety

Identical inputs produce byte-identical cards. The renderer is a pure
projection of the validated comparison document plus fixed contract
sentences; it keeps input files byte-unchanged, opens them read-only, and
writes only to stdout.
