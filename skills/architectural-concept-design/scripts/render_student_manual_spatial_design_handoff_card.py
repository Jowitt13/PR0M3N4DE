"""Render one deterministic Simplified-Chinese manual spatial design handoff card.

This local, offline, read-only renderer accepts only a valid, untampered
ARCH-111 spatial transition state handoff whose human review continued to
manual spatial design. It reuses ARCH-111's public validation entry,
therefore re-running the full ARCH-097~111 chain with upstream error codes
propagated unchanged. It writes UTF-8 Markdown to stdout only: it creates no
file, receipt, selection record, coordinate, drawing, or design conclusion.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import build_student_spatial_transition_state_handoff as handoff_builder
from build_student_spatial_program import (
    _error,
    _load_failure,
    load_json_object,
)

JsonObject = Mapping[str, Any]
DocumentChain = Sequence[JsonObject]

CONTINUE_OUTCOME = "continue_to_manual_spatial_design"

ROLE_LABELS: Mapping[str, str] = {
    "main_space": "主要空间",
    "supporting_space": "支持空间",
    "shared_service": "共享服务",
}

TRANSITION_LABELS: Mapping[str, str] = {
    "gradual_opening": "渐进开放",
    "gradual_enclosure": "渐进围合",
    "buffered_transition": "缓冲过渡",
    "interwoven_access": "交织流线",
    "remain_independent": "保持独立",
}

NO_QUESTIONS_LINE = "当前没有待确认的澄清问题。"

CONTINUE_SECTION_LINES: tuple[str, ...] = (
    "基于上面已确认的空间层级与空间过渡意图，学生可以继续自己的手工空间设计。",
    "本卡片只是已确认事实的交接说明；它不产生坐标、尺寸、矩形、图纸、平面或方案结论。",
)

BOUNDARY_SECTION_LINES: tuple[str, ...] = (
    "不得据此推断任何坐标、尺寸、矩形、入口、走廊、墙、门、柱、楼梯、厕所、总平面、体量或朝向。",
    "不得据此得出结构、法规、成本、性能、可建性或任何专业审批结论。",
    "本卡片不含任何排序、评分、优胜者或自动选择语义；已确认事实之外的判断仍由学生自己作出。",
    "本卡片不生成平面、绘图、图像、HTML、PPTX、三维模型或专业结论。",
)


class CardError(TypedDict):
    """One deterministic rejection without a partial card."""

    code: str
    path: str
    message: str


class CardResult(TypedDict):
    """The public result of rendering one manual design handoff card."""

    ok: bool
    errors: list[CardError]


def _continued_errors(document: JsonObject) -> list[CardError]:
    """Fail closed unless the supplied handoff records a human continuation."""

    source_binding = document.get("source_binding")
    if not isinstance(source_binding, Mapping) or source_binding.get("review_outcome") != CONTINUE_OUTCOME:
        return [_error("MANUAL_DESIGN_HANDOFF_CARD_NOT_CONTINUED", "/source_binding/review_outcome", "the handoff card renderer accepts only a handoff whose human review continued to manual spatial design")]
    return []


def _render_card(document: JsonObject) -> str:
    """Compose the deterministic seven-section card from confirmed handoff facts."""

    view = document["student_handoff"]
    binding = document["source_binding"]
    review_summary = view["review_summary"]
    lines: list[str] = [
        "# 已确认的空间设计起点",
        "",
        f"- 项目：{str(view['project_title']).strip()}",
        f"- 审阅人：{str(review_summary['reviewed_by']).strip()}（{str(review_summary['reviewed_at']).strip()}）",
        f"- 审阅结论：继续手工空间设计（{str(binding['review_outcome']).strip()}）",
        "",
        "## 空间层级",
        "",
    ]
    for item in view["space_hierarchy"]:
        role = str(item["role"])
        lines.append(f"- {str(item['space_name']).strip()}（{ROLE_LABELS.get(role, role)}）：{str(item['note']).strip()}")
    lines.extend(["", "## 空间过渡意图", ""])
    for item in view["transition_patterns"]:
        kind = str(item["transition_kind"])
        lines.append(
            f"- {str(item['from_space_name']).strip()} → {str(item['to_space_name']).strip()}（{TRANSITION_LABELS.get(kind, kind)}）：{str(item['note']).strip()}"
        )
    lines.extend(["", "## 本轮人工审阅意见", ""])
    notes = review_summary["review_notes"]
    if notes:
        for note in notes:
            lines.append(f"- {str(note).strip()}")
    else:
        lines.append("- 本轮审阅未留下书面意见。")
    lines.extend(["", "## 现在可以手工继续什么", ""])
    lines.extend(CONTINUE_SECTION_LINES)
    lines.extend(["", "## 还需要你确认的问题", ""])
    questions = view["clarification_questions"]
    if questions:
        for question in questions:
            lines.append(f"- {str(question).strip()}")
    else:
        lines.append(NO_QUESTIONS_LINE)
    lines.extend(["", "## 不应擅自推断什么", ""])
    lines.extend(BOUNDARY_SECTION_LINES)
    return "\n".join(lines) + "\n"


def render_manual_spatial_design_handoff_card(
    chain: DocumentChain,
    review: JsonObject,
    handoff: JsonObject,
    support_draft: JsonObject,
    support_framework: JsonObject,
    draft: JsonObject,
    framework: JsonObject,
    transition_review: JsonObject,
    transition_handoff: JsonObject,
    schemas: Mapping[str, JsonObject],
) -> tuple[str | None, CardResult]:
    """Render only after the continuation gate and the full upstream chain pass."""

    continued = _continued_errors(transition_handoff)
    if continued:
        return None, {"ok": False, "errors": continued}
    upstream = handoff_builder.validate_spatial_transition_state_handoff(
        chain, review, handoff, support_draft, support_framework, draft, framework, transition_review, transition_handoff, schemas
    )
    if not upstream["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in upstream["errors"]]}  # type: ignore[misc]
    return _render_card(transition_handoff), {"ok": True, "errors": []}


def _load_schemas() -> dict[str, JsonObject]:
    """Load the committed ARCH-097~111 schemas reused from ARCH-111."""

    return handoff_builder._load_schemas()


def main(argv: Sequence[str]) -> int:
    """Render one continued ARCH-111 handoff as a Simplified-Chinese handoff card on stdout."""

    parser = argparse.ArgumentParser(description=__doc__)
    handoff_builder._add_arguments(parser)
    parser.add_argument("transition_handoff", type=Path, help="validated ARCH-111 spatial transition state handoff JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        schemas = _load_schemas()
        chain = handoff_builder._load_chain(arguments)
        review = load_json_object(arguments.review)
        handoff = load_json_object(arguments.handoff)
        support_draft = load_json_object(arguments.support_draft)
        support_framework = load_json_object(arguments.support_framework)
        draft = load_json_object(arguments.draft)
        framework = load_json_object(arguments.framework)
        transition_review = load_json_object(arguments.transition_review)
        transition_handoff = load_json_object(arguments.transition_handoff)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(_load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    card, result = render_manual_spatial_design_handoff_card(
        chain, review, handoff, support_draft, support_framework, draft, framework, transition_review, transition_handoff, schemas
    )
    if card is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    sys.stdout.buffer.write(card.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
