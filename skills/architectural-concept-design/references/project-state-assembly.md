# Project state assembly

Use this local-only entry point when a schema-valid brief already exists and a
designer or agent has explicitly drafted the first hypotheses, concept options,
and comparison criteria. It converts those two local JSON documents into the
existing [`output.schema.json`](output.schema.json) state package. It is a
deterministic assembly aid, not a design generator.

## Boundary

The input brief remains authoritative for `project`, `sources`, `evidence`,
`constraints`, `program.spaces`, and `relations`. The assembly draft supplies
only already-authored output content: `hypotheses`, at least two `options`,
`criteria`, and optional dependency and deliverable records. The resulting
state package always has an empty `decisions` array and therefore remains
waiting for an explicit human design decision.

The assembler:

- calculates the existing ADR-0001 input hash rather than accepting one from a
  caller;
- preserves input source and evidence records without changing labels or
  claims;
- uses only the caller-supplied `generated_at` value and never reads a clock;
- validates the resulting document through `validate_state.py`; and
- writes no output at all when either the draft or resulting state is invalid.

It never creates hypotheses or options, fills missing site/area/regulatory
information, ranks or selects an option, performs stale propagation, accesses a
network, starts a subprocess, invokes a runtime, fetches precedents, or creates
`CARD-`, `SRC-`, `E-`, media, or PPTX artifacts.

## Assembly draft

Shape a local draft to
[`project-state-assembly.schema.json`](project-state-assembly.schema.json).
This draft is not a JSON state package and must not be delivered as one. Its
`decision_state` is always `AWAITING_HUMAN_DESIGN_DECISION`; it intentionally
has no `decisions` field. Detailed `H-`, `O-`, `K-`, `DEP-`, and `A-` field
checks are performed against the existing output contract after assembly.

Every referenced `E-`, `S-`, `C-`, `H-`, `O-`, or `K-` ID must resolve through
the supplied brief or an assembled record. Do not add inferred source facts or
replace a `PROVIDED` or `VERIFIED` evidence item in this entry point.

## Command

Run only after the brief ledger and first concept drafts are complete:

```text
uv run python skills/architectural-concept-design/scripts/assemble_project_state.py \
  <input.json> <assembly-draft.json> --output <state-package.json>
```

The optional `--output` file is written atomically as UTF-8 only after all
validation succeeds. Without `--output`, the command writes the conforming
state package to stdout. In either case, run the existing validator again before
delivery:

```text
uv run python skills/architectural-concept-design/scripts/validate_state.py \
  validate <input.json> <state-package.json>
```

Continue with the site, program, grid/core, and option-comparison references.
Record a `D-xxx` only through the separate explicit human-decision workflow;
the assembly draft cannot bypass that gate.
