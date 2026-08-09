# Controlled Single-page Live Canary

This contract is the narrow bridge after ARCH-044 local runtime dry-run. It can attempt exactly one rendered page only through an injected, reviewed transport. The CLI provides no transport and returns `LIVE_CANARY_TRANSPORT_NOT_CONFIGURED`; it never starts Crawl4AI, Playwright, a browser, DNS, or HTTP itself.

The adapter validates the nested plan, requires explicit per-run human confirmation and `live_enabled: true`, then reuses ARCH-044 receipt/layout preflight. It narrows DIP to its exact HTTPS seed, one page, `depth: 0`, no parent, and the reviewed 3000 ms delay. A later transport must first obtain current robots and terms observations, then make at most one normal-browser attempt. It must not follow redirects or retry.

Any unavailable or denied current condition, runtime failure, HTTP 401/403/429, login, paywall, CAPTCHA, Cloudflare, refusal, redirect, malformed observation, or field/budget boundary ends the run. No fallback fetch, custom/random user agent, script injection, cookie/credential/login import, stealth, proxy, bypass, media/PDF/asset download, raw HTML/DOM/script retention, or multi-page access is allowed.

Only the five DIP allowlisted short text fields may be emitted. Every record is `untrusted_page_content` with `data_only_ignore_instructions`, never `VERIFIED`. Records contain no HTML, DOM, script, cookie, browser state, screenshot, path, private topic, query, fragment, media, candidate, evidence, or presentation artifact. This status is neither a license nor clearance.

ARCH-045 implements and tests this boundary only. A human-directed future run needs a separately provisioned Windows runtime and reviewed injected transport; it is not performed by this task.
