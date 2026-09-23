"""Cross-renderer PNG evidence: Chrome headless and PowerPoint-compatible COM."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping
from struct import unpack
import zlib

DEFAULT_THRESHOLDS = {
    "max_mean_abs_diff": 18.0,
    "max_bbox_shift_ratio": 0.04,
    "min_ink_overlap_ratio": 0.86,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_chrome() -> Path | None:
    candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    return next((path for path in candidates if path.is_file()), None)


def chrome_render(svg_path: Path, png_path: Path, width: int, height: int) -> dict[str, Any]:
    chrome = find_chrome()
    if chrome is None:
        return {"available": False, "ok": False, "id": "chrome-headless", "notes": "chrome executable not found"}
    version = ""
    try:
        import ctypes

        version_size = ctypes.windll.version.GetFileVersionInfoSizeW(str(chrome), None)
        if version_size:
            data = ctypes.create_string_buffer(version_size)
            if ctypes.windll.version.GetFileVersionInfoW(str(chrome), 0, version_size, data):
                buf = ctypes.c_void_p()
                length = ctypes.c_uint()
                if ctypes.windll.version.VerQueryValueW(data, "\\", ctypes.byref(buf), ctypes.byref(length)):
                    raw = ctypes.string_at(buf.value, length.value)
                    if len(raw) >= 16:
                        ms = int.from_bytes(raw[8:12], "little")
                        ls = int.from_bytes(raw[12:16], "little")
                        version = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:
        version = ""
    command = [
        str(chrome),
        "--headless",
        "--disable-gpu",
        f"--screenshot={png_path}",
        f"--window-size={width},{height}",
        "--default-background-color=FFFFFFFF",
        svg_path.resolve().as_uri(),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": True, "ok": False, "id": "chrome-headless", "version": version, "notes": str(error)}
    ok = completed.returncode == 0 and png_path.is_file() and png_path.stat().st_size > 0
    if completed.returncode == 0 and not ok:
        # On some hosts the headless launcher forks the screenshot into a child
        # that exits later, so the PNG can land after the parent returns.
        # Waiting a bounded interval keeps the render honest instead of
        # reporting a failure for a screenshot that is still being written.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if png_path.is_file() and png_path.stat().st_size > 0:
                ok = True
                break
            time.sleep(0.25)
    result: dict[str, Any] = {"available": True, "ok": ok, "id": "chrome-headless", "version": version}
    if ok:
        result["png_sha256"] = sha256_file(png_path)
        result["width"] = width
        result["height"] = height
    else:
        result["notes"] = (completed.stderr or completed.stdout or b"").decode("utf-8", errors="replace")[:200]
    return result


def _probe_powerpoint_engine() -> str:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "try { $a=New-Object -ComObject PowerPoint.Application; Write-Output $a.Path; $a.Quit() } catch { Write-Output '' }",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    path = (completed.stdout or "").strip()
    lowered = path.lower()
    if "wps" in lowered or "kingsoft" in lowered:
        return "wps-presentation-powerpoint-com"
    if "powerpnt" in lowered:
        return "microsoft-powerpoint-com"
    return path or "powerpoint-compatible-com"


def powerpoint_render(svg_path: Path, png_path: Path, width: int, height: int) -> dict[str, Any]:
    """Render through PowerPoint.Application COM.

    On machines without Microsoft PowerPoint the ProgID may be provided by
    WPS Presentation; the returned id records the actual engine.

    Slide.Export exports the entire slide, not the picture bounds. The slide
    page is therefore resized to the SVG canvas before the picture is placed,
    so a tight export is comparable with the Chrome headless screenshot.
    """
    engine_id = _probe_powerpoint_engine()
    script = f"""
$ErrorActionPreference = "Stop"
$svg = {json.dumps(str(svg_path))}
$out = {json.dumps(str(png_path))}
$w = {int(width)}
$h = {int(height)}
$wpp = New-Object -ComObject PowerPoint.Application
try {{
  $pres = $wpp.Presentations.Add()
  $pres.PageSetup.SlideWidth = $w
  $pres.PageSetup.SlideHeight = $h
  $slide = $pres.Slides.Add(1, 12)
  $slide.Shapes.AddPicture($svg, 0, -1, 0, 0, $w, $h) | Out-Null
  $slide.Export($out, "PNG", $w, $h)
  $pres.Close()
  Write-Host "OK"
}} catch {{
  Write-Host ("FAIL: " + $_.Exception.Message)
}} finally {{
  try {{ $wpp.Quit() }} catch {{}}
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wpp) | Out-Null
}}
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=90,
            check=False,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "ok": False, "id": engine_id, "notes": str(error)}
    stdout = (completed.stdout or "").strip()
    ok = completed.returncode == 0 and stdout.endswith("OK") and png_path.is_file() and png_path.stat().st_size > 0
    result: dict[str, Any] = {"available": True, "ok": ok, "id": engine_id, "version": "com"}
    if ok:
        result["png_sha256"] = sha256_file(png_path)
        result["width"] = width
        result["height"] = height
    else:
        result["notes"] = stdout[:200] or (completed.stderr or "")[:200]
    return result


def read_png_gray(path: Path) -> tuple[int, int, list[int]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = bytearray()
    while pos < len(data):
        length = unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = unpack(">IIBB", chunk[:10])
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth != 8:
        raise ValueError("unsupported png")
    raw = zlib.decompress(bytes(idat))
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("unsupported color type")
    stride = width * channels
    pixels: list[int] = []
    offset = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        scan = bytearray(raw[offset : offset + stride])
        offset += stride
        if filter_type == 1:
            for i in range(channels, stride):
                scan[i] = (scan[i] + scan[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                scan[i] = (scan[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = scan[i - channels] if i >= channels else 0
                scan[i] = (scan[i] + ((left + previous[i]) // 2)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = scan[i - channels] if i >= channels else 0
                b = previous[i]
                c = previous[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                scan[i] = (scan[i] + predictor) & 0xFF
        elif filter_type != 0:
            raise ValueError("bad png filter")
        previous = scan
        for x in range(width):
            base = x * channels
            if channels >= 3:
                gray = (scan[base] * 299 + scan[base + 1] * 587 + scan[base + 2] * 114) // 1000
            else:
                gray = scan[base]
            pixels.append(gray)
    return width, height, pixels


def write_png_gray(path: Path, width: int, height: int, pixels: list[int]) -> None:
    """Write an 8-bit grayscale PNG (test helper and synthetic fixtures)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        row = pixels[y * width : (y + 1) * width]
        raw.extend(max(0, min(255, int(value))) for value in row)
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + tag
            + payload
            + (zlib.crc32(tag + payload) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 0, 0, 0, 0])
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.write_bytes(png)


def compare_pngs(chrome_png: Path, ppt_png: Path, thresholds: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Compare two rendered PNGs and report pixel-agreement metrics.

    Naming caveat kept for interface compatibility: the second argument and the
    ``powerpoint_png_sha256`` metric name only identify the **second comparison
    target**, not a PowerPoint render. Callers may compare any two images (for
    example a Chrome render of the compiled SVG against a Chrome render of the
    editable source); a populated ``powerpoint_png_sha256`` therefore proves
    nothing about PowerPoint or WPS availability.
    """
    thr = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        thr.update({key: float(value) for key, value in thresholds.items()})
    cw, ch, cp = read_png_gray(chrome_png)
    pw, ph, pp = read_png_gray(ppt_png)
    if (pw, ph) != (cw, ch):
        resized: list[int] = []
        for y in range(ch):
            sy = min(ph - 1, y * ph // ch)
            for x in range(cw):
                sx = min(pw - 1, x * pw // cw)
                resized.append(pp[sy * pw + sx])
        pp = resized
    total = cw * ch
    abs_sum = 0
    chrome_ink = 0
    ppt_ink = 0
    both = 0
    chrome_bbox = [cw, ch, -1, -1]
    ppt_bbox = [cw, ch, -1, -1]
    for index in range(total):
        a = cp[index]
        b = pp[index]
        abs_sum += abs(a - b)
        a_ink = a < 240
        b_ink = b < 240
        if a_ink:
            chrome_ink += 1
            x, y = index % cw, index // cw
            chrome_bbox[0] = min(chrome_bbox[0], x)
            chrome_bbox[1] = min(chrome_bbox[1], y)
            chrome_bbox[2] = max(chrome_bbox[2], x)
            chrome_bbox[3] = max(chrome_bbox[3], y)
        if b_ink:
            ppt_ink += 1
            x, y = index % cw, index // cw
            ppt_bbox[0] = min(ppt_bbox[0], x)
            ppt_bbox[1] = min(ppt_bbox[1], y)
            ppt_bbox[2] = max(ppt_bbox[2], x)
            ppt_bbox[3] = max(ppt_bbox[3], y)
        if a_ink and b_ink:
            both += 1
    mean_abs = abs_sum / total
    union = max(1, chrome_ink + ppt_ink - both)
    overlap = both / union if union else 0.0

    def center(bbox: list[int]) -> tuple[float, float]:
        if bbox[2] < bbox[0]:
            return cw / 2.0, ch / 2.0
        return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0

    ccx, ccy = center(chrome_bbox)
    pcx, pcy = center(ppt_bbox)
    diagonal = (cw * cw + ch * ch) ** 0.5 or 1.0
    shift = ((ccx - pcx) ** 2 + (ccy - pcy) ** 2) ** 0.5 / diagonal
    ok = (
        mean_abs <= thr["max_mean_abs_diff"]
        and shift <= thr["max_bbox_shift_ratio"]
        and overlap >= thr["min_ink_overlap_ratio"]
    )
    return {
        "ok": ok,
        "method": "grayscale-mean-abs+bbox-shift+ink-overlap",
        "thresholds": thr,
        "metrics": {
            "mean_abs_diff": round(mean_abs, 4),
            "bbox_shift_ratio": round(shift, 6),
            "ink_overlap_ratio": round(overlap, 6),
            "chrome_png_sha256": sha256_file(chrome_png),
            "powerpoint_png_sha256": sha256_file(ppt_png),
        },
    }


__all__ = [
    "DEFAULT_THRESHOLDS",
    "chrome_render",
    "compare_pngs",
    "find_chrome",
    "powerpoint_render",
    "read_png_gray",
    "sha256_file",
    "write_png_gray",
]
