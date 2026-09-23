"""Compile SVG <text> into TrueType glyph outline paths (stdlib only)."""

from __future__ import annotations

import hashlib
import struct
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SVG_NS = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", SVG_NS)

COMPILER_ID = "svg_text_to_path"
COMPILER_VERSION = "1.4.0"
COMPILER_BACKEND = "pure_python_truetype_glyf"

# Orientation contract (ARCH-126 R1-D): outlines are parsed and composed in
# font units with Y up, and converted to SVG's Y-down user space exactly once,
# during path serialization. The per-glyph transform must therefore keep both
# scale factors positive; a negative Y scale here flips every glyph a second
# time and mirrors cap-height ink below its baseline.
_MAX_COMPOSITE_DEPTH = 8
_F2DOT14 = 16384.0
_COMPONENT_ARG_WORDS = 0x0001
_COMPONENT_ARGS_XY = 0x0002
_COMPONENT_SCALE = 0x0008
_COMPONENT_MORE = 0x0020
_COMPONENT_XY_SCALE = 0x0040
_COMPONENT_2x2 = 0x0080
_COMPONENT_SCALED_OFFSET = 0x0800
_COMPONENT_UNSCALED_OFFSET = 0x1000

# Missing-glyph contract (ARCH-126 R1-D R2): a font that cannot cover every
# visible character must fail the whole compilation with a stable code instead
# of emitting an empty run. Coverage is decided only by the font's own cmap
# result (glyph id 0 == .notdef), never by hard-coding font names, script
# ranges, or per-character allow lists, and never by silently stitching an
# uncertain system fallback onto the stack.

# Common system fonts. Files are read from disk and never packaged.
_SYSTEM_FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "microsoft yahei": ("msyh.ttc", "msyh.ttf", "msyhl.ttc", "NotoSansCJK-Regular.ttc", "NotoSansSC-Regular.otf", "wqy-microhei.ttc", "DroidSansFallbackFull.ttf"),
    "microsoft yahei ui": ("msyh.ttc", "msyh.ttf"),
    "segoe ui": ("segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"),
    "arial": ("arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf", "FreeSans.ttf"),
    "calibri": ("calibri.ttf", "Carlito-Regular.ttf", "LiberationSans-Regular.ttf"),
    "simhei": ("simhei.ttf", "NotoSansCJK-Regular.ttc", "wqy-microhei.ttc"),
    "simsun": ("simsun.ttc", "simsun.ttf", "NotoSansCJK-Regular.ttc"),
    "sans-serif": ("DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf", "segoeui.ttf", "arial.ttf"),
    "serif": ("DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", "FreeSerif.ttf"),
    "monospace": ("DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "FreeMono.ttf"),
}

_FONT_SEARCH_DIRS = (
    Path(r"C:\Windows\Fonts"),
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
    Path("/usr/share/fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/freefont"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/wqy"),
    Path("/usr/local/share/fonts"),
)


class TextToPathError(Exception):
    """Raised when glyph compilation cannot proceed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _read_i16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]


def _read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _read_tag(data: bytes, offset: int) -> str:
    return data[offset : offset + 4].decode("ascii", errors="replace")


@dataclass(frozen=True)
class FontRecord:
    family: str
    file_name: str
    path: Path
    face_index: int
    units_per_em: int
    sha256_prefix: str
    available: bool


class TrueTypeFont:
    """Minimal TrueType/TTC glyf outline reader."""

    def __init__(self, path: Path, face_index: int = 0) -> None:
        self.path = path
        self.face_index = face_index
        self.data = path.read_bytes()
        self.tables = self._parse_tables(self.data, face_index)
        if "glyf" not in self.tables or "loca" not in self.tables:
            # Separate "the file is not a usable font" from "the file is a real
            # font whose outline format this reader does not implement".
            # OpenType CFF and CFF2 are legitimate outline formats; the pure
            # stdlib reader only implements TrueType glyf/loca, so a CFF font
            # must be reported as an unsupported format rather than silently
            # dropped, reported as missing, or rendered as an empty path.
            if "CFF " in self.tables or "CFF2" in self.tables:
                raise TextToPathError(
                    "SVG_FONT_FORMAT_UNSUPPORTED",
                    f"font {path.name} carries CFF/CFF2 outlines; "
                    "this reader supports TrueType glyf/loca outlines only",
                )
            raise TextToPathError("SVG_FONT_UNAVAILABLE", f"font {path.name} lacks glyf/loca")
        if "cmap" not in self.tables:
            raise TextToPathError("SVG_FONT_UNAVAILABLE", f"font {path.name} lacks cmap")
        head = self.tables["head"][0]
        self.units_per_em = _read_u16(self.data, head + 18)
        self._hhea_num = _read_u16(self.data, self.tables["hhea"][0] + 34)

    @staticmethod
    def _parse_tables(data: bytes, face_index: int) -> dict[str, tuple[int, int]]:
        if data[:4] == b"ttcf":
            num_fonts = _read_u32(data, 8)
            if face_index >= num_fonts:
                raise TextToPathError("SVG_FONT_UNAVAILABLE", "face index out of range")
            offset = _read_u32(data, 12 + face_index * 4)
        else:
            offset = 0
        num_tables = _read_u16(data, offset + 4)
        tables: dict[str, tuple[int, int]] = {}
        for index in range(num_tables):
            record = offset + 12 + index * 16
            tag = _read_tag(data, record)
            tables[tag] = (_read_u32(data, record + 8), _read_u32(data, record + 12))
        return tables

    def glyph_id(self, character: int) -> int:
        toff, _ = self.tables["cmap"]
        count = _read_u16(self.data, toff + 2)
        best: int | None = None
        for index in range(count):
            record = toff + 4 + index * 8
            platform = _read_u16(self.data, record)
            encoding = _read_u16(self.data, record + 2)
            subtable = _read_u32(self.data, record + 4)
            fmt = _read_u16(self.data, toff + subtable)
            if platform == 3 and encoding == 1 and fmt == 4:
                best = toff + subtable
                break
            if platform == 0 and fmt == 4 and best is None:
                best = toff + subtable
        if best is None:
            raise TextToPathError("SVG_FONT_UNAVAILABLE", "no usable cmap subtable")
        if _read_u16(self.data, best) != 4:
            raise TextToPathError("SVG_FONT_UNAVAILABLE", "unsupported cmap format")
        seg_x2 = _read_u16(self.data, best + 6)
        segments = seg_x2 // 2
        end_o = best + 14
        start_o = end_o + seg_x2 + 2
        delta_o = start_o + seg_x2
        range_o = delta_o + seg_x2
        for index in range(segments):
            end = _read_u16(self.data, end_o + index * 2)
            if character <= end:
                start = _read_u16(self.data, start_o + index * 2)
                if character < start:
                    return 0
                delta = _read_i16(self.data, delta_o + index * 2)
                range_offset = _read_u16(self.data, range_o + index * 2)
                if range_offset == 0:
                    return (character + delta) & 0xFFFF
                glyph = _read_u16(self.data, range_o + index * 2 + range_offset + (character - start) * 2)
                return 0 if glyph == 0 else (glyph + delta) & 0xFFFF
        return 0

    def advance_width(self, glyph_id: int) -> int:
        hmtx = self.tables["hmtx"][0]
        if glyph_id < self._hhea_num:
            return _read_u16(self.data, hmtx + glyph_id * 4)
        return _read_u16(self.data, hmtx + (self._hhea_num - 1) * 4)

    def _glyph_range(self, glyph_id: int) -> tuple[int, int] | None:
        head = self.tables["head"][0]
        loca_format = _read_i16(self.data, head + 50)
        maxp = self.tables["maxp"][0]
        num_glyphs = _read_u16(self.data, maxp + 4)
        if glyph_id >= num_glyphs:
            return None
        loca = self.tables["loca"][0]
        if loca_format == 0:
            start = _read_u16(self.data, loca + glyph_id * 2) * 2
            end = _read_u16(self.data, loca + (glyph_id + 1) * 2) * 2
        else:
            start = _read_u32(self.data, loca + glyph_id * 4)
            end = _read_u32(self.data, loca + (glyph_id + 1) * 4)
        if start == end:
            return None
        return start, end

    def glyph_contours(self, glyph_id: int, depth: int = 0) -> list[list[tuple[int, int, int]]]:
        """Return raw font-space (Y-up) contours as (x, y, flag) triples.

        Composite glyphs (numberOfContours == -1) are resolved recursively
        from their components with TrueType placement transforms applied.
        """
        glyph_range = self._glyph_range(glyph_id)
        if glyph_range is None:
            return []
        go = self.tables["glyf"][0] + glyph_range[0]
        contour_count = _read_i16(self.data, go)
        if contour_count >= 0:
            return self._simple_glyph_contours(go, contour_count)
        if depth >= _MAX_COMPOSITE_DEPTH:
            raise TextToPathError("SVG_GLYPH_UNSUPPORTED", "composite glyph nesting is too deep")
        return self._composite_glyph_contours(go, depth)

    def _simple_glyph_contours(self, go: int, contour_count: int) -> list[list[tuple[int, int, int]]]:
        if contour_count <= 0:
            return []
        pointer = go + 10
        end_points = [_read_u16(self.data, pointer + i * 2) for i in range(contour_count)]
        pointer = go + 10 + contour_count * 2
        instruction_length = _read_u16(self.data, pointer)
        pointer += 2 + instruction_length
        point_count = end_points[-1] + 1
        flags: list[int] = []
        while len(flags) < point_count:
            flag = self.data[pointer]
            pointer += 1
            flags.append(flag)
            if flag & 8:
                repeat = self.data[pointer]
                pointer += 1
                flags.extend([flag] * repeat)
        xs: list[int] = []
        x = 0
        for flag in flags:
            if flag & 2:
                delta = self.data[pointer]
                pointer += 1
                x += delta if (flag & 16) else -delta
            elif not (flag & 16):
                x += _read_i16(self.data, pointer)
                pointer += 2
            xs.append(x)
        ys: list[int] = []
        y = 0
        for flag in flags:
            if flag & 4:
                delta = self.data[pointer]
                pointer += 1
                y += delta if (flag & 32) else -delta
            elif not (flag & 32):
                y += _read_i16(self.data, pointer)
                pointer += 2
            ys.append(y)
        contours: list[list[tuple[int, int, int]]] = []
        start_index = 0
        for end_index in end_points:
            points = list(zip(xs[start_index : end_index + 1], ys[start_index : end_index + 1], flags[start_index : end_index + 1]))
            start_index = end_index + 1
            if not points:
                continue
            on_index = next((i for i, item in enumerate(points) if item[2] & 1), None)
            if on_index is None:
                continue
            contours.append(points[on_index:] + points[:on_index])
        return contours

    def _composite_glyph_contours(self, go: int, depth: int) -> list[list[tuple[int, int, int]]]:
        contours: list[list[tuple[int, int, int]]] = []
        pointer = go + 10
        components = 0
        while True:
            components += 1
            if components > 64:
                raise TextToPathError("SVG_GLYPH_UNSUPPORTED", "composite glyph has too many components")
            flags = _read_u16(self.data, pointer)
            component_id = _read_u16(self.data, pointer + 2)
            pointer += 4
            if flags & _COMPONENT_ARG_WORDS:
                arg1 = _read_i16(self.data, pointer)
                arg2 = _read_i16(self.data, pointer + 2)
                pointer += 4
            else:
                arg1 = struct.unpack_from(">b", self.data, pointer)[0]
                arg2 = struct.unpack_from(">b", self.data, pointer + 1)[0]
                pointer += 2
            # OpenType stores a 2x2 as (xscale, scale01, scale10, yscale) in
            # that byte order and applies it as
            #   x' = xscale*x + scale10*y + dx
            #   y' = scale01*x + yscale*y + dy
            # so the (a, b, c, d) read order maps to
            #   a=xscale, b=scale01, c=scale10, d=yscale.
            a, b, c, d = 1.0, 0.0, 0.0, 1.0
            if flags & _COMPONENT_2x2:
                a = _read_i16(self.data, pointer) / _F2DOT14
                b = _read_i16(self.data, pointer + 2) / _F2DOT14
                c = _read_i16(self.data, pointer + 4) / _F2DOT14
                d = _read_i16(self.data, pointer + 6) / _F2DOT14
                pointer += 8
            elif flags & _COMPONENT_XY_SCALE:
                a = _read_i16(self.data, pointer) / _F2DOT14
                d = _read_i16(self.data, pointer + 2) / _F2DOT14
                pointer += 4
            elif flags & _COMPONENT_SCALE:
                a = d = _read_i16(self.data, pointer) / _F2DOT14
                pointer += 2
            if not (flags & _COMPONENT_ARGS_XY):
                # Point-matching placement depends on hinted outlines; without
                # it the glyph would land in the wrong place. Fail closed.
                raise TextToPathError(
                    "SVG_GLYPH_UNSUPPORTED",
                    "composite glyph uses point-matching placement, which is not supported",
                )
            # Component offset semantics: SCALED_COMPONENT_OFFSET means the
            # offset must be transformed by the 2x2 matrix before it is added;
            # UNSCALED_COMPONENT_OFFSET (and the default when neither flag is
            # set) means the offset is added as-is. Setting both is
            # contradictory, so it fails closed instead of guessing.
            dx, dy = float(arg1), float(arg2)
            scaled = bool(flags & _COMPONENT_SCALED_OFFSET)
            unscaled = bool(flags & _COMPONENT_UNSCALED_OFFSET)
            if scaled and unscaled:
                raise TextToPathError(
                    "SVG_GLYPH_UNSUPPORTED",
                    "composite glyph sets both SCALED_COMPONENT_OFFSET and UNSCALED_COMPONENT_OFFSET",
                )
            if scaled:
                dx, dy = a * dx + c * dy, b * dx + d * dy
            for contour in self.glyph_contours(component_id, depth + 1):
                contours.append(
                    [(a * px + c * py + dx, b * px + d * py + dy, flag) for px, py, flag in contour]
                )
            if not (flags & _COMPONENT_MORE):
                return contours

    @staticmethod
    def _contours_to_path(contours: list[list[tuple[int, int, int]]]) -> str:
        """Serialize font-space contours to an SVG path, converting Y-up to
        Y-down exactly once (the single legitimate Y flip in the pipeline)."""
        parts: list[str] = []
        for points in contours:
            if not points:
                continue

            def point_at(index: int) -> tuple[int, int, int]:
                return points[index % len(points)]

            parts.append(f"M{points[0][0]:.1f},{-points[0][1]:.1f}")
            index = 1
            while index <= len(points):
                current = point_at(index)
                if current[2] & 1:
                    parts.append(f"L{current[0]:.1f},{-current[1]:.1f}")
                    index += 1
                else:
                    nxt = point_at(index + 1)
                    if nxt[2] & 1:
                        parts.append(f"Q{current[0]:.1f},{-current[1]:.1f} {nxt[0]:.1f},{-nxt[1]:.1f}")
                        index += 2
                    else:
                        mid_x = (current[0] + nxt[0]) / 2
                        mid_y = (current[1] + nxt[1]) / 2
                        parts.append(f"Q{current[0]:.1f},{-current[1]:.1f} {mid_x:.1f},{-mid_y:.1f}")
                        index += 1
            parts.append("Z")
        return "".join(parts)

    def glyph_path(self, glyph_id: int) -> str:
        return self._contours_to_path(self.glyph_contours(glyph_id))


def resolve_system_font_ex(family: str) -> tuple[FontRecord | None, str | None]:
    """Resolve one family, reporting an unsupported outline format separately.

    Returns ``(record, unsupported_note)``. A CFF/CFF2 file is a real font this
    reader cannot use; reporting that as "no font installed" or as a missing
    glyph would be a wrong diagnosis, so the fact is carried out separately.
    """
    normalized = family.strip().strip("'\"").lower()
    candidates = _SYSTEM_FONT_CANDIDATES.get(normalized, ())
    if not candidates:
        compact = normalized.replace(" ", "")
        candidates = (f"{compact}.ttf", f"{compact}.ttc", f"{normalized}.ttf", f"{compact}.otf")
    search_dirs: list[Path] = []
    for directory in _FONT_SEARCH_DIRS:
        if directory.is_dir():
            search_dirs.append(directory)
    # One-level subdirectory scan covers common Linux layouts.
    for directory in list(search_dirs):
        try:
            for child in directory.iterdir():
                if child.is_dir() and child not in search_dirs:
                    search_dirs.append(child)
        except OSError:
            continue
    unsupported: str | None = None
    for directory in search_dirs:
        for name in candidates:
            path = directory / name
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
                font = TrueTypeFont(path, 0)
            except TextToPathError as error:
                if error.code == "SVG_FONT_FORMAT_UNSUPPORTED":
                    unsupported = unsupported or f"{family.strip()}({name})"
                continue
            except OSError:
                continue
            digest = hashlib.sha256(data).hexdigest()
            return (
                FontRecord(
                    family=family.strip().strip("'\""),
                    file_name=name,
                    path=path,
                    face_index=0,
                    units_per_em=font.units_per_em,
                    sha256_prefix=digest[:16],
                    available=True,
                ),
                None,
            )
    return None, unsupported


def resolve_system_font(family: str) -> FontRecord | None:
    record, _unsupported = resolve_system_font_ex(family)
    return record


def font_available(family: str) -> bool:
    return resolve_system_font(family) is not None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _font_families_from_text(element: ElementTree.Element) -> list[str]:
    raw = (element.get("font-family") or "").strip()
    if not raw:
        raise TextToPathError("SVG_FONT_UNDECLARED", "text element missing font-family")
    families = [part.strip().strip("'\"") for part in raw.split(",")]
    families = [part for part in families if part]
    if not families:
        raise TextToPathError("SVG_FONT_UNDECLARED", "text element font-family empty")
    return families


def required_glyph_id(font: TrueTypeFont, character: str, family_label: str) -> int:
    """Resolve one character's glyph id, failing closed when the font lacks it.

    Coverage is decided only by the font's own cmap: glyph id 0 is .notdef.
    No font name, script range, or character list is hard-coded here, and no
    system fallback is stitched on silently — a font that cannot cover the
    text must fail so the caller supplies a font that can.
    """
    glyph_id = font.glyph_id(ord(character))
    if glyph_id == 0:
        raise TextToPathError(
            "SVG_GLYPH_MISSING",
            f"font {family_label} has no glyph for U+{ord(character):04X}; "
            "provide a font that covers every visible character of this text run",
        )
    return glyph_id


def compile_text_elements(
    svg_source: str,
    *,
    font_cache: dict[str, tuple[TrueTypeFont, FontRecord]] | None = None,
) -> tuple[str, list[FontRecord], int]:
    """Replace every <text>/<tspan> with glyph <path> groups.

    Returns (compiled_svg, font_records, compiled_run_count).
    """
    cache = font_cache if font_cache is not None else {}
    try:
        root = ElementTree.fromstring(svg_source)
    except ElementTree.ParseError as error:
        raise TextToPathError("SVG_SOURCE_INVALID", f"SVG parse error: {error}") from error
    if _local(root.tag) != "svg":
        raise TextToPathError("SVG_SOURCE_INVALID", "root element is not svg")

    fonts_used: dict[str, FontRecord] = {}
    compiled_runs = 0

    def load_font_stack(families: list[str], content: str) -> tuple[TrueTypeFont, str]:
        """Pick the first font *declared in the stack* that covers the text.

        Choosing among the families the author declared is expected behaviour;
        silently appending some other system font that happens to exist is not,
        so no font outside the declared stack is ever considered. When no
        declared family covers every visible character the run fails closed
        with SVG_GLYPH_MISSING instead of emitting a partially rendered glyph
        set or an empty group.
        """
        tried: list[str] = []
        resolvable = False
        first_uncovered: str | None = None
        format_unsupported: list[str] = []
        for family in families:
            key = family.strip().lower()
            cached = cache.get(key)
            if cached is not None:
                font, record = cached
            else:
                record, unsupported = resolve_system_font_ex(family)
                if unsupported:
                    format_unsupported.append(unsupported)
                if record is None or not record.available:
                    tried.append(family)
                    continue
                font = TrueTypeFont(record.path, record.face_index)
                cache[key] = (font, record)
            resolvable = True
            missing = next(
                (character for character in content if not character.isspace() and font.glyph_id(ord(character)) == 0),
                None,
            )
            if missing is None:
                fonts_used[record.family] = record
                return font, record.family
            if first_uncovered is None:
                first_uncovered = missing
            tried.append(f"{family}(missing U+{ord(missing):04X})")
        # A declared CFF/CFF2 candidate is a real font this reader does not
        # implement. That fact must survive to the caller: reporting "no font
        # installed" or "missing glyph" would both be wrong diagnoses, and it
        # outranks them because the caller's fix is different.
        if format_unsupported:
            raise TextToPathError(
                "SVG_FONT_FORMAT_UNSUPPORTED",
                f"no usable TrueType glyf/loca font in the declared stack "
                f"(unsupported outline formats: {', '.join(format_unsupported)}; "
                f"stack: {', '.join(families)})",
            )
        if not resolvable:
            # No declared family could even be opened; that is a font
            # availability failure, not a coverage failure.
            raise TextToPathError(
                "SVG_FONT_UNAVAILABLE",
                f"no font from stack available: {', '.join(families)}",
            )
        uncovered = first_uncovered or next(
            (character for character in content if not character.isspace()), ""
        )
        raise TextToPathError(
            "SVG_GLYPH_MISSING",
            f"no font in the declared stack covers every visible character "
            f"(stack: {', '.join(families)}; uncovered: U+{ord(uncovered):04X}); "
            "provide a font that covers the full character set",
        )

    def text_element_to_paths(element: ElementTree.Element) -> list[ElementTree.Element]:
        nonlocal compiled_runs
        families = _font_families_from_text(element)
        content = "".join(element.itertext())
        font, font_label = load_font_stack(families, content)
        size_raw = element.get("font-size") or "16"
        try:
            size = float(size_raw)
        except ValueError as error:
            raise TextToPathError("SVG_SOURCE_INVALID", f"invalid font-size: {size_raw}") from error
        if size <= 0:
            raise TextToPathError("SVG_SOURCE_INVALID", "non-positive font-size")
        fill = element.get("fill") or "#000000"
        x_raw = element.get("x") or "0"
        y_raw = element.get("y") or "0"
        try:
            x = float(x_raw)
            y = float(y_raw)
        except ValueError as error:
            raise TextToPathError("SVG_SOURCE_INVALID", f"invalid text coordinates: {x_raw},{y_raw}") from error
        anchor = element.get("text-anchor") or "start"
        scale = size / font.units_per_em
        advances: list[float] = []
        outlines: list[str] = []
        pen = 0.0
        for character in content:
            if character.isspace():
                space_adv = size * 0.35
                advances.append(space_adv)
                pen += space_adv
                continue
            glyph_id = required_glyph_id(font, character, font_label)
            outline = font.glyph_path(glyph_id)
            advance = font.advance_width(glyph_id) * scale
            advances.append(advance)
            if outline:
                outlines.append(outline)
            pen += advance
        total_width = pen
        origin_x = x
        if anchor == "middle":
            origin_x = x - total_width / 2
        elif anchor == "end":
            origin_x = x - total_width
        group = ElementTree.Element(f"{{{SVG_NS}}}g")
        group.set("data-svg-text-run", "1")
        group.set("font-size", f"{size:g}")
        pen = origin_x
        for character in content:
            if character.isspace():
                pen += size * 0.35
                continue
            glyph_id = required_glyph_id(font, character, font_label)
            outline = font.glyph_path(glyph_id)
            advance = font.advance_width(glyph_id) * scale
            if outline:
                path = ElementTree.SubElement(group, f"{{{SVG_NS}}}path")
                path.set("d", outline)
                path.set("fill", fill)
                # Serialization already emitted Y-down path data; both scale
                # factors stay positive so no second Y flip can occur.
                path.set("transform", f"translate({pen:.2f},{y:.2f}) scale({scale:.6f},{scale:.6f})")
            pen += advance
        compiled_runs += 1
        return [group]

    def walk(parent: ElementTree.Element) -> None:
        replacements: list[tuple[int, list[ElementTree.Element]]] = []
        for index, child in enumerate(list(parent)):
            if _local(child.tag) in {"text", "tspan"}:
                replacements.append((index, text_element_to_paths(child)))
            else:
                walk(child)
        for index, nodes in reversed(replacements):
            parent.remove(list(parent)[index])
            for offset, node in enumerate(nodes):
                parent.insert(index + offset, node)

    walk(root)
    compiled = ElementTree.tostring(root, encoding="unicode")
    if not compiled.startswith("<?xml"):
        compiled = '<?xml version="1.0" encoding="UTF-8"?>\n' + compiled
    return compiled, list(fonts_used.values()), compiled_runs


def count_text_elements(svg_source: str) -> int:
    try:
        root = ElementTree.fromstring(svg_source)
    except ElementTree.ParseError:
        return -1
    return sum(1 for element in root.iter() if _local(element.tag) in {"text", "tspan"})


__all__ = [
    "COMPILER_BACKEND",
    "COMPILER_ID",
    "COMPILER_VERSION",
    "FontRecord",
    "TextToPathError",
    "TrueTypeFont",
    "compile_text_elements",
    "count_text_elements",
    "font_available",
    "resolve_system_font",
]
