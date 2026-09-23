# Presentation usability, speaker notes, and human acceptance (ARCH-125)

> **Single authority** for whether a deck is actually presentable: the
> usability plan, the independent human usability review, and real rehearsal
> evidence. Additive to the ARCH-122 audience-copy contract and the ARCH-124
> freshness authority — it never replaces either and never duplicates their
> logic.

## Contents

- [Purpose](#purpose)
- [1. The three contracts](#1-the-three-contracts)
- [2. Usability plan](#2-usability-plan)
- [3. Human usability review](#3-human-usability-review)
- [4. Real rehearsal evidence](#4-real-rehearsal-evidence)
- [5. Structural language checks](#5-structural-language-checks)
- [6. Delivery integration](#6-delivery-integration)
- [7. Stable error codes](#7-stable-error-codes)
- [8. Boundaries](#8-boundaries)

## Purpose

A deck that passes every structural gate can still be unpresentable: copy
written for systems instead of audiences, notes that repeat the slides,
timings invented by a model, no human ever having spoken the deck aloud.
ARCH-125 answers the acceptance questions — is this for the audience, does
every page have a purpose, do the notes help a real presenter, did a human
check the copy, did anyone actually rehearse it — while keeping internal
trace, error codes, state IDs, and approval流水 off every slide.

## 1. The three contracts

One additive schema ([presentation-usability.schema.json](presentation-usability.schema.json))
defines three caller-supplied documents, all hash-bound to the actual handoff
and deck:

| Contract | Kind | Provided by | Answers |
| --- | --- | --- | --- |
| Usability plan | `PRESENTATION_USABILITY_PLAN` | the working team | per-page purpose, key message, sequence, visual reference, evidence note, transition, estimated seconds, notes hash |
| Usability review | `PRESENTATION_USABILITY_REVIEW` | a human reviewer | APPROVED / CHANGES_REQUESTED plus per-page findings |
| Rehearsal evidence | `PRESENTATION_REHEARSAL_EVIDENCE` | a human presenter | actual timestamps and durations, stuck/skipped pages, feedback, COMPLETED / NEEDS_CHANGES |

Speaker notes stay invisible and keep the ARCH-122 four-layer contract; the
plan's `notes_sha256` binds each page's actual `speaker_notes` object so any
notes edit voids the plan, the review, and the rehearsal.

## 2. Usability plan

The plan binds the canonical hash of the whole handoff plus the exact page
order. Each page declares its internal `communication_purpose`, an
`estimated_seconds` planning value, and the seven speaker-support fields
(`key_message`, `sequence_hint`, `visual_reference`, `evidence_note`,
`transition_hint`, plus the notes hash). Estimated seconds are planning data:
no gate accepts them as rehearsal time. Internal entity IDs and error-code
shaped tokens are rejected in purposes, note fields, and notes.

## 3. Human usability review

The review is a separate human-supplied receipt; agent, model, bot, and
system labels are rejected by the same boundary as the ARCH-122 copy review.
`APPROVED` is required for delivery. It binds the plan hash, handoff hash,
visible-copy digest, speaker-notes digest, page order, deck bytes, per-page
findings, resolutions, and their self-binding hash — so any visible copy
change, notes change, page reorder, or deck byte change voids it. Like every
human check here, this is a syntactic and process boundary, not real-world
identity authentication.

## 4. Real rehearsal evidence

The rehearsal receipt records a human presenter, explicit `started_at` /
`ended_at`, `actual_total_seconds` (must equal the timestamp difference),
per-page seconds summing to the total, stuck / skipped / hard-to-explain
pages, audience feedback, change requests, and a human-set conclusion
(`COMPLETED` / `NEEDS_CHANGES`). Builders can never fill in a conclusion;
planning estimates never count as actual durations; a missing rehearsal, an
inconsistent one, or a `NEEDS_CHANGES` result fails delivery closed.

## 5. Structural language checks

Automation checks structure only: internal entity IDs (for example `RC-001`),
error-code-shaped tokens, notes that repeat the visible headline verbatim,
missing pages, and order mismatches. Natural-language quality — whether a
title sounds like a human presenter, whether the audience will understand it,
whether process language such as "阶段一：约束摄取" slipped in — is decided by
the human reviewer through findings and review status. There is no global
banned-word list, and identical strings in a legitimate context are not
auto-rejected.

## 6. Delivery integration

E2E delivery mode and the unique release entry both require the three
ARCH-125 documents and re-verify them against the actual handoff and deck
bytes, alongside the ARCH-124 freshness verdict and the human data review:

```text
python scripts/presentation_usability.py validate-plan <plan> --handoff <handoff.json>
python scripts/presentation_usability.py verify <plan> <review> <rehearsal> \
    --handoff <handoff.json> --deck <deck.pptx> --expect-deck-sha256 <sha>
```

Intermediate decks (explicit `--mode intermediate`) are marked
`INTERMEDIATE_NOT_FOR_DELIVERY`, may omit all of this, and are stably
rejected by every delivery and release entry.

## 7. Stable error codes

`PLAN_HANDOFF_MISMATCH`, `PLAN_PAGE_ORDER_MISMATCH`, `PLAN_PAGES_INCOMPLETE`,
`PLAN_NOTES_MISSING`, `PLAN_NOTES_MISMATCH`, `NOTES_REPEAT_COPY`,
`INTERNAL_ID_IN_TEXT`, `ERROR_CODE_IN_TEXT`, `USABILITY_REVIEW_REQUIRED`,
`USABILITY_REVIEW_NOT_APPROVED`, `USABILITY_REVIEWER_LABEL_REJECTED`,
`REVIEW_HASH_MISMATCH`, `REHEARSAL_REQUIRED`, `REHEARSAL_NOT_COMPLETED`,
`REHEARSAL_PRESENTER_LABEL_REJECTED`, `REHEARSAL_TIME_INVALID`,
`REHEARSAL_TARGET_MISMATCH`, `REHEARSAL_PAGES_MISMATCH`,
`REHEARSAL_HASH_MISMATCH`, `USABILITY_EVIDENCE_REQUIRED`,
`USABILITY_EVIDENCE_INVALID`, `USABILITY_VERIFIER_UNAVAILABLE`,
`USABILITY_VERIFICATION_FAILED`, `USABILITY_VERIFIER_OUTPUT_INVALID`.

## 8. Boundaries

The contracts never modify ARCH-122 schemas, never put notes or trace on
slides, never let an agent approve or rehearse, never convert test passes
into Human Pilot conclusions, and never claim Microsoft PowerPoint
verification without a real run. Real Human Pilots on real projects belong to
ARCH-126; this contract ships the capability plus anonymous validation only.
