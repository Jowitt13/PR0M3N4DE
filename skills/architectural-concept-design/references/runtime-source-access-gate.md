# Runtime Source Access Gate

Use this reference before every automated runtime request under ADR-0005. The authoritative allowlist is [source-access-registry.json](source-access-registry.json); this file defines how the local gate executes it.

## Boundary

`scripts/check_source_access.py` only reads local JSON and emits a deterministic decision. It does not install a dependency, resolve DNS, send HTTP, follow redirects, search, fetch, create a candidate, or register `SRC-xxx` / `E-xxx` evidence.

The caller must stop on `BLOCKED`. `REQUEST_READY` means only that the supplied plan conforms to the local registry contract. It is not a provider authorization, a rate-limit reservation, permission to reproduce media, or permission to ignore a later `401`, `403`, `429`, login, paywall, CAPTCHA, Cloudflare challenge, redirect, or explicit denial.

## Request-plan contract

Pass one UTF-8 JSON object to the gate:

```json
{
  "domain": "openverse.org",
  "method": "GET",
  "endpoint": "https://api.openverse.org/v1/images",
  "operation": "metadata_search",
  "expected_response_kind": "json_api",
  "query_parameters": [{"name": "q", "value": "privacy-safe terms"}],
  "manual_rate_limit_confirmation": {
    "confirmed": true,
    "request_readiness": "manual_current_rate_limit_confirmation_required",
    "confirmed_by": "named human reviewer",
    "confirmed_at": "2026-07-16T12:00:00Z",
    "confirmation_reference": "current provider conditions checked for this run"
  },
  "request_controls": {
    "follow_redirects": false,
    "html_page_scrape": false,
    "media_download": false,
    "asset_scrape": false,
    "bulk_download": false,
    "stealth": false,
    "browser_impersonation": false,
    "captcha_solving": false,
    "cloudflare_solving": false,
    "proxy_rotation": false,
    "curl_impersonate": false
  }
}
```

- `domain` must exactly match one registry entry. Subdomains, aliases, redirects, and fuzzy matches are not normalized.
- `endpoint` must be HTTPS, credential-free, port-free, query-free, fragment-free, and inside one exact approved endpoint path prefix. Put URL parameters only in `query_parameters`.
- `method`, `operation`, and `expected_response_kind` must exactly appear in the selected source contract.
- Include every registry `required_query_parameters` pair. Do not put credentials, cookies, tokens, or private brief text into the plan; later clients obtain credentials from their own secret store after this gate succeeds.
- `manual_rate_limit_confirmation` records a run-specific human assertion. The gate verifies its structure and RFC 3339 timestamp but cannot independently verify a provider's live limits or identity.
- Every `request_controls` value is required and must be `false`.

For a POST source, add a `post_body` string. It must contain every literal marker from the registry `post_request_contract.required_body_markers`. The gate never echoes the body. A POST body marker is not a URL query parameter.

## Invocation and decision

```text
python scripts/check_source_access.py request-plan.json
```

The gate always loads its sibling `references/source-access-registry.json`; callers cannot substitute another allowlist at runtime. The result contains only safe audit metadata: decision, source domain/status, safe endpoint, method, operation, expected response kind, required parameter names, and machine-readable errors. It deliberately omits query values, the POST body, and the confirmation text.

| Decision | Exit code | Required caller action |
|---|---:|---|
| `REQUEST_READY` | 0 | A separately installed, approved client may issue exactly this one structured-data request, then apply provider response and rights gates. |
| `BLOCKED` | 2 | Make no request. Return the errors or switch to permitted manual review/user material. |
| input/registry load failure | 3 | Correct local input or registry; make no request. |

After any actual request, stop rather than bypass access controls. Later tasks must separately implement candidate normalization, the six-candidate gate, one-to-three human selection, runtime `SRC-xxx` / `E-xxx` registration, and per-item media rights review.
