# Student Guided Decision Interaction Contract

## Contents

- [Scope](#scope)
- [Language default](#language-default)
- [Decision card template](#decision-card-template)
- [Candidate display rules](#candidate-display-rules)
- [Zero or one candidate fallback](#zero-or-one-candidate-fallback)
- [Recommendation provenance](#recommendation-provenance)
- [Boundaries](#boundaries)
- [Anonymous example structure](#anonymous-example-structure)

## Scope

This contract governs how the Skill answers at a human decision point: a
moment when a confirmed state already requires the student or human to choose.
It is a conversational delivery contract only. It is not a web UI, a database,
a frontend, a PPT generator, an automatic designer, a new top-level Skill, or
any new parsing, network, browser, or media capability.

It applies whenever a confirmed state demands a human choice, including the
confirmed student chain gates that already require human records: dimension
candidate selection, hypothesis comparison selection, and any later stage
whose confirmed state names a pending human decision. It never replaces,
re-runs, or bypasses those existing human selection records and their hash
bindings.

## Language default

The decision card defaults to clear Simplified Chinese that a student can
read directly. Switch language only when the user explicitly asks for another
language. Technical tokens such as option keys, action names, and error codes
stay in their exact confirmed forms in any language.

## Decision card template

Whenever a confirmed state requires a human choice, answer with exactly one
decision card containing these sections in this exact order:

1. `现在要决定什么`
   One sentence naming the decision object and why the decision is due now.
2. `为什么现在要决定`
   Cite only already confirmed facts from the brief, program, hypothesis,
   comparison, or state documents. Never cite model preference as fact.
3. `可选方案`
   Present every actually existing valid candidate, following the candidate
   display rules below.
4. Per-option block, for every option shown:
   - what it is;
   - its applicable premise;
   - its merits;
   - its costs, risks, or trade-offs;
   - what would overturn it.
5. `建议先重点考虑`
   Governed by the recommendation provenance rules below.
6. `你可以怎样回答`
   State clearly that the human may choose an option key, ask to modify or
   supplement the options, or mark the item unresolved. Never present a
   suggestion as an already-made choice; the final decision still requires
   the existing human selection record.

## Candidate display rules

- Show the real valid candidates that actually exist in the confirmed state; never force exactly two options labeled A/B.
- When there are two to six valid candidates, present all of them completely, in the confirmed human-authored order, without reordering.
- Never add, drop, merge, split, rename, or invent a candidate.
- Never describe a candidate with language that declares a winner, a best option, a ranking, or a score.

## Zero or one candidate fallback

When zero or one valid candidate exists, do not fabricate a multiple-choice question. The card must say plainly that there are currently not enough real alternatives, and it must name what the human still needs to author: for example, a second dimension candidate, another hypothesis, or the missing comparison content. The card then points to the existing authoring gate for that content instead of inventing options.

## Recommendation provenance

`建议先重点考虑` may name one option only when the confirmed comparison
contains a single, traceable human guidance or focus that points to it. The
card must then state the source of that guidance explicitly: which confirmed
comparison record and which human-written guidance field it comes from.

Every such section must include the fixed sentence:

`这是帮助你判断的决策引导，不是自动替你做建筑决定。`

When no single traceable focus exists, the card must state exactly:

`当前没有足够依据给出单一优先建议`

and must not fabricate a recommendation, a default choice, or a preference.

## Boundaries

This contract decides nothing automatically. It selects no default, declares no winner or best option, assigns no rank or score, and never turns model preference into confirmed fact. It adds, removes, reorders, or fabricates no candidate.

It does not bypass any existing human selection or hash-binding contract, and it does not weaken any prior gate. It creates no network access, browser, database, frontend, PPT, image, or format-parsing capability. A decision card is conversational guidance only; the binding decision still happens through the existing human selection record of the relevant stage.

## Anonymous example structure

The following is an anonymous synthetic structure for illustration only. It
references no real project, site, person, or document.

```text
现在要决定什么
- One sentence: which confirmed decision is due now.

为什么现在要决定
- Confirmed fact one, with its confirmed source document name.
- Confirmed fact two, with its confirmed source document name.

可选方案
- 方案 <option key 1>
  - 它是什么：…
  - 适用前提：…
  - 优点：…
  - 代价、风险或取舍：…
  - 什么情况会推翻它：…
- 方案 <option key 2>
  - 它是什么：…
  - 适用前提：…
  - 优点：…
  - 代价、风险或取舍：…
  - 什么情况会推翻它：…

建议先重点考虑
- <option key>, only when one traceable human guidance exists.
- 来源理由：confirmed comparison record and its human-written guidance field.
- 这是帮助你判断的决策引导，不是自动替你做建筑决定。
- Or exactly: 当前没有足够依据给出单一优先建议

你可以怎样回答
- 选择某个 option key；
- 要求修改或补充方案；
- 或标记为 unresolved。
- 最终决定仍需现有的人类选择记录与 hash 绑定。
```

## Hypothesis decision card renderer

For one ARCH-104 student hypothesis comparison in the pending_selection state, read [student-hypothesis-decision-card.md](student-hypothesis-decision-card.md) and use `scripts/render_student_hypothesis_decision_card.py` to render the deterministic Simplified-Chinese decision card to stdout only. The renderer re-validates the complete ARCH-097~104 chain through the ARCH-104 public validation entry, propagates upstream error codes unchanged, fails closed on a selected document or on missing human facts, and never writes a file, a selection record, or an automatic decision.
