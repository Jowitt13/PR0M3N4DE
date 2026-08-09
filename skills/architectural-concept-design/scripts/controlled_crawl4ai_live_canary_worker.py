"""Locked-runtime worker for one reviewed, rendered Crawl4AI canary page.

The worker is registry-driven: it never hard-codes a source. The seed, terms,
and robots URLs are supplied by the reviewed launcher/gate from the exact
`controlled_crawl_allowed` registry record. The worker still fails closed and
enforces that all three URLs are HTTPS on the one same host and that robots is
the standard same-host location.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NotRequired, Protocol, TypedDict
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser


MAX_TEXT_LENGTH = 280
WORKER_RESULT_FILENAME = "result.json"
WORKER_RESULT_MAX_BYTES = 4096
ROBOTS_TIMEOUT_SECONDS = 10
TERMS_TIMEOUT_SECONDS = 10
PAGE_TIMEOUT_MILLISECONDS = 20_000
ROBOTS_MAX_BYTES = 64 * 1024
MINIMUM_DELAY_MS = 3000
REQUEST_KEYS = {"seed_url", "terms_url", "robots_url", "runtime_root", "minimum_delay_ms"}
EXPLICIT_REFUSAL_MARKERS = ("explicit refusal", "access explicitly refused")

# ARCH-066: fixed, sanitized exit envelope for known local worker boundary
# failures.  A non-zero exit prints exactly one short fixed-token JSON line;
# it never carries exception text, tracebacks, paths, URLs, commands,
# environment values, or page data.  Unknown failures stay fail-closed.
WORKER_EXIT_STATUS = 3
WORKER_EXIT_ENVELOPE_VERSION = "1.0.0"
WORKER_EXIT_ENVELOPE_KEYS = frozenset({"worker_exit_envelope", "exit_reason"})
WORKER_EXIT_REASONS = frozenset({
    "request_load_failed",
    "request_contract_invalid",
    "crawl4ai_import_failed",
    "browser_configuration_failed",
    "crawler_session_failed",
    "page_render_failed",
    "worker_local_failure",
})

PageKind = Literal[
    "response",
    "redirect",
    "login",
    "paywall",
    "captcha",
    "cloudflare",
    "refusal",
    "navigation_timeout",
    "navigation_failure",
    "runtime_exception",
    "unexpected_response",
    "malformed_response",
]
RuntimeStage = Literal[
    "crawl4ai_import",
    "browser_configuration",
    "crawler_session",
    "page_render",
    "unclassified",
]

# ARCH-066: the last locally classified runtime stage, recorded so a later
# non-zero exit can attribute an escaped local failure without exception text.
_STAGE_EXIT_REASONS: dict[RuntimeStage, str] = {
    "crawl4ai_import": "crawl4ai_import_failed",
    "browser_configuration": "browser_configuration_failed",
    "crawler_session": "crawler_session_failed",
    "page_render": "page_render_failed",
    "unclassified": "worker_local_failure",
}
_last_local_stage: RuntimeStage | None = None


class PageObservation(TypedDict):
    kind: PageKind
    http_status: int | None
    observed_url: str | None
    extracted_text: dict[str, str]
    runtime_stage: NotRequired[RuntimeStage]


class WorkerObservation(TypedDict):
    robots: str
    terms: str
    checked_at: str
    page: PageObservation | None


def _runtime_exception(stage: RuntimeStage) -> PageObservation:
    """Return a non-retaining, allowlisted local runtime diagnostic."""

    global _last_local_stage
    _last_local_stage = stage
    return {
        "kind": "runtime_exception",
        "http_status": None,
        "observed_url": None,
        "extracted_text": {},
        "runtime_stage": stage,
    }


class AsyncTextRequest(Protocol):
    async def __call__(self, url: str) -> tuple[int, str, str | None]: ...


class AsyncStatusRequest(Protocol):
    async def __call__(self, url: str) -> tuple[int, str]: ...


class AsyncPageRequest(Protocol):
    async def __call__(self, request: Mapping[str, object]) -> PageObservation: ...


class AsyncPause(Protocol):
    async def __call__(self, seconds: float) -> None: ...


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _https_host(value: object) -> str | None:
    """Return the host of an exact HTTPS URL with no credentials/port/fragment."""

    if not isinstance(value, str) or not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port or parts.fragment:
        return None
    return parts.hostname


def _same_host_target(request: Mapping[str, object]) -> tuple[str, str, str] | None:
    """Return (seed_url, terms_url, robots_url) only when all share one HTTPS host."""

    seed_url, terms_url, robots_url = request.get("seed_url"), request.get("terms_url"), request.get("robots_url")
    seed_host = _https_host(seed_url)
    if seed_host is None or _https_host(terms_url) != seed_host or _https_host(robots_url) != seed_host:
        return None
    if robots_url != f"https://{seed_host}/robots.txt":
        return None
    assert isinstance(seed_url, str) and isinstance(terms_url, str) and isinstance(robots_url, str)
    return seed_url, terms_url, robots_url


def _request_code(request: Mapping[str, object]) -> str | None:
    if set(request) != REQUEST_KEYS:
        return "invalid"
    if _same_host_target(request) is None:
        return "invalid"
    root = request.get("runtime_root")
    delay = request.get("minimum_delay_ms")
    if not isinstance(root, str) or not root or isinstance(delay, bool) or not isinstance(delay, int) or delay < MINIMUM_DELAY_MS:
        return "invalid"
    return None


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized if 0 < len(normalized) <= MAX_TEXT_LENGTH else None


def _metadata_text(metadata: object) -> dict[str, str]:
    if not isinstance(metadata, Mapping):
        return {}
    values: dict[str, str] = {}
    title = _safe_text(metadata.get("title"))
    description = _safe_text(metadata.get("description"))
    if title is not None:
        values["project_title"] = title
    if description is not None:
        values["short_project_description"] = description
    return values


def _bounded_robots_text(body: bytes) -> str | None:
    """Decode a complete bounded robots response or mark it unavailable."""

    if len(body) > ROBOTS_MAX_BYTES:
        return None
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _page_kind(status: object, error: object, observed_url: object, seed_url: str) -> PageKind:
    """Classify a failed renderer result without retaining its error text.

    ``refusal`` is intentionally narrow: it represents an explicit source
    refusal signal only. A navigation problem, timeout, unknown HTTP response,
    or incomplete Crawl4AI result must retain its own fail-closed category.
    """

    if isinstance(observed_url, str) and observed_url != seed_url:
        return "redirect"
    message = error.lower() if isinstance(error, str) else ""
    if "login" in message:
        return "login"
    if "paywall" in message:
        return "paywall"
    if "captcha" in message:
        return "captcha"
    if "cloudflare" in message:
        return "cloudflare"
    if isinstance(status, int) and status in {401, 403, 429}:
        return "response"
    if any(marker in message for marker in EXPLICIT_REFUSAL_MARKERS):
        return "refusal"
    if "timeout" in message:
        return "navigation_timeout"
    if isinstance(status, int):
        return "unexpected_response"
    if message:
        return "navigation_failure"
    return "malformed_response"


async def observe_once(
    request: Mapping[str, object],
    *,
    fetch_robots: AsyncTextRequest,
    check_terms: AsyncStatusRequest,
    crawl_page: AsyncPageRequest,
    pause: AsyncPause = asyncio.sleep,
    now: Callable[[], str] = _utc_now,
) -> WorkerObservation:
    """Run one bounded observation from injectable, non-retaining primitives."""

    if _request_code(request) is not None:
        return {"robots": "unavailable", "terms": "unavailable", "checked_at": now(), "page": None}
    target = _same_host_target(request)
    assert target is not None
    seed_url, terms_url, robots_url = target
    try:
        robots_status, robots_returned_url, robots_text = await fetch_robots(robots_url)
        if not isinstance(robots_text, str):
            robots_allowed = None
        else:
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(robots_text.splitlines())
            robots_allowed = robots_status == 200 and robots_returned_url == robots_url and parser.can_fetch("*", seed_url)
    except Exception:
        robots_allowed = None
    if robots_allowed is not True:
        return {"robots": "denied" if robots_allowed is False else "unavailable", "terms": "unavailable", "checked_at": now(), "page": None}

    await pause(float(request["minimum_delay_ms"]) / 1000)
    try:
        terms_status, terms_returned_url = await check_terms(terms_url)
    except Exception:
        terms_status, terms_returned_url = None, None
    if terms_status != 200 or terms_returned_url != terms_url:
        return {"robots": "allowed", "terms": "denied" if terms_status in {401, 403, 429} else "unavailable", "checked_at": now(), "page": None}

    await pause(float(request["minimum_delay_ms"]) / 1000)
    try:
        page = await crawl_page(request)
    except TimeoutError:
        page = {"kind": "navigation_timeout", "http_status": None, "observed_url": None, "extracted_text": {}}
    except Exception:
        page = _runtime_exception("unclassified")
    return {"robots": "allowed", "terms": "allowed", "checked_at": now(), "page": page}


async def _fetch_robots(url: str) -> tuple[int, str, str | None]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=ROBOTS_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
        async with session.get(url, allow_redirects=False) as response:
            body = await response.content.read(ROBOTS_MAX_BYTES + 1)
            return response.status, str(response.url), _bounded_robots_text(body)


async def _check_terms(url: str) -> tuple[int, str]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=TERMS_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
        async with session.head(url, allow_redirects=False) as response:
            return response.status, str(response.url)


async def _crawl_page(request: Mapping[str, object]) -> PageObservation:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except Exception:
        return _runtime_exception("crawl4ai_import")

    target = _same_host_target(request)
    assert target is not None
    seed_url, _terms_url, _robots_url = target
    runtime_root = Path(str(request["runtime_root"]))
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(runtime_root / "browsers")
    try:
        browser = BrowserConfig(
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
        config = CrawlerRunConfig(
            only_text=True,
            excluded_tags=["script", "style", "noscript", "svg", "iframe"],
            remove_forms=True,
            cache_mode=CacheMode.BYPASS,
            check_robots_txt=True,
            page_timeout=PAGE_TIMEOUT_MILLISECONDS,
            wait_until="domcontentloaded",
            wait_for_images=False,
            screenshot=False,
            pdf=False,
            capture_mhtml=False,
            capture_network_requests=False,
            capture_console_messages=False,
            process_iframes=False,
            scan_full_page=False,
            js_code=None,
            js_code_before_wait=None,
            c4a_script=None,
            max_retries=0,
            fallback_fetch_function=None,
        )
    except Exception:
        return _runtime_exception("browser_configuration")

    try:
        with tempfile.TemporaryDirectory(prefix="architecture-crawl4ai-canary-") as temporary:
            async with AsyncWebCrawler(config=browser, base_directory=temporary) as crawler:
                class _CurrentRobotsGate:
                    async def can_fetch(self, url: str, _user_agent: str) -> bool:
                        return url == seed_url

                crawler.robots_parser = _CurrentRobotsGate()
                try:
                    result = await crawler.arun(seed_url, config=config)
                except TimeoutError:
                    return {"kind": "navigation_timeout", "http_status": None, "observed_url": None, "extracted_text": {}}
                except Exception:
                    return _runtime_exception("page_render")
    except Exception:
        return _runtime_exception("crawler_session")

    try:
        status = getattr(result, "status_code", None)
        observed_url = getattr(result, "redirected_url", None) or getattr(result, "url", None)
        if getattr(result, "success", False) and status == 200 and observed_url == seed_url:
            return {"kind": "response", "http_status": 200, "observed_url": seed_url, "extracted_text": _metadata_text(getattr(result, "metadata", None))}
        return {"kind": _page_kind(status, getattr(result, "error_message", None), observed_url, seed_url), "http_status": status if isinstance(status, int) else None, "observed_url": observed_url if isinstance(observed_url, str) else None, "extracted_text": {}}
    except Exception:
        return _runtime_exception("unclassified")


def _load_request(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, Mapping) else {}


def _local_exit_reason() -> str:
    """Map the last recorded local stage to one fixed exit-envelope token."""

    stage = _last_local_stage
    if stage is None:
        return "worker_local_failure"
    return _STAGE_EXIT_REASONS.get(stage, "worker_local_failure")


def _emit_exit_envelope(reason: str) -> int:
    """Print one fixed single-line envelope and return the fixed exit status.

    Only a fixed allowlisted token leaves the process; any unknown token is
    replaced so exception details can never travel through the envelope.
    """

    safe_reason = reason if reason in WORKER_EXIT_REASONS else "worker_local_failure"
    envelope = {"exit_reason": safe_reason, "worker_exit_envelope": WORKER_EXIT_ENVELOPE_VERSION}
    print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return WORKER_EXIT_STATUS


def _result_path(request_path: Path) -> Path:
    """Keep the successful observation inside the launcher's private directory."""

    return request_path.with_name(WORKER_RESULT_FILENAME)


def _write_result(request_path: Path, observation: WorkerObservation) -> None:
    """Atomically publish one bounded UTF-8 observation without using stdout.

    The request path is created by the launcher inside its short-lived
    ``TemporaryDirectory``.  The result contains only the existing observation
    contract and is removed with that directory after the launcher consumes it.
    """

    payload = json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not payload or len(payload) > WORKER_RESULT_MAX_BYTES:
        raise ValueError("worker result is outside the fixed byte boundary")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".worker-result-", suffix=".tmp", dir=request_path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, _result_path(request_path))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    arguments = parser.parse_args(argv[1:])
    try:
        request = _load_request(arguments.request)
    except (OSError, ValueError, json.JSONDecodeError):
        return _emit_exit_envelope("request_load_failed")
    if _request_code(request) is not None:
        return _emit_exit_envelope("request_contract_invalid")
    try:
        result = asyncio.run(observe_once(request, fetch_robots=_fetch_robots, check_terms=_check_terms, crawl_page=_crawl_page))
        _write_result(arguments.request, result)
    except Exception:
        return _emit_exit_envelope(_local_exit_reason())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
