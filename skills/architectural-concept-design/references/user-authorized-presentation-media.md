# User-Authorized Noncommercial Presentation Media

> **Single authority** for the future, per-run presentation-media mode accepted
> by [ADR-0007](../../../docs/adr/0007-user-authorized-noncommercial-presentation-media.md).
> ADR-0007 is merged, but the mode is not currently operational. Until its
> separately reviewed runtime and presentation-handoff implementations exist, do not access, download,
> extract, render, or embed third-party media.

## Contents

- [Purpose and boundary](#purpose-and-boundary)
- [1. Activation gate](#1-activation-gate)
- [2. Authorization record](#2-authorization-record)
- [3. Normal-access gate](#3-normal-access-gate)
- [4. Media manifest](#4-media-manifest)
- [5. Presentation handoff](#5-presentation-handoff)
- [6. Stop conditions and prohibitions](#6-stop-conditions-and-prohibitions)

## Purpose and boundary

This optional mode serves one current project and one noncommercial project
presentation. It may support an explicitly selected image, drawing, or PDF from
one to three human-selected runtime candidates. It does not change the static
eight-field case-card JSON, the controlled local corpus, or the team-original
default in `presentation-handoff.schema.json`.

`user_authorized_noncommercial_use` records a project lead's direction about
this presentation use. It is not a license, permission, clearance, or an
ADR-0001 `VERIFIED` label. Do not represent a source with unclear rights as
licensed, cleared, authorized by its owner, or verified for reuse.

## 1. Activation gate

Do not use this mode unless all four conditions are true:

1. ADR-0007 is Accepted and merged;
2. the dedicated runtime authorization-and-manifest implementation is merged;
3. the dedicated versioned presentation-handoff adaptation is merged; and
4. the current run has a complete explicit human authorization record.

Until then, make only `team_original_diagram_only` presentation visuals and
return the normal handoff without third-party source media.

## 2. Authorization record

The implementation must validate one current record before every media action:

```json
{
  "authorization_id": "UMA-001",
  "authorized_by": "named human project lead",
  "authorized_at": "2026-07-18T12:00:00+08:00",
  "project_id": "P-001",
  "purpose": "noncommercial_project_presentation",
  "selected_candidate_ids": ["RC-001"],
  "authorization_mode": "user_directed_noncommercial_use",
  "acknowledgement": "This direction is not a license or permission claim."
}
```

The record must name one to three candidates already selected through
`explicit_human_selection`. The `authorized_by` field must name a human, not
an agent or model. A changed project, candidate set, or purpose requires a new
record. Never infer authorization from a previous deck, a generic setting, or
an agent instruction.

Use [user-authorized-media.schema.json](user-authorized-media.schema.json) and
run this deterministic, read-only command only for assets already present in a
per-run directory outside this repository:

```text
scripts/validate_user_authorized_media.py <authorization.json> <manifest.json> <candidate-set.json> --assets-root <per-run-root>
```

A passing result validates the authorization, current human candidate selection,
manifest links, safe relative paths, local SHA-256 values, and local media magic
bytes. It does not make a request, download, render, embed, or package media.

## 3. Normal-access gate

This mode does not loosen the source-access registry or ADR-0006. Before a
future media attempt, validate the selected source's registry entry, seed URL,
path boundary, robots review, terms review, request budget, and ordinary
runtime plan. On `401`, `403`, `429`, CAPTCHA, Cloudflare challenge, login,
paywall, robots denial, explicit refusal, malformed content, or an out-of-scope
redirect, stop that source and report the insufficiency.

Never use stealth, an undetected browser, proxy rotation, browser
impersonation, custom or random user agents, injected scripts, fallback fetch,
cookies, credentials, CAPTCHA solving, Cloudflare solving, login, paywall, or
robots bypass. Do not use ArchDaily or gooood automatically unless a later
reviewed registry decision explicitly allows the exact source and path.

## 4. Media manifest

Before the future presentation renderer receives a local file, validate one
manifest entry with these fields:

| Field | Required value or rule |
| --- | --- |
| `asset_id` | Stable asset ID. |
| `project_id` | Equals the authorization record's `project_id`. |
| `source_candidate_id` | One selected `RC-xxx`. |
| `source_locator` | HTTPS attribution locator. |
| `retrieved_at` | RFC 3339 timestamp with timezone. |
| `sha256` | Hash of the local asset bytes. |
| `content_type` | Observed local media type. |
| `asset_kind` | `image`, `drawing`, or `pdf`. |
| `intended_use` | `noncommercial_project_presentation`. |
| `rights_status` | `user_authorized_noncommercial_use`. |
| `user_authorization_id` | Resolves to the active authorization record. |
| `attribution_text` | Concise deck attribution. |
| `access_result` | Normal-access outcome, never a rights conclusion. |

The manifest is not the evidence ledger. Register architectural claims in
`SRC-xxx` and `E-xxx` separately, and do not make the asset or its source
`VERIFIED` merely because it was retrieved.

## 5. Presentation handoff

The future handoff adaptation must require an attribution line for every
embedded third-party asset and retain the authorization and media-manifest IDs.
It must keep the final deck scoped to the named project and project lead. A PDF
may be locally retained for the current deck only; selected pages may be
rendered for that deck, but neither the PDF, page extract, local cache, nor
source media may enter `CARD-xxx`, the local corpus, a distributable Skill
release, or a reusable media library.

The renderer remains the independently installed `ppt-master` Skill. It must
not re-search sources, change selected candidates, alter architectural evidence,
or add any asset not present in the validated manifest.

## 6. Stop conditions and prohibitions

Stop before any media action when the ADR status, implementation, authorization
record, source-access plan, candidate selection, hash, attribution, or manifest
validation is missing or invalid. Do not bulk download or package raw source
HTML, browser profiles, credentials, cookies, private paths, or source media in
Git or the release package.

Noncommercial intent never creates permission to publish the deck or the source
media publicly. Keep third-party material local to the authorized project deck
and report unclear rights as unclear.
