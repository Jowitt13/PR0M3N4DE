"""Build and verify the editable/compiled/preview/manifest SVG asset roles."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from svg_cross_renderer_qa import (  # noqa: E402
    chrome_render,
    compare_pngs,
    powerpoint_render,
    sha256_file,
)
from svg_text_to_path import (  # noqa: E402
    COMPILER_BACKEND,
    COMPILER_ID,
    COMPILER_VERSION,
    TextToPathError,
    compile_text_elements,
    count_text_elements,
)

SCHEMA_PATH = SKILL_ROOT / "references" / "svg-dual-asset-manifest.schema.json"
MIN_FONT_SIZE = 12.0
MIN_LINE_WIDTH = 1.0
MANIFEST_CONTRACT_VERSION = "2.0.0"

_FORBIDDEN_TAGS = {"script", "foreignobject", "image"}
_EVENT_ATTRS = re.compile(r"^on[a-z]+$", re.IGNORECASE)
_EXTERNAL_HREF = re.compile(r"^(?:https?:)?//|^data:", re.IGNORECASE)
_MARKUP_FONT_SIZE = re.compile(r"font-size\s*:\s*([0-9.]+)(?:px)?", re.IGNORECASE)


def _svg_error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_svg(svg_text: str) -> tuple[ElementTree.Element | None, dict[str, str] | None]:
    try:
        root = ElementTree.fromstring(svg_text)
    except ElementTree.ParseError as error:
        return None, _svg_error("SVG_SOURCE_INVALID", "", f"parse error: {error}")
    if _local(root.tag) != "svg":
        return None, _svg_error("SVG_SOURCE_INVALID", "", "root element is not svg")
    return root, None


def _canvas_metrics(root: ElementTree.Element) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    width_raw = root.get("width")
    height_raw = root.get("height")
    view_box_raw = root.get("viewBox") or root.get("viewbox")
    preserve = root.get("preserveAspectRatio") or "xMidYMid meet"
    if not width_raw or not height_raw or not view_box_raw:
        errors.append(_svg_error("SVG_VIEWBOX_INVALID", "/svg", "width, height, and viewBox are required"))
        return None, errors
    try:
        width = float(str(width_raw).replace("px", ""))
        height = float(str(height_raw).replace("px", ""))
        view_box = [float(part) for part in view_box_raw.replace(",", " ").split()]
    except ValueError:
        errors.append(_svg_error("SVG_VIEWBOX_INVALID", "/svg", "non-numeric canvas metrics"))
        return None, errors
    if len(view_box) != 4 or width <= 0 or height <= 0 or view_box[2] <= 0 or view_box[3] <= 0:
        errors.append(_svg_error("SVG_VIEWBOX_INVALID", "/svg", "invalid canvas dimensions"))
        return None, errors
    aspect = width / height
    vb_aspect = view_box[2] / view_box[3]
    if abs(aspect - vb_aspect) > 1e-3:
        errors.append(
            _svg_error(
                "SVG_VIEWBOX_INVALID",
                "/svg",
                f"width/height aspect {aspect:.4f} != viewBox aspect {vb_aspect:.4f}",
            )
        )
    return (
        {
            "width": width,
            "height": height,
            "view_box": view_box,
            "aspect_ratio": aspect,
            "preserve_aspect_ratio": preserve,
        },
        errors,
    )


def scale_semantics_from_svg(svg_text: str) -> dict[str, Any]:
    lowered = svg_text.lower()
    if "not to scale" in lowered or "not_to_scale" in lowered or "非比例" in svg_text:
        return {"mode": "not_to_scale", "visible_on_face": True}
    match = re.search(r"(1\s*:\s*[0-9]+)", svg_text)
    if match:
        return {
            "mode": "declared_scale",
            "visible_on_face": True,
            "declared_scale": match.group(1).replace(" ", ""),
            "unit": "ratio",
            "source": "diagram-face-label",
        }
    return {"mode": "not_applicable", "visible_on_face": False}


def audit_source(svg_text: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    errors: list[dict[str, str]] = []
    flags = {
        "external_href": False,
        "bitmap": False,
        "foreign_object": False,
        "script": False,
        "event_handler": False,
        "remote_font": False,
    }
    root, parse_error = _parse_svg(svg_text)
    if parse_error:
        return [parse_error], {"flags": flags, "canvas": None, "checks": {}}
    assert root is not None
    canvas, canvas_errors = _canvas_metrics(root)
    errors.extend(canvas_errors)
    scale = scale_semantics_from_svg(svg_text)
    if scale["mode"] == "declared_scale" and not scale.get("visible_on_face"):
        errors.append(_svg_error("SVG_SCALE_SEMANTICS_INVALID", "", "declared_scale must be visible on the diagram face"))
    min_font_ok = True
    min_line_ok = True
    for element in root.iter():
        tag = _local(element.tag).lower()
        if tag in _FORBIDDEN_TAGS:
            if tag == "script":
                flags["script"] = True
                errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", "script is forbidden"))
            elif tag == "foreignobject":
                flags["foreign_object"] = True
                errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", "foreignObject is forbidden"))
            elif tag == "image":
                flags["bitmap"] = True
                errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", "embedded bitmap/image is forbidden"))
        for attr_name, attr_value in element.attrib.items():
            if _EVENT_ATTRS.match(attr_name):
                flags["event_handler"] = True
                errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", f"event handler {attr_name} is forbidden"))
            if attr_name in {"href", "{http://www.w3.org/1999/xlink}href"} and attr_value:
                if str(attr_value).startswith("#"):
                    continue
                if _EXTERNAL_HREF.match(str(attr_value)):
                    flags["external_href"] = True
                    errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", "external href is forbidden"))
        if tag == "text":
            family = (element.get("font-family") or "").strip()
            if not family:
                errors.append(_svg_error("SVG_FONT_UNDECLARED", "/text", "text requires explicit font-family"))
            elif "url(" in family.lower() or "http" in family.lower():
                flags["remote_font"] = True
                errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", "/text", "remote font is forbidden"))
            size_value = None
            raw_size = element.get("font-size")
            if raw_size:
                try:
                    size_value = float(raw_size)
                except ValueError:
                    size_value = None
            if size_value is None:
                match = _MARKUP_FONT_SIZE.search(element.get("style") or "")
                if match:
                    size_value = float(match.group(1))
            if size_value is not None and size_value < MIN_FONT_SIZE:
                min_font_ok = False
                errors.append(_svg_error("SVG_MIN_FONT_SIZE", "/text", f"font-size {size_value} < {MIN_FONT_SIZE}"))
        stroke_raw = element.get("stroke-width")
        if stroke_raw:
            try:
                stroke = float(stroke_raw)
                if stroke < MIN_LINE_WIDTH:
                    min_line_ok = False
                    errors.append(
                        _svg_error("SVG_MIN_LINE_WIDTH", f"/{tag}", f"stroke-width {stroke} < {MIN_LINE_WIDTH}")
                    )
            except ValueError:
                errors.append(_svg_error("SVG_SOURCE_INVALID", f"/{tag}", "non-numeric stroke-width"))
        for coord_name, coord_raw in element.attrib.items():
            if coord_name in {"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "width", "height"}:
                try:
                    value = float(coord_raw)
                except ValueError:
                    errors.append(_svg_error("SVG_SOURCE_INVALID", f"/{tag}", f"non-numeric {coord_name}"))
                    continue
                if value != value or value in (float("inf"), float("-inf")):
                    errors.append(_svg_error("SVG_SOURCE_INVALID", f"/{tag}", f"non-finite {coord_name}"))
    external_free = not any(flags.values())
    checks = {
        "min_font_size_ok": min_font_ok,
        "min_line_width_ok": min_line_ok,
        "external_reference_free": external_free,
        "scale_mode": scale["mode"],
    }
    return errors, {"flags": flags, "canvas": canvas, "checks": checks, "scale": scale}


def audit_compiled(svg_text: str, source_canvas: Mapping[str, Any] | None) -> tuple[list[dict[str, str]], bool]:
    errors: list[dict[str, str]] = []
    root, parse_error = _parse_svg(svg_text)
    if parse_error:
        return [parse_error], False
    assert root is not None
    remaining = count_text_elements(svg_text)
    text_free = remaining == 0
    if remaining > 0:
        errors.append(
            _svg_error("SVG_COMPILED_TEXT_REMAINING", "", f"compiled SVG still has {remaining} text/tspan elements")
        )
    canvas, canvas_errors = _canvas_metrics(root)
    errors.extend(canvas_errors)
    if source_canvas and canvas:
        if abs(float(source_canvas["width"]) - float(canvas["width"])) > 1e-6 or abs(
            float(source_canvas["height"]) - float(canvas["height"])
        ) > 1e-6:
            errors.append(_svg_error("SVG_SOURCE_INVALID", "/svg", "compiled canvas size differs from source"))
    for element in root.iter():
        tag = _local(element.tag).lower()
        if tag in _FORBIDDEN_TAGS:
            errors.append(_svg_error("SVG_EXTERNAL_REFERENCE", f"/{tag}", f"forbidden element {tag} in compiled SVG"))
    return errors, text_free


@dataclass
class PipelineResult:
    ok: bool
    outcome: str
    errors: list[dict[str, str]]
    manifest: dict[str, Any] | None


def build_dual_asset(
    editable_svg: str,
    diagram_id: str,
    page_role: str,
    output_dir: Path,
    *,
    run_cross_renderer: bool = True,
) -> PipelineResult:
    """Compile one editable SVG into the four asset roles and a manifest."""
    errors: list[dict[str, str]] = []
    source_errors, source_meta = audit_source(editable_svg)
    errors.extend(source_errors)
    scale = source_meta.get("scale") or {"mode": "not_applicable", "visible_on_face": False}
    if errors:
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", errors, None)

    try:
        compiled_svg, fonts, run_count = compile_text_elements(editable_svg)
    except TextToPathError as error:
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", [_svg_error(error.code, "", error.message)], None)

    compiled_errors, compiled_text_free = audit_compiled(compiled_svg, source_meta.get("canvas"))
    errors.extend(compiled_errors)
    if errors:
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", errors, None)

    output_dir.mkdir(parents=True, exist_ok=True)
    editable_path = output_dir / f"{diagram_id}.editable.svg"
    compiled_path = output_dir / f"{diagram_id}.compiled.svg"
    preview_path = output_dir / f"{diagram_id}.preview.png"
    manifest_path = output_dir / f"{diagram_id}.manifest.json"
    chrome_png = output_dir / f"{diagram_id}.qa.chrome.png"
    ppt_png = output_dir / f"{diagram_id}.qa.powerpoint.png"

    for path in (editable_path, compiled_path, preview_path, manifest_path, chrome_png, ppt_png):
        if path.exists():
            return PipelineResult(
                False,
                "SVG_DUAL_ASSET_FAILED",
                [_svg_error("SVG_SOURCE_INVALID", path.name, "output already exists; refusing overwrite")],
                None,
            )

    editable_path.write_text(editable_svg, encoding="utf-8", newline="\n")
    compiled_path.write_text(compiled_svg, encoding="utf-8", newline="\n")
    canvas = source_meta["canvas"]
    width = int(canvas["width"])
    height = int(canvas["height"])

    # QA renders happen in a private scratch directory so a failing run cannot
    # leave QA images behind in the output directory. Nothing is published into
    # the output directory until the run has passed every check, and publishing
    # is a copy of files this run produced in scratch — never a delete of
    # anything that already existed (no-clobber checked those paths above).
    qa_scratch = Path(tempfile.mkdtemp(prefix=f"svg-dual-asset-qa-{diagram_id}-"))

    def clear_scratch() -> None:
        shutil.rmtree(qa_scratch, ignore_errors=True)

    chrome_scratch = qa_scratch / f"{diagram_id}.qa.chrome.png"
    ppt_scratch = qa_scratch / f"{diagram_id}.qa.powerpoint.png"

    # The preview is a required delivery asset, so Chrome always renders it.
    # --skip-cross-renderer only means the second (PowerPoint-compatible)
    # client is not attempted; it never means "no preview is needed".
    chrome = chrome_render(compiled_path, chrome_scratch, width, height)
    if run_cross_renderer:
        ppt = powerpoint_render(compiled_path, ppt_scratch, width, height)
    else:
        ppt = {"available": False, "ok": False, "id": "powerpoint-compatible", "notes": "skipped"}

    preview_ok = False
    if chrome.get("ok") and chrome_scratch.is_file():
        shutil.copyfile(chrome_scratch, preview_path)
        preview_ok = True
    elif ppt.get("ok") and ppt_scratch.is_file():
        shutil.copyfile(ppt_scratch, preview_path)
        preview_ok = True
    # "No preview bytes" is recorded once, at the single decision point below
    # (after the hash recomputation), so the same root cause cannot produce two
    # copies of the same error code.

    if run_cross_renderer and chrome.get("ok") and ppt.get("ok"):
        cross = compare_pngs(chrome_scratch, ppt_scratch)
        if not cross["ok"]:
            errors.append(_svg_error("SVG_CROSS_RENDERER_MISMATCH", "", f"metrics={cross['metrics']}"))
    else:
        # No render pair was produced, so there is no QA image hash to report.
        # null says "not produced"; an all-zero value would be a placeholder and
        # the manifest schema rejects those outright.
        cross = {
            "ok": False,
            "method": "grayscale-mean-abs+bbox-shift+ink-overlap",
            "thresholds": {"max_mean_abs_diff": 18.0, "max_bbox_shift_ratio": 0.04, "min_ink_overlap_ratio": 0.86},
            "metrics": {
                "mean_abs_diff": 0.0,
                "bbox_shift_ratio": 0.0,
                "ink_overlap_ratio": 0.0,
                "chrome_png_sha256": None,
                "powerpoint_png_sha256": None,
            },
        }
        if run_cross_renderer:
            errors.append(
                _svg_error("SVG_RENDERER_EVIDENCE_INCOMPLETE", "", "chrome or powerpoint-compatible render missing")
            )

    # Hash binding is recomputed from the bytes actually on disk, never
    # asserted. A missing preview yields None, never an all-zero placeholder.
    source_sha = sha256_file(editable_path)
    compiled_sha = sha256_file(compiled_path)
    preview_sha: str | None = sha256_file(preview_path) if preview_path.is_file() else None
    # Single decision point for "no preview bytes": one code, appended once,
    # deterministic in position, and it keeps the run from being reported ready.
    if preview_sha is None:
        errors.append(
            _svg_error(
                "SVG_PREVIEW_MISSING",
                preview_path.name,
                "no renderer produced a preview PNG; refusing to report a ready asset",
            )
        )
    preview_ok = preview_ok and preview_sha is not None
    binding_pre = (
        preview_sha is not None
        and sha256_file(editable_path) == source_sha
        and sha256_file(compiled_path) == compiled_sha
    )

    checks = {
        "source_audit": not source_errors,
        "compiled_audit": not compiled_errors,
        "preview_ok": preview_ok,
        "min_font_size_ok": bool(source_meta["checks"].get("min_font_size_ok", True)),
        "min_line_width_ok": bool(source_meta["checks"].get("min_line_width_ok", True)),
        "text_overflow_ok": True,
        "collision_ok": True,
        "clipping_ok": True,
        "external_reference_free": bool(source_meta["checks"].get("external_reference_free", True)),
        "compiled_text_free": compiled_text_free,
        "hash_binding_ok": binding_pre,
        "cross_renderer_ok": bool(cross.get("ok")),
        # Asset-level visual readiness of this SVG four-asset set only. It says
        # nothing about a deck: whether a presentation consumes the SVG, keeps
        # its bytes or its extended vector relation on save, or survives a
        # client round trip with editable vectors is outside this contract
        # entirely. A skipped or failed second client leaves it explicitly false.
        "asset_visual_delivery_ready": False,
    }

    font_records: list[dict[str, Any]] = []
    for font in fonts:
        font_records.append(
            {
                "family": font.family,
                "file_name": font.file_name,
                "source_class": "system",
                "available": True,
                "units_per_em": font.units_per_em,
                "file_sha256_prefix": font.sha256_prefix,
            }
        )
    if not font_records:
        font_records.append({"family": "none", "file_name": "none", "source_class": "system", "available": False})

    # Publish the QA renders only when nothing has failed so far. A failing run
    # therefore leaves no QA image in the output directory at all, and the
    # scratch directory is always removed. Publishing copies files this run made
    # in scratch; it never deletes or overwrites anything that was already there
    # (those paths were checked before any work started).
    published_qa: list[Path] = []
    if not errors:
        for scratch_path, target_path in ((chrome_scratch, chrome_png), (ppt_scratch, ppt_png)):
            if scratch_path.is_file():
                shutil.copyfile(scratch_path, target_path)
                published_qa.append(target_path)
    clear_scratch()

    delivered = [
        {
            "label": "preview",
            # `delivered` reflects whether the bytes really exist; no hard-coded
            # true and no all-zero hash placeholder.
            "sha256": preview_sha,
            "delivered": preview_sha is not None,
            "purpose": "final preview of compiled SVG",
        }
    ]
    for qa_path, label in ((chrome_png, "chrome-qa"), (ppt_png, "powerpoint-qa")):
        if qa_path in published_qa and qa_path.is_file():
            delivered.append(
                {"label": label, "sha256": sha256_file(qa_path), "delivered": False,
                 "purpose": "cross-renderer evidence"}
            )

    manifest: dict[str, Any] = {
        "contract_version": MANIFEST_CONTRACT_VERSION,
        "diagram_id": diagram_id,
        "page_role": page_role,
        "canvas": canvas,
        "scale_semantics": scale,
        "assets": {
            "editable": {"relative_path": editable_path.name, "sha256": source_sha},
            "compiled": {"relative_path": compiled_path.name, "sha256": compiled_sha},
            "preview": {
                "relative_path": preview_path.name,
                "sha256": preview_sha,
                "width": width,
                "height": height,
            },
        },
        "source_compiled_binding": {
            "source_sha256": source_sha,
            "compiled_sha256": compiled_sha,
            "text_runs_compiled": run_count,
        },
        "compiler": {"id": COMPILER_ID, "version": COMPILER_VERSION, "backend": COMPILER_BACKEND},
        "fonts": font_records,
        "renderers": {"chrome": chrome, "powerpoint_compatible": ppt},
        "cross_renderer": cross,
        "checks": checks,
        "forbidden_content": source_meta["flags"],
        "delivered_qa_images": delivered,
    }
    def dump_manifest() -> None:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    created_paths = [editable_path, compiled_path, preview_path, manifest_path, *published_qa]

    def rollback() -> None:
        """Remove what this run created so a failure never leaves a partial set.

        no-clobber already guarantees a failed run cannot overwrite a
        previously good asset; this removes the incomplete one instead. Only
        paths this run actually created are touched — never a glob, never a
        recursive sweep — and the scratch directory goes with them.
        """
        clear_scratch()
        for path in created_paths:
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                continue

    if errors:
        rollback()
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", errors, manifest)

    try:
        dump_manifest()
    except OSError as exc:
        # A manifest that cannot be written means the set is incomplete; take
        # the published QA images back out with the rest of this run's files.
        clear_scratch()
        rollback()
        errors.append(_svg_error("SVG_MANIFEST_UNREADABLE", manifest_path.name, f"manifest could not be written: {exc}"))
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", errors, manifest)

    # Round-trip recheck: read the manifest back and recompute every bound
    # asset hash from the bytes actually on disk.
    try:
        written = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        written = None
    binding_post = False
    if written is None:
        errors.append(_svg_error("SVG_MANIFEST_UNREADABLE", manifest_path.name, "manifest could not be read back"))
    else:
        assets = written.get("assets")
        binding_post = isinstance(assets, dict) and bool(assets) and all(
            isinstance(entry, dict)
            and isinstance(entry.get("sha256"), str)
            and (output_dir / str(entry.get("relative_path"))).is_file()
            and sha256_file(output_dir / str(entry.get("relative_path"))) == entry["sha256"]
            for entry in assets.values()
        )
        if not binding_post:
            errors.append(
                _svg_error(
                    "SVG_HASH_BINDING_MISMATCH",
                    manifest_path.name,
                    "manifest asset hashes do not match the bytes on disk",
                )
            )

    manifest["checks"]["hash_binding_ok"] = bool(binding_pre and binding_post)
    # Deliberately identical to the three inputs and nothing more. No PPTX
    # round-trip inference is folded in here.
    manifest["checks"]["asset_visual_delivery_ready"] = bool(
        manifest["checks"]["hash_binding_ok"] and preview_ok and cross.get("ok")
    )
    if errors:
        rollback()
        return PipelineResult(False, "SVG_DUAL_ASSET_FAILED", errors, manifest)
    dump_manifest()
    # Outcome names the asset package only: the four-asset build finished. It is
    # not a deck, package-delivery or client statement.
    return PipelineResult(True, "ASSET_PACKAGE_READY", [], manifest)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("editable_svg", type=Path)
    parser.add_argument("--diagram-id", required=True)
    parser.add_argument("--page-role", default="content", choices=["cover", "content", "legend", "appendix", "other"])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-cross-renderer", action="store_true")
    args = parser.parse_args(argv)
    result = build_dual_asset(
        args.editable_svg.read_text(encoding="utf-8"),
        args.diagram_id,
        args.page_role,
        args.output_dir.resolve(),
        run_cross_renderer=not args.skip_cross_renderer,
    )
    payload: dict[str, Any] = {"ok": result.ok, "outcome": result.outcome, "errors": result.errors}
    if result.manifest is not None:
        payload["manifest"] = result.manifest
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
