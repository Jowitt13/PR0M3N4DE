# Controlled Crawl4AI live-canary transport

Use this narrow production transport only after the local plan, current human
confirmation, and ARCH-044 runtime dry-run all pass. It is the concrete
transport for the existing one-page canary contract; it is not a discovery
client, search engine, candidate builder, media client, or presentation tool.

## Invocation

The command is intentionally inert without its explicit execution flag:

```text
python scripts/execute_controlled_crawl4ai_live_canary.py <input.json>
python scripts/execute_controlled_crawl4ai_live_canary.py <input.json> --execute-live
```

The first form returns `LIVE_CANARY_EXPLICIT_EXECUTION_FLAG_REQUIRED` and
makes no request. The second form may invoke exactly one locked-runtime worker
only after the existing live-canary validator accepts the nested plan,
`live_enabled`, human confirmation, the registry's sole exact seed,
one-page/depth-zero budget, source-specific delay, and ARCH-044 receipt/layout
preflight.

## Runtime boundary

The launcher invokes only the receipt-validated runtime's `.venv/Scripts/python.exe`
with an internal worker and a supervised timeout. The worker receives only the
registry-resolved exact seed, official terms URL, and same-host standard robots
URL; it does not accept an arbitrary URL, browser option, proxy, header,
script, credential, cookie, or download target.

Before the rendered seed attempt, the worker makes non-retained access-control
checks for the exact same-host `robots.txt` and official terms URL. Those checks
return only `allowed`, `denied`, or `unavailable`; they retain neither response
body nor cache. They are preflight signals, not candidate pages. The registered
one-page budget still limits the only rendered/content page: the exact seed.

The rendered attempt uses the locked Crawl4AI Chromium runtime with robots
checking enabled, HTTPS errors retained as errors, no persistent context, no
downloads, no screenshot/PDF/MHTML/network capture, no cache read/write, no
redirect following, no retries, and no stealth, proxy, custom/random user
agent, browser-script injection, fallback fetch, cookie, credential, or login
state. Its temporary browser/cache directory is removed when the worker exits.

Only `project_title` and `short_project_description` may be derived from the
renderer metadata; the worker never emits source HTML, DOM, scripts, headers,
cookies, browser state, screenshots, URLs other than the already-approved
locator, media, PDFs, or error text. On a zero-exit worker run, that existing
short observation is atomically written as one bounded UTF-8 JSON file next to
the launcher's private request file; the launcher consumes it in the same
short-lived directory and ignores worker stdout/stderr. This isolates the
result from third-party runtime noise without retaining page data after the
transport returns. Non-zero exits still use only the existing fixed sanitized
stdout envelope. All returned source text remains `untrusted_page_content` and
is handled as data only.

## Stop conditions and refusal attribution

The transport fails closed on any unavailable, malformed, or over-limit robots
observation; robots denial; terms denial; runtime process timeout/failure; non-200 response;
login/paywall/CAPTCHA/Cloudflare/refusal, redirect, malformed worker output, or
missing/forbidden/oversized text. It never retries, falls back to another
fetcher, or turns an unsuccessful canary into a candidate or evidence record.

Each stopped run exposes only one stable, non-content reason code. Runtime and
worker failures additionally carry either `runtime_diagnostic: null` or one
schema-validated `{category, stage}` pair. This is a local health diagnostic
for the reviewed runtime path, not a page-access conclusion, browser-usability
claim, or reason to retry. It never contains an exception message, class name,
stack trace, URL, path, command, cookie, browser state, or page-derived value.
The code and, where applicable, fixed diagnostic are operational diagnostics,
not claims about a page's content or access right:

| Condition | Result reason code |
| --- | --- |
| Worker process timeout/failure | `RUNTIME_WORKER_TIMEOUT` / `RUNTIME_WORKER_EXECUTION_FAILED`; `{worker_process, worker_invocation}` |
| Missing, oversized, non-JSON, or shape-invalid worker result | `WORKER_OUTPUT_MALFORMED`; `{worker_output, worker_result}` |
| Renderer navigation timeout/failure | `BROWSER_NAVIGATION_TIMEOUT` / `BROWSER_NAVIGATION_FAILED`; `{renderer_navigation, page_render}` |
| Crawl4AI import failure | `RUNTIME_CRAWL4AI_IMPORT_FAILED`; `{renderer_runtime, crawl4ai_import}` |
| Browser/configuration failure | `RUNTIME_BROWSER_CONFIGURATION_FAILED`; `{renderer_runtime, browser_configuration}` |
| Crawler session start/close failure | `RUNTIME_CRAWLER_SESSION_FAILED`; `{renderer_runtime, crawler_session}` |
| Renderer call failure | `RUNTIME_RENDER_FAILED`; `{renderer_runtime, page_render}` |
| Unclassified runtime exception | `RUNTIME_EXCEPTION`; `{renderer_runtime, unclassified}` |
| Non-200 response outside existing 401/403/429 handling | `UNEXPECTED_PAGE_RESPONSE` |
| Incomplete renderer result | `MALFORMED_PAGE_RESPONSE` |
| Explicit source refusal signal | `EXPLICIT_REFUSAL` |

`EXPLICIT_REFUSAL` is deliberately narrow. It is not a fallback category for a
timeout, runtime exception, malformed worker output, unknown status, or generic
navigation error. The transport never emits error text, response content,
browser state, local paths, or command details with any of these codes. Once a
worker command has been invoked, launcher-level timeout/failure/output cases
conservatively report `attempt_count: 1`; this records uncertainty without
creating an implicit retry path.

The diagnostic is passive: ARCH-061 neither runs a local browser health probe
nor changes the explicit `--execute-live` gate. A later local probe, if ever
reviewed, still requires its own human authorization and must not contact a
source page. This contract only makes a failing worker's known local stage
machine-readable and fail-closed.

Running this adapter is an external access action. A validated plan or an
installed runtime is not authorization by itself; obtain a fresh explicit human
confirmation for the exact run before using `--execute-live`.
