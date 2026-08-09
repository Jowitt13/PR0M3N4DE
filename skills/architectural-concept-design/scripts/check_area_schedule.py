"""Deterministically calculate an architecture area schedule from structured input."""

from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence


def _as_decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field_name} must be numeric")
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} must be numeric") from error
    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be a finite number")
    return decimal_value


def _area_value(area: object, field_name: str) -> Decimal:
    if not isinstance(area, Mapping):
        raise ValueError(f"{field_name} must be an object with value and unit")
    if area.get("unit") != "m2":
        raise ValueError(f"{field_name}.unit must be m2")
    value = _as_decimal(area.get("value"), f"{field_name}.value")
    if value < 0:
        raise ValueError(f"{field_name}.value must be non-negative")
    return value


def calculate_area_schedule(payload: Mapping[str, object]) -> dict[str, object]:
    """Return deterministic net and gross area totals for an area-schedule payload."""
    spaces = payload.get("spaces")
    if not isinstance(spaces, Sequence) or isinstance(spaces, (str, bytes)) or not spaces:
        raise ValueError("spaces must be a non-empty array")

    identifiers: set[str] = set()
    net_total = Decimal("0")
    for index, space in enumerate(spaces):
        if not isinstance(space, Mapping):
            raise ValueError(f"spaces[{index}] must be an object")
        space_id = space.get("id")
        if not isinstance(space_id, str) or not space_id:
            raise ValueError(f"spaces[{index}].id must be a non-empty string")
        if space_id in identifiers:
            raise ValueError(f"duplicate space id: {space_id}")
        identifiers.add(space_id)
        net_total += _area_value(space.get("area"), f"spaces[{index}].area")

    raw_factor = payload.get("grossing_factor", {"value": 1, "unit": "ratio"})
    if not isinstance(raw_factor, Mapping) or raw_factor.get("unit") != "ratio":
        raise ValueError("grossing_factor must use the ratio unit")
    factor = _as_decimal(raw_factor.get("value"), "grossing_factor.value")
    if factor <= 0:
        raise ValueError("grossing_factor.value must be greater than zero")

    precision = Decimal("0.001")
    try:
        net_value = net_total.quantize(precision, rounding=ROUND_HALF_UP)
        gross_value = (net_total * factor).quantize(precision, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise ValueError("area values are too large to represent at 0.001 precision") from error
    return {
        "space_count": len(identifiers),
        "net_area": {"value": float(net_value), "unit": "m2"},
        "gross_area": {"value": float(gross_value), "unit": "m2"},
        "grossing_factor": {"value": float(factor), "unit": "ratio"},
    }


def main(argv: Sequence[str]) -> int:
    """Read one JSON file and write a machine-readable result or an actionable error."""
    if len(argv) != 2:
        print("usage: check_area_schedule.py <area-schedule.json>", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("top-level JSON value must be an object")
        print(json.dumps(calculate_area_schedule(payload), ensure_ascii=False, sort_keys=True))
    except (OSError, json.JSONDecodeError, InvalidOperation, ValueError) as error:
        print(f"area schedule validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
