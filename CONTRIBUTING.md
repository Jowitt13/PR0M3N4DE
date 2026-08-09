# Contributing to PR0M3N4DE

Thank you for your interest in PR0M3N4DE. This repository is a public
distribution of an installable, local-first architecture pre-design Skill.
Contributions are welcome where they improve clarity, correctness, or
traceability without widening what the project claims.

## Welcome contributions

- **Documentation.** Clearer explanations of the reasoning workflow,
  references, and the boundaries the project deliberately does not cross.
- **Deterministic local tools.** Improvements to the local scripts under
  `skills/architectural-concept-design/scripts/` that remain deterministic,
  typed, and reproducible from the pinned environment.
- **Contracts and schemas.** Corrections to JSON Schemas, example records,
  and contract documentation under `skills/architectural-concept-design/
  references/`, where the change preserves existing evidence labels and
  human-decision boundaries.
- **Evaluation improvements.** Better fixed-input examples and clearer
  validation criteria for the deterministic checks the package ships.

## Never submit

Do not include any of the following in a contribution:

- private project materials or real-project records;
- human-provided source material from any real engagement;
- credentials, tokens, or local configuration;
- real PPTX files or other generated deliverables;
- third-party media of any kind;
- assets whose rights have not been confirmed.

The public package excludes all third-party media by policy. Source
locators in the repository are attribution only; they are not a license,
permission, or instruction to fetch or reproduce external content.

## Change requirements

- Keep every change limited to a single, clearly described scope, and state
  in the pull request how the change was verified.
- A change to a contract, schema, or behavior boundary must come with the
  corresponding test or validation evidence, or an explicit explanation of
  why none is possible in this public distribution.
- Do not change `README.md`, `README.zh-CN.md`, `LICENSE`, `NOTICE`,
  `PUBLIC-DISTRIBUTION-MANIFEST.json`, the release archive, package
  metadata, or version numbers unless the change itself is the reviewed
  subject of the pull request.
- Do not claim capabilities that are not implemented: there is no CI in
  this public repository, no automatic release pipeline, no media rights
  clearance, and no automated design.

## Verification

This public distribution intentionally omits the development-only test and
governance sources. Contributors should verify locally with the pinned
environment, for example:

```bash
uv sync --project skills/architectural-concept-design --frozen --group test

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/check_area_schedule.py \
  <area-schedule.json>
```

Report exactly what you ran and what it printed. If no check applies, say
so; do not report checks as passed when nothing was executed.

## Pull request process

1. Open a draft pull request first and describe the scope, the reasoning,
   and the verification performed.
2. Keep changes small and reviewable; prefer several focused pull requests
   over one large one.
3. A pull request may be merged only after independent review by someone
   other than its author. Authors must not approve or merge their own
   pull requests.

Text files should be UTF-8 without BOM, LF line endings only, and free of
trailing whitespace.
