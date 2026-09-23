"""Shared audience-copy gate for all three local presentation handoff paths.

This module is the single authority for the four-layer page contract
(``internal_trace`` / ``design_content`` / ``visible_slide_copy`` /
``speaker_notes``), the audience context, the internal-trace leakage scan,
the audience-language review, the public-claim gate, and the human copy
review with canonical hash binding. The runtime-candidate, state-only, and
synthetic-teaching validators must all call these functions; they must not
re-implement divergent rules.

The gate is local-only and deterministic: no network, no subprocess, no
browser, no system clock, no file writes, and no mutation of its inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

JsonObject = dict[str, Any]

REVIEW_KIND = "PRESENTATION_HUMAN_COPY_REVIEW"
REVIEW_STATUS_APPROVED = "APPROVED"
REVIEW_RESOLUTION_KEEP = "KEEP_WITH_REASON"

# Version of the audit rules baked into every review binding hash. Bumping it
# voids every existing review, which is the intended fail-closed behavior.
AUDIT_RULES_VERSION = "1.0.0"
REVIEW_REQUIRED_FIELDS = (
    "review_kind",
    "reviewed_by",
    "reviewed_at",
    "scope",
    "audience_context_sha256",
    "visible_copy_sha256",
    "findings_sha256",
    "audit_rules_version",
    "findings",
    "status",
)

# Only a real evidence record (E-xxx) carried by the transferred
# architectural chain may back a public claim. State, constraint, option, or
# any other ID kind is not an evidence record and can never support one.
EVIDENCE_RECORD_PREFIX = "E-"
# The claim's evidence_status is a handoff-internal declaration. This gate
# verifies structure and binding only; it cannot and does not prove any
# external fact.
SUPPORTED_EVIDENCE_STATUSES = ("VERIFIED",)

AUDIENCE_TYPES = (
    "studio_critic_review",
    "jury_review",
    "client_briefing",
    "public_exhibition",
    "teaching_demo",
)
AUDIENCE_CONTEXT_REQUIRED = (
    "presentation_language",
    "audience_type",
    "setting",
    "key_takeaway",
    "planned_minutes",
)
AUDIENCE_CONTEXT_OPTIONAL_LISTS = ("audience_already_knows", "internal_only_topics", "human_claim_confirmations_required")
PUBLIC_CLAIM_TYPES = (
    "permission",
    "approval",
    "regulatory_compliance",
    "exemption",
    "area_basis",
)
PUBLIC_CLAIM_REQUIRED = (
    "page_id",
    "quoted_text",
    "claim_type",
    "evidence_ids",
    "evidence_status",
    "limitations",
    "allowed_for_public_display",
    "confirmed_by",
)

# Stable, cross-path error codes. Validators must reuse these verbatim.
CODE_AUDIENCE_CONTEXT_INVALID = "PRESENTATION_AUDIENCE_CONTEXT_INVALID"
CODE_VISIBLE_COPY_INTERNAL_TRACE = "PRESENTATION_VISIBLE_COPY_INTERNAL_TRACE"
CODE_COPY_REVIEW_REQUIRED = "PRESENTATION_COPY_REVIEW_REQUIRED"
CODE_COPY_REVIEW_UNRESOLVED = "PRESENTATION_COPY_REVIEW_UNRESOLVED"
CODE_COPY_REVIEW_HASH_MISMATCH = "PRESENTATION_COPY_REVIEW_HASH_MISMATCH"
CODE_PUBLIC_CLAIM_UNSUPPORTED = "PRESENTATION_PUBLIC_CLAIM_UNSUPPORTED"
CODE_PUBLIC_CLAIM_REVIEW_REQUIRED = "PRESENTATION_PUBLIC_CLAIM_REVIEW_REQUIRED"
CODE_AUDIENCE_COPY_PAGES_INCOMPLETE = "PRESENTATION_AUDIENCE_COPY_PAGES_INCOMPLETE"

# Internal trace tokens that may never reach a visible area. This is a
# targeted structural scan (state IDs, error codes, hashes, review numbers,
# page locator IDs), not a general-purpose banned-word list.
INTERNAL_ID_RE = re.compile(
    r"\b(?:E|C|S|R|H|O|K|D|A|VA|RC|RCR|SRC|REQ|CONF|UNK|PH|SOH|STH|SOP|STP|P)-\d{2,}(?:-[a-z0-9]+)*\b",
    re.IGNORECASE,
)
HASH_LIKE_RE = re.compile(r"\b[0-9a-f]{40,64}\b", re.IGNORECASE)
MACHINE_STATUS_RE = re.compile(
    r"\bVERIFIED\b|\b[A-Z][A-Z0-9_]{2,}_(?:INVALID|MISMATCH|FORBIDDEN|MISSING|FAILED|REQUIRED|UNRESOLVED|BLOCKED|DUPLICATE)\b",
)
REVIEW_RECORD_RE = re.compile(r"\bPR[- ]#?\d+\b|\breview(?:er)?\s*id\s*[:=]", re.IGNORECASE)

# Audience-language risk patterns. A hit is a review finding for a human to
# resolve (rewrite the copy, or keep it with an explicit human reason); it is
# never an automatic rejection and never a global repository-wide ban — the
# same wording inside speaker_notes or internal_trace is legitimate.
PROCESS_LANGUAGE_PATTERNS = (
    "先读墙",
    "读场",
    "立约",
    "破题",
    "落证",
    "收账",
    "扩面许可",
    "分毫未动",
    "一项没删",
    "压线合规",
    "书面批准",
    "任务书口径",
    "证据链",
    "一张图完成全部辩护",
    "每张证明一件事",
    "三张文脉牌",
    "三条红线",
    "全部兑现",
    "本页证明",
    "evidence chain",
    "closing the books",
)

# High-risk public claim wording. Any occurrence inside visible copy requires
# a structured, human-confirmed public claim record; insufficient backing
# forces the degraded, qualified wording instead.
PUBLIC_CLAIM_RISK_PATTERNS = (
    "许可",
    "批准",
    "合规",
    "豁免",
    "不计容",
    "不计占地",
    "满足规范",
    "符合规范",
    "教师书面批准",
    "扩面许可",
    "permission",
    "approved",
    "approval",
    "compliant",
    "compliance",
    "exemption",
    "excluded from gfa",
    "excluded from far",
    "code-compliant",
    "code compliant",
)


class AudienceError(TypedDict):
    """One deterministic audience-copy gate error."""

    code: str
    path: str
    message: str


class CopyFinding(TypedDict):
    """One audience-language risk finding that a human review must resolve."""

    page_id: str
    matched_text: str
    pattern: str


def canonical_json_sha256(payload: object) -> str:
    """Return the shared canonical JSON SHA-256 used for hash binding."""

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audience_context_sha256(audience_context: Mapping[str, Any]) -> str:
    """Return the canonical hash binding a copy review to the audience context."""

    return canonical_json_sha256(audience_context)


def visible_copy_sha256(pages: Sequence[Mapping[str, Any]], public_claims: Sequence[Mapping[str, Any]]) -> str:
    """Return the canonical hash binding a copy review to the reviewed payload.

    The binding covers the audit-rules version, every page in order with its
    trace/supporting IDs (`required_entity_ids` / `required_state_ids`) and
    its visible copy, and the full public-claim records including their
    evidence IDs, status, limitations, and display decision. Changing any of
    these after a review voids it.
    """

    return canonical_json_sha256(
        {
            "audit_rules_version": AUDIT_RULES_VERSION,
            "pages": [
                {
                    "page_id": page.get("page_id"),
                    "required_entity_ids": page.get("required_entity_ids"),
                    "required_state_ids": page.get("required_state_ids"),
                    "visible_slide_copy": page.get("visible_slide_copy"),
                }
                for page in pages
            ],
            "public_claims": list(public_claims),
        }
    )


def findings_sha256(findings: Sequence[Mapping[str, Any]]) -> str:
    """Return the canonical hash binding a review to its own findings record.

    Editing a resolution or a `KEEP_WITH_REASON` reason changes this hash, so
    a tampered findings block can never ride along with an old approval.
    """

    return canonical_json_sha256(list(findings))


def is_human_reviewer_label(value: object) -> bool:
    """Reject obvious agent, model, bot, and system labels as human reviewers.

    This is a syntactic and procedural boundary, not an identity check: the
    caller is responsible for ensuring the review file really was supplied by
    a human. The gate verifies structure and binding, never real-world
    identity.
    """

    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    lowered = text.lower()
    forbidden = (
        "codex", "deepseek", "agent", "bot", "model", "gpt", "chatgpt",
        "claude", "glm", "flash", "llm", "system", "auto", "pipeline",
        "openai", "anthropic", "gemini", "qwen", "kimi", "mistral", "llama",
    )
    return not any(token in lowered for token in forbidden)


def error(code: str, path: str, message: str) -> AudienceError:
    return {"code": code, "path": path, "message": message}


def validate_audience_context(context: object, errors: list[AudienceError], path: str = "/audience_context") -> bool:
    """Validate the required audience context; never guess the audience."""

    if not isinstance(context, Mapping):
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, path, "audience context is required and must be an object"))
        return False
    unknown = sorted(set(context) - set(AUDIENCE_CONTEXT_REQUIRED) - set(AUDIENCE_CONTEXT_OPTIONAL_LISTS))
    missing = [field for field in AUDIENCE_CONTEXT_REQUIRED if field not in context]
    if unknown or missing:
        errors.append(
            error(
                CODE_AUDIENCE_CONTEXT_INVALID,
                path,
                f"audience context must define exactly {sorted(AUDIENCE_CONTEXT_REQUIRED)} plus optional lists; missing={missing}, unknown={unknown}",
            )
        )
        return False
    language = context.get("presentation_language")
    if not isinstance(language, str) or not re.fullmatch(r"[a-zA-Z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/presentation_language", "presentation_language must be a BCP 47 language tag"))
    if context.get("audience_type") not in AUDIENCE_TYPES:
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/audience_type", f"audience_type must be one of {list(AUDIENCE_TYPES)}"))
    for field in ("setting", "key_takeaway"):
        value = context.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/{field}", f"{field} must be a non-empty string"))
    minutes = context.get("planned_minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 5 <= minutes <= 30:
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/planned_minutes", "planned_minutes must be an integer between 5 and 30"))
    for field in AUDIENCE_CONTEXT_OPTIONAL_LISTS:
        values = context.get(field)
        if values is None:
            continue
        if (
            not isinstance(values, list)
            or len(values) > 8
            or not all(isinstance(item, str) and item.strip() for item in values)
            or len(values) != len({item for item in values if isinstance(item, str)})
        ):
            errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/{field}", f"{field} must be a list of at most 8 unique non-empty strings"))
    return not any(item["code"] == CODE_AUDIENCE_CONTEXT_INVALID for item in errors)


def _visible_texts(page: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Yield (field_path, text) for every string that would be rendered."""

    texts: list[tuple[str, str]] = []
    copy = page.get("visible_slide_copy")
    if not isinstance(copy, Mapping):
        return texts
    headline = copy.get("headline")
    if isinstance(headline, str):
        texts.append((f"{page.get('page_id', '?')}/visible_slide_copy/headline", headline))
    points = copy.get("supporting_points")
    if isinstance(points, list):
        for index, point in enumerate(points):
            if isinstance(point, str):
                texts.append((f"{page.get('page_id', '?')}/visible_slide_copy/supporting_points/{index}", point))
    return texts


def scan_visible_copy(pages: Sequence[Mapping[str, Any]], errors: list[AudienceError]) -> list[CopyFinding]:
    """Hard-fail internal trace leakage and collect audience-language findings."""

    findings: list[CopyFinding] = []
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        for field_path, text in _visible_texts(page):
            for label, pattern in (
                ("internal ID", INTERNAL_ID_RE),
                ("hash-like value", HASH_LIKE_RE),
                ("machine status code", MACHINE_STATUS_RE),
                ("review record reference", REVIEW_RECORD_RE),
            ):
                if pattern.search(text):
                    errors.append(
                        error(
                            CODE_VISIBLE_COPY_INTERNAL_TRACE,
                            f"/deck_framework/{field_path}",
                            f"visible copy must not contain {label} data: internal_trace stays out of visible areas",
                        )
                    )
            lowered = text.lower()
            for pattern in PROCESS_LANGUAGE_PATTERNS:
                if pattern.lower() in lowered:
                    findings.append({"page_id": str(page.get("page_id", "?")), "matched_text": text, "pattern": pattern})
    return findings


def validate_public_claims(
    pages: Sequence[Mapping[str, Any]],
    public_claims: object,
    resolvable_ids: set[str],
    errors: list[AudienceError],
) -> None:
    """Require structured human-confirmed backing for risky public wording."""

    claims = public_claims if isinstance(public_claims, list) else []
    deck_page_ids = {str(page.get("page_id")) for page in pages if isinstance(page, Mapping) and isinstance(page.get("page_id"), str)}
    for index, claim in enumerate(claims):
        path = f"/public_claims/{index}"
        if not isinstance(claim, Mapping) or any(field not in claim for field in PUBLIC_CLAIM_REQUIRED) or set(claim) != set(PUBLIC_CLAIM_REQUIRED):
            errors.append(error(CODE_PUBLIC_CLAIM_UNSUPPORTED, path, f"public claim must define exactly {sorted(PUBLIC_CLAIM_REQUIRED)}"))
            continue
        if claim.get("page_id") not in deck_page_ids:
            errors.append(error(CODE_PUBLIC_CLAIM_UNSUPPORTED, f"{path}/page_id", "public claim page_id must name a page in this deck"))
        if claim.get("claim_type") not in PUBLIC_CLAIM_TYPES:
            errors.append(error(CODE_PUBLIC_CLAIM_UNSUPPORTED, f"{path}/claim_type", f"claim_type must be one of {list(PUBLIC_CLAIM_TYPES)}"))
        evidence_ids = claim.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids or not all(isinstance(item, str) for item in evidence_ids):
            errors.append(error(CODE_PUBLIC_CLAIM_UNSUPPORTED, f"{path}/evidence_ids", "public claim must cite at least one internal evidence record ID"))
        else:
            for evidence_id in evidence_ids:
                if not isinstance(evidence_id, str):
                    continue
                if not evidence_id.startswith(EVIDENCE_RECORD_PREFIX):
                    errors.append(
                        error(
                            CODE_PUBLIC_CLAIM_UNSUPPORTED,
                            f"{path}/evidence_ids",
                            f"{evidence_id} is not an evidence record: only {EVIDENCE_RECORD_PREFIX}-prefixed IDs carried by the transferred chain may back a claim",
                        )
                    )
                elif evidence_id not in resolvable_ids:
                    errors.append(
                        error(
                            CODE_PUBLIC_CLAIM_UNSUPPORTED,
                            f"{path}/evidence_ids",
                            f"{evidence_id} does not resolve to an evidence record in the transferred architectural chain; a well-formed but absent ID is refused",
                        )
                    )
        if claim.get("evidence_status") not in SUPPORTED_EVIDENCE_STATUSES:
            errors.append(
                error(
                    CODE_PUBLIC_CLAIM_UNSUPPORTED,
                    f"{path}/evidence_status",
                    f"only an exact {list(SUPPORTED_EVIDENCE_STATUSES)} declaration on a resolved evidence record may back a public claim; case or spacing variants and PROVIDED/ASSUMED/INFERRED wording must stay degraded",
                )
            )
        if claim.get("allowed_for_public_display") is not True:
            errors.append(error(CODE_PUBLIC_CLAIM_UNSUPPORTED, f"{path}/allowed_for_public_display", "the human reviewer must allow this wording for public display"))
        if not is_human_reviewer_label(claim.get("confirmed_by")):
            errors.append(error(CODE_PUBLIC_CLAIM_REVIEW_REQUIRED, f"{path}/confirmed_by", "a public claim requires an explicit human confirmation, not an agent label"))

    supported: set[tuple[str, str]] = set()
    for claim in claims:
        if isinstance(claim, Mapping) and isinstance(claim.get("page_id"), str) and isinstance(claim.get("quoted_text"), str):
            supported.add((claim["page_id"], claim["quoted_text"]))
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        page_id = str(page.get("page_id", "?"))
        for _field_path, text in _visible_texts(page):
            for pattern in PUBLIC_CLAIM_RISK_PATTERNS:
                if pattern.lower() in text.lower() and not any(
                    page_id == claimed_page and pattern.lower() in quoted.lower() and quoted.lower() in text.lower()
                    for claimed_page, quoted in supported
                ):
                    errors.append(
                        error(
                            CODE_PUBLIC_CLAIM_UNSUPPORTED,
                            f"/deck_framework/{_field_path}",
                            f"risky public wording {pattern!r} requires a human-confirmed public claim backed by VERIFIED evidence; use qualified degraded wording instead",
                        )
                    )


def validate_human_copy_review(
    review: object,
    expected_audience_hash: str,
    expected_visible_hash: str,
    findings: Sequence[Mapping[str, Any]],
    errors: list[AudienceError],
) -> None:
    """Fail closed unless an explicit human review binds the exact reviewed payload.

    The reviewer label check is a syntactic and procedural boundary, not an
    identity proof: the caller must guarantee the review file was genuinely
    supplied by a human. The gate verifies the structure, the binding hashes,
    and that every finding is resolved.
    """

    if not isinstance(review, Mapping):
        errors.append(error(CODE_COPY_REVIEW_REQUIRED, "/human_copy_review", "an explicit human copy review is required before audience-ready status"))
        return
    if set(review) != set(REVIEW_REQUIRED_FIELDS):
        errors.append(
            error(
                CODE_COPY_REVIEW_REQUIRED,
                "/human_copy_review",
                f"review must define exactly {sorted(REVIEW_REQUIRED_FIELDS)}; missing={sorted(set(REVIEW_REQUIRED_FIELDS) - set(review))}, unexpected={sorted(set(review) - set(REVIEW_REQUIRED_FIELDS))}",
            )
        )
        return
    if review.get("review_kind") != REVIEW_KIND:
        errors.append(error(CODE_COPY_REVIEW_REQUIRED, "/human_copy_review/review_kind", f"review_kind must be {REVIEW_KIND}"))
    if not is_human_reviewer_label(review.get("reviewed_by")):
        errors.append(error(CODE_COPY_REVIEW_REQUIRED, "/human_copy_review/reviewed_by", "reviewed_by must identify a human, not an agent, model, or system label"))
    if review.get("status") != REVIEW_STATUS_APPROVED:
        errors.append(error(CODE_COPY_REVIEW_REQUIRED, "/human_copy_review/status", "the copy review must be APPROVED; PENDING and REVISE stay blocked"))
    if review.get("audit_rules_version") != AUDIT_RULES_VERSION:
        errors.append(error(CODE_COPY_REVIEW_HASH_MISMATCH, "/human_copy_review/audit_rules_version", f"the review was made under audit rules {review.get('audit_rules_version')!r}, but the current rules are {AUDIT_RULES_VERSION!r}; re-review required"))
    if review.get("audience_context_sha256") != expected_audience_hash:
        errors.append(error(CODE_COPY_REVIEW_HASH_MISMATCH, "/human_copy_review/audience_context_sha256", "the review is bound to a different audience context; re-review required"))
    if review.get("visible_copy_sha256") != expected_visible_hash:
        errors.append(error(CODE_COPY_REVIEW_HASH_MISMATCH, "/human_copy_review/visible_copy_sha256", "the reviewed pages, trace IDs, visible copy, or public claims changed after review; the old review is void"))
    recorded_findings = review.get("findings")
    if not isinstance(recorded_findings, list):
        errors.append(error(CODE_COPY_REVIEW_REQUIRED, "/human_copy_review/findings", "findings must be a list"))
        recorded_findings = []
    if review.get("findings_sha256") != findings_sha256(recorded_findings):
        errors.append(error(CODE_COPY_REVIEW_HASH_MISMATCH, "/human_copy_review/findings_sha256", "the recorded findings, resolutions, or KEEP_WITH_REASON reasons were edited after approval; the old review is void"))
    covered = {
        (item.get("page_id"), item.get("matched_text"))
        for item in recorded_findings
        if isinstance(item, Mapping) and item.get("resolution") == REVIEW_RESOLUTION_KEEP and isinstance(item.get("reason"), str) and item["reason"].strip()
    }
    for finding in findings:
        if (finding.get("page_id"), finding.get("matched_text")) not in covered:
            errors.append(
                error(
                    CODE_COPY_REVIEW_UNRESOLVED,
                    f"/deck_framework/{finding.get('page_id')}",
                    f"audience-language finding {finding.get('pattern')!r} is unresolved; rewrite the copy or record an explicit human KEEP_WITH_REASON",
                )
            )


AUDIENCE_COPY_KIND = "PRESENTATION_AUDIENCE_COPY"


def validate_audience_copy_document(
    document: object,
    expected_page_ids: Sequence[str],
    errors: list[AudienceError],
    path: str = "/audience_copy",
) -> tuple[JsonObject, dict[str, JsonObject], list[JsonObject]]:
    """Validate the shared builder input that supplies audience copy for a deck.

    Builders never invent visible copy: they either receive this explicit
    document or fail closed. Returns (audience_context, pages_by_id,
    public_claims); the structures are only trustworthy when ``errors`` stays
    empty for the returned codes other than context-detail errors.
    """

    context: JsonObject = {}
    pages_by_id: dict[str, JsonObject] = {}
    claims: list[JsonObject] = []
    if not isinstance(document, Mapping):
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, path, "an explicit audience-copy document is required; builders must not invent visible copy"))
        return context, pages_by_id, claims
    if document.get("copy_kind") != AUDIENCE_COPY_KIND:
        errors.append(error(CODE_AUDIENCE_CONTEXT_INVALID, f"{path}/copy_kind", f"copy_kind must be {AUDIENCE_COPY_KIND}"))
    provided = document.get("pages")
    if not isinstance(provided, list):
        errors.append(error(CODE_AUDIENCE_COPY_PAGES_INCOMPLETE, f"{path}/pages", "the audience-copy document must list every deck page in order"))
        provided = []
    provided_ids = [page.get("page_id") for page in provided if isinstance(page, Mapping) and isinstance(page.get("page_id"), str)]
    if provided_ids != list(expected_page_ids):
        errors.append(
            error(
                CODE_AUDIENCE_COPY_PAGES_INCOMPLETE,
                f"{path}/pages",
                f"audience-copy pages must match the deck page sequence exactly; expected {list(expected_page_ids)}, got {provided_ids}",
            )
        )
    for index, page in enumerate(provided):
        if not isinstance(page, Mapping):
            continue
        page_id = page.get("page_id")
        if isinstance(page_id, str):
            pages_by_id[page_id] = page
    claims = document.get("public_claims") if isinstance(document.get("public_claims"), list) else []
    validate_audience_context(document.get("audience_context"), errors, f"{path}/audience_context")
    context = document.get("audience_context") if isinstance(document.get("audience_context"), Mapping) else {}
    return context, pages_by_id, claims


def audience_readiness_errors(
    deck_framework: Sequence[Mapping[str, Any]],
    audience_context: object,
    public_claims: object,
    copy_review: object,
    resolvable_ids: set[str],
) -> list[AudienceError]:
    """Run the full shared gate and return its deterministic error list."""

    errors: list[AudienceError] = []
    validate_audience_context(audience_context, errors)
    findings = scan_visible_copy(deck_framework, errors)
    validate_public_claims(deck_framework, public_claims, resolvable_ids, errors)
    audience_hash = audience_context_sha256(audience_context) if isinstance(audience_context, Mapping) else ""
    visible_hash = visible_copy_sha256(deck_framework, public_claims if isinstance(public_claims, list) else [])
    validate_human_copy_review(copy_review, audience_hash, visible_hash, findings, errors)
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors
