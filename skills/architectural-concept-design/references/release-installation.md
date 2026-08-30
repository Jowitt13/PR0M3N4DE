# Release package and clean installation

> **Single authority** for building, verifying, and clean-installing a distributable `architectural-concept-design` archive. This process packages only the existing Skill runtime. It does not install external sibling Skills, contact a network, create a Git tag, publish a GitHub Release, or generate a PPTX.

## Contents

- [Release prerequisites](#release-prerequisites)
- [Pinned Python runtime](#pinned-python-runtime)
- [Build and verify](#build-and-verify)
- [Checksum sidecar](#checksum-sidecar)
- [Clean install and smoke check](#clean-install-and-smoke-check)
- [Installed student workflow smoke](#installed-student-workflow-smoke)
- [Cross-agent discovery contracts](#cross-agent-discovery-contracts)
- [Package boundary](#package-boundary)

## Release prerequisites

Build a release only from a reviewed, merged commit with successful CI and the fixed evaluation suite. Supply the exact source commit and an explicit RFC 3339 build time; the builder never reads the system clock. The generated manifest records the Skill SemVer from `pyproject.toml`, source commit, build time, and every packaged file's relative path, byte size, and SHA-256.

## Pinned Python runtime

`pyproject.toml` and `uv.lock` beside `SKILL.md` are the sole runtime-environment authority. They pin Python 3.13 and the deterministic validator dependencies. Test-only dependencies remain in the `test` group and are not required for ordinary installed Skill use.

Prepare the locked environment before local validation:

```text
uv sync --project skills/architectural-concept-design --frozen --group test
```

## Build and verify

Build outside the source Skill directory. Reusing the same source commit and build time produces byte-identical output.

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/release_skill_package.py build \
  --output <release-directory>/architectural-concept-design-<version>.zip \
  --source-commit <full-40-character-git-sha> \
  --build-time <RFC-3339-timestamp>

uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/release_skill_package.py verify \
  --archive <release-directory>/architectural-concept-design-<version>.zip
```

## Checksum sidecar

The authoritative archive checksum entry is the release packager itself; never treat
shell-specific checksum output as the release contract. Write and verify the canonical
sidecar `<archive-name>.sha256` (UTF-8, exactly one LF-terminated line `<lowercase-sha256>  <archive filename>`):

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/release_skill_package.py checksum write \
  --archive <release-directory>/architectural-concept-design-<version>.zip

uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/release_skill_package.py checksum verify \
  --archive <release-directory>/architectural-concept-design-<version>.zip
```

Verification binds the sidecar to the archive's raw bytes and filename and fails closed on
tampered bytes, a wrong filename, a wrong hash, extra fields, CRLF, missing LF, non-UTF-8
content, a missing sidecar, or a missing archive. Neither operation reads the system clock or
contacts a network.

## Clean install and smoke check

Install only into an empty or manifest-identical sibling location. A conflicting existing Skill is never overwritten.

```text
uv run --project skills/architectural-concept-design --frozen python \
  skills/architectural-concept-design/scripts/release_skill_package.py install \
  --archive <release-directory>/architectural-concept-design-<version>.zip \
  --skills-root <clean-codex-skills-root>

uv sync --project <clean-codex-skills-root>/architectural-concept-design --frozen --no-group test
```

The release test suite performs this clean install in a temporary directory, checks the installed manifest byte-for-byte, and runs the installed deterministic area-schedule CLI on an anonymous temporary input. Run the external-sibling bootstrap separately and only after a human has reviewed its dry-run plan.

## Installed student workflow smoke

Verification archives are temporary evidence: they are built in a temporary directory from the exact task head with an explicit fixed RFC 3339 build time, never read the system clock, and are never committed as ZIP, manifest, receipt, or installed directory. The Skill version in the manifest always comes from the current `pyproject.toml`; building a verification archive is not a release action and creates no release artifact. A release-candidate verification likewise creates no Git tag, GitHub Release, release asset, or Feishu `skill-released` record; those irreversible actions happen only after the candidate PR is independently reviewed and merged and a human grants separate release authorization, following the post-merge plan in [docs/releases/architectural-concept-design-v0.2.0-release-notes.md](../../../docs/releases/architectural-concept-design-v0.2.0-release-notes.md).

The ARCH-119 installed smoke generates the anonymous ARCH-097~111 chain checkpoints in the parent test process, writes them into a temporary chain directory, and runs one isolated worker subprocess (`python -I`, cleared `PYTHONPATH`, working directory outside the source repository) whose Skill imports come only from the installed root. It proves, from the installed package: the ARCH-111 final validator recursively re-validates the whole ARCH-097~110 upstream chain (never a shallow schema check); the installed ARCH-111 builder reconstructs the final handoff byte-for-byte against the real checkpoint; one tampered upstream document fails closed with the original upstream error codes and writes no output; and the installed ARCH-114 manual-design handoff card renderer stays stdout-only and keeps the human manual-design boundary. The worker reports `INSTALLED_SOURCE_PATH_LEAK` whenever a key module resolves outside the installed root. The worker lives under `tests/` and never ships in the archive.

## Cross-agent discovery contracts

`scripts/verify-cross-agent-installation.mjs` is a read-only, stdout-only, machine-readable contract verifier. For a Codex-style skills root it checks the exact skill directory name, the `SKILL.md` frontmatter (name equals the directory name, non-empty description, no absolute paths), a parseable `agents/openai.yaml` carrying `display_name`, `short_description`, and a `default_prompt` referencing `$architectural-concept-design`, every local `SKILL.md` route target inside the package, and manifest alignment when a release manifest is present. Repository-context routes using `../` are reported separately; they are repository routes, not installed-package routes. A passing check declares `CODEX_SKILL_DISCOVERY_CONTRACT_VALID` only and never claims a real Codex client restarted or actually triggered the Skill. For the DeepSeek path it checks that `agents/deepseek/BOOTSTRAP.md` exists, keeps the fixed governance statements, and only references repository files that really exist; a passing check declares `DEEPSEEK_BOOTSTRAP_CONTRACT_VALID` only and never claims the DeepSeek model understood, loaded, or executed the bootstrap. Both agents read the same product route and evidence policy; there is never a second product contract.

## Package boundary

The archive contains only `SKILL.md`, `agents/openai.yaml`, `pyproject.toml`, `uv.lock`, and required `references/`, `scripts/`, and `assets/` resources. The Crawl4AI project definition, lock, and browser metadata under `references/crawl4ai-runtime/` are installation metadata only; they do not contain or install the external runtime as part of release packaging. The archive excludes repository governance, tests, fixtures, caches, virtual environments, browser binaries, `.qoder/`, local Feishu configuration, credentials, temporary outputs, and source history.
