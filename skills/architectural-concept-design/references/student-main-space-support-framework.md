# Student Main Space, Supporting Space, and Sequence Framework

## Purpose

This stage lets a student make the next human design move after an ARCH-108
schematic-plan state handoff: distinguish the spaces that carry the main
activity from supporting and shared-service spaces, state how support is
intended to work, and describe a small number of spatial sequences.

It is a traceable organization record, not automated planning. It does not
rate a room, choose the main space, make a plan drawing, or turn an intention
into a measured environmental or performance fact.

## Inputs and confirmation

The builder accepts the complete ARCH-097~108 chain and reuses the public
ARCH-108 `validate_schematic_plan_state_handoff` entry. The student then writes
one closed draft bound to the whole handoff through canonical JSON plus newline
SHA-256.

Before build, a human must confirm the pending draft with exactly four fields:
`action`, `confirmed_by`, `confirmed_at`, and
`pending_main_space_support_draft_sha256`. The action is fixed as
`CONFIRM_STUDENT_MAIN_SPACE_SUPPORT_DRAFT`; the label must identify a human,
the time must be timezone-qualified RFC 3339, and the hash binds the entire
pending document. The machine never invents confirmation data or reads a
system clock.

## What the student writes

Every space in the reviewed handoff appears exactly once in `space_roles` as a
`main_space`, `supporting_space`, or `shared_service`, with a human note.
There must be at least one main space.

Each supporting or shared-service space must be linked to at least one real
main space. A link says only `direct_support`, `shared_support`, or
`buffered_transition` and carries the student's note. It is not a claimed
distance, geometric adjacency, code separation, or mandatory layout rule.

Optional sequence intentions name real spaces on one existing level, in the
student's written order. `active_to_quiet`, `open_to_contained`,
`public_to_private`, and `flexible_to_defined` are intentions rather than site,
noise, privacy, lighting, or performance measurements. The builder neither
reorders nor completes them.

An unresolved record may name real spaces and a reason. It cannot disappear
from the confirmed framework and changes the next action to
`resolve_main_space_support_gaps`.

## Output and validation

`build_student_main_space_support.py confirm` converts only a valid pending
draft into its bound confirmed form. `build` projects a closed JSON framework;
`validate` reruns the entire upstream chain, validates the confirmation and
semantics, rebuilds the expected framework, and compares canonical JSON plus
newline bytes exactly.

The framework exposes human-readable names and notes but no internal IDs,
hashes, scores, winner, best option, or recommendation. It carries at most the
three clarification questions already present in the reviewed handoff.

## Explicit boundaries

This stage decides no rectangle, coordinate, orientation, entrance, corridor,
wall, door, column, stair, toilet, total plan, massing, structural system,
regulation, cost, performance, environmental conclusion, constructibility, or
professional approval. It produces no drawing, image, HTML, PPTX, or model.

It does not parse DOC, DOCX, PDF, HTML, image, or OCR input; it opens no
socket or browser and imports no Crawl4AI, Playwright, PowerPoint, PPTX, or
generic project-state package.

## Error codes

| Code | Meaning |
| --- | --- |
| `MAIN_SPACE_SUPPORT_DRAFT_SCHEMA_INVALID` | The closed draft is malformed. |
| `MAIN_SPACE_SUPPORT_DRAFT_NOT_CONFIRMED` | The draft remains pending. |
| `MAIN_SPACE_SUPPORT_DRAFT_CONFIRMATION_INVALID` | The human confirmation record is invalid. |
| `MAIN_SPACE_SUPPORT_DRAFT_HASH_MISMATCH` | The confirmation does not bind this exact pending draft. |
| `MAIN_SPACE_SUPPORT_SOURCE_HANDOFF_MISMATCH` | The draft does not bind the supplied state handoff. |
| `MAIN_SPACE_SUPPORT_ROLE_INVALID` | A role is unknown, duplicated, missing, or lacks a main space. |
| `MAIN_SPACE_SUPPORT_RELATION_INVALID` | A support link is invalid, duplicated, or leaves a supporting/shared space unlinked. |
| `MAIN_SPACE_SUPPORT_SEQUENCE_INVALID` | A sequence uses an unknown level or space, crosses levels, or duplicates a sequence. |
| `MAIN_SPACE_SUPPORT_UNRESOLVED_INVALID` | An unresolved record is duplicate or names an unknown space. |
| `STUDENT_MAIN_SPACE_SUPPORT_SCHEMA_INVALID` | A supplied output violates its closed schema. |
| `STUDENT_MAIN_SPACE_SUPPORT_CONTENT_MISMATCH` | A valid chain was supplied with a non-projected output. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written without clobbering existing data. |

All ARCH-097~108 errors propagate unchanged.
