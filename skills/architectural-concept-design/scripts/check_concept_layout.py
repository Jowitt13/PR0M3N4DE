"""Read-only checks of ordinary rectangular D1 SVG drafts, never a designer.

Reuse the teaching builder's pure rectangle predicates without manufacturing
its human-authored input chain. No search, rendering, network, clock or writes.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import xml.etree.ElementTree as ET

from build_student_schematic_plan_blocks import _rectangles_overlap, _share_positive_boundary
from check_area_schedule import calculate_area_schedule

LIMITATIONS = (
    "Rectangular working blocks only; SVG coordinates increase downwards. "
    "A shared edge is not a door, accessible route or evacuation proof. "
    "This checker is not a renderer and does not certify that paint, colors or labels are visible. "
    "Labels, architectural quality, site permission, performance and external edits "
    "are not certified. This is not the formal human-authored teaching chain."
)
SVG = "{http://www.w3.org/2000/svg}"
FIELDS = ("x", "y", "width", "height")
Rect = tuple[Decimal, Decimal, Decimal, Decimal]


def _number(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean geometry")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("numeric geometry required") from error
    # Keep exact arithmetic and finite JSON outputs bounded, including hostile exponents.
    if not number.is_finite() or abs(number) > Decimal("1000000000") or (number != 0 and float(number) == 0):
        raise ValueError("geometry must be finite and within 1e9 metres")
    return number


def _read_svg(source: str) -> dict[str, tuple[str, str, Rect]]:
    if "<!DOCTYPE" in source.upper() or "<!ENTITY" in source.upper():
        raise ValueError("DTD and entity declarations are unsupported")
    if re.search(r"<\?(?!xml\s)", source, re.I):
        raise ValueError("processing instructions other than the XML declaration are unsupported")
    root = ET.fromstring(source)
    if root.tag != SVG + "svg" or root.get("data-unit") != "m":
        raise ValueError("SVG namespace and explicit data-unit=m required")
    ids: set[str] = set()
    blocks: dict[str, tuple[str, str, Rect]] = {}
    for element in root.iter():
        tag = element.tag.removeprefix(SVG)
        if tag in {"defs", "symbol", "clipPath", "mask", "marker", "pattern", "switch"} or (
            tag == "svg" and element is not root
        ):
            raise ValueError("non-rendered or nested SVG containers are unsupported")
        if tag in {"script", "foreignObject", "image", "use", "style", "animate", "set", "animateTransform", "animateMotion"}:
            raise ValueError("active, external or indirect SVG content is unsupported")
        for key, value in element.attrib.items():
            if re.search(r"url\s*\(", value, re.I):
                raise ValueError("indirect paint or CSS references are unsupported")
            if key.lower() in {"display", "visibility", "opacity"}:
                raise ValueError("visibility and opacity overrides are unsupported")
            if key.lower().startswith("on") or key.endswith("href") or key == "transform":
                raise ValueError("event, link and transform attributes are unsupported")
            if key == "style":
                if "/*" in value or "*/" in value or "\\" in value:
                    raise ValueError("CSS comments and escapes are unsupported")
                if re.search(r"(?:^|;)\s*(?:transform|x|y|width|height|rx|ry|display|visibility|opacity)\s*:", value, re.I):
                    raise ValueError("CSS geometry and visibility overrides are unsupported")
        identifier = element.get("id")
        if identifier:
            if identifier in ids:
                raise ValueError("duplicate SVG id")
            ids.add(identifier)
        role = element.get("data-role")
        if role is None:
            if identifier and identifier.startswith("S-"):
                raise ValueError("space id missing its explicit role")
            continue
        if role not in {"space", "circulation", "decoration"}:
            raise ValueError("unsupported block role")
        if role == "decoration":
            continue
        if element.tag != SVG + "rect" or not identifier:
            raise ValueError("checked blocks must be identified rect elements")
        title = element.find(SVG + "title")
        name = "" if title is None else "".join(title.itertext()).strip()
        if not name:
            raise ValueError("checked blocks require a title")
        rect: Rect = tuple(_number(element.get(key, "0" if key in {"x", "y"} else None)) for key in FIELDS)  # type: ignore[assignment]
        if rect[2] <= 0 or rect[3] <= 0:
            raise ValueError("positive rectangle dimensions required")
        if any(element.get(key, "0") != "0" for key in ("rx", "ry")):
            raise ValueError("rounded blocks are outside rectangular checks")
        blocks[identifier] = (role, name, rect)
    return blocks


def check_layout(
    svg_source: str,
    *,
    container: tuple[float, float],
    required_spaces: Sequence[str],
    adjacent_pairs: Sequence[tuple[str, str]] = (),
    previous_svg: str | None = None,
    locked: Mapping[str, Sequence[str]] | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Check the supplied SVG against independent dimensions, space IDs and locks.

    Width/depth and required IDs come from the actual brief, not from a candidate
    rewriting its own requirements. Lock fields are x/y/width/height in SVG user
    coordinates. Missing or unsupported inputs fail closed, with no output files.
    """
    errors: list[dict[str, str]] = []

    def reject(code: str, subject: str = "") -> None:
        errors.append({"code": code, "subject": subject})

    result: dict[str, Any] = {
        "ok": False, "errors": errors, "limitations": LIMITATIONS,
        "source_sha256": hashlib.sha256(svg_source.encode("utf-8")).hexdigest(),
    }
    if expected_sha256 is not None and expected_sha256 != result["source_sha256"]:
        reject("CONCEPT_LAYOUT_SOURCE_CHANGED")
    try:
        width, depth = (_number(value) for value in container)
        if width <= 0 or depth <= 0 or not required_spaces or len(set(required_spaces)) != len(required_spaces):
            raise ValueError("positive brief bounds and distinct required IDs required")
        if any(not re.fullmatch(r"S-[0-9]{3,}", name) for name in required_spaces):
            raise ValueError("use existing stable S-xxx space identifiers")
        blocks = _read_svg(svg_source)
        root = ET.fromstring(svg_source)
        viewbox = tuple(_number(v) for v in re.split(r"[\s,]+", root.get("viewBox", "").strip()))
        if viewbox != (Decimal(0), Decimal(0), width, depth):
            raise ValueError("viewBox does not match independent brief bounds")
    except (ValueError, InvalidOperation, ET.ParseError, TypeError):
        reject("CONCEPT_LAYOUT_GEOMETRY_INVALID")
        return result

    spaces = {key: value for key, value in blocks.items() if value[0] == "space"}
    traffic = {key: value for key, value in blocks.items() if value[0] == "circulation"}
    for identifier in required_spaces:
        if identifier not in spaces:
            reject("CONCEPT_LAYOUT_SPACE_MISSING", identifier)
    if not traffic:
        reject("CONCEPT_LAYOUT_TRAFFIC_MISSING")
    for identifier, (_, _, (x, y, w, h)) in blocks.items():
        if x < 0 or y < 0 or x + w > width or y + h > depth:
            reject("CONCEPT_LAYOUT_OUT_OF_BOUNDS", identifier)
    contacts: list[list[str]] = []
    for index, (first_id, (_, _, first)) in enumerate(blocks.items()):
        for second_id, (_, _, second) in list(blocks.items())[index + 1:]:
            if _rectangles_overlap(first, second):
                reject("CONCEPT_LAYOUT_OVERLAP", first_id + ":" + second_id)
            if _share_positive_boundary(first, second):
                contacts.append([first_id, second_id])
    for identifier, (_, _, rect) in spaces.items():
        if not any(_share_positive_boundary(rect, other[2]) for other in traffic.values()):
            reject("CONCEPT_LAYOUT_TRAFFIC_CONTACT_MISSING", identifier)
    for first, second in adjacent_pairs:
        if first not in blocks or second not in blocks or not _share_positive_boundary(blocks[first][2], blocks[second][2]):
            reject("CONCEPT_LAYOUT_ADJACENCY_MISSING", first + ":" + second)

    if locked:
        try:
            if previous_svg is None:
                raise ValueError("locks require a previous source")
            previous = _read_svg(previous_svg)
            for identifier, fields in locked.items():
                if identifier not in previous or identifier not in blocks or not fields:
                    raise ValueError("locked space is missing")
                for field in fields:
                    if field not in FIELDS:
                        raise ValueError("unknown lock field")
                    if previous[identifier][2][FIELDS.index(field)] != blocks[identifier][2][FIELDS.index(field)]:
                        reject("CONCEPT_LAYOUT_LOCK_CHANGED", identifier + ":" + field)
        except (ValueError, InvalidOperation, ET.ParseError, TypeError):
            reject("CONCEPT_LAYOUT_LOCK_INVALID")

    space_area = sum((r[2][2] * r[2][3] for r in spaces.values()), Decimal(0))
    traffic_area = sum((r[2][2] * r[2][3] for r in traffic.values()), Decimal(0))
    result.update({
        "space_area_m2": float(space_area), "circulation_area_m2": float(traffic_area),
        "unassigned_area_m2": float(width * depth - space_area - traffic_area),
        "blocks": {key: {"role": role, "name": name, **{k: float(v) for k, v in zip(FIELDS, rect)}, "area_m2": float(rect[2] * rect[3])} for key, (role, name, rect) in blocks.items()},
        "shared_boundaries": contacts,
    })
    try:
        result["area_schedule"] = calculate_area_schedule({"spaces": [
            {"id": key, "name": value[1], "area": {"value": str(value[2][2] * value[2][3]), "unit": "m2"}}
            for key, value in spaces.items()
        ]})
    except ValueError:
        reject("CONCEPT_LAYOUT_GEOMETRY_INVALID")
    result["ok"] = not errors
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Read one SVG and print a deterministic check; never modify project files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--width", type=float, required=True)
    parser.add_argument("--depth", type=float, required=True)
    parser.add_argument("--required", required=True, help="Comma-separated brief S-xxx identifiers")
    parser.add_argument("--expect-sha256")
    args = parser.parse_args(argv)
    try:
        result = check_layout(args.svg.read_bytes().decode("utf-8"), container=(args.width, args.depth), required_spaces=args.required.split(","), expected_sha256=args.expect_sha256)
    except (OSError, UnicodeError):
        result = {"ok": False, "errors": [{"code": "CONCEPT_LAYOUT_SOURCE_UNREADABLE"}], "limitations": LIMITATIONS}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
