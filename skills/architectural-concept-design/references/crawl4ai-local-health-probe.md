# Crawl4AI Local Health Probe Execution Boundary

This contract extends the merged ARCH-062 `local_probe_not_executed` health
diagnostic into a future, explicitly invokable, zero-webpage local probe
boundary. It distinguishes, in live-worker order, Crawl4AI import,
`BrowserConfig` construction, ARCH-071 live-worker pre-navigation
configuration compatibility, crawler construction/session, browser launch,
and post-entry robots-gate assignability failures inside the locked runtime
only.
The gate CLI carries no runner and always refuses execution; the reviewed
locked runner below never weakens a gate, and nothing in this contract
touches a website, robots, terms, or seed.

## Invocation and gates

```text
python scripts/execute_crawl4ai_local_health_probe.py <probe-input.json>
python scripts/execute_crawl4ai_local_health_probe.py <probe-input.json> --execute-local-probe
```

Without `--execute-local-probe` the boundary refuses with
`PROBE_EXPLICIT_FLAG_REQUIRED` before any other validation. With the flag, the
gates run strictly in order: `execution_mode: local_health_probe`; the
`ProbeInput` schema in `crawl4ai-local-health-probe.schema.json`; one per-run
human confirmation validated against the live-canary `HumanConfirmation`
authority; the reused ARCH-044 receipt/local-layout dry-run. Only after every
gate passes may a reviewed, injected runner ever be considered — the gate CLI
injects none and terminates with `PROBE_RUNNER_NOT_CONFIGURED`, while the
locked runner CLI below injects exactly one fixed worker command. A single
flag, stale confirmation, or installed runtime is never execution
authorization by itself.

## Locked runner and worker

`scripts/execute_crawl4ai_locked_local_health_probe.py` wires the reused,
unchanged ARCH-063 gate to the only permitted invocation: the
receipt-validated runtime's exact `.venv/Scripts/python.exe` in isolated `-I`
mode (which ignores every `PYTHON*` environment variable) running the fixed
repository worker `crawl4ai_local_health_probe_worker.py` with one
temporary request file that contains exactly `runtime_root`. The supervised
process uses a plain argument list under the fixed `PROBE_TIMEOUT_SECONDS`
budget — no shell, PATH lookup, relative path, command concatenation,
environment or working-directory injection, extra argument, or page locator.
A timeout, nonzero exit, or any other process failure surfaces only as the
gate's fixed `PROBE_WORKER_TIMEOUT` / `PROBE_WORKER_EXECUTION_FAILED` codes.
The worker walks only the fixed local stages (import, BrowserConfig,
live_configuration, crawler construction/session, browser launch/context
entry, and post-entry robots_gate assignment), has no network client,
navigation, rendering, or capture call, and prints exactly one
`{"outcome": <fixed>}` line; an invalid request exits nonzero with no output.
Invoking this CLI live remains an explicit human action under every gate
above; this repository's tests exercise it only with fake processes.

## Future probe boundary

A future reviewed runner may start only the receipt-validated locked runtime,
supervised by the fixed `PROBE_TIMEOUT_SECONDS` budget, with a request that
contains exactly `runtime_root`. The probe has no page URL, search,
navigation, download, media, HTML/DOM, cookie, script, or screenshot
retention, and must not use a proxy, user-agent disguise, stealth, login,
cookie import, script injection, retry, or any bypass. Worker output is
fail-closed: one line, at most 512 characters, exactly `{"outcome": <fixed>}`.
Any timeout, malformed or oversized output, unknown status, nonzero-exit
mapping, or network intent (`http` appearing anywhere in the raw output)
stops the run immediately with one fixed code — never a fallback or retry.

## Fixed outcome and diagnostic allowlist

| Worker outcome / condition | Reason code | `probe_diagnostic` | ARCH-062 health classification |
| --- | --- | --- | --- |
| runner timeout | `PROBE_WORKER_TIMEOUT` | `{probe_process, probe_invocation}` | — |
| runner failure / nonzero exit | `PROBE_WORKER_EXECUTION_FAILED` | `{probe_process, probe_invocation}` | — |
| oversized / non-JSON / wrong-shape output | `PROBE_OUTPUT_MALFORMED` | `{probe_output, probe_result}` | — |
| unknown outcome value | `PROBE_STATUS_UNKNOWN` | `{probe_output, probe_result}` | — |
| network intent in raw output | `PROBE_NETWORK_INTENT_FORBIDDEN` | `{probe_output, probe_result}` | — |
| `crawl4ai_import_failed` | `PROBE_CRAWL4AI_IMPORT_FAILED` | `{probe_runtime, crawl4ai_import}` | `{renderer_runtime, crawl4ai_import}` |
| `browser_configuration_failed` | `PROBE_BROWSER_CONFIGURATION_FAILED` | `{probe_runtime, browser_configuration}` | `{renderer_runtime, browser_configuration}` |
| `live_configuration_failed` | `PROBE_LIVE_CONFIGURATION_FAILED` | `{probe_runtime, live_configuration}` | `null` (probe-only stage) |
| `live_configuration_cache_mode_incompatible` | `PROBE_LIVE_CONFIGURATION_CACHE_MODE_INCOMPATIBLE` | `{probe_runtime, live_configuration}` | `null` (probe-only stage) |
| `live_configuration_parameter_incompatible` (+ `parameter`) | `PROBE_LIVE_CONFIGURATION_PARAMETER_INCOMPATIBLE` | `{probe_runtime, live_configuration}` | `null` (probe-only stage) |
| `live_configuration_combination_incompatible` | `PROBE_LIVE_CONFIGURATION_COMBINATION_INCOMPATIBLE` | `{probe_runtime, live_configuration}` | `null` (probe-only stage) |
| `crawler_session_failed` | `PROBE_CRAWLER_SESSION_FAILED` | `{probe_runtime, crawler_session}` | `{renderer_runtime, crawler_session}` |
| `browser_launch_failed` | `PROBE_BROWSER_LAUNCH_FAILED` | `{probe_runtime, browser_launch}` | `null` (probe-only stage) |
| `robots_gate_incompatible` | `PROBE_ROBOTS_GATE_INCOMPATIBLE` | `{probe_runtime, robots_gate}` | `null` (probe-only stage) |
| `completed` | `PROBE_COMPLETED_LOCAL_STAGES_ONLY` | `null` | `null` |

The probe stages run in the same order the live canary worker uses:
`import → BrowserConfig → live_configuration → crawler construction/session →
browser launch/context entry → robots_gate assignment`. The ARCH-071
`live_configuration` stage constructs only the exact pre-navigation
`CrawlerRunConfig`/`CacheMode` surface the live worker really builds (mirrored
verbatim and value-for-value drift-checked against
`controlled_crawl4ai_live_canary_worker` by an offline AST test, including its
`PAGE_TIMEOUT_MILLISECONDS` module constant). Most of that surface pins
capture/rendering/JS/retry capabilities OFF, but `check_robots_txt=True` is a
deliberately enabled local-compatibility parameter, not a disabled one. The
`robots_gate` stage runs only after the crawler session is entered and mirrors
the live worker, which assigns `crawler.robots_parser = <gate>` post-entry: the
probe assigns an inert local sentinel and verifies only that just-assigned
object's identity, so a normal dynamic crawler with no pre-existing
`robots_parser` succeeds while a `__slots__` or read-only-property crawler that
rejects the assignment fails closed. Neither stage ever receives a URL, page
object, `arun`, navigation, HTTP, DNS, download, cookie, HTML/DOM, screenshot,
PDF, or media call. A passing stage means only that the locked runtime is
locally compatible with the live worker's pre-navigation API surface — never
that a page is accessible, a source is authorized, robots/terms permit
anything, or a live canary is authorized.

## ARCH-072 live_configuration incompatibility attribution

When the complete `CrawlerRunConfig` mirror does not construct, the worker adds
a fixed, URL-free attribution breakdown that never modifies, deletes, or
weakens any live-worker kwarg — it only reports which fixed part is
incompatible, in one deterministic, auditable order:

1. **`CacheMode.BYPASS` baseline** — construct `CrawlerRunConfig(cache_mode=CacheMode.BYPASS)` alone. Failure ⇒ `live_configuration_cache_mode_incompatible` / `PROBE_LIVE_CONFIGURATION_CACHE_MODE_INCOMPATIBLE`.
2. **Single kwarg** — construct the baseline plus each statically allowlisted kwarg on its own, in `LIVE_RUN_CONFIG_KWARGS` insertion order; the **first** failing kwarg is reported as `live_configuration_parameter_incompatible` / `PROBE_LIVE_CONFIGURATION_PARAMETER_INCOMPATIBLE`, and its name is surfaced in the fixed `incompatible_parameter` result field (enum-constrained to the allowlist below — never free text).
3. **Complete mirror (final construction check)** — construct the baseline plus every kwarg. Success ⇒ the stage passes and the probe proceeds. Failure after every single kwarg constructed ⇒ `live_configuration_combination_incompatible` / `PROBE_LIVE_CONFIGURATION_COMBINATION_INCOMPATIBLE`.

The retained generic `live_configuration_failed` / `PROBE_LIVE_CONFIGURATION_FAILED`
covers only the crawl4ai import failure and any unclassified condition; unknown
or malformed worker output, or a `parameter` value outside the allowlist or on
any other outcome, stays fail-closed (`PROBE_OUTPUT_MALFORMED` /
`PROBE_STATUS_UNKNOWN`). All four ARCH-072 outcomes keep the existing
`{probe_runtime, live_configuration}` diagnostic and probe-only (`null`) health
classification, and `retry_count` is always `0`. The `incompatible_parameter`
allowlist is exactly, in order: `only_text`, `excluded_tags`, `remove_forms`,
`check_robots_txt`, `page_timeout`,
`wait_until`, `wait_for_images`, `screenshot`, `pdf`, `capture_mhtml`,
`capture_network_requests`, `capture_console_messages`, `process_iframes`,
`scan_full_page`, `js_code`, `js_code_before_wait`, `c4a_script`, `max_retries`,
`fallback_fetch_function` — statically defined in the worker mirror, the gate
allowlist, and this schema enum, bound together by an offline drift test. No
attribution result carries an exception message, path, command, environment,
URL, page content, or browser state. A later compatibility correction must
update the live worker and probe mirror together, then await a separately
confirmed real probe before any webpage operation.

`CacheMode.BYPASS` is the sole cache control in the mirrored configuration. The
deprecated legacy flags `no_cache_read` and `no_cache_write` are intentionally
absent: the pinned runtime rejects their non-default values, while `BYPASS`
continues to prohibit both cache reads and writes for the operation. This is a
compatibility correction only; it does not relax any page, retry, retention,
robots, or anti-bypass control.

The shared stages reuse the ARCH-061/062 gate-built `{renderer_runtime,
<stage>}` pair so a failed probe plugs directly into the merged health
diagnostic audit. Results carry only these fixed codes and pairs — never a
command line, exception message, path, environment variable, URL, HTML/DOM,
cookie, or browser state. `retry_count` is always `0` and `attempt_count` is
at most `1`.

## Refusal codes

`PROBE_EXPLICIT_FLAG_REQUIRED`, `PROBE_EXECUTION_MODE_FORBIDDEN`,
`PROBE_INPUT_SCHEMA_INVALID`, `PROBE_HUMAN_CONFIRMATION_REQUIRED`,
`PROBE_RUNTIME_DRY_RUN_NOT_READY` (with the reused ARCH-044 codes appended),
`PROBE_RUNNER_NOT_CONFIGURED`, `PROBE_RESULT_SCHEMA_INVALID`, and
`PROBE_AUTHORITY_LOAD_FAILED` all report
`probe_status: local_probe_not_executed`.

## Result semantics

`local_probe_completed_local_stages_only` means only that the locked runtime
finished its local stages once. It is never a claim that a webpage is
accessible, that the browser is usable for a source, that robots or terms
permit anything, or that a live canary is authorized. The live-canary
one-page, zero-retry, robots→delay→terms→delay→seed sequence and every
anti-bypass boundary remain unchanged and are not exercised by this contract.
