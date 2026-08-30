"""Render one deterministic Simplified-Chinese card for one pending ARCH-097 digest.

This local, offline, read-only renderer accepts only a schema-valid
AssignmentBriefDigest whose human confirmation is still pending. It validates
the supplied digest against ARCH-097's authoritative digest schema and never
re-implements, rewrites, or extends the brief contract. It reads no intake
and parses no DOC, DOCX, PDF, HTML, image, or scanned content. It writes UTF-8
Markdown to stdout only: it creates no file, confirmation record, or design
content. Human confirmation still happens only through the ARCH-097 confirm
contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import build_assignment_brief_digest as digest_builder

JsonObject = Mapping[str, Any]

CATEGORY_ORDER: tuple[str, ...] = (
    "hard_constraint",
    "program",
    "site",
    "spatial_relationship",
    "circulation",
    "deliverable",
    "design_goal",
    "scoring_focus",
    "reference_only",
)

CATEGORY_LABELS: Mapping[str, str] = {
    "hard_constraint": "硬性约束",
    "program": "功能与面积",
    "site": "场地条件",
    "spatial_relationship": "空间关系",
    "circulation": "流线",
    "deliverable": "交付要求",
    "design_goal": "设计目标",
    "scoring_focus": "评分关注点",
    "reference_only": "仅供参考",
}

STATUS_LABELS: Mapping[str, str] = {
    "included": "已明确",
    "duplicate_merged": "重复（已合并，但保留原来源）",
    "conflict": "存在冲突",
    "missing": "缺失",
    "unreadable": "不可读",
    "deferred_with_reason": "暂缓",
}

NO_QUESTIONS_LINE = "当前无待确认问题。"
CONFLICT_NO_WINNER_LINE = "上述冲突需要人类裁决；机器不选择胜者。"
NOTES_NOT_REQUIREMENTS_LINE = "以上为人工备注，不等同于任务书要求。"

DO_NOT_START_LINES: tuple[str, ...] = (
    "未确认前，不输出任何设计分析。",
    "未确认前，不输出功能面积分配。",
    "未确认前，不决定层数、入口或体量。",
    "未确认前，不输出动线、方案或任何自动选择语义。",
)

REPLY_PATH_LINES: tuple[str, ...] = (
    "- 确认这份摘要；",
    "- 或指出需要修正的字面内容；",
    "- 或补充缺失、不可读的材料；",
    "- 或先回答现有的澄清问题。",
    "- 本卡片不代替确认；人工确认仍只能由既有 confirm 合同绑定。",
)


class CardError(TypedDict):
    """One deterministic rejection without a partial card."""

    code: str
    path: str
    message: str


class CardResult(TypedDict):
    """The public result of rendering one brief digest card."""

    ok: bool
    errors: list[CardError]


def _load_schemas() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the committed ARCH-097 intake and digest schemas."""

    return (
        digest_builder.load_json_object(digest_builder.INTAKE_SCHEMA_PATH),
        digest_builder.load_json_object(digest_builder.DIGEST_SCHEMA_PATH),
    )


def _pending_errors(digest: JsonObject) -> list[CardError]:
    """Fail closed unless the digest is still awaiting human confirmation."""

    confirmation = digest.get("human_confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("status") != "pending":
        return [digest_builder._error("BRIEF_DIGEST_CARD_NOT_PENDING", "/human_confirmation", "the digest card renderer accepts only a pending digest; a confirmed digest cannot be repackaged as an awaiting-confirmation choice")]
    return []


def _clear_lines(digest: JsonObject) -> list[str]:
    """Group included and duplicate_merged requirements by fixed category order."""

    lines: list[str] = []
    requirements = list(digest["requirements"])
    for category in CATEGORY_ORDER:
        grouped = [item for item in requirements if item["category"] == category and item["status"] in ("included", "duplicate_merged")]
        if not grouped:
            continue
        lines.extend(["", f"### {CATEGORY_LABELS[category]}"])
        for item in grouped:
            lines.extend(
                [
                    f"- {str(item['concise_text']).strip()}",
                    f"  - 状态：{STATUS_LABELS[str(item['status'])]}",
                    f"  - 来源：{str(item['source_locator']).strip()}",
                ]
            )
    return lines


def _conflict_lines(digest: JsonObject) -> list[str]:
    """Restate every declared conflict with both sides' locators, choosing no winner."""

    lines: list[str] = []
    requirements = list(digest["requirements"])
    for conflict in digest["conflicts"]:
        lines.append(f"- 冲突描述：{str(conflict['description']).strip()}")
        for locator in conflict["locators"]:
            lines.append(f"  - 冲突来源：{str(locator).strip()}")
        for item in requirements:
            if item["status"] == "conflict" and str(conflict["conflict_id"]) in [str(conflict_id) for conflict_id in item.get("conflict_ids", [])]:
                lines.extend(
                    [
                        f"  - 相关条目：{str(item['concise_text']).strip()}",
                        f"    - 来源：{str(item['source_locator']).strip()}",
                    ]
                )
    if digest["conflicts"]:
        lines.append(f"- {CONFLICT_NO_WINNER_LINE}")
    else:
        lines.append("- 本摘要未声明冲突。")
    return lines


def _gap_lines(digest: JsonObject) -> list[str]:
    """Restate missing, unreadable, and deferred items verbatim without filling values."""

    lines: list[str] = []
    order = ("missing", "unreadable", "deferred_with_reason")
    for status in order:
        grouped = [item for item in digest["requirements"] if item["status"] == status]
        if not grouped:
            continue
        lines.extend(["", f"### {STATUS_LABELS[status]}"])
        for item in grouped:
            lines.append(f"- {str(item['concise_text']).strip()}")
            if status == "missing":
                lines.append("  - 来源：已声明缺失（没有可读来源提供该信息）")
            elif status == "unreadable":
                lines.append("  - 来源：已声明不可读（唯一可能来源是不可读文件）")
            else:
                lines.append(f"  - 暂缓原因：{str(item['deferred_reason']).strip()}")
    return lines


def _question_lines(digest: JsonObject) -> list[str]:
    """Project clarification questions verbatim in order, at most three."""

    questions = digest["clarification_questions"]
    if not questions:
        return [f"- {NO_QUESTIONS_LINE}"]
    return [f"- {str(question).strip()}" for question in questions]


def _render_card(digest: JsonObject) -> str:
    """Compose the deterministic eight-section card from confirmed digest facts."""

    summary = digest["coverage_summary"]
    lines: list[str] = [
        "# 任务书摘要（待人工确认）",
        "",
        f"- 项目：{str(digest['project_title']).strip()}",
        "- 状态：待人工确认",
        f"- 输入文件：{summary['input_file_count']} 份，其中不可读 {summary['unreadable_file_count']} 份",
        "",
        "## 已明确的任务书要求",
    ]
    lines.extend(_clear_lines(digest))
    lines.extend(["", "## 存在冲突、不能替你裁决的内容", ""])
    lines.extend(_conflict_lines(digest))
    lines.extend(["", "## 缺失、无法读取或暂缓的信息"])
    lines.extend(_gap_lines(digest))
    lines.extend(["", "## 人工备注（不等同于任务书要求）", ""])
    notes = digest["human_notes"]
    if notes:
        for note in notes:
            lines.append(f"- {str(note['text']).strip()}")
        lines.append(f"- {NOTES_NOT_REQUIREMENTS_LINE}")
    else:
        lines.append("- 本摘要未携带人工备注。")
    lines.extend(["", "## 需要你确认的问题", ""])
    lines.extend(_question_lines(digest))
    lines.extend(["", "## 确认前不要开始什么", ""])
    for line in DO_NOT_START_LINES:
        lines.append(f"- {line}")
    lines.extend(["", "## 你可以怎样回答", ""])
    lines.extend(REPLY_PATH_LINES)
    return "\n".join(lines) + "\n"


def render_brief_digest_card(
    digest: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
) -> tuple[str | None, CardResult]:
    """Render only after the authoritative schema gate and the pending gate pass."""

    registry = digest_builder._registry(intake_schema, digest_schema)
    schema_errors = digest_builder._schema_errors(digest, digest_schema, registry, "DIGEST_SCHEMA_INVALID")
    if schema_errors:
        return None, {"ok": False, "errors": [dict(error) for error in schema_errors]}  # type: ignore[misc]
    pending_errors = _pending_errors(digest)
    if pending_errors:
        return None, {"ok": False, "errors": pending_errors}
    return _render_card(digest), {"ok": True, "errors": []}


def main(argv: Sequence[str]) -> int:
    """Render one pending ARCH-097 digest as a Simplified-Chinese card on stdout."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("digest", type=Path, help="pending assignment brief digest JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema, digest_schema = _load_schemas()
        digest = digest_builder.load_json_object(arguments.digest)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(digest_builder._load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    card, result = render_brief_digest_card(digest, intake_schema, digest_schema)
    if card is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    sys.stdout.buffer.write(card.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
