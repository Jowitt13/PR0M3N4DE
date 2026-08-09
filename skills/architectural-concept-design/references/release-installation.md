# Release package and clean installation

> **Single authority** for building, verifying, and clean-installing a distributable `architectural-concept-design` archive. This process packages only the existing Skill runtime. It does not install external sibling Skills, contact a network, create a Git tag, publish a GitHub Release, or generate a PPTX.

## Contents

- [Release prerequisites](#release-prerequisites)
- [Pinned Python runtime](#pinned-python-runtime)
- [Build and verify](#build-and-verify)
- [Clean install and smoke check](#clean-install-and-smoke-check)
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

## Package boundary

The archive contains only `SKILL.md`, `agents/openai.yaml`, `pyproject.toml`, `uv.lock`, and required `references/`, `scripts/`, and `assets/` resources. The Crawl4AI project definition, lock, and browser metadata under `references/crawl4ai-runtime/` are installation metadata only; they do not contain or install the external runtime as part of release packaging. The archive excludes repository governance, tests, fixtures, caches, virtual environments, browser binaries, `.qoder/`, local Feishu configuration, credentials, temporary outputs, and source history.
