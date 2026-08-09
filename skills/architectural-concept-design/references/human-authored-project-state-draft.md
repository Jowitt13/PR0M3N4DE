# Human-authored project-state draft gate

Use this local-only gate after ARCH-080 has produced a normalized-brief human
assembly handoff, and before ARCH-078 creates a state package.

## Human responsibility

A human, not an agent, authors three separate local JSON documents:

1. an ADR-0001 input brief conforming to `input.schema.json`;
2. an ARCH-078 assembly draft conforming to
   `project-state-assembly.schema.json`; and
3. a declaration conforming to
   `human-authored-project-state-draft.schema.json`.

The declaration binds its handoff through a canonical SHA-256, records a
caller attestation, and resolves every handoff `UNKNOWN` or `MISSING` todo in
the exact handoff order. `HUMAN_PROVIDED` means only that the human caller
supplied information; it is not `VERIFIED`, an identity check, a permission
claim, or a regulatory conclusion.

The declaration intentionally carries no brief, source, evidence, constraint,
relation, program-space, hypothesis, option, criterion, dependency,
deliverable, or decision content. Those records stay in the separate two
human-authored documents. It is not a direct input to
`assemble_project_state.py`.

## Local validation

Run this command before ARCH-078 assembly:

```text
uv run python skills/architectural-concept-design/scripts/validate_human_authored_project_state_draft.py \
  <handoff.json> <declaration.json> <input.json> <assembly-draft.json>
```

The gate validates the ARCH-080 handoff schema and semantics, its canonical
hash binding, the declaration, exact todo reconciliation, and the supplied
input/draft pair through the existing ARCH-078 assembly logic in memory. It
does not write a state package, invent project content, resolve missing
information, issue a decision, access a network, start a subprocess, or
create `SRC`, `Evidence`, `CARD`, `Candidate`, `VERIFIED`, media, or PPTX
artifacts.

On success, the command prints only a machine-readable readiness receipt. A
human may then invoke `assemble_project_state.py` separately. On any failed
gate, it returns non-zero and prints no state package.
