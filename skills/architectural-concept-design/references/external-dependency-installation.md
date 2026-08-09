# Explicit external dependency bootstrap

> **Single authority** for installing the independently maintained `ppt-master`
> sibling Skill and the optional isolated Crawl4AI runtime described by
> [external-dependency-lock.json](external-dependency-lock.json). This reference
> does not authorize source discovery, crawling, media download, renderer
> invocation, candidate creation, or PPTX generation.

## Contents

- [Purpose and boundary](#purpose-and-boundary)
- [Locked components](#locked-components)
- [Explicit installation workflow](#explicit-installation-workflow)
- [Integrity, receipt, and idempotence gates](#integrity-receipt-and-idempotence-gates)
- [Operational limits](#operational-limits)

## Purpose and boundary

Use this bootstrap only when a human explicitly requests installation. Normal
use of `architectural-concept-design` never downloads or installs an external
dependency. The bootstrap keeps the presentation Skill under a human-selected
`--skills-root`; it provisions Crawl4AI only under a separate human-selected
`--runtime-root`. Neither source tree, Python package, virtual environment, nor
browser binary is vendored into this Skill.

The optional runtime is not a permission to crawl. Until the later registry,
plan-validator, adapter, and minimal-live-canary tasks are merged, a successful
receipt only means that the locked runtime is available for a future approved
adapter. It does not change the source registry or authorize a request.

## Locked components

`external-dependency-lock.json` is the sole authority for the Git identity of
`ppt-master`, the Crawl4AI distribution version and wheel hash, Python version,
Playwright wheel hash, Chromium revision, frozen `uv.lock`, exact installation
commands, receipt shape, and prohibited runtime capabilities.

| Component | Installation state | Purpose |
| --- | --- | --- |
| `ppt-master` | required sibling Skill | Independent editable-PPTX layout and export Skill; bootstrap never invokes it. |
| `crawl4ai-runtime` | explicit opt-in isolated runtime | Future controlled HTML rendering/extraction runtime under ADR-0006; bootstrap never invokes a crawl. |

The frozen metadata under `references/crawl4ai-runtime/` is release-packaged so
an installed Skill can reproduce the reviewed environment. It contains only a
project definition, `uv.lock`, browser-lock metadata, and an upstream browser
metadata snapshot; it contains no package source, virtual environment, browser
binary, cookie, credential, page content, or source media.

The runtime currently supports `windows-x86_64` only. A new platform, Python
version, package version, browser revision, or browser binary update requires a
reviewed lock change, compatibility tests, regression evaluation, and a new
receipt.

## Explicit installation workflow

First inspect the deterministic local plan. It makes no network request and
writes no target files:

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/bootstrap_external_skills.py \
  --skills-root <target-skills-root> --dry-run
```

To include the separately provisioned crawler runtime in the plan, name a
separate empty target:

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/bootstrap_external_skills.py \
  --skills-root <target-skills-root> \
  --runtime-root <target-crawl4ai-runtime-root> \
  --include-crawl4ai-runtime --dry-run
```

After a human reviews the exact IDs, commits, package hashes, target paths,
licenses, and commands, repeat the same command with
`--apply-reviewed-plan`:

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/bootstrap_external_skills.py \
  --skills-root <target-skills-root> \
  --runtime-root <target-crawl4ai-runtime-root> \
  --include-crawl4ai-runtime --apply-reviewed-plan
```

For the optional runtime only, the reviewed apply sequence is exactly:

```text
uv python install 3.13.14
uv sync --project <runtime-root> --python 3.13.14 --frozen --no-dev
<runtime-root>/.venv/Scripts/python.exe -m playwright install chromium
```

The bootstrap executes this sequence only after the explicit apply flag. It
sets `PLAYWRIGHT_BROWSERS_PATH` to the isolated runtime root, checks the
installed Playwright `browsers.json` SHA-256 and Chromium revision `1228`, then
writes the receipt. It never uses `latest`, a moving branch, a global Python
environment, a global browser cache, or a browser selected by the system.

## Integrity, receipt, and idempotence gates

The bootstrap stops before installation when the lock is malformed, a path is
unsafe, a required runtime capability prohibition is missing, the frozen
metadata disagrees with the lock, the target platform is not supported, or a
target already exists without the exact matching receipt.

For `ppt-master`, the bootstrap creates a temporary local Git repository and
proves the exact locked SHA is a local commit before any detached checkout. If
the pin is absent, it performs one bounded acquisition only against the locked
remote and locked SHA: `fetch --no-tags --depth=1 origin <locked-sha>`. It does
not fetch a default branch, tag, arbitrary revision, or full history. It proves
the pin again with local Git object validation before checkout; a timeout,
acquisition failure, or non-commit object returns a redacted machine code and
stops before copying a target, creating a receipt, or provisioning the runtime.
After verification, it checks out the exact commit, verifies the Git tree and
locked blobs, then atomically copies only the declared Skill directory,
`UPSTREAM_LICENSE`, and manifest.

For Crawl4AI, the bootstrap copies only the three reviewed lock metadata files
to a temporary runtime root, provisions there, and verifies the exact browser
metadata and installed Chromium directory before committing the root and then
finalizing `.architecture-pre-design-crawl4ai-runtime.json`. On an exact
receipt match, it reports `already_installed` and does not run Git, `uv`, or
Playwright again.

Before the staged runtime is committed, the bootstrap rechecks that the parent,
staging directory, and absent target are absolute local paths on the approved
fixed drive and contain no UNC, symlink, junction, or reparse-point traversal.
It tracks only the process trees that it starts for the three reviewed runtime
commands; if any owned child remains active, it blocks the commit without
scanning, stopping, or affecting unrelated system processes. The staging root
contains no receipt. Only after its atomic root commit succeeds does the
bootstrap atomically finalize the receipt in the formal runtime root.

If that root commit receives exactly one transient Windows access-denied
`WinError 5`, the bootstrap makes at most one immediate **commit-only** retry
of the same verified staging directory. It never reruns `uv`, Playwright,
downloads, path selection, or a fallback copy/move during this retry. Any other
commit failure, or a second `WinError 5`, returns the redacted machine code
`RUNTIME_ATOMIC_COMMIT_FAILED` with only the commit stage, attempt count, and
native error class. A failed commit leaves no formal target or receipt.

The runtime receipt records no secret, local brief, source response, cookie,
browser profile, absolute path, or generated presentation. It records only the
reviewed runtime identity, lock hashes, browser revision, prohibited capability
set, and upstream license/attribution requirement.

## Operational limits

Do not enable an undetected browser mode, stealth integration, proxy
configuration, custom or randomized user agent, browser-script injection,
fallback fetch function, cookie import, credentials or login state, CAPTCHA
solving, Cloudflare solving, or browser impersonation. Do not add API keys,
cookies, local absolute paths, or private brief data to the lock, receipts, or
logs.

The package dependency graph may contain libraries with broader capability
surfaces; installing a pinned dependency does not authorize its use. A later
adapter must enforce ADR-0006's normal-browser, robots, seed/path, budget, and
stop-on-denial contracts before it can make any request. ArchDaily and gooood
remain manual-only unless a separately reviewed registry decision changes that
status.

Crawl4AI's upstream Apache-2.0 license includes an attribution notice. Keep
that notice in release and runtime documentation whenever this runtime is
distributed or publicly described.
