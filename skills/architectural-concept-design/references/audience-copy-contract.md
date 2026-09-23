# Audience copy contract for presentation handoffs

> **Single authority** for the four-layer page contract, the audience context,
> the internal-trace leakage gate, the public-claim gate, and the human copy
> review with canonical hash binding. All three local presentation paths —
> the runtime-candidate [presentation handoff](presentation-handoff.md), the
> [state-only handoff](state-only-presentation-handoff.md), and the
> [synthetic teaching handoff](synthetic-teaching-presentation-handoff.md) —
> reuse this one contract through the shared
> `scripts/presentation_audience_copy.py` helper. They must never re-implement
> divergent rules. This is not a new product phase, a parallel state chain, or
> a Markdown card renderer.

## 1. Why this exists

The post-v0.2.0 Human Pilot review concluded
`engineering-pass-teaching-delivery-fail`: process labels such as
`读场 / 立约 / 破题 / 落证 / 收账`, internal evidence IDs, approval wording, and
model working notes reached the visible slides, so audiences saw the
production process instead of the architecture. The root cause is a missing
layer between internal state and external communication:

> internal state is not a speech, a design statement is not a slide, an
> evidence label is not a page title, and a passing validation is not an
> audience conclusion.

## 2. Four-layer page contract

Every presentation page separates four layers. Renderers may display only
layer 3 (plus the fixed boundary labels each route already requires, such as
the state-only notice or the three teaching labels).

| Layer | Contents | May be rendered visibly |
| --- | --- | --- |
| `internal_trace` | `page_id`, `required_entity_ids` / `required_state_ids`, `internal_purpose`, hashes, validation records, source bindings | never |
| `design_content` | the validated state entities a page traces to; the factual basis of the copy | never directly; it is the source the copy must stay faithful to |
| `visible_slide_copy` | `headline` plus optional `supporting_points` written for the declared audience | yes — the only free visible text |
| `speaker_notes` | `delivery_hint`, `evidence_and_limitations` (sources, qualifications, open questions) | never; spoken or printed notes only |

`page_id` values such as `STP-01`, `SOP-03`, or `P-04-precedent-operations`
are internal locators. A renderer may show an ordinary page number
(`02/08`) but never the locator itself.

## 3. Audience context

A handoff without an explicit audience context cannot reach an
audience-ready state, and no builder may guess the audience. The context is a
required object with exactly these fields:

- `presentation_language` — BCP 47 tag (for example `zh-CN`);
- `audience_type` — one of `studio_critic_review`, `jury_review`,
  `client_briefing`, `public_exhibition`, `teaching_demo`;
- `setting` — the review or presentation situation;
- `key_takeaway` — the one thing the audience should understand;
- `planned_minutes` — integer 5–30;
- optional lists (at most 8 unique non-empty strings each):
  `audience_already_knows`, `internal_only_topics`,
  `human_claim_confirmations_required`.

`internal_only_topics` names what must stay in notes; it does not weaken the
structural leakage scan.

## 4. Gate sequence

`scripts/presentation_audience_copy.py` implements one deterministic
sequence, and every path validator calls it:

1. **Audience context** must be structurally valid, otherwise
   `PRESENTATION_AUDIENCE_CONTEXT_INVALID`.
2. **Internal-trace leakage scan** over visible copy only. Internal IDs
   (`E-001`, `RC-002`, `D-001`, `SOP-03`, `P-01-cover`, …), hash-like
   values, machine status codes (`VERIFIED`, `*_INVALID`, `*_MISMATCH`, …),
   and review/PR references hard-fail with
   `PRESENTATION_VISIBLE_COPY_INTERNAL_TRACE`. The same text inside
   `speaker_notes` or `internal_trace` is legitimate and must not be flagged.
3. **Audience-language findings.** Process jargon and production-task wording
   (`读场`, `立约`, `破题`, `落证`, `收账`, `扩面许可`, `书面批准`,
   `一项没删`, `压线合规`, `证据链`, `一张图完成全部辩护`, `本页证明`, …)
   produce review findings. They are **not** global banned words: a human may
   keep one with an explicit reason, and the same wording in notes never
   triggers the visible-area check.
4. **Public-claim gate.** Risky public wording (许可/批准/合规/豁免/不计容/
   不计占地/满足规范/教师书面批准 and the English equivalents permission,
   approved, compliant, exemption, excluded from GFA, code-compliant, …)
   inside visible copy requires a structured public claim record that cites
   resolvable evidence IDs, carries `evidence_status: VERIFIED`, an explicit
   human `confirmed_by`, and `allowed_for_public_display: true`. Otherwise
   the wording is rejected with `PRESENTATION_PUBLIC_CLAIM_UNSUPPORTED`
   (or `PRESENTATION_PUBLIC_CLAIM_REVIEW_REQUIRED` when only the human
   confirmation is missing). `PROVIDED`, `ASSUMED`, `INFERRED`, course
   discussion, and model inference can never back a public claim; use the
   degraded qualified forms instead (「按当前设定初步测算」「设计阶段暂按此
   条件处理」「仍需正式复核」).
5. **Human copy review.** An explicit review record
   (`review_kind: PRESENTATION_HUMAN_COPY_REVIEW`, human `reviewed_by`,
   `status: APPROVED`) must bind the canonical SHA-256 of the audience
   context and of the full reviewed payload — every page in order with its
   trace/supporting IDs (`required_entity_ids` / `required_state_ids`), its
   visible copy, and the public claims — under the current
   `audit_rules_version`. The review also self-binds its own findings block
   (`findings_sha256`), so editing a resolution or a `KEEP_WITH_REASON`
   reason voids the approval. Any payload, context, findings, or rules
   change voids the review (`PRESENTATION_COPY_REVIEW_HASH_MISMATCH`).
   Every language finding must be resolved — rewritten (the finding then no
   longer exists) or kept with an explicit human `KEEP_WITH_REASON` reason —
   otherwise `PRESENTATION_COPY_REVIEW_UNRESOLVED`. A missing or
   non-APPROVED review is `PRESENTATION_COPY_REVIEW_REQUIRED`. Agents must
   never fabricate a review or a `KEEP_WITH_REASON`.

> **What this gate proves — and what it does not.** The validator verifies
> only the internal structure and binding of the handoff: that a claim cites
> evidence records which exist in the transferred chain with the correct
> `E-` record type, that the wording rules pass, and that the review binds
> the exact payload. It does **not** prove any regulation, permission,
> approval, or real-world identity, and the human copy review is not a fact
> check. A `VERIFIED` evidence status is a handoff-internal declaration on a
> resolved evidence record — a necessary condition for a public claim, never
> a sufficient real-world proof.

> **Reviewer label boundary.** Rejecting obvious agent/model/system labels
> (including `glm5.3flash`, `ChatGPT`, `Codex`, `DeepSeek`) is a syntactic
> and procedural boundary only; it is not an identity check. The caller must
> guarantee that the review file was genuinely supplied by a human; this
> gate cannot prove that a real person did the review.

## 5. Public claim record

Exactly these fields: `page_id`, `quoted_text` (a substring of the page's
visible copy containing the risky wording), `claim_type` (one of
`permission`, `approval`, `regulatory_compliance`, `exemption`,
`area_basis`), `evidence_ids`, `evidence_status`, `limitations`,
`allowed_for_public_display`, `confirmed_by`.

Every `evidence_ids` entry must be an `E-`-prefixed evidence record that
actually resolves in the transferred architectural chain. State,
constraint, option, or any other ID kind is refused, and a well-formed but
absent `E-xxx` is refused: `C-001 plus a self-reported VERIFIED` can never
back a public claim.

## 6. Cross-path consistency

The three validators must produce the same verdict for the same content. The
three handoff schemas embed identical `AudienceContext`, `VisibleSlideCopy`,
`SpeakerNotes`, and `PublicClaim` definitions, and the evaluation tests lock
this: a divergence between schema fragments or error codes is a failing
test. The shared error codes are stable identifiers; do not rename them per
path.
