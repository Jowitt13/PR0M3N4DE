"""Shared RFC 3339 date-time validation for Skill runtime scripts and tests."""

from __future__ import annotations

import datetime as _datetime
import re

_RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?"
    r"(Z|[+-][0-9]{2}:[0-9]{2})$",
)


def is_rfc3339_datetime(instance: object) -> bool:
    """Return whether *instance* is a timezone-qualified RFC 3339 date-time."""
    if not isinstance(instance, str) or not _RFC3339_RE.fullmatch(instance):
        return False
    try:
        _datetime.datetime.fromisoformat(instance)
    except ValueError:
        return False
    return True
