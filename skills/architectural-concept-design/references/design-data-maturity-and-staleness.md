# Design data maturity and global staleness propagation

> **Single authority** for the design-data ledger: maturity, public wording,
> actual-file source bindings, builder provenance, copy-slot bindings, and
> recomputed freshness. R1 closes the four bypasses found in review
> 5170116606: the gate is no longer optional, ledgers cannot self-attest,
> public wording binds to real visible copy, and human freeze confirmation is
> an independent receipt. Additive to ADR-0001 and ARCH-122; it never replaces
> either.

## Contents

- [Purpose](#purpose)
- [1. Three separated concepts](#1-three-separated-concepts)
- [2. Ledger contract (v2)](#2-ledger-contract-v2)
- [3. Independent human review receipt](#3-independent-human-review-receipt)
- [4. Freshness algorithm](#4-freshness-algorithm)
- [5. Recovery](#5-recovery)
- [6. Delivery and intermediate modes](#6-delivery-and-intermediate-modes)
- [7. Public wording on real copy](#7-public-wording-on-real-copy)
- [8. The unique release entry](#8-the-unique-release-entry)
- [9. Stable error codes](#9-stable-error-codes)
- [10. Boundaries](#10-boundaries)

## Purpose

The chain could prove JSON well-formed but could not answer: how mature is
this number, where does it come from, which diagrams and pages consume it, and
what is outdated after one upstream change? The ledger registers key design
data and downstream artifacts so that one changed value marks every dependent
diagram, copy block, PPT page, and deck stale, and stale content cannot reach
final delivery.

## 1. Three separated concepts

| Axis | Values | Question it answers | Authority |
| --- | --- | --- | --- |
| Evidence provenance | `PROVIDED`, `VERIFIED`, `INFERRED`, `ASSUMED`, `PROPOSED` | What backs this claim? | ADR-0001 evidence records |
| Design maturity | `UNRESOLVED`, `WORKING`, `COORDINATED`, `FROZEN_FOR_DELIVERY` | How settled is this value? | This ledger |
| Freshness | `CURRENT`, `STALE` | Is this artifact still bound to current inputs? | Recomputed, never stored |

Maturity never uses `VERIFIED`, never means permit, license, compliance, or
professional approval, and never upgrades an evidence label. A calculated
value records its derivation method, not an evidence label; invalidation is a
freshness event, not a label.

## 2. Ledger contract (v2)

The closed schema is [design-data-maturity.schema.json](design-data-maturity.schema.json)
(`contract_version` `2.0.0`). One ledger holds:

- **data records** — `DD-xxx`, `canonical_value` with its canonical SHA-256
  (ADR-0001 canonicalization), `maturity`, `public_wording`, optional
  `evidence_ids` and `derivation`, `state_entity_ids`, `used_by`, `stale_if`,
  and a mandatory **source binding**: `{document_role, document_sha256,
  json_pointer}` into an actual caller-supplied document. The verifier
  re-reads the pointer from the real file and re-hashes it; a ledger-only
  value or hash edit cannot pass.
- **artifact records** — `ART-xxx`, kind, optional `relative_path` (required
  for physical kinds), `content_sha256`, `deterministic` flag, and
  `built_from`. Caller-authoritative `input_hashes` are removed. A
  deterministic artifact requires a **builder-owned provenance sidecar**
  (`{path, sha256}`) whose own bytes are hash-bound and whose `output_sha256`
  and `inputs` are enforced against the artifact bytes and the data's current
  canonical hashes. The sidecar describes a reproducible build; by itself it
  cannot prove that the builder actually ran or that the artifact was
  regenerated from the current inputs (R2: the self-attestation bypass).
  **Every delivery artifact — deterministic or not — must be covered by the
  independent human review receipt's `artifact_bindings`** (exact
  `content_sha256` plus the canonical input-binding digest); a missing or
  changed binding fails the review.
- **copy bindings** — one record per visible copy slot of the actual handoff
  (`page_id`, `json_pointer`, `text_sha256`, plus either `data_ids` +
  `wording_mode`, or `no_key_data_dependency: true` with a human review
  note). A slot without a binding, a binding without a slot, and any text
  change fail closed.
- **change events** — caller-supplied `event_id` and explicit RFC 3339
  `occurred_at`; the implementation never reads a clock.

`used_by` and `built_from.data_ids` declare the same edge on both ends; any
fork is rejected.

## 3. Independent human review receipt

[design-data-human-review.schema.json](design-data-human-review.schema.json)
is a separate caller-supplied file; an agent must never generate it, and the
reviewed-by label passes the same human-label boundary as the ARCH-122 copy
review (agent, model, bot, and system labels are rejected). It binds:

- `status` (only `APPROVED` may enter delivery);
- `ledger_canonical_sha256` — any ledger edit voids the review;
- `frozen_data_bindings` — every `COORDINATED`/`FROZEN_FOR_DELIVERY` value and
  wording; one changed digit voids the review;
- `public_wording_bindings_sha256` — the copy-bindings section;
- `artifact_bindings` — the exact input/output hash combination of **every
  delivery artifact, deterministic or not** (R2: a deterministic artifact can
  no longer skip the independent human binding);
- `findings`, `findings_resolutions`, and their self-binding hash;
- `audit_rules_version`.

This check is a syntactic and process gate: it does not prove that a real
human acted in the real world — the caller is responsible for supplying a
genuine human record, and an agent must never fabricate one.

## 4. Freshness algorithm

Freshness is always recomputed by `scripts/design_data_staleness.py`; no
stored verdict is trusted. A data record is STALE when its canonical value no
longer matches its recorded hash (`DATA_VALUE_CHANGED_UNBOUND`), when the
bound actual document's bytes changed (`SOURCE_DOCUMENT_CHANGED`), when the
value re-read from the pointer contradicts the ledger (`SOURCE_BINDING_MISMATCH`),
when a bound ADR-0001 state entity carries a propagate-stale record
(`STATE_CHAIN_STALE`), or when any `stale_if` upstream data is stale. An
artifact is STALE when its file is missing or its bytes changed
(`FILE_MISSING`, `CONTENT_HASH_CHANGED`), when an SVG manifest's referenced
assets no longer match (`MANIFEST_ASSET_MISMATCH`), when its provenance
sidecar is missing, altered, or claims an output that the artifact bytes do
not match (`PROVENANCE_MISMATCH`, `PROVENANCE_OUTPUT_MISMATCH`), when a
provenance input hash differs from the data's current canonical hash
(`INPUT_HASH_CHANGED`), or when any upstream data or artifact is stale.
Traversal is sorted and memoized; key order and record order cannot change any
result.

## 5. Recovery

Editing the ledger cannot clear staleness: data edits are checked against
actual documents, artifact staleness is checked against actual bytes, and any
ledger edit voids the human review hash. Recovery means changing the actual
source, rebuilding the artifact from current inputs, refreshing the
builder-owned provenance, registering the new hashes in the ledger, and
obtaining a fresh human review. Only the rebuilt closure becomes CURRENT.

## 6. Delivery and intermediate modes

`--mode intermediate|delivery` is explicit and mandatory wherever a deck is
rendered or validated; a missing mode is a stable `MODE_REQUIRED` rejection.

- **INTERMEDIATE** — exploration and teaching decks. Products are marked
  `INTERMEDIATE_NOT_FOR_DELIVERY` in the deck manifest and structure report,
  may omit the freshness inputs entirely, must not carry delivery freshness
  arguments, can never emit `PPTX_VALIDATED` (E2E reports
  `INTERMEDIATE_PPTX_VALIDATED` with an `intermediate_only` check), and are
  stably rejected by the release entry.
- **DELIVERY** — requires the ledger, the freshness receipt, the independent
  human review receipt, the actual handoff and state documents, and the actual
  PPTX; every entry re-verifies against the real files (`verify-delivery`,
  E2E delivery mode, and the release verifier). Any missing input, any stale
  bound entry, or any receipt/recomputation mismatch fails closed.

## 7. Public wording on real copy

Copy bindings tie ledger data to the handoff's actual `headline` and
`supporting_points` slots. The verifier re-hashes the real copy text from the
handoff document and enforces: `UNRESOLVED` data is refused; `NOT_PUBLIC`
values are refused; `WORKING` can only bind `QUALIFIED_ESTIMATE` and its
declared qualified template must appear in the actual text (so a plain
definite expression fails even with an approved review);
`COORDINATED`/`FROZEN_FOR_DELIVERY` may bind `CURRENT_DESIGN_VALUE`. Wording
is confirmed by the human review receipt — never by a global banned-word scan,
and the ledger never generates copy: visible text still comes only from
ARCH-122 `visible_slide_copy` plus its hash-bound human review. Permits,
approvals, compliance, and exemptions still require the ARCH-122 public claim
gate with `VERIFIED` evidence; maturity never overrides it.

## 8. The unique release entry

`scripts/release-verified-pptx.mjs` is the only authorized PPTX release entry
and runs the freshness stage first. Its closed request schema takes
`mode: "delivery"`, the ledger, receipt, human review, handoff and state
document paths, and nothing else: verifier executables, environments, and
verdict fields are rejected as `INVALID_REQUEST`. The compositor recomputes
the candidate PPTX SHA-256 itself, then invokes the fixed repository verifier
(`skills/architectural-concept-design/scripts/design_data_staleness.py
verify-release`) with an argument array, `shell: false`, and a pinned
environment — no PATH search, no caller executable, no network, no clock. A
nonzero exit, empty or malformed output, any stderr output, a non-DELIVERY
mode, or a PPTX hash mismatch fails closed before the ARCH-089 visual QA and
ARCH-088 integrity gates run.

## 9. Stable error codes

Structural: `DATA_ID_NOT_UNIQUE`, `ARTIFACT_ID_NOT_UNIQUE`,
`EVENT_ID_NOT_UNIQUE`, `REF_NOT_FOUND`, `DATA_ARTIFACT_EDGE_MISMATCH`,
`LEDGER_GRAPH_CYCLE`, `MATURITY_WORDING_CONFLICT`, `WORDING_TEMPLATE_INVALID`,
`PHYSICAL_ARTIFACT_PATH_REQUIRED`, `PROVENANCE_REQUIRED`,
`SOURCE_BINDING_INVALID`, `COPY_BINDING_AMBIGUOUS`, `COPY_BINDING_NOTE_REQUIRED`,
`COPY_WORDING_MISMATCH`, `UNRESOLVED_DATA_BOUND_TO_COPY`,
`NOT_PUBLIC_DATA_BOUND_TO_COPY`.

Freshness reasons: `DATA_VALUE_CHANGED_UNBOUND`, `SOURCE_DOCUMENT_CHANGED`,
`SOURCE_BINDING_MISMATCH`, `UPSTREAM_DATA_STALE`, `STATE_CHAIN_STALE`,
`INPUT_HASH_CHANGED`, `CONTENT_HASH_CHANGED`, `FILE_MISSING`,
`MANIFEST_ASSET_MISMATCH`, `PROVENANCE_MISMATCH`, `PROVENANCE_OUTPUT_MISMATCH`,
`UPSTREAM_ARTIFACT_STALE`.

Delivery, review, and copy: `RECEIPT_MISMATCH`, `RECEIPT_NOT_CURRENT`,
`RECEIPT_BINDING_MISSING`, `HUMAN_REVIEW_REQUIRED`, `HUMAN_REVIEW_NOT_APPROVED`,
`HUMAN_REVIEWER_LABEL_REJECTED`, `REVIEW_HASH_MISMATCH`,
`REVIEW_ARTIFACT_BINDING_MISSING`, `DOCUMENT_ROLE_MISSING`,
`COPY_SHAPE_UNKNOWN`, `COPY_POINTER_NOT_FOUND`, `COPY_TEXT_CHANGED`,
`COPY_BINDING_MISSING`, `UNRESOLVED_DATA_IN_VISIBLE_COPY`,
`NOT_PUBLIC_VALUE_VISIBLE`, `UNQUALIFIED_ESTIMATE_VISIBLE`,
`CURRENT_DESIGN_VALUE_VISIBLE_MISMATCH`,
`COPY_DATA_REF_NOT_FOUND`, `MODE_REQUIRED`, `INTERMEDIATE_MODE_REJECTS_FRESHNESS_INPUTS`,
`DELIVERY_FRESHNESS_RECEIPT_REQUIRED`, `DELIVERY_STALE_CONTENT_BLOCKED`,
`DELIVERY_FRESHNESS_INVALID`, `FRESHNESS_GATE_INVALID`,
`FRESHNESS_RECEIPT_MISMATCH`, `FRESHNESS_RECEIPT_STALE`.

Release entry: `FRESHNESS_VERIFIER_UNAVAILABLE`,
`FRESHNESS_VERIFICATION_FAILED`, `FRESHNESS_VERIFIER_OUTPUT_INVALID`,
`FRESHNESS_PPTX_UNREADABLE`, `FRESHNESS_PPTX_HASH_MISMATCH`.

## 10. Boundaries

The layer never modifies business schemas, never invents design content,
never claims a permit or compliance outcome, never replaces human decisions,
the copy review, or the public claim gate, and never marks anything CURRENT
without recomputation against actual files. No new dependencies; canonical
hashing reuses the ADR-0001 implementation; no network, no clock, no shell in
the Python verifier itself.
