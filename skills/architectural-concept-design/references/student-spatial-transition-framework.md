# Student Spatial Hierarchy, Openness, Enclosure, and Transition Framework

## Purpose

This stage gives a student a controlled place to record spatial transition
intentions after the ARCH-109 main-space-support framework is complete. The
already human-authored roles remain the visible spatial hierarchy. The student
then states how each grounded same-level pair should be understood in a
sequence: gradual opening, gradual enclosure, buffered transition, interwoven
access, or remaining independent.

This is a traceable intention record, not automatic planning. A gradual or
buffered transition is not a dimension, a geometric gradient, a visual claim,
or a performance result.

## Inputs and confirmation

The builder accepts the full ARCH-097~109 chain and uses the public ARCH-109
`validate_main_space_support_framework` entry. A non-empty ARCH-109 unresolved
list blocks this stage before the new draft is considered.

The student writes one closed draft bound to the complete ARCH-109 framework
with canonical JSON plus newline SHA-256. Before build, a human confirms the
pending draft with exactly `action`, `confirmed_by`, `confirmed_at`, and
`pending_spatial_transition_draft_sha256`. The action is
`CONFIRM_STUDENT_SPATIAL_TRANSITION_DRAFT`; the label must identify a human and
the time must be timezone-qualified RFC 3339. The machine never generates a
confirmation or reads a system clock.

## What the student writes

The builder derives the eligible pair set, without inventing it, from real
same-level consecutive entries in ARCH-109 sequence intentions and from
same-level main/support links. Each derived unordered pair appears exactly
once either as a `transition_pattern` or as an explicit unresolved item.

The direction recorded in `from_space_name` and `to_space_name` stays the
student's wording. `gradual_opening` and `gradual_enclosure` communicate only
that written order. `buffered_transition`, `interwoven_access`, and
`remain_independent` do not create a corridor, partition, opening, distance,
or adjacency requirement. The builder never chooses a pattern, reverses a
pair, fills a missing transition, or converts an unresolved item into a
resolved one.

## Output and validation

`build_student_spatial_transition.py confirm` binds only a valid pending draft.
`build` projects the hierarchy from ARCH-109 and the student's transitions;
`validate` reruns the whole upstream chain, validates the new draft, rebuilds
the expected framework, and compares canonical JSON plus newline bytes.

The student view exposes readable names, roles, notes, patterns, and reasons.
It excludes internal identifiers, hashes, scores, winner/best language, and
any automatic choice. It preserves at most the three questions already in the
reviewed handoff.

## Explicit boundaries

This stage decides no coordinate, rectangle, size, orientation, entrance,
corridor, wall, door, column, stair, toilet, total plan, massing, structural
system, regulation, cost, performance, environmental conclusion,
constructibility, or professional approval. It produces JSON only: no drawing,
image, HTML, PPTX, or model.

It parses no DOC, DOCX, PDF, HTML, image, or OCR input. It opens no socket or
browser and imports no Crawl4AI, Playwright, PowerPoint, PPTX, or generic
project-state package.

## Error codes

| Code | Meaning |
| --- | --- |
| `SPATIAL_TRANSITION_DRAFT_SCHEMA_INVALID` | The closed draft is malformed. |
| `SPATIAL_TRANSITION_DRAFT_NOT_CONFIRMED` | The draft remains pending. |
| `SPATIAL_TRANSITION_DRAFT_CONFIRMATION_INVALID` | The human confirmation record is invalid. |
| `SPATIAL_TRANSITION_DRAFT_HASH_MISMATCH` | The confirmation does not bind this exact pending draft. |
| `SPATIAL_TRANSITION_SOURCE_FRAMEWORK_MISMATCH` | The draft does not bind the supplied ARCH-109 framework. |
| `SPATIAL_TRANSITION_UPSTREAM_UNRESOLVED` | ARCH-109 still contains a human-recorded gap. |
| `SPATIAL_TRANSITION_PAIR_INVALID` | A pair is unknown, self-referential, duplicate, or not grounded upstream. |
| `SPATIAL_TRANSITION_COVERAGE_INVALID` | A grounded pair is missing or appears as both resolved and unresolved. |
| `SPATIAL_TRANSITION_UNRESOLVED_INVALID` | An unresolved transition record is invalid. |
| `STUDENT_SPATIAL_TRANSITION_SCHEMA_INVALID` | A supplied output violates its closed schema. |
| `STUDENT_SPATIAL_TRANSITION_CONTENT_MISMATCH` | A valid chain was supplied with a non-projected output. |
| `OUTPUT_WRITE_FAILED` | The destination could not be written without clobbering existing data. |

All ARCH-097~109 errors propagate unchanged.
