# Offline Controlled Crawl Replay Adapter

This contract exercises the future controlled Crawl4AI adapter without a
network, browser, Crawl4AI installation, or external dependency receipt. It
accepts a local controlled-crawl plan and a local synthetic replay fixture,
then emits only a machine-readable execution or insufficiency result.

## Boundary

The adapter always validates the plan first through
`validate_controlled_crawl_plan.py`. A replay is not a request authorization,
runtime receipt, candidate set, `SRC-xxx`, `E-xxx`, `RC-xxx`, `CARD-xxx`, media
manifest, or presentation handoff. It never creates one of those artifacts.

The replay may retain only a source locator without query or fragment, the
fixture's access timestamp, plan and registry identifiers, the source's named
short text fields, and a short team-authored summary. Every emitted short-text
record has the fixed labels `source_text_trust: untrusted_page_content` and
`instruction_handling: data_only_ignore_instructions`. Downstream consumers
must treat those fields as untrusted source data only: they are never
instructions, execution policy, evidence, a candidate, media, or
`VERIFIED` material. Its audit status is always `offline_replay_unverified`.

Raw HTML, page scripts, cookies, browser state, media, PDFs, response bodies,
page prompts, private brief text, absolute paths, and extended copied prose are
never emitted. `untrusted_page_text` exists only to prove prompt-injection
content is ignored and never changes the output contract. The same treatment
applies to prompt-injection text placed inside an otherwise allowed short-text
field.

## Inputs and results

Run locally:

```text
python scripts/execute_controlled_crawl_replay.py <plan.json> <replay.json>
```

Both inputs are local JSON. The replay input and result shapes are defined in
`controlled-crawl-replay.schema.json`. The script does not load, inspect, or
invoke Crawl4AI, Playwright, browser binaries, HTTP clients, sockets, or a
subprocess network tool. Every completed, blocked, insufficiency,
dependency-unavailable, and local-load-failure result is checked against the
`ExecutionResult` Schema before it is emitted. If an invalid plan identifier
cannot safely conform, the adapter emits a fixed schema-conforming failure and
does not echo that identifier.

`execution_mode` must be `offline_replay`. A requested live mode is blocked.
`runtime_state: unavailable` and `receipt_lock_mismatch` return a deterministic
dependency-unavailable result; the adapter never installs or repairs a runtime.

## Stop conditions

Events are the ordered prefix of pages actually attempted, not an assertion
that every planned page was attempted. A completed result must cover every
requested page in plan order. A denial, redirect, malformed response, or HTTP
denial may end at any allowed prefix and retains its specific reason code
instead of being rewritten as a page-count error. A replay that supplies an
event after a stop is blocked with `EVENT_AFTER_STOP_FORBIDDEN`; it is never
silently ignored. Responses must match the next requested page, and non-seed
pages require their named parent to have been successfully processed.

The first denial ends processing with `retry_count: 0`. The adapter returns a
safe reason code, never the page text or a sensitive URL, for robots denial,
401/403/429, login, paywall, CAPTCHA, Cloudflare challenge, explicit refusal,
malformed replay data, redirects, plan/budget/seed/field boundary failures, and
any invalid control. Redirects are never followed: cross-host or out-of-path
targets are specifically reported as `REDIRECT_OUT_OF_BOUNDARY`.

The future live adapter remains separately reviewed work. It must use the
independently locked runtime in `external-dependency-lock.json`, current human
confirmation, current robots checks, and all ADR-0006 stop conditions. This
offline contract enables none of those actions.
