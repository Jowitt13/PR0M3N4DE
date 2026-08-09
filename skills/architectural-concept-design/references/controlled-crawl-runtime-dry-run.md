# Controlled Crawl Runtime Dry-run

This contract turns an already validated controlled-crawl plan into a safe,
offline-only future invocation plan for the separately provisioned Crawl4AI
runtime. It does not install, repair, launch, or invoke Crawl4AI, Playwright,
a browser, DNS, HTTP, or a page request.

## Inputs

Run only against local JSON:

```text
python scripts/prepare_controlled_crawl_runtime_dry_run.py <dry-run-input.json>
```

The input must provide a controlled-crawl plan, `execution_mode: dry_run`, an
explicit independent runtime root, the lock version, and the installation
receipt shape from `external-dependency-lock.json`. The adapter first reuses
the controlled-crawl plan validator; no runtime-root or receipt check can turn
an invalid plan into an executable request.

After plan, mode, input-Schema, and lock validation, the adapter uses the
installer's authoritative host-platform check before it examines the runtime
root. The current locked runtime supports only `windows-x86_64`; every other
host returns `RUNTIME_PLATFORM_UNSUPPORTED` without reading the root, receipt,
or local layout. A matching platform still permits only this dry-run contract;
it does not prove that the runtime can execute.

The supplied root must be an existing absolute local directory outside the
repository and Skill. UNC paths are refused before the adapter resolves, lists,
or reads anything below them. Windows drive type is fail-closed: only an
explicit fixed local drive is accepted; remote, unknown, rootless, and
unverifiable drives are refused. Before any `resolve`, `exists`, `is_dir`, or
receipt read, the adapter uses non-following local metadata checks on every
existing component from the drive root through the target and refuses any
symlink, junction, or other reparse point. Relative paths and path escapes are
also refused. The adapter checks the root's receipt, locked
Python/Crawl4AI/Playwright/Chromium
identity, metadata hashes, browser revision, and required local runtime layout
against the existing external-dependency lock and installer receipt authority.
The layout check reads only local files: `.venv/Scripts/python.exe` must start
with the Windows `MZ` executable marker; `.venv/pyvenv.cfg` must declare the
locked Python version using either `version = 3.13.14`, uv's
`version_info = 3.13.14`, or uv's `version_info = 3.13.14.final.0`; and the
locked `crawl4ai`/`playwright` package folders and their exact `METADATA`
Name/Version records must exist. Other suffixes, malformed values, and every
other semantic version are refused. It never executes the Python file. It never
creates a root, virtual environment, receipt, browser directory, or dependency
download.

## Results

A successful `ready_dry_run` result has
`runtime_status: receipt_and_local_layout_validated_dry_run_only`. It means
only that the bounded plan, receipt, and minimal local layout agree with the
lock for a future reviewed adapter. It reports an abstract
`isolated_runtime_dry_run_only` invocation kind; it does not prove wheel
provenance, that a browser can start, that the runtime is usable, that robots
were checked, or that a source was accessed.

Results retain only safe identifiers, the locked runtime ID, control and budget
confirmation, and machine reason codes. They never retain or print a runtime
path, plan topics, URL query or fragment, cookie, credential, media locator,
shell command, environment variable, raw HTML, candidate, evidence, or
`VERIFIED` label.

Any `live`, `execute`, `browser`, or `network` mode returns
`LIVE_EXECUTION_NOT_IMPLEMENTED`. A missing or incomplete external runtime
returns `dependency_unavailable`; it is not installed or repaired. This
dry-run enables no network action and does not authorize a future request.
