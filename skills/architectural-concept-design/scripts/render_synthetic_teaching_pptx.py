"""Render a validated ADR-0008 teaching handoff through locked local ppt-master."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict
from zipfile import ZipFile

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import design_data_staleness as data_staleness  # noqa: E402
import evaluate_presentation_e2e as normal_e2e  # noqa: E402
from presentation_audience_copy import INTERNAL_ID_RE  # noqa: E402
from svg_dual_asset_pipeline import audit_source as audit_svg_source  # noqa: E402
from svg_text_to_path import compile_text_elements, count_text_elements  # noqa: E402
from validate_synthetic_teaching_presentation_handoff import (  # noqa: E402
    SCHEMA_PATH,
    TEACHING_LABELS,
    canonical_sha256,
    load_json_object,
    validate_synthetic_teaching_presentation_handoff,
)

JsonObject = dict[str, Any]
PAGE_COUNT = 8
NOTICE = "TEACHING DEMO — NOT A REAL PROJECT VALIDATION"
LABEL_LINE = "HUMAN_AUTHORIZED_ASSUMPTION · DEMO_ONLY · NOT_A_REAL_SITE_OR_BUILDABILITY_CONCLUSION"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class RenderError(TypedDict):
    code: str
    path: str
    message: str


class RenderResult(TypedDict):
    ok: bool
    outcome: str
    errors: list[RenderError]


def _error(errors: list[RenderError], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _renderer_python(renderer_root: Path) -> Path | None:
    candidates = (renderer_root / ".venv" / "Scripts" / "python.exe", renderer_root / ".venv" / "bin" / "python")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _locked_renderer_errors(renderer_root: Path) -> list[RenderError]:
    errors: list[RenderError] = []
    normal_errors: list[normal_e2e.E2eError] = []
    normal_e2e._validate_renderer_receipt(renderer_root, normal_errors, normal_e2e.LOCK_PATH)
    for item in normal_errors:
        _error(errors, item["code"], item["path"], item["message"])
    if _renderer_python(renderer_root) is None:
        _error(errors, "SYNTHETIC_RENDERER_PYTHON_UNAVAILABLE", "/ppt-master-root/.venv", "locked ppt-master must provide its isolated Python executable")
    if not (renderer_root / "scripts" / "svg_to_pptx.py").is_file() or not (renderer_root / "scripts" / "svg_quality_checker.py").is_file():
        _error(errors, "SYNTHETIC_RENDERER_SCRIPT_UNAVAILABLE", "/ppt-master-root/scripts", "locked ppt-master export and quality scripts are required")
    return errors


def _spec_lock() -> str:
    return """## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## mode
- mode: instructional

## teaching_boundary
- classification: HUMAN_AUTHORIZED_ASSUMPTION
- demonstration: DEMO_ONLY
- conclusion: NOT_A_REAL_SITE_OR_BUILDABILITY_CONCLUSION

## visual_style
- visual_style: swiss-minimal

## colors
- bg: #F6F4EF
- primary: #172B4D
- accent: #E56B4F
- secondary_accent: #4B8F8C
- text: #172B4D
- text_secondary: #52616B
- border: #C9D2D8

## typography
- font_family: "Microsoft YaHei", Arial, sans-serif
- title_family: "Microsoft YaHei", Arial, sans-serif
- body: 24
- title: 50
- subtitle: 30
- annotation: 18
- footnote: 16

## icons
- library: tabler-filled
- inventory: book, users, layout-grid, route, checklist

## page_rhythm
- P01: anchor
- P02: dense
- P03: dense
- P04: breathing
- P05: dense
- P06: anchor
- P07: dense
- P08: breathing

## pptx_structure
- mode: flat
"""


def _short(value: object, limit: int = 22) -> str:
    text = str(value).strip()
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _text(x: int, y: int, value: object, size: int = 20, *, weight: str = "400", fill: str = "#172B4D", anchor: str = "start", limit: int = 22) -> str:
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{_escape(_short(value, limit))}</text>'


def _header(title: object, index: int) -> str:
    """Author the fixed page header.

    The only free visible text is the page's visible_slide_copy headline.
    The project display name and every design-content string are excluded by
    construction; the boundary labels are fixed constants.
    """

    title_size = 52 if index == 1 else 38
    return "\n".join(
        (
            '<rect x="0" y="0" width="1280" height="720" fill="#F6F4EF"/>',
            '<rect x="0" y="0" width="1280" height="18" fill="#E56B4F"/>',
            '<text x="62" y="72" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#4B8F8C">SYNTHETIC TEACHING PPTX</text>',
            _text(62, 134, title, title_size, weight="700", limit=64),
            '<line x1="62" y1="202" x2="1218" y2="202" stroke="#C9D2D8" stroke-width="2"/>',
        )
    )


def _footer(index: int) -> str:
    """The footer carries only the fixed boundary labels and an ordinary page number.

    The internal ``page_id`` locator (STP-xx) never reaches a visible area.
    """

    return "\n".join(
        (
            '<rect x="62" y="620" width="1156" height="56" rx="8" fill="#172B4D"/>',
            f'<text x="84" y="646" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" font-weight="700" fill="#FFFFFF">{NOTICE}</text>',
            f'<text x="84" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[0]}</text>',
            f'<text x="380" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[1]}</text>',
            f'<text x="530" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[2]}</text>',
            _text(1218, 704, f"{index:02d}/08", 16, fill="#52616B", anchor="end"),
        )
    )


def _program_groups(spaces: list[Mapping[str, Any]]) -> list[tuple[str, list[Mapping[str, Any]], str]]:
    if len(spaces) == 10:
        return [
            ("公共共享", [spaces[index] for index in (0, 1, 5)], "#E7F0EF"),
            ("可变活动", [spaces[index] for index in (3, 4)], "#FCE7DF"),
            ("安静学习", [spaces[index] for index in (2, 6)], "#EEF0F8"),
            ("后勤支撑", [spaces[index] for index in (7, 8, 9)], "#F2EEE5"),
        ]
    midpoint = max(1, len(spaces) // 2)
    return [("功能组 A", spaces[:midpoint], "#E7F0EF"), ("功能组 B", spaces[midpoint:], "#EEF0F8")]


def _page_visual(page: Mapping[str, Any], teaching_content: Mapping[str, Any], index: int) -> str:
    """Author one team-original vector page.

    Visible text comes only from the page's ``visible_slide_copy`` headline,
    fixed page compositions with fixed labels, and the fixed teaching
    boundary labels. The project display name, decision records, state
    descriptions, design-content string values (names, spatial operations,
    hypotheses), internal purposes, page locators, and speaker notes never
    render; only structural facts (list lengths, enum presence) steer the
    fixed compositions.
    """

    page_id = str(page["page_id"])
    copy = page.get("visible_slide_copy")
    headline = str(copy.get("headline", "")) if isinstance(copy, Mapping) else ""
    program = [item for item in teaching_content.get("program_spaces", []) if isinstance(item, Mapping)]
    options = [item for item in teaching_content.get("concept_options", []) if isinstance(item, Mapping)]
    hypotheses = [item for item in teaching_content.get("hypotheses", []) if isinstance(item, Mapping)]
    content: list[str] = [_header(headline, index)]

    if page_id == "STP-01":
        content.extend(
            (
                _text(62, 262, "从人类确认的假设条件，形成可编辑的教学演示。", 28, weight="700"),
                _text(62, 302, "它验证表达链路，不验证真实场地、法规或工程可行性。", 22, fill="#52616B"),
                '<circle cx="940" cy="356" r="128" fill="#E7F0EF" stroke="#4B8F8C" stroke-width="3"/>',
                '<circle cx="1010" cy="356" r="96" fill="none" stroke="#4B8F8C" stroke-width="3"/>',
                '<circle cx="950" cy="430" r="72" fill="none" stroke="#E56B4F" stroke-width="3"/>',
                _text(940, 344, "公共", 24, weight="700", anchor="middle"),
                _text(1010, 370, "活动", 20, weight="700", anchor="middle"),
                _text(950, 438, "安静", 20, weight="700", anchor="middle"),
                _text(62, 430, "人类已确认的设计方向", 22, weight="700"),
            )
        )
    elif page_id == "STP-02":
        content.extend(
            (
                '<rect x="430" y="282" width="440" height="230" rx="8" fill="#FFFFFF" stroke="#172B4D" stroke-width="3" stroke-dasharray="12 8"/>',
                _text(650, 387, "纯虚构教学地块", 30, weight="700", anchor="middle"),
                _text(650, 422, "非比例关系示意", 20, fill="#52616B", anchor="middle"),
                '<line x1="650" y1="250" x2="650" y2="282" stroke="#172B4D" stroke-width="3"/>',
                _text(650, 245, "北向：图纸上方（假设）", 18, weight="700", anchor="middle"),
                '<line x1="650" y1="512" x2="650" y2="552" stroke="#E56B4F" stroke-width="4"/>',
                _text(650, 580, "公共到达与主入口（假设）", 20, weight="700", fill="#E56B4F", anchor="middle"),
                '<line x1="390" y1="396" x2="430" y2="396" stroke="#4B8F8C" stroke-width="4"/>',
                _text(318, 390, "受控服务", 20, weight="700", fill="#4B8F8C", anchor="middle"),
                '<line x1="870" y1="396" x2="910" y2="396" stroke="#4B8F8C" stroke-width="4"/>',
                _text(985, 390, "安静界面", 20, weight="700", fill="#4B8F8C", anchor="middle"),
            )
        )
    elif page_id == "STP-03":
        groups = _program_groups(program)
        positions = ((62, 250), (650, 250), (62, 430), (650, 430))
        for position, (group_name, records, color) in zip(positions, groups):
            x, y = position
            content.append(f'<rect x="{x}" y="{y}" width="548" height="146" rx="12" fill="{color}" stroke="#C9D2D8" stroke-width="2"/>')
            content.append(_text(x + 26, y + 38, group_name, 24, weight="700"))
            for record_index in range(min(3, len(records))):
                # Only the structural count steers the page; the record names
                # are design content and never render.
                content.append(_text(x + 26, y + 76 + record_index * 24, f"空间 {record_index + 1}", 17, fill="#52616B"))
    elif page_id == "STP-04":
        content.extend(
            (
                '<line x1="650" y1="370" x2="340" y2="330" stroke="#C9D2D8" stroke-width="7"/>',
                '<line x1="650" y1="370" x2="960" y2="330" stroke="#C9D2D8" stroke-width="7"/>',
                '<line x1="650" y1="370" x2="650" y2="500" stroke="#C9D2D8" stroke-width="7"/>',
                '<rect x="530" y="320" width="240" height="100" rx="18" fill="#E7F0EF" stroke="#4B8F8C" stroke-width="3"/>',
                '<rect x="170" y="270" width="250" height="100" rx="18" fill="#FCE7DF" stroke="#E56B4F" stroke-width="3"/>',
                '<rect x="870" y="270" width="250" height="100" rx="18" fill="#EEF0F8" stroke="#4B8F8C" stroke-width="3"/>',
                '<rect x="530" y="465" width="240" height="80" rx="18" fill="#F2EEE5" stroke="#172B4D" stroke-width="3"/>',
                _text(650, 362, "共享核心", 26, weight="700", anchor="middle"),
                _text(295, 312, "可变活动", 24, weight="700", anchor="middle"),
                _text(995, 312, "安静学习", 24, weight="700", anchor="middle"),
                _text(650, 513, "受控后勤", 22, weight="700", anchor="middle"),
                _text(650, 580, "关系表达为教学假设，不对应技术流线或消防结论。", 18, fill="#52616B", anchor="middle"),
            )
        )
    elif page_id == "STP-05":
        panels = ((62, 248, "#E7F0EF"), (650, 248, "#FCE7DF"))
        for option_index, (panel, option) in enumerate(zip(panels, options[:2]), start=1):
            x, y, color = panel
            content.append(f'<rect x="{x}" y="{y}" width="568" height="290" rx="14" fill="{color}" stroke="#C9D2D8" stroke-width="2"/>')
            content.append(_text(x + 30, y + 46, f"概念方向{('一', '二')[option_index - 1]}", 23, weight="700"))
            if panel == panels[0]:
                content.extend((
                    f'<line x1="{x + 90}" y1="{y + 176}" x2="{x + 470}" y2="{y + 176}" stroke="#4B8F8C" stroke-width="10"/>',
                    f'<circle cx="{x + 185}" cy="{y + 176}" r="34" fill="#FFFFFF" stroke="#4B8F8C" stroke-width="3"/>',
                    f'<circle cx="{x + 375}" cy="{y + 176}" r="34" fill="#FFFFFF" stroke="#4B8F8C" stroke-width="3"/>',
                ))
            else:
                content.extend((
                    f'<rect x="{x + 204}" y="{y + 114}" width="160" height="124" rx="10" fill="#FFFFFF" stroke="#E56B4F" stroke-width="3"/>',
                    f'<rect x="{x + 150}" y="{y + 84}" width="268" height="184" rx="20" fill="none" stroke="#E56B4F" stroke-width="9"/>',
                ))
        content.append(_text(640, 570, "仅比较组织关系；不自动评分或推荐。", 17, fill="#52616B", anchor="middle"))
    elif page_id == "STP-06":
        # A fixed composition: no selected-option value (a design-content
        # string such as the spatial operation) may steer or appear on the
        # page.
        content.append(_text(62, 248, "人类已选方向", 26, weight="700"))
        content.extend((
            '<line x1="250" y1="400" x2="1030" y2="400" stroke="#4B8F8C" stroke-width="24"/>',
            '<rect x="420" y="320" width="170" height="160" rx="16" fill="#FCE7DF" stroke="#E56B4F" stroke-width="3"/>',
            '<rect x="690" y="320" width="170" height="160" rx="16" fill="#EEF0F8" stroke="#4B8F8C" stroke-width="3"/>',
            _text(505, 410, "活动", 24, weight="700", anchor="middle"),
            _text(775, 410, "安静", 24, weight="700", anchor="middle"),
            _text(640, 518, "共享公共脊线", 22, weight="700", anchor="middle"),
        ))
        if hypotheses:
            content.append(_text(640, 575, "公共、活动、安静与服务保持可调整的概念关系。", 17, fill="#52616B", anchor="middle"))
    elif page_id == "STP-07":
        labels = {"budget_range": "预算", "target_opening_date": "开业时间", "known_regulations_or_assumptions": "法规与工程条件"}
        unresolved = teaching_content.get("unresolved_inputs", [])
        if not isinstance(unresolved, list):
            unresolved = []
        cards = ((62, 302), (434, 302), (806, 302))
        for position, unresolved_item in zip(cards, unresolved[:3]):
            x, y = position
            field = unresolved_item.get("field") if isinstance(unresolved_item, Mapping) else None
            # Only the contract's fixed enum labels may render; any other or
            # unknown value falls back to a fixed phrase.
            content.extend((
                f'<rect x="{x}" y="{y}" width="330" height="180" rx="14" fill="#FFFFFF" stroke="#C9D2D8" stroke-width="2"/>',
                _text(x + 26, y + 58, labels.get(field, "待确认输入"), 24, weight="700"),
                _text(x + 26, y + 110, "UNKNOWN", 26, weight="700", fill="#E56B4F"),
                _text(x + 26, y + 148, "不补造，不转为技术结论", 17, fill="#52616B"),
            ))
    else:
        content.extend(
            (
                '<line x1="220" y1="390" x2="1040" y2="390" stroke="#C9D2D8" stroke-width="5"/>',
                '<circle cx="300" cy="390" r="54" fill="#E7F0EF" stroke="#4B8F8C" stroke-width="3"/>',
                '<circle cx="575" cy="390" r="54" fill="#FCE7DF" stroke="#E56B4F" stroke-width="3"/>',
                '<circle cx="850" cy="390" r="54" fill="#EEF0F8" stroke="#4B8F8C" stroke-width="3"/>',
                '<circle cx="1040" cy="390" r="54" fill="#F2EEE5" stroke="#172B4D" stroke-width="3"/>',
                _text(300, 398, "人类确认", 18, weight="700", anchor="middle"),
                _text(575, 398, "状态包", 18, weight="700", anchor="middle"),
                _text(850, 398, "教学表达", 18, weight="700", anchor="middle"),
                _text(1040, 398, "可编辑 PPTX", 18, weight="700", anchor="middle"),
                _text(640, 520, "真实项目验证必须另行提供真实任务书与允许使用的资料。", 21, weight="700", anchor="middle", limit=40),
            )
        )
    content.append(_footer(index))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="{"cover" if index == 1 else "content"}">\n' + "\n".join(content) + "\n</svg>"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _pptx_text_by_slide(pptx_path: Path) -> list[str]:
    texts: list[str] = []
    with ZipFile(pptx_path) as archive:
        names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        for name in names:
            root = ElementTree.fromstring(archive.read(name))
            texts.append("".join(element.text or "" for element in root.iter(f"{{{DRAWING_NS}}}t")))
    return texts


def _design_content_strings(handoff: Mapping[str, Any]) -> list[str]:
    """Collect every design-content string value a slide must never display.

    Covers the teaching content (space names, spatial operations, hypothesis
    descriptions), the human-authorized assumption records, and the project
    display name. Structural keys are not collected; only the values.
    """

    values: list[str] = []
    display_name = handoff.get("project_display_name")
    if isinstance(display_name, str) and display_name.strip():
        values.append(display_name)

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and value.strip():
            values.append(value)

    for section in ("teaching_content", "human_authorized_assumptions"):
        walk(handoff.get(section))
    return values


def _page_allowed_visible_values(page: Mapping[str, Any]) -> set[str]:
    """Return the exact visible strings this page's approved copy may display.

    Only the hash-bound ``visible_slide_copy`` fields grant an exemption: the
    headline and the supporting points. No other field does.
    """

    copy = page.get("visible_slide_copy")
    if not isinstance(copy, Mapping):
        return set()
    allowed: set[str] = set()
    headline = copy.get("headline")
    if isinstance(headline, str) and headline:
        allowed.add(headline)
    points = copy.get("supporting_points")
    if isinstance(points, list):
        for point in points:
            if isinstance(point, str) and point:
                allowed.add(point)
    return allowed


def _page_forbidden_design_values(page: Mapping[str, Any], design_values: Sequence[str]) -> list[str]:
    """Drop design-content values this page's approved visible copy exactly equals.

    The exemption is page-local and exact-match on the whole string: a value
    approved on one page stays forbidden on every other page, and a substring
    relationship in either direction never exempts anything. Genuine leaks
    keep the stable ``SYNTHETIC_PPTX_DESIGN_CONTENT_VISIBLE`` error code.
    """

    allowed = _page_allowed_visible_values(page)
    return [value for value in design_values if value not in allowed]


def audit_synthetic_teaching_pptx(
    pptx_path: Path,
    expected_slide_count: int = PAGE_COUNT,
    handoff: JsonObject | None = None,
) -> RenderResult:
    """Perform local OOXML audit for the synthetic teaching deck only.

    When the source handoff is supplied, the audit also enforces the visible
    input boundary: every slide shows its ``visible_slide_copy.headline``,
    and no slide shows the project display name, any design-content string
    value, internal IDs, page locators, internal purposes, or speaker-notes
    text — checked both in the extracted visible text and in the raw slide
    XML (covering alt text and shape names).
    """

    errors: list[RenderError] = []
    normal_errors: list[normal_e2e.E2eError] = []
    normal_e2e._validate_pptx(pptx_path, expected_slide_count, normal_errors)
    for item in normal_errors:
        _error(errors, item["code"], item["path"], item["message"])
    if pptx_path.is_file():
        try:
            with ZipFile(pptx_path) as archive:
                names = archive.namelist()
                if any(name.lower().endswith("vbaProject.bin".lower()) for name in names):
                    _error(errors, "SYNTHETIC_PPTX_MACRO_FORBIDDEN", "/pptx", "teaching deck must not contain macro parts")
                if any(name.startswith("ppt/media/") for name in names):
                    _error(errors, "SYNTHETIC_PPTX_MEDIA_FORBIDDEN", "/pptx", "teaching deck must not package media")
            slide_texts = _pptx_text_by_slide(pptx_path)
            if len(slide_texts) == expected_slide_count:
                for index, text in enumerate(slide_texts, start=1):
                    if NOTICE not in text or any(label not in text for label in TEACHING_LABELS):
                        _error(errors, "SYNTHETIC_PPTX_VISIBLE_LABEL_MISSING", f"/pptx/slide-{index}", "every slide must retain the visible teaching boundary and all three labels")
            if handoff is not None and len(slide_texts) == expected_slide_count:
                framework = handoff.get("deck_framework")
                pages = [page for page in framework if isinstance(page, Mapping)] if isinstance(framework, list) else []
                design_values = [value for value in _design_content_strings(handoff) if value not in {label for label in TEACHING_LABELS}]
                for index, page in enumerate(pages):
                    slide_text = slide_texts[index] if index < len(slide_texts) else ""
                    copy = page.get("visible_slide_copy")
                    headline = str(copy.get("headline", "")) if isinstance(copy, Mapping) else ""
                    if headline and headline not in slide_text:
                        _error(errors, "SYNTHETIC_PPTX_VISIBLE_COPY_MISSING", f"/pptx/slide-{index + 1}", "the slide must render its visible_slide_copy headline")
                    notes = page.get("speaker_notes")
                    if isinstance(notes, Mapping):
                        for value in [notes.get("delivery_hint"), *(notes.get("evidence_and_limitations") or [])]:
                            if isinstance(value, str) and value and value in slide_text:
                                _error(errors, "SYNTHETIC_PPTX_SPEAKER_NOTES_VISIBLE", f"/pptx/slide-{index + 1}", "speaker notes must never reach the visible slide text")
                    for field in ("page_id", "internal_purpose"):
                        value = page.get(field)
                        if isinstance(value, str) and value and value in slide_text:
                            _error(errors, "SYNTHETIC_PPTX_INTERNAL_TRACE_VISIBLE", f"/pptx/slide-{index + 1}", f"internal {field} must never reach the visible slide text")
                    if INTERNAL_ID_RE.search(slide_text):
                        _error(errors, "SYNTHETIC_PPTX_INTERNAL_TRACE_VISIBLE", f"/pptx/slide-{index + 1}", "visible slide text must not contain internal state IDs")
                    # Page-local provenance: a design-content string is only
                    # tolerated on the page whose human-approved visible copy
                    # exactly equals it; every other page still fails.
                    for value in _page_forbidden_design_values(page, design_values):
                        if value in slide_text:
                            _error(errors, "SYNTHETIC_PPTX_DESIGN_CONTENT_VISIBLE", f"/pptx/slide-{index + 1}", "design-content strings outside this page's approved visible copy must never reach the visible slide text")
                # Raw-part scan: also covers alt text and shape names, and
                # refuses the review sentinel literals anywhere in a part.
                with ZipFile(pptx_path) as archive:
                    for name in (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                        raw = archive.read(name).decode("utf-8", errors="replace")
                        if "PD_SENTINEL" in raw or "DC_SENTINEL" in raw:
                            _error(errors, "SYNTHETIC_PPTX_INTERNAL_TRACE_VISIBLE", f"/pptx/{name}", "review sentinel literals must never appear in any slide part")
        except (OSError, ValueError, ElementTree.ParseError) as error:
            _error(errors, "SYNTHETIC_PPTX_AUDIT_FAILED", "/pptx", str(error))
    errors.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return {"ok": not errors, "outcome": "SYNTHETIC_PPTX_VALIDATED" if not errors else "SYNTHETIC_PPTX_VALIDATION_FAILED", "errors": errors}


_STAGING_PATH_BUDGET = 220
_STAGING_PATH_OVERHEAD = 80


def _staging_root() -> Path:
    """Pick a short staging root for the locked renderer's temporary files.

    Prefers the OS temp dir; when the projected path exceeds the Windows
    long-path budget (len(root) + overhead > 220), falls back to the root of
    the temp dir's drive, and finally to the current working directory with a
    budget warning on stderr.
    """

    temp_dir = Path(tempfile.gettempdir())
    candidates = [temp_dir]
    drive_root = Path(os.path.splitdrive(str(temp_dir))[0] + os.sep)
    if drive_root != temp_dir:
        candidates.append(drive_root)
    for candidate in candidates:
        if len(str(candidate)) + _STAGING_PATH_OVERHEAD <= _STAGING_PATH_BUDGET:
            return candidate
    fallback = Path.cwd()
    print(f"warning: staging path budget exceeds {_STAGING_PATH_BUDGET} chars, falling back to {fallback}", file=sys.stderr)
    return fallback


def _rollback_outputs(output_dir: Path, names: Sequence[str], was_missing: bool) -> None:
    """Remove artifacts written by this run and, when empty again, the directory itself."""

    for name in names:
        target = output_dir / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            continue
        target.unlink(missing_ok=True)
        (output_dir / f".{name}.tmp-{os.getpid()}").unlink(missing_ok=True)
    if was_missing:
        try:
            output_dir.rmdir()
        except OSError:
            pass


def _deliver_outputs(
    output_dir: Path,
    deck_path: Path,
    manifest_path: Path,
    report_path: Path,
    svg_editable_dir: Path | None = None,
    svg_compiled_dir: Path | None = None,
) -> None:
    """Atomically move staged artifacts into the final output directory.

    Each artifact is first copied to a sibling temp name inside output_dir,
    then os.replace renames it into place (same-volume atomic rename). If any
    step fails, every file written by this run is rolled back and the error
    propagates so the render reports a runtime failure.
    """

    was_missing = not output_dir.exists()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = (
        (deck_path, "synthetic-teaching-demo.pptx"),
        (manifest_path, "synthetic-teaching-demo.manifest.json"),
        (report_path, "synthetic-teaching-demo.structure-report.json"),
    )
    names = [name for _, name in artifacts]
    try:
        for source, name in artifacts:
            temp_target = output_dir / f".{name}.tmp-{os.getpid()}"
            shutil.copyfile(source, temp_target)
            os.replace(temp_target, output_dir / name)
        for source_dir, target_name in (
            (svg_editable_dir, "svg-editable"),
            (svg_compiled_dir, "svg-compiled"),
        ):
            if source_dir is None or not source_dir.is_dir():
                continue
            target = output_dir / target_name
            target.mkdir(parents=True, exist_ok=True)
            for svg_file in sorted(source_dir.glob("*.svg")):
                temp_target = target / f".{svg_file.name}.tmp-{os.getpid()}"
                shutil.copyfile(svg_file, temp_target)
                os.replace(temp_target, target / svg_file.name)
            names.append(target_name)
    except OSError:
        _rollback_outputs(output_dir, names, was_missing)
        raise


def _freshness_gate_errors(
    freshness_ledger: JsonObject,
    freshness_receipt: JsonObject,
    ledger_base_dir: Path,
    human_review: JsonObject,
    handoff_path: Path,
    state_document: Path,
    *,
    handoff_sha256: str,
) -> tuple[list[RenderError], JsonObject]:
    """DELIVERY-mode gate: recompute ledger freshness through the shared ARCH-124 layer.

    Requires the independent human review receipt and the actual handoff
    document; verifies copy bindings; never trusts the stored receipt verdict.
    """
    ok, errors, summary = data_staleness.verify_delivery_freshness(
        freshness_ledger,
        freshness_receipt,
        base_dir=ledger_base_dir,
        documents={
            data_staleness.HANDOFF_PRESENTATION_ROLE: handoff_path,
            "state_output": state_document,
        },
        human_review=human_review,
        expected_bindings=[("presentation_handoff", handoff_sha256)],
        require_human_review=True,
        verify_copy_bindings=True,
    )
    if ok:
        return [], {
            "verdict": "CURRENT",
            "delivery_status": "DELIVERY",
            "ledger_canonical_sha256": summary["ledger_canonical_sha256"],
            "receipt_sha256": canonical_sha256(freshness_receipt),
            "human_review_digest": summary.get("human_review_digest"),
        }
    if any(item["code"] == "RECEIPT_MISMATCH" for item in errors):
        code = "FRESHNESS_RECEIPT_MISMATCH"
    elif any(item["code"] in {"RECEIPT_NOT_CURRENT", "RECEIPT_BINDING_MISSING"} for item in errors):
        code = "FRESHNESS_RECEIPT_STALE"
    elif any(item["code"] in {"HUMAN_REVIEW_REQUIRED", "HUMAN_REVIEW_NOT_APPROVED", "HUMAN_REVIEWER_LABEL_REJECTED", "REVIEW_HASH_MISMATCH", "REVIEW_ARTIFACT_BINDING_MISSING"} for item in errors):
        code = "HUMAN_REVIEW_REJECTED"
    else:
        code = "FRESHNESS_GATE_INVALID"
    return [
        {
            "code": code,
            "path": "",
            "message": "; ".join(f"{item['code']}: {item['message']}" for item in errors)[:500],
        }
    ], {}


def render_synthetic_teaching_pptx(
    handoff: JsonObject,
    renderer_root: Path,
    output_dir: Path,
    schema: JsonObject,
    copy_review: JsonObject | None = None,
    *,
    mode: str,
    freshness_ledger: JsonObject | None = None,
    freshness_receipt: JsonObject | None = None,
    ledger_base_dir: Path | None = None,
    human_review: JsonObject | None = None,
    handoff_path: Path | None = None,
    state_document: Path | None = None,
) -> tuple[JsonObject | None, RenderResult]:
    """Stage SVG pages on a short path, invoke only locked ppt-master, then atomically deliver the audited deck.

    ``mode`` is mandatory and has exactly two values. ``intermediate`` marks
    every produced artifact ``INTERMEDIATE_NOT_FOR_DELIVERY`` and refuses
    delivery freshness inputs; ``delivery`` requires the data ledger, the
    freshness receipt, and the independent human review receipt, recomputes
    freshness against the actual files, and refuses the render when anything
    bound to the handoff is stale.
    """

    if mode not in {"intermediate", "delivery"}:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "MODE_REQUIRED", "path": "--mode", "message": "mode must be explicitly intermediate or delivery"}]}
    if mode == "intermediate" and any(argument is not None for argument in (freshness_ledger, freshness_receipt, human_review)):
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "FRESHNESS_GATE_INVALID", "path": "", "message": "intermediate renders must not carry delivery freshness inputs"}]}
    handoff_result = validate_synthetic_teaching_presentation_handoff(handoff, schema, copy_review)
    if not handoff_result["ok"]:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": handoff_result["errors"]}
    freshness_summary: JsonObject | None = None
    delivery_status = "INTERMEDIATE_NOT_FOR_DELIVERY" if mode == "intermediate" else "DELIVERY"
    if mode == "delivery":
        if freshness_ledger is None or freshness_receipt is None or ledger_base_dir is None or human_review is None or handoff_path is None or state_document is None:
            return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "MODE_REQUIRED", "path": "--mode", "message": "delivery renders require --data-ledger, --freshness-receipt, --human-review, --handoff, and --state-document together"}]}
        gate_errors, freshness_summary = _freshness_gate_errors(
            freshness_ledger,
            freshness_receipt,
            ledger_base_dir,
            human_review,
            handoff_path,
            state_document,
            handoff_sha256=canonical_sha256(handoff),
        )
        if gate_errors:
            return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": gate_errors}
    renderer_errors = _locked_renderer_errors(renderer_root)
    if renderer_errors:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": renderer_errors}

    artifact_names = ("ppt-master-workspace", "synthetic-teaching-demo.pptx", "synthetic-teaching-demo.manifest.json", "synthetic-teaching-demo.structure-report.json", "svg-editable", "svg-compiled")
    if any((output_dir / name).exists() for name in artifact_names):
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "SYNTHETIC_OUTPUT_EXISTS", "path": str(output_dir), "message": "output directory must not already contain this run's synthetic artifacts"}]}

    staging = _staging_root() / f".arch086-stg-{os.getpid()}"
    workspace = staging / "ppt-master-workspace"
    deck_path = staging / "synthetic-teaching-demo.pptx"
    manifest_path = staging / "synthetic-teaching-demo.manifest.json"
    report_path = staging / "synthetic-teaching-demo.structure-report.json"
    try:
        _write_text(workspace / "spec_lock.md", _spec_lock())
        teaching_content = handoff["teaching_content"]
        assumptions = handoff["human_authorized_assumptions"]
        assert isinstance(teaching_content, Mapping) and isinstance(assumptions, Mapping)
        visual_content: JsonObject = dict(teaching_content)
        visual_content["unresolved_inputs"] = assumptions["unresolved_inputs"]
        # ARCH-123 dual asset roles: editable source is authored and audited
        # first; PPTX export consumes only the compiled (text-to-path) SVG.
        asset_roles: list[JsonObject] = []
        for index, page in enumerate(handoff["deck_framework"], start=1):
            assert isinstance(page, Mapping)
            page_id = str(page["page_id"])
            editable_svg = _page_visual(page, visual_content, index)
            source_errors, _source_meta = audit_svg_source(editable_svg)
            if source_errors:
                return None, {
                    "ok": False,
                    "outcome": "SYNTHETIC_RENDER_FAILED",
                    "errors": [
                        {
                            "code": item["code"],
                            "path": f"/svg-editable/{index:02d}",
                            "message": item["message"],
                        }
                        for item in source_errors
                    ],
                }
            try:
                compiled_svg, _fonts, runs = compile_text_elements(editable_svg)
            except Exception as error:  # TextToPathError and font errors
                code = getattr(error, "code", "SYNTHETIC_SVG_COMPILE_FAILED")
                return None, {
                    "ok": False,
                    "outcome": "SYNTHETIC_RENDER_FAILED",
                    "errors": [{"code": str(code), "path": f"/svg-editable/{index:02d}", "message": str(error)}],
                }
            if count_text_elements(compiled_svg) != 0:
                return None, {
                    "ok": False,
                    "outcome": "SYNTHETIC_RENDER_FAILED",
                    "errors": [
                        {
                            "code": "SVG_COMPILED_TEXT_REMAINING",
                            "path": f"/svg-compiled/{index:02d}",
                            "message": "compiled teaching page still contains text elements",
                        }
                    ],
                }
            editable_name = f"{index:02d}_{page_id}.editable.svg"
            compiled_name = f"{index:02d}_{page_id}.compiled.svg"
            _write_text(workspace / "svg_editable" / editable_name, editable_svg)
            # svg_output is the ppt-master export input; it receives compiled SVG.
            _write_text(workspace / "svg_output" / f"{index:02d}_{page_id}.svg", compiled_svg)
            _write_text(workspace / "svg_compiled" / compiled_name, compiled_svg)
            asset_roles.append(
                {
                    "index": index,
                    "page_id": page_id,
                    "editable": editable_name,
                    "compiled": compiled_name,
                    "text_runs_compiled": runs,
                    "editable_sha256": hashlib.sha256(editable_svg.encode("utf-8")).hexdigest(),
                    "compiled_sha256": hashlib.sha256(compiled_svg.encode("utf-8")).hexdigest(),
                }
            )

        python = _renderer_python(renderer_root)
        assert python is not None
        checker = subprocess.run(
            [str(python), str(renderer_root / "scripts" / "svg_quality_checker.py"), str(workspace), "--format", "ppt169", "--quick-generate", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if checker.returncode != 0:
            return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "SYNTHETIC_SVG_QUALITY_FAILED", "path": "/ppt-master-workspace/svg_output", "message": (checker.stderr or checker.stdout).strip()[:500]}]}
        exporter = subprocess.run(
            [str(python), str(renderer_root / "scripts" / "svg_to_pptx.py"), str(workspace), "--output", str(deck_path), "--format", "ppt169", "--quick-generate", "--pptx-structure", "flat", "--transition", "none", "--animation", "none", "--no-notes"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
        if exporter.returncode != 0:
            return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "SYNTHETIC_PPT_MASTER_EXPORT_FAILED", "path": "/ppt-master-workspace", "message": (exporter.stderr or exporter.stdout).strip()[:500]}]}
        audit = audit_synthetic_teaching_pptx(deck_path, handoff=handoff)
        if not audit["ok"]:
            return None, audit
        manifest: JsonObject = {
            "manifest_version": "1.0.0",
            "mode": "SYNTHETIC_NO_PRECEDENT_DEMO",
            "delivery_status": delivery_status,
            "teaching_labels": list(TEACHING_LABELS),
            "not_real_project_validation": True,
            "handoff_sha256": canonical_sha256(handoff),
            "pptx_filename": deck_path.name,
            "pptx_sha256": _sha256_file(deck_path),
            "expected_slide_count": PAGE_COUNT,
            "renderer": "ppt-master",
            "third_party_media_packaged": False,
            "external_urls_permitted": False,
            "svg_dual_asset_pipeline": {
                "contract_version": "1.0.0",
                "source_before_compile": True,
                "pptx_consumes": "compiled_svg",
                "pages": asset_roles,
            },
        }
        if freshness_summary is not None:
            manifest["data_freshness"] = freshness_summary
        _write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        report: JsonObject = {"ok": True, "outcome": "SYNTHETIC_PPTX_VALIDATED", "mode": "SYNTHETIC_NO_PRECEDENT_DEMO", "delivery_status": delivery_status, "teaching_labels": list(TEACHING_LABELS), "not_real_project_validation": True, "checks": ["locked_ppt_master_receipt", "svg_editable_source_audit", "svg_text_to_path_compile", "svg_compiled_text_free", "svg_quality", "native_editable_pptx", "no_external_relationships", "no_macros", "no_media", "visible_teaching_labels"], "pptx_sha256": manifest["pptx_sha256"], "svg_pages_compiled": len(asset_roles)}
        _write_text(report_path, json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        _deliver_outputs(
            output_dir,
            deck_path,
            manifest_path,
            report_path,
            workspace / "svg_editable",
            workspace / "svg_compiled",
        )
        return manifest, {"ok": True, "outcome": "SYNTHETIC_PPTX_RENDERED", "errors": []}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "SYNTHETIC_RENDER_RUNTIME_ERROR", "path": "", "message": str(error)}]}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: Sequence[str]) -> int:
    """Render one local synthetic deck and emit a machine-readable outcome."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--ppt-master-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--copy-review", type=Path, required=True, help="explicit human copy review; the final renderer refuses a deck that is not audience-ready")
    parser.add_argument("--mode", required=True, choices=["intermediate", "delivery"], help="intermediate marks the deck INTERMEDIATE_NOT_FOR_DELIVERY; delivery requires the full freshness gate")
    parser.add_argument("--data-ledger", type=Path, help="ARCH-124 design-data ledger (delivery mode only)")
    parser.add_argument("--freshness-receipt", type=Path, help="freshness receipt matching --data-ledger (delivery mode only)")
    parser.add_argument("--human-review", type=Path, help="independent human design-data review receipt (delivery mode only)")
    parser.add_argument("--state-document", type=Path, help="actual state/source document the ledger data binds to (delivery mode only)")
    arguments = parser.parse_args(argv)
    if arguments.mode == "delivery":
        freshness_ledger = load_json_object(arguments.data_ledger) if arguments.data_ledger else None
        freshness_receipt = load_json_object(arguments.freshness_receipt) if arguments.freshness_receipt else None
        human_review = load_json_object(arguments.human_review) if arguments.human_review else None
        ledger_base_dir = arguments.data_ledger.resolve().parent if arguments.data_ledger else None
        state_document = arguments.state_document.resolve() if arguments.state_document else None
    else:
        freshness_ledger = freshness_receipt = human_review = None
        ledger_base_dir = None
    manifest, result = render_synthetic_teaching_pptx(
        load_json_object(arguments.handoff),
        arguments.ppt_master_root.resolve(),
        arguments.output_dir.resolve(),
        load_json_object(SCHEMA_PATH),
        load_json_object(arguments.copy_review),
        mode=arguments.mode,
        freshness_ledger=freshness_ledger,
        freshness_receipt=freshness_receipt,
        ledger_base_dir=ledger_base_dir,
        human_review=human_review,
        handoff_path=arguments.handoff.resolve(),
        state_document=state_document,
    )
    payload: JsonObject = dict(result)
    if manifest is not None:
        payload["manifest"] = manifest
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
