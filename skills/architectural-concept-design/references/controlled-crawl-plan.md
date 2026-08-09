# Controlled Crawl Plan

Use this contract only for an exact `controlled_crawl_allowed` source in the
authoritative [source-access registry](source-access-registry.json). Reviewed
records exist only for the exact domains listed there. A valid local plan still cannot cause a network request: it requires current human confirmation, current denial checks, and a later separately reviewed adapter.

## Boundary

The plan is a finite local declaration. It is not a search engine, browser
profile, request log, downloaded page, candidate set, media manifest, or
permission to access a source. It carries only privacy-safe discovery topics;
never place a full private brief, attachment content, credential, cookie, query
secret, or media locator in it.

Validate a plan before a later Crawl4AI adapter is allowed to open a page:

```text
python scripts/validate_controlled_crawl_plan.py controlled-crawl-plan.json
```

The validator always loads its sibling Schema and source-access registry. It
does not accept replacement authorities, resolve DNS, read robots.txt, launch a
browser, make a request, or mutate the plan.

## Required registry contract

A source is eligible only when its exact registry record has status
`controlled_crawl_allowed` and a `controlled_crawl` object with:

- exact HTTPS `seed_urls` and same-host non-wildcard `allowed_path_prefixes`;
- positive `max_pages_per_run` and `minimum_delay_ms` budgets, plus a
  non-negative `max_depth`; `max_depth: 0` permits only an exact seed page and
  rejects every child page;
- a non-empty allowlist of short metadata/text fields; and
- a machine-checked `rendered_short_text_extraction` object that requires only
  approved-plan pages and normal browser rendering, permits only the named
  short fields, and sets raw HTML collection/retention/output, page-script,
  cookie, browser-state, and media retention to `false`; and
- the full ADR-0006 prohibition set, with raw HTML, media, asset, and bulk
  collection or retention remaining forbidden.

`manual_or_discovery_only`, `api_allowed`, `automated_access_allowed`,
`blocked`, `future_scope`, unregistered domains, ArchDaily, and gooood cannot
form a controlled-crawl plan.

## Plan rules

- The recorded registry version, source domain, delay, source seed, page count,
  depth, parent chain, host, and path prefix must match the reviewed registry.
- A depth-zero page is an exact registered seed and has `parent_page_id: null`.
  A deeper page must name an earlier page one depth closer to the seed.
- The run confirmation names a human, has an RFC 3339 timestamp, and records
  only that current conditions were reviewed for this bounded run.
- `html_page_scrape: false` prohibits generic webpage scraping and any raw HTML
  collection, retention, or output. The registry's separate rendered-short-text
  contract is the only extraction boundary: a future adapter may read named
  short fields after normal rendering of an approved plan page, and may not
  retain raw HTML, scripts, cookies, browser state, or media. It is not a
  request authorization.
- All request-control fields are explicitly `false`: `follow_redirects`,
  `html_page_scrape`, custom/random user agents, injected browser scripts,
  fallback fetch, cookie import, credentials, login state, media download,
  asset scrape, bulk collection, raw HTML retention, stealth, browser
  impersonation, CAPTCHA/Cloudflare solving, proxy rotation, and
  `curl-impersonate`.
- A later adapter must stop a source on robots denial, `401`, `403`, `429`,
  login, paywall, CAPTCHA, Cloudflare challenge, malformed content, explicit
  refusal, or an out-of-boundary redirect. It must return an insufficiency
  record rather than retrying or fabricating a candidate.

## Handoff boundary

Passing this validator does not install or invoke Crawl4AI and does not make a
request. A later reviewed adapter may use only the isolated locked runtime from
`external-dependency-lock.json`, after current human confirmation and current
robots/denial checks, then retain only the approved short fields needed for
candidate normalization. It must never retain source HTML, page scripts,
browser storage or state, cookies, credentials, images, drawings, PDFs, or a
reusable media cache.
