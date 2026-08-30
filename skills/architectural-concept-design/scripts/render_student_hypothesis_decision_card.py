"""Render one deterministic Simplified-Chinese decision card for a pending ARCH-104 comparison.

This local, offline, read-only renderer accepts only a valid, untampered
ARCH-104 student hypothesis comparison in the pending_selection state. It
reuses ARCH-104's public validation entry, therefore re-running the full
ARCH-097~104 chain with upstream error codes propagated unchanged. It writes
UTF-8 Markdown to stdout only: it creates no file, receipt, selection record,
or architectural decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import build_student_hypothesis_comparison as comparison_builder
from build_student_spatial_program import (
    _error,
    _load_failure,
    load_json_object,
)

JsonObject = Mapping[str, Any]

NO_SINGLE_BASIS_SENTENCE = "当前没有足够依据给出单一优先建议。"
GUIDANCE_BOUNDARY_SENTENCE = "这是帮助你判断的决策引导，不是自动替你做建筑决定。"

CONFIRMED_UPSTREAM_LINE = (
    "上游已确认：任务书摘要、设计启动板、空间任务书、尺寸计划、人类尺寸选择、"
    "楼层分区框架与流线环境框架均已确认，体量-柱网-层高假设框架已通过验证。"
)

_SCHEMA_KEYS: tuple[str, ...] = (
    "intake",
    "digest",
    "board",
    "program_draft",
    "program",
    "dimension_draft",
    "dimension_plan",
    "selection",
    "zoning_draft",
    "zoning",
    "ce_draft",
    "ce",
    "mgh_draft",
    "mgh",
    "comparison_draft",
    "comparison",
)

_CHAIN_ARGUMENTS: tuple[tuple[str, str], ...] = (
    ("digest", "confirmed assignment brief digest JSON"),
    ("board", "student design start board JSON"),
    ("program_draft", "confirmed student spatial program draft JSON"),
    ("program", "student spatial program JSON"),
    ("dimension_draft", "confirmed student dimension plan draft JSON"),
    ("dimension_plan", "student dimension plan JSON"),
    ("selection", "human dimension selection record JSON"),
    ("zoning_draft", "confirmed student floor zoning draft JSON"),
    ("zoning_framework", "student floor zoning framework JSON"),
    ("ce_draft", "confirmed student circulation-environment draft JSON"),
    ("ce_framework", "student circulation-environment framework JSON"),
    ("mgh_draft", "confirmed student massing-grid-height draft JSON"),
    ("mgh_framework", "student massing-grid-height framework JSON"),
    ("comparison_draft", "confirmed student hypothesis comparison draft JSON"),
)


class CardError(TypedDict):
    """One deterministic rejection without a partial card."""

    code: str
    path: str
    message: str


class CardResult(TypedDict):
    """The public result of rendering one decision card."""

    ok: bool
    errors: list[CardError]


def _blank(value: Any) -> bool:
    """Return True unless the value is a human-readable non-blank string."""

    return not isinstance(value, str) or not value.strip()


def _blank_list(items: Any) -> bool:
    """Return True unless the value is a non-empty list of non-blank strings."""

    if not isinstance(items, Sequence) or isinstance(items, str) or not items:
        return True
    return any(_blank(item) for item in items)


def _pending_selection_errors(document: JsonObject) -> list[CardError]:
    """Fail closed unless the document is a pending_selection comparison."""

    if document.get("selection_status") != "pending_selection":
        return [_error("DECISION_CARD_NOT_PENDING_SELECTION", "/selection_status", "the decision card renderer accepts only a pending_selection comparison; a selected comparison is answered by its human selection record")]
    return []


def _source_incomplete_errors(document: JsonObject) -> list[CardError]:
    """Fail closed when any human fact the card needs is missing or blank."""

    errors: list[CardError] = []
    view = document.get("student_view")
    if not isinstance(view, Mapping):
        return [_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view", "the comparison document carries no student view")]
    if _blank(view.get("decision_prompt")):
        errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/decision_prompt", "the decision card needs a human-traceable decision prompt"))
    candidates = view.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, str) or not 2 <= len(candidates) <= 6:
        return errors + [_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/candidates", "the decision card needs the two to six real human-authored candidates")]
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/candidates/{index}", "each candidate must be a human-authored record"))
            continue
        if _blank(candidate.get("label")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/candidates/{index}/label", "each candidate needs its human-written label"))
        if _blank(candidate.get("note")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/candidates/{index}/note", "each candidate needs its human-written description of what it is"))
        assessment = candidate.get("student_assessment")
        if not isinstance(assessment, Mapping):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/candidates/{index}/student_assessment", "each candidate needs its human-written assessment"))
            continue
        for field in ("applicable_preconditions", "advantages", "costs_or_risks", "reconsider_when"):
            if _blank_list(assessment.get(field)):
                errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/candidates/{index}/student_assessment/{field}", "each candidate needs human-written applicable preconditions, advantages, costs or risks, and overturn conditions"))
    guidance = view.get("guidance")
    if isinstance(guidance, Mapping) and guidance.get("status") == "guidance_available":
        if _blank(guidance.get("basis")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/guidance/basis", "the guidance needs its human-written basis"))
        if _blank_list(guidance.get("basis_criteria")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/guidance/basis_criteria", "the guidance needs its human-written basis criteria"))
        for field in ("advantages", "costs_or_risks", "reconsider_when"):
            if _blank_list(guidance.get(field)):
                errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", f"/student_view/guidance/{field}", "the guidance needs human-written advantages, costs or risks, and overturn conditions"))
        if "recommended_to_consider_first" in guidance and _blank(guidance.get("recommended_to_consider_first")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/guidance/recommended_to_consider_first", "a single focus suggestion needs its human-written candidate label"))
        if "suggested_focus" in guidance and _blank_list(guidance.get("suggested_focus")):
            errors.append(_error("DECISION_CARD_SOURCE_INCOMPLETE", "/student_view/guidance/suggested_focus", "a multi-focus suggestion needs its human-written candidate labels"))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return errors


def _bullet_list(lines: list[str], items: Sequence[Any], indent: str = "") -> None:
    """Append one deterministic bullet per human-written item."""

    for item in items:
        lines.append(f"{indent}- {str(item).strip()}")


def _criteria_lines(view: JsonObject) -> list[str]:
    """Restate only the human-authored comparison criteria."""

    criteria = view.get("comparison_criteria")
    if not isinstance(criteria, Sequence) or isinstance(criteria, str) or not criteria:
        return ["- 学生未提供比较准则，本卡仅复述人类书写的假设事实与评估。"]
    lines = ["- 人类书写的比较准则："]
    for criterion in criteria:
        lines.append(f"  - {str(criterion['name']).strip()}：{str(criterion['description']).strip()}")
    return lines


def _guidance_lines(view: JsonObject) -> list[str]:
    """Render the guidance section from human-written facts only."""

    guidance = view.get("guidance")
    if isinstance(guidance, Mapping) and guidance.get("status") == "guidance_available":
        if not _blank(guidance.get("recommended_to_consider_first")):
            lines = [
                f"- 建议先重点考虑：{str(guidance['recommended_to_consider_first']).strip()}",
                f"- 原始依据：{str(guidance['basis']).strip()}",
                f"- 依据准则：{'、'.join(str(item).strip() for item in guidance['basis_criteria'])}",
                "- 优点：",
            ]
            _bullet_list(lines, guidance["advantages"], indent="  ")
            lines.append("- 代价/风险：")
            _bullet_list(lines, guidance["costs_or_risks"], indent="  ")
            lines.append("- 推翻条件：")
            _bullet_list(lines, guidance["reconsider_when"], indent="  ")
            lines.append(f"- {GUIDANCE_BOUNDARY_SENTENCE}")
            return lines
        lines = ["- 人类书写了多个关注点，未形成单一依据："]
        _bullet_list(lines, guidance.get("suggested_focus", []), indent="  ")
        lines.append(f"- {NO_SINGLE_BASIS_SENTENCE}")
        return lines
    return [f"- {NO_SINGLE_BASIS_SENTENCE}"]


def _render_card(document: JsonObject) -> str:
    """Compose the deterministic six-section Markdown card from confirmed facts."""

    view = document["student_view"]
    lines: list[str] = ["# 现在要决定什么", "", str(view["decision_prompt"]).strip(), "", "## 为什么现在要决定", "", f"- {CONFIRMED_UPSTREAM_LINE}"]
    lines.extend(_criteria_lines(view))
    candidates = list(view["candidates"])
    lines.append(f"- 候选数量：{len(candidates)} 个人类候选，按人类原顺序完整呈现。")
    lines.extend(["", "## 可选方案"])
    for index, candidate in enumerate(candidates, start=1):
        assessment = candidate["student_assessment"]
        lines.extend(
            [
                "",
                f"### 候选 {index}：{str(candidate['label']).strip()}",
                "",
                f"- 它是什么：{str(candidate['note']).strip()}",
                "- 适用前提：",
            ]
        )
        _bullet_list(lines, assessment["applicable_preconditions"], indent="  ")
        lines.append("- 优点：")
        _bullet_list(lines, assessment["advantages"], indent="  ")
        lines.append("- 代价/风险：")
        _bullet_list(lines, assessment["costs_or_risks"], indent="  ")
        lines.append("- 推翻条件：")
        _bullet_list(lines, assessment["reconsider_when"], indent="  ")
    lines.extend(["", "## 建议先重点考虑", ""])
    lines.extend(_guidance_lines(view))
    lines.extend(
        [
            "",
            "## 你可以怎样回答",
            "",
            "- 选择上面一个真实候选并说出它的名称；最终选择仍按现有 ARCH-104 人类选择记录合同完成。",
            "- 或要求修订、补充人类候选，然后重建比较。",
            "- 或将本决定标记为 unresolved 并记录理由。",
            "- 本卡片不是选择本身；机器不替你写入任何选择。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_hypothesis_decision_card(
    chain: Sequence[JsonObject],
    document: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[str | None, CardResult]:
    """Render only after the pending gate, human-fact gate, and full upstream chain pass."""

    pending_errors = _pending_selection_errors(document)
    if pending_errors:
        return None, {"ok": False, "errors": pending_errors}
    incomplete_errors = _source_incomplete_errors(document)
    if incomplete_errors:
        return None, {"ok": False, "errors": incomplete_errors}
    if len(chain) != len(_CHAIN_ARGUMENTS):  # pragma: no cover - CLI and tests supply the fixed contract.
        return None, {"ok": False, "errors": [_error("DECISION_CARD_CHAIN_INVALID", "", "the decision card renderer requires the complete ARCH-097~104 document chain")]}
    upstream = comparison_builder.validate_comparison(*chain, document, *(schemas[key] for key in _SCHEMA_KEYS))
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}  # type: ignore[misc]
    return _render_card(document), {"ok": True, "errors": []}


def _load_schemas() -> dict[str, JsonObject]:
    """Load the committed ARCH-097~104 schemas reused from ARCH-104."""

    return comparison_builder._load_schemas()


def main(argv: Sequence[str]) -> int:
    """Render one pending ARCH-104 comparison as a Simplified-Chinese decision card on stdout."""

    parser = argparse.ArgumentParser(description=__doc__)
    for name, help_text in _CHAIN_ARGUMENTS:
        parser.add_argument(name, type=Path, help=help_text)
    parser.add_argument("document", type=Path, help="pending ARCH-104 hypothesis comparison document JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
        chain = tuple(load_json_object(getattr(arguments, name)) for name, _ in _CHAIN_ARGUMENTS)
        document = load_json_object(arguments.document)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    card, result = render_hypothesis_decision_card(chain, document, schemas)
    if card is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    sys.stdout.buffer.write(card.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
