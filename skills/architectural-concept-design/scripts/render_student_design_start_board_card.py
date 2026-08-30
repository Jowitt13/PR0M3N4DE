"""Render one deterministic Simplified-Chinese card for one validated ARCH-098 start board.

This local, offline, read-only renderer accepts exactly one confirmed
ARCH-097 AssignmentBriefDigest and one start board derived from it. Its sole
upstream entry is ARCH-098's public validate_board, which re-validates the
confirmed digest binding chain and the board projection; upstream error codes
propagate unchanged. The renderer never rebuilds, repairs, or reinterprets
the digest or board, creates no space, allocates no area, and decides no
floor count, entrance, circulation, massing, or scheme. It writes UTF-8
Markdown to stdout only: it creates no file, confirmation record, or JSON
artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import build_student_design_start_board as board_builder

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

KIND_LABELS: Mapping[str, str] = {
    "conflict": "冲突",
    "missing": "缺失",
    "unreadable": "不可读",
    "deferred_with_reason": "暂缓",
}

NO_QUESTIONS_LINE = "当前无待确认问题。"
NO_UNRESOLVED_LINE = "当前没有未解决项。"
CONFLICT_NO_WINNER_LINE = "该冲突需要人类裁决；机器不选择胜者。"

PREPARATION_LINES: tuple[str, ...] = (
    "- 由你自己整理功能空间清单；",
    "- 由你自己整理已有或未解决的面积信息；",
    "- 由你自己整理使用者与访问层级；",
    "- 由你自己整理动与静的需求；",
    "- 由你自己整理邻接或分离关系；",
    "- 以上均由人类自行准备；本卡片不创建具体空间名、面积数值、优先级或建筑建议。",
)

NO_AUTO_DECISION_LINE = "本卡片不自动决定面积、尺寸、楼层、入口、动线、体量、柱网、环境结论或方案。"


class CardError(TypedDict):
    """One deterministic rejection without a partial card."""

    code: str
    path: str
    message: str


class CardResult(TypedDict):
    """The public result of rendering one start board card."""

    ok: bool
    errors: list[CardError]


def _load_schemas() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load the committed ARCH-097 intake, digest, and ARCH-098 board schemas."""

    return (
        board_builder.load_json_object(board_builder.INTAKE_SCHEMA_PATH),
        board_builder.load_json_object(board_builder.DIGEST_SCHEMA_PATH),
        board_builder.load_json_object(board_builder.BOARD_SCHEMA_PATH),
    )


def _requirement_lines(view: JsonObject) -> list[str]:
    """Project confirmed requirements by fixed category order, keeping board order."""

    lines: list[str] = []
    groups = {str(group["category"]): list(group["items"]) for group in view["confirmed_requirements"]}
    for category in CATEGORY_ORDER:
        items = groups.get(category, [])
        if not items:
            continue
        lines.extend(["", f"### {CATEGORY_LABELS[category]}"])
        for item in items:
            lines.extend(
                [
                    f"- {str(item['requirement']).strip()}",
                    f"  - 来源：{str(item['source_locator']).strip()}",
                ]
            )
    return lines


def _unresolved_lines(view: JsonObject) -> list[str]:
    """Project unresolved items in board order without choosing winners or filling values."""

    items = list(view["unresolved_items"])
    if not items:
        return [f"- {NO_UNRESOLVED_LINE}"]
    lines: list[str] = []
    for item in items:
        kind = str(item["kind"])
        lines.append(f"- {KIND_LABELS[kind]}：{str(item['description']).strip()}")
        if kind == "conflict":
            for locator in item["conflicting_locators"]:
                lines.append(f"  - 冲突来源：{str(locator).strip()}")
            lines.append(f"  - {CONFLICT_NO_WINNER_LINE}")
        elif kind == "deferred_with_reason":
            lines.append(f"  - 暂缓原因：{str(item['deferred_reason']).strip()}")
            lines.append(f"  - 来源：{str(item['source_locator']).strip()}")
        else:
            lines.append(f"  - 来源：{str(item['source_locator']).strip()}")
    return lines


def _question_lines(view: JsonObject) -> list[str]:
    """Project clarification questions verbatim in order, at most three."""

    questions = view["clarification_questions"]
    if not questions:
        return [f"- {NO_QUESTIONS_LINE}"]
    return [f"- {str(question).strip()}" for question in questions]


def _render_card(board: JsonObject) -> str:
    """Compose the deterministic seven-section card from validated board facts."""

    view = board["student_view"]
    lines: list[str] = [
        "# 已确认的任务书起点",
        "",
        f"- 项目：{str(view['project_title']).strip()}",
        "- 阶段：任务书已确认，准备进入功能与面积编排",
        "",
        "## 已明确的任务书要求",
    ]
    lines.extend(_requirement_lines(view))
    lines.extend(["", "## 还未解决、不能替你决定的内容", ""])
    lines.extend(_unresolved_lines(view))
    lines.extend(["", "## 进入功能与面积编排前的问题", ""])
    lines.extend(_question_lines(view))
    lines.extend(
        [
            "",
            "## 下一步：功能与面积编排",
            "",
            f"- 行动：{str(view['next_action']['action']).strip()}",
            f"- 说明：{str(view['next_action']['description']).strip()}",
            "",
            "## 你可以先写什么",
            "",
        ]
    )
    lines.extend(PREPARATION_LINES)
    lines.extend(["", "## 现在不要自动决定什么", "", f"- {NO_AUTO_DECISION_LINE}"])
    for boundary in view["boundaries"]:
        lines.append(f"- {str(boundary).strip()}")
    return "\n".join(lines) + "\n"


def render_design_start_board_card(
    digest: JsonObject,
    board: JsonObject,
    intake_schema: JsonObject,
    digest_schema: JsonObject,
    board_schema: JsonObject,
) -> tuple[str | None, CardResult]:
    """Render only after the sole ARCH-098 validation entry passes."""

    result = board_builder.validate_board(digest, board, intake_schema, digest_schema, board_schema)
    if not result["ok"]:
        return None, {"ok": False, "errors": [dict(error) for error in result["errors"]]}  # type: ignore[misc]
    return _render_card(board), {"ok": True, "errors": []}


def main(argv: Sequence[str]) -> int:
    """Render one validated ARCH-098 start board as a Simplified-Chinese card on stdout."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("digest", type=Path, help="confirmed assignment brief digest JSON")
    parser.add_argument("board", type=Path, help="student design start board JSON")

    arguments = parser.parse_args(argv[1:])
    try:
        intake_schema, digest_schema, board_schema = _load_schemas()
        digest = board_builder.load_json_object(arguments.digest)
        board = board_builder.load_json_object(arguments.board)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps(board_builder._load_failure("DOCUMENT_LOAD_FAILED", str(error)), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2

    card, result = render_design_start_board_card(digest, board, intake_schema, digest_schema, board_schema)
    if card is None:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    sys.stdout.buffer.write(card.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
