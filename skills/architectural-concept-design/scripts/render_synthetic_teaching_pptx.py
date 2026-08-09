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

import evaluate_presentation_e2e as normal_e2e  # noqa: E402
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


def _header(title: object, project_name: str, index: int) -> str:
    title_size = 52 if index == 1 else 38
    return "\n".join(
        (
            '<rect x="0" y="0" width="1280" height="720" fill="#F6F4EF"/>',
            '<rect x="0" y="0" width="1280" height="18" fill="#E56B4F"/>',
            '<text x="62" y="72" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#4B8F8C">SYNTHETIC TEACHING PPTX</text>',
            _text(62, 134, title, title_size, weight="700"),
            _text(62, 174, project_name, 22, fill="#52616B"),
            '<line x1="62" y1="202" x2="1218" y2="202" stroke="#C9D2D8" stroke-width="2"/>',
        )
    )


def _footer(page_id: object, index: int) -> str:
    return "\n".join(
        (
            '<rect x="62" y="620" width="1156" height="56" rx="8" fill="#172B4D"/>',
            f'<text x="84" y="646" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" font-weight="700" fill="#FFFFFF">{NOTICE}</text>',
            f'<text x="84" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[0]}</text>',
            f'<text x="380" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[1]}</text>',
            f'<text x="530" y="668" font-family="Microsoft YaHei, Arial, sans-serif" font-size="16" fill="#FFFFFF">{TEACHING_LABELS[2]}</text>',
            _text(1218, 704, f"{page_id} · {index:02d}/08", 16, fill="#52616B", anchor="end"),
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


def _page_visual(page: Mapping[str, Any], project_name: str, decision: Mapping[str, Any], teaching_content: Mapping[str, Any], index: int) -> str:
    page_id = str(page["page_id"])
    title = str(page["title"])
    program = [item for item in teaching_content.get("program_spaces", []) if isinstance(item, Mapping)]
    options = [item for item in teaching_content.get("concept_options", []) if isinstance(item, Mapping)]
    selected = teaching_content.get("selected_option")
    selected_option = selected if isinstance(selected, Mapping) else {}
    hypotheses = [item for item in teaching_content.get("hypotheses", []) if isinstance(item, Mapping)]
    content: list[str] = [_header(title, project_name, index)]

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
                _text(62, 430, f"人类决定：{decision['decision_id']} / {decision['chosen_option_id']}", 22, weight="700"),
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
            for record_index, record in enumerate(records[:3]):
                label = f"{record.get('id')}  {record.get('name')}"
                content.append(_text(x + 26, y + 76 + record_index * 24, label, 17, fill="#52616B"))
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
            content.append(_text(x + 30, y + 46, f"{option.get('id')}  概念方向{('一', '二')[option_index - 1]}", 23, weight="700"))
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
        operation = str(selected_option.get("spatial_operation", "")).lower()
        is_courtyard = "court" in operation or "院" in operation
        content.append(_text(62, 248, f"人类已选：{selected_option.get('id')}", 26, weight="700"))
        if is_courtyard:
            content.extend((
                '<rect x="380" y="286" width="520" height="240" rx="26" fill="#E7F0EF" stroke="#4B8F8C" stroke-width="16"/>',
                '<rect x="520" y="356" width="240" height="100" rx="16" fill="#F6F4EF" stroke="#172B4D" stroke-width="3"/>',
                _text(640, 415, "内院 / 共享环路", 24, weight="700", anchor="middle"),
                _text(445, 325, "服务", 20, weight="700", anchor="middle"),
                _text(835, 325, "安静学习", 20, weight="700", anchor="middle"),
                _text(445, 500, "活动", 20, weight="700", anchor="middle"),
                _text(835, 500, "公共论坛", 20, weight="700", anchor="middle"),
            ))
        else:
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
            field = unresolved_item.get("field") if isinstance(unresolved_item, Mapping) else "UNKNOWN"
            content.extend((
                f'<rect x="{x}" y="{y}" width="330" height="180" rx="14" fill="#FFFFFF" stroke="#C9D2D8" stroke-width="2"/>',
                _text(x + 26, y + 58, labels.get(field, str(field)), 24, weight="700"),
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
    content.append(_footer(page_id, index))
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


def audit_synthetic_teaching_pptx(pptx_path: Path, expected_slide_count: int = PAGE_COUNT) -> RenderResult:
    """Perform local OOXML audit for the synthetic teaching deck only."""

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
        (output_dir / name).unlink(missing_ok=True)
        (output_dir / f".{name}.tmp-{os.getpid()}").unlink(missing_ok=True)
    if was_missing:
        try:
            output_dir.rmdir()
        except OSError:
            pass


def _deliver_outputs(output_dir: Path, deck_path: Path, manifest_path: Path, report_path: Path) -> None:
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
    try:
        for source, name in artifacts:
            temp_target = output_dir / f".{name}.tmp-{os.getpid()}"
            shutil.copyfile(source, temp_target)
            os.replace(temp_target, output_dir / name)
    except OSError:
        _rollback_outputs(output_dir, [name for _, name in artifacts], was_missing)
        raise


def render_synthetic_teaching_pptx(
    handoff: JsonObject,
    renderer_root: Path,
    output_dir: Path,
    schema: JsonObject,
) -> tuple[JsonObject | None, RenderResult]:
    """Stage SVG pages on a short path, invoke only locked ppt-master, then atomically deliver the audited deck."""

    handoff_result = validate_synthetic_teaching_presentation_handoff(handoff, schema)
    if not handoff_result["ok"]:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": handoff_result["errors"]}
    renderer_errors = _locked_renderer_errors(renderer_root)
    if renderer_errors:
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": renderer_errors}

    artifact_names = ("ppt-master-workspace", "synthetic-teaching-demo.pptx", "synthetic-teaching-demo.manifest.json", "synthetic-teaching-demo.structure-report.json")
    if any((output_dir / name).exists() for name in artifact_names):
        return None, {"ok": False, "outcome": "SYNTHETIC_RENDER_FAILED", "errors": [{"code": "SYNTHETIC_OUTPUT_EXISTS", "path": str(output_dir), "message": "output directory must not already contain this run's synthetic artifacts"}]}

    staging = _staging_root() / f".arch086-stg-{os.getpid()}"
    workspace = staging / "ppt-master-workspace"
    deck_path = staging / "synthetic-teaching-demo.pptx"
    manifest_path = staging / "synthetic-teaching-demo.manifest.json"
    report_path = staging / "synthetic-teaching-demo.structure-report.json"
    try:
        _write_text(workspace / "spec_lock.md", _spec_lock())
        decision = handoff["human_design_decision"]
        teaching_content = handoff["teaching_content"]
        assumptions = handoff["human_authorized_assumptions"]
        assert isinstance(decision, Mapping)
        assert isinstance(teaching_content, Mapping) and isinstance(assumptions, Mapping)
        visual_content: JsonObject = dict(teaching_content)
        visual_content["unresolved_inputs"] = assumptions["unresolved_inputs"]
        for index, page in enumerate(handoff["deck_framework"], start=1):
            assert isinstance(page, Mapping)
            _write_text(workspace / "svg_output" / f"{index:02d}_{page['page_id']}.svg", _page_visual(page, str(handoff["project_display_name"]), decision, visual_content, index))

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
        audit = audit_synthetic_teaching_pptx(deck_path)
        if not audit["ok"]:
            return None, audit
        manifest: JsonObject = {
            "manifest_version": "1.0.0",
            "mode": "SYNTHETIC_NO_PRECEDENT_DEMO",
            "teaching_labels": list(TEACHING_LABELS),
            "not_real_project_validation": True,
            "handoff_sha256": canonical_sha256(handoff),
            "pptx_filename": deck_path.name,
            "pptx_sha256": _sha256_file(deck_path),
            "expected_slide_count": PAGE_COUNT,
            "renderer": "ppt-master",
            "third_party_media_packaged": False,
            "external_urls_permitted": False,
        }
        _write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        report: JsonObject = {"ok": True, "outcome": "SYNTHETIC_PPTX_VALIDATED", "mode": "SYNTHETIC_NO_PRECEDENT_DEMO", "teaching_labels": list(TEACHING_LABELS), "not_real_project_validation": True, "checks": ["locked_ppt_master_receipt", "svg_quality", "native_editable_pptx", "no_external_relationships", "no_macros", "no_media", "visible_teaching_labels"], "pptx_sha256": manifest["pptx_sha256"]}
        _write_text(report_path, json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        _deliver_outputs(output_dir, deck_path, manifest_path, report_path)
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
    arguments = parser.parse_args(argv)
    manifest, result = render_synthetic_teaching_pptx(
        load_json_object(arguments.handoff),
        arguments.ppt_master_root.resolve(),
        arguments.output_dir.resolve(),
        load_json_object(SCHEMA_PATH),
    )
    payload: JsonObject = dict(result)
    if manifest is not None:
        payload["manifest"] = manifest
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
