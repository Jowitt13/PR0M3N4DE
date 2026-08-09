# Brief and evidence protocol

[evidence.schema.json](evidence.schema.json) is the sole field-level data contract for Source and Evidence Record definitions. This document describes evidence label semantics, intake workflow, and human judgment guidance only. Field requirements, types, patterns, and conditional constraints are enforced by evidence.schema.json, not by this document.

## Intake ledger

Capture the following before developing an option:

- project purpose, users, building type, deliverables, and decision horizon;
- site location, boundary, access, orientation, climate observations, context, and available source material;
- program spaces, target areas, adjacency, occupancy, operations, and special constraints;
- project constraints: time, budget statement if provided, height, accessibility, heritage, risk, and jurisdiction;
- missing inputs and their impact on the current proposal.

Ask only questions that would change a major decision. Continue with a clearly labelled assumption when an answer is unavailable.

## Evidence labels

| Label | Meaning | Use |
| --- | --- | --- |
| `PROVIDED` | Supplied in the current brief or an attached source. | Quote or paraphrase with source ID. |
| `VERIFIED` | Confirmed against a recorded authoritative source. | Record source, retrieval date, and verification scope. |
| `INFERRED` | Reasoned from evidence. | State the evidence and inference rule. |
| `ASSUMED` | Temporary working premise because information is missing. | State owner, impact, and validation action. |
| `PROPOSED` | Design move or recommendation. | Present alternatives and invite a human decision. |

Never change a label without recording why. A regulatory claim also requires jurisdiction, edition, clause, source URL or document identifier, retrieval date, and verification status.

## Constraint IDs

Use stable IDs: `C-001` for constraints, `S-001` for spaces, `R-001` for relations, `O-001` for options, `D-001` for decisions, and `A-001` for deliverables. Keep an ID when wording changes; mark it stale instead of silently replacing its downstream effects.
