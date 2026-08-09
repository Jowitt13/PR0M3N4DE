"""Shared deterministic guard for fields that must identify a human record holder."""

from __future__ import annotations

import re

_NON_HUMAN_MARKERS = re.compile(
    r"agent|model|codex|deepseek|chatgpt|openai|(?:^|[^a-z0-9])(ai|gpt)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)


def is_human_record_label(value: object) -> bool:
    """Return whether *value* is a non-empty human-record label, not an agent label."""
    return isinstance(value, str) and bool(value.strip()) and _NON_HUMAN_MARKERS.search(value) is None
