# Crawl4AI Live-worker Health Diagnostic

This contract extends the ARCH-061 sanitized `runtime_diagnostic` into an
auditable, offline local diagnostic entry. It classifies one already-recorded
`{category, stage}` pair, audits its pairing with one ARCH-061 reason code, and
re-runs the ARCH-044 receipt/local-layout dry-run. It never installs, starts,
probes, or contacts Crawl4AI, Playwright, a browser, a subprocess, DNS, HTTP,
robots, terms, or any architectural source, and it never changes the
live-canary robots→delay→terms→delay→seed sequence, one-page budget,
zero-retry rule, or anti-bypass boundary.

## Invocation

```text
python scripts/diagnose_crawl4ai_live_worker_health.py <diagnostic-input.json>
python scripts/diagnose_crawl4ai_live_worker_health.py <diagnostic-input.json> --execute-local-probe
```

The input must match `HealthDiagnosticInput` in
`crawl4ai-live-worker-health-diagnostic.schema.json`: `execution_mode:
local_health_diagnostic`, the full ARCH-044 `runtime_dry_run_input`, and either
both `observed_reason_code` and `observed_runtime_diagnostic` from one prior
live-canary result or both `null` for a pure health recheck. Every other
`execution_mode`, and the `--execute-local-probe` flag, returns
`LOCAL_PROBE_EXECUTION_NOT_IMPLEMENTED` before any other validation. The flag
exists only as the independent explicit gate a future reviewed probe would
require; this contract provides no probe, and a future local probe still needs
its own project-lead authorization and must not contact a source page.

## Fixed diagnostic allowlist

The `{category, stage}` authority is the `RuntimeDiagnostic` definition in
`controlled-crawl-live-canary.schema.json`; this contract's schema carries a
drift-checked mirror. The audited reason-code pairing is derived from the
ARCH-061 gate:

| Reason code | Fixed pair |
| --- | --- |
| `RUNTIME_WORKER_TIMEOUT` / `RUNTIME_WORKER_EXECUTION_FAILED` | `{worker_process, worker_invocation}` |
| `WORKER_OUTPUT_MALFORMED` / `MALFORMED_WORKER_OBSERVATION` | `{worker_output, worker_result}` |
| `BROWSER_NAVIGATION_TIMEOUT` / `BROWSER_NAVIGATION_FAILED` | `{renderer_navigation, page_render}` |
| `RUNTIME_CRAWL4AI_IMPORT_FAILED` | `{renderer_runtime, crawl4ai_import}` |
| `RUNTIME_BROWSER_CONFIGURATION_FAILED` | `{renderer_runtime, browser_configuration}` |
| `RUNTIME_CRAWLER_SESSION_FAILED` | `{renderer_runtime, crawler_session}` |
| `RUNTIME_RENDER_FAILED` | `{renderer_runtime, page_render}` |
| `RUNTIME_EXCEPTION` | `{renderer_runtime, unclassified}` |

A reported classification is always the gate-built expected pair, never an
echo of input. Results never contain an exception message, class name, stack
trace, URL, path, HTML, DOM, cookie, command line, environment variable,
browser state, or page-derived value.

## Results

Every result keeps `probe_status: local_probe_not_executed`; the schema allows
no other value, so any future probe status requires a reviewed schema change.
`runtime_health: receipt_and_local_layout_validated_dry_run_only` only repeats
the ARCH-044 dry-run conclusion; it is not proof that a browser can start,
that a page is accessible, or that a request is authorized.

| Reason code | Meaning |
| --- | --- |
| `LOCAL_PROBE_NOT_EXECUTED` | Successful diagnostics confirm no probe ran. |
| `RUNTIME_HEALTH_RECEIPT_AND_LAYOUT_VALIDATED` | The reused ARCH-044 dry-run passed. |
| `RUNTIME_HEALTH_DRY_RUN_NOT_READY` | The reused dry-run failed; its own codes are appended. |
| `DIAGNOSTIC_PAIR_CONSISTENT` | Code and pair match the fixed ARCH-061 mapping. |
| `DIAGNOSTIC_NOT_SUPPLIED` | No prior diagnostic was provided; health recheck only. |
| `DIAGNOSTIC_OBSERVATION_INCOMPLETE` | Code and pair must be supplied together. |
| `DIAGNOSTIC_CODE_NOT_ALLOWLISTED` | The reason code is not an ARCH-061 diagnostic code. |
| `DIAGNOSTIC_CODE_PAIR_MISMATCH` | The pair does not match the fixed mapping for the code. |
| `DIAGNOSTIC_PAIR_NOT_ALLOWLISTED` | The pair is not an allowlisted `{category, stage}`. |
| `DIAGNOSTIC_INPUT_SCHEMA_INVALID` | The input does not match `HealthDiagnosticInput`. |
| `DIAGNOSTIC_RESULT_SCHEMA_INVALID` | Fail-closed fallback when a result would not validate. |
| `DIAGNOSTIC_AUTHORITY_LOAD_FAILED` | A local authority file could not be loaded. |
| `LOCAL_PROBE_EXECUTION_NOT_IMPLEMENTED` | A probe or non-diagnostic mode was requested and refused. |

This diagnostic is a passive local health audit for the reviewed runtime path.
It is not a page-access conclusion, a browser-usability claim, a reason to
retry, a source-registry change, an access permission, or an ADR-0001
`VERIFIED` label.
