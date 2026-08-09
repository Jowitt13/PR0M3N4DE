"""Locked-runtime worker probing only local Crawl4AI stages; it never opens a page.

The worker walks these fixed local stages in live-worker order:
import -> BrowserConfig -> live_configuration -> crawler construction/session
-> browser launch/context entry -> robots_gate assignment, inside the
receipt-validated runtime. The robots_gate stage mirrors the live worker,
which assigns ``crawler.robots_parser`` only after entering the session, so it
verifies post-entry assignability (not pre-existence). The worker has no page
locator, no rendering call, and no network client of its own, and it emits
exactly one short fixed-outcome JSON line for the ARCH-063 gate. A completed
probe is never a page-access, robots/terms, source-authorization, or
live-canary-authorization claim.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

REQUEST_KEYS = frozenset({"runtime_root"})

# ARCH-071: the exact pre-navigation configuration surface the live canary
# worker really constructs before it could ever navigate. The values MUST
# mirror ``controlled_crawl4ai_live_canary_worker._crawl_page`` verbatim; an
# offline AST drift test enforces that this mirror never diverges from the
# live worker. ``cache_mode`` is applied separately because it needs the
# imported ``CacheMode.BYPASS`` member. No URL, page object, or navigation
# call is ever involved in this stage.
LIVE_RUN_CONFIG_KWARGS: dict[str, object] = {
    "only_text": True,
    "excluded_tags": ["script", "style", "noscript", "svg", "iframe"],
    "remove_forms": True,
    "check_robots_txt": True,
    "page_timeout": 20_000,
    "wait_until": "domcontentloaded",
    "wait_for_images": False,
    "screenshot": False,
    "pdf": False,
    "capture_mhtml": False,
    "capture_network_requests": False,
    "capture_console_messages": False,
    "process_iframes": False,
    "scan_full_page": False,
    "js_code": None,
    "js_code_before_wait": None,
    "c4a_script": None,
    "max_retries": 0,
    "fallback_fetch_function": None,
}
# The live worker's robots gate override point; it assigns this attribute on the
# crawler AFTER entering the session (it does not require pre-existence). The
# probe therefore verifies local, URL-free assignability, not prior existence.
LIVE_ROBOTS_GATE_ATTRIBUTE = "robots_parser"


def _load_request(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, Mapping) else {}


def _valid_runtime_root(request: Mapping[str, object]) -> str | None:
    """Accept exactly one absolute runtime root and nothing else."""

    if set(request) != REQUEST_KEYS:
        return None
    root = request.get("runtime_root")
    if not isinstance(root, str) or not root or not Path(root).is_absolute():
        return None
    return root


def _robots_gate_assignable(crawler: object) -> bool:
    """Mirror the live worker's post-entry robots-gate assignment, URL-free.

    The live worker sets ``crawler.robots_parser = <gate>`` only after entering
    the session; it never requires the attribute to pre-exist. This check
    assigns an inert local sentinel (never a network object, never called) and
    verifies only the just-assigned object's identity. Both the assignment and
    the read-back/identity verification are guarded: any failure of either (a
    ``__slots__``/read-only-property setter, or a getter/descriptor that raises
    or returns a different object) means the live worker's required post-entry
    assignment cannot be safely verified, so this returns ``False`` and the
    session stage reports ``robots_gate_incompatible`` rather than leaking the
    failure out of the entered context. It never navigates, fetches, or touches
    a URL.
    """

    sentinel = object()
    try:
        setattr(crawler, LIVE_ROBOTS_GATE_ATTRIBUTE, sentinel)
        return getattr(crawler, LIVE_ROBOTS_GATE_ATTRIBUTE, None) is sentinel
    except Exception:
        return False


async def _session_and_launch_stages(browser_configuration: object, crawler_type: type) -> str:
    """Open and close one local crawler without ever requesting a page.

    Stage order mirrors the live worker: construct the crawler, enter its
    session (browser launch/context entry), then perform the post-entry,
    URL-free robots-gate assignment check. A construction failure is
    ``crawler_session_failed``; a context-entry (or exit) failure is
    ``browser_launch_failed``; only a rejected assignment after a successful
    entry is ``robots_gate_incompatible``.
    """

    with tempfile.TemporaryDirectory(prefix="architecture-local-health-probe-") as temporary:
        try:
            crawler = crawler_type(config=browser_configuration, base_directory=temporary)
        except Exception:
            return "crawler_session_failed"
        gate_assignable = False
        try:
            async with crawler:
                gate_assignable = _robots_gate_assignable(crawler)
        except Exception:
            return "browser_launch_failed"
    return "completed" if gate_assignable else "robots_gate_incompatible"


def _live_configuration_outcome() -> tuple[str, str | None] | None:
    """Construct only the live worker's pre-navigation configuration surface.

    This stage never receives a URL and never navigates; it proves only that
    the locked runtime still accepts the exact configuration the live worker
    would build before any request could exist. When the complete mirror does
    not construct, ARCH-072 attributes the incompatibility with a fixed,
    URL-free breakdown in one deterministic order: the ``CacheMode.BYPASS``
    baseline first, then each statically allowlisted kwarg on its own (the
    first failing kwarg in insertion order is reported), then the complete
    mirror; if every single kwarg constructs but the complete mirror still
    fails the result is a fixed "combination incompatible". Returns ``None`` on
    full success, otherwise ``(outcome, parameter_or_None)`` where ``parameter``
    is only set for the single-kwarg case and is always one of
    ``LIVE_RUN_CONFIG_KWARGS``.
    """

    try:
        from crawl4ai import CacheMode, CrawlerRunConfig
    except Exception:
        return ("live_configuration_failed", None)
    try:
        CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    except Exception:
        return ("live_configuration_cache_mode_incompatible", None)
    for name, value in LIVE_RUN_CONFIG_KWARGS.items():
        try:
            CrawlerRunConfig(cache_mode=CacheMode.BYPASS, **{name: value})
        except Exception:
            return ("live_configuration_parameter_incompatible", name)
    try:
        CrawlerRunConfig(cache_mode=CacheMode.BYPASS, **LIVE_RUN_CONFIG_KWARGS)
    except Exception:
        return ("live_configuration_combination_incompatible", None)
    return None


def _walk_stages() -> tuple[str, str | None]:
    """Walk the fixed local stages once; return ``(outcome, parameter_or_None)``."""

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
    except Exception:
        return ("crawl4ai_import_failed", None)
    try:
        browser_configuration = BrowserConfig(
            browser_type="chromium",
            headless=True,
            browser_mode="dedicated",
            use_managed_browser=False,
            use_persistent_context=False,
            accept_downloads=False,
            ignore_https_errors=False,
            enable_stealth=False,
            verbose=False,
        )
    except Exception:
        return ("browser_configuration_failed", None)
    live_configuration_outcome = _live_configuration_outcome()
    if live_configuration_outcome is not None:
        return live_configuration_outcome
    try:
        return (asyncio.run(_session_and_launch_stages(browser_configuration, AsyncWebCrawler)), None)
    except Exception:
        return ("crawler_session_failed", None)


def probe_local_observation() -> dict[str, str]:
    """Return the fixed, sanitized observation the ARCH-063 gate will map.

    The only optional key is ``parameter`` (present solely for the single-kwarg
    ``live_configuration_parameter_incompatible`` case and always an allowlisted
    kwarg name). No exception text, path, command, URL, or browser state ever
    appears.
    """

    outcome, parameter = _walk_stages()
    observation = {"outcome": outcome}
    if parameter is not None:
        observation["parameter"] = parameter
    return observation


def probe_local_stages() -> str:
    """Backward-compatible single-token accessor (outcome only)."""

    return probe_local_observation()["outcome"]


def main(argv: Sequence[str]) -> int:
    """Emit one fixed-outcome line or exit nonzero without printing anything."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    arguments = parser.parse_args(argv[1:])
    try:
        request = _load_request(arguments.request)
    except (OSError, ValueError, json.JSONDecodeError):
        return 2
    root = _valid_runtime_root(request)
    if root is None:
        return 2
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(root) / "browsers")
    print(json.dumps(probe_local_observation(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
