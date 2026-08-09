# Normalized Brief Ledger

## Purpose

Give a human a direct, offline entry point that turns a loose project brief into
a normalized, verifiable ledger. The ledger preserves the raw human input and
classifies every known field so a later, human-authored ADR-0001 input brief can
feed the existing project-state assembly (`assemble_project_state.py`). This
entry point authors no design content and makes no design decision.

## Contracts

- Input: [`normalized-brief-ledger.input.schema.json`](normalized-brief-ledger.input.schema.json).
- Output: [`normalized-brief-ledger.output.schema.json`](normalized-brief-ledger.output.schema.json).
- Script: [`../scripts/normalize_project_brief.py`](../scripts/normalize_project_brief.py).

## Known fields

The brief accepts exactly these thirteen keys; any other key is rejected:

`project_name`, `project_location`, `site_boundary_or_redline`,
`north_orientation`, `road_edges_and_access`, `building_type`,
`target_area_or_scale`, `users`, `required_spaces`, `budget_range`,
`target_opening_date`, `design_goals`, `known_regulations_or_assumptions`.

`required_spaces` and `design_goals` are lists of text; the rest are text.

## Field status

Each field is reported as exactly one status:

- `PROVIDED`: a real value was supplied. `normalized_value` holds the trimmed
  text or list; `raw_present` is `true`.
- `UNKNOWN`: the human explicitly declared the value unknown, using the literal
  string `"UNKNOWN"` or an explicit `{ "status": "UNKNOWN" }` object.
  `normalized_value` is `null`; `raw_present` is `true`.
- `MISSING`: the key was absent. `normalized_value` is `null`; `raw_present` is
  `false`. Absence is never inferred into a real value.

A value may also be given as an explicit `{ "status": "PROVIDED", "value": ... }`
object when the literal text `"UNKNOWN"` is itself the intended value.

## Fail-closed rules

The script emits no ledger and returns a non-zero exit code when:

- an unknown top-level key is present (`BRIEF_SCHEMA_INVALID`);
- a field has the wrong type (`TYPE_ERROR` / `BRIEF_SCHEMA_INVALID`);
- an empty or whitespace-only string is used instead of the explicit `UNKNOWN`
  literal (`EMPTY_STRING_NOT_ALLOWED`);
- a status object uses a status other than `PROVIDED` or `UNKNOWN`, or declares
  `MISSING` (`ILLEGAL_STATUS`);
- a `PROVIDED` status object omits a usable value (`PROVIDED_VALUE_INVALID`);
- `project_name` is not `PROVIDED` with a real value (`PROJECT_NAME_REQUIRED`).

## Determinism and safety

- The script opens no socket and starts no subprocess.
- Output is deterministic for identical input; it records no wall-clock time and
  reports `input_hash` as the SHA-256 of the canonical raw brief.
- With `--output`, the destination is written atomically and only after full
  validation, so a failed run leaves any existing file unchanged.

## Downstream boundary

The ledger is a normalization layer only. It generates no `hypotheses`,
`options`, `decisions`, massing, plan, `SRC`, `Evidence`, `CARD`, or `VERIFIED`
content. `PROVIDED` fields become candidate facts a human authors as sourced
evidence in the ADR-0001 input brief; `UNKNOWN` and `MISSING` fields become the
missing-information register. Concept direction remains a human decision.
