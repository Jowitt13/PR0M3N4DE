# Student Assignment Brief Digest Card Renderer

## Contents

- [Scope](#scope)
- [Input](#input)
- [Output](#output)
- [Fixed card structure](#fixed-card-structure)
- [Fidelity, grouping, and boundaries](#fidelity-grouping-and-boundaries)
- [Error codes](#error-codes)
- [Explicit non-claims](#explicit-non-claims)
- [Determinism and safety](#determinism-and-safety)

## Scope

This reference governs one local, offline, read-only renderer: it turns one
valid, pending ARCH-097 AssignmentBriefDigest into one deterministic
Simplified-Chinese Markdown card so a student can read, classify, and
confirm the brief before any design work. It solves the first step — read
the dense brief literally, categorize it, and shrink it — and nothing else.
It is not a file parser, design analyzer, automatic confirmer, recommender,
option generator, web page, PPT generator, or drawing generator.

## Input

The input is one existing ARCH-097 digest JSON document. The renderer
validates it against ARCH-097's authoritative digest schema and never
re-implements, rewrites, or extends the brief contract. A structurally
invalid digest fails closed with `DIGEST_SCHEMA_INVALID`, keeping ARCH-097's
authoritative error semantics. A load failure reports `DOCUMENT_LOAD_FAILED`.

Only `human_confirmation.status == "pending"` is rendered. A confirmed
digest fails closed with `BRIEF_DIGEST_CARD_NOT_PENDING`: a confirmed
summary can never be repackaged as an awaiting-confirmation choice. The
renderer reads no intake and parses no DOC, DOCX, PDF, HTML, image, or OCR
content, and it never fills missing information on the digest's behalf.

## Output

The renderer writes UTF-8 Markdown to stdout only. It offers no `--output`
flag and creates no file, cache, log, receipt, confirmation record, or JSON
artifact. Identical inputs produce byte-identical cards, and the input file
stays byte-unchanged. The renderer never calls build or confirm and never
generates a `CONFIRM_BRIEF_DIGEST` record; human confirmation still happens
only through the ARCH-097 `confirm` contract.

## Fixed card structure

Every card carries exactly these sections in this exact order:

1. `# 任务书摘要（待人工确认）`
2. `## 已明确的任务书要求`
3. `## 存在冲突、不能替你裁决的内容`
4. `## 缺失、无法读取或暂缓的信息`
5. `## 人工备注（不等同于任务书要求）`
6. `## 需要你确认的问题`
7. `## 确认前不要开始什么`
8. `## 你可以怎样回答`

## Fidelity, grouping, and boundaries

Requirements are grouped by the nine intake categories in their fixed
order: `hard_constraint`, `program`, `site`, `spatial_relationship`,
`circulation`, `deliverable`, `design_goal`, `scoring_focus`,
`reference_only`. Empty categories are omitted. Within each group the
digest's original order is preserved; the renderer never sorts by text,
area, or any model preference.

`included` and `duplicate_merged` requirements appear under the confirmed
requirements section. The other four statuses are shown completely and
explicitly: `conflict` in the conflict section, and `missing`,
`unreadable`, and `deferred_with_reason` in the gaps section. Every item
keeps its concise text; segment-backed items keep their source locators. A
duplicate item states that it was merged while its original sources stay
visible, and its locators keep every original location. A conflict keeps
its description and every locator from both sides and states that the
machine chooses no winner. Missing, unreadable, and deferred items keep
their original descriptions and reasons; no value is ever invented. Items
derived from declared unknowns state their declared nature without exposing
internal identifiers.

Human notes are projected verbatim and are marked as not being brief
requirements. Clarification questions stay verbatim, in order, at most
three; with zero questions the card shows only the fixed no-pending-question
sentence and never invents questions.

The do-not-start section fixes the rule that before confirmation there is
no design analysis, program or area allocation, floor count, entrance,
massing, circulation, scheme, or recommendation. The reply section offers
only the fixed paths: confirm the summary, point out literal content to
correct, supply missing or unreadable material, or answer the existing
clarification questions first. The renderer never confirms on the user's
behalf and never writes a confirmation record.

The card exposes no internal REQ/SEG/CONF/UNK/NOTE identifier, input hash,
or SHA. It claims no VERIFIED status, regulation conclusion, or format
parsing support. It generates no architectural advice, area, floor count,
entrance, coordinate, circulation, plan, drawing, HTML, PPTX, image, or
model.

## Error codes

| Code | Meaning |
| --- | --- |
| `BRIEF_DIGEST_CARD_NOT_PENDING` | The supplied digest is not pending; no card is rendered. |
| `DIGEST_SCHEMA_INVALID` | The supplied digest violates the authoritative ARCH-097 digest schema. |
| `DOCUMENT_LOAD_FAILED` | The digest document or a committed schema could not be loaded. |

## Explicit non-claims

The renderer decides nothing. It introduces no network access, browser,
subprocess, system-clock dependency, database, OCR, PPTX, or generic
state-package capability, and it does not call `assemble_project_state.py`.

## Determinism and safety

Identical inputs produce byte-identical cards. The renderer is a pure
projection of the validated pending digest plus fixed contract sentences;
it opens the input file read-only, writes only to stdout, and never
modifies the input document.
