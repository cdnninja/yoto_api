"""Small helpers: nested dict/list lookups, datetime parsing, volume mapping."""

import datetime
import re
from bisect import bisect_left
from typing import Any, Optional


def get_child_value(data: Any, key: str) -> Any:
    """
    Look up `key` in a nested dict/list. Dotted keys descend into children.

    String values that look like numbers or booleans are coerced
    (e.g. "16" -> 16, "true" -> True). Use `get_raw_value` for ID-shaped
    fields like chapter or track keys where leading-zero formatting matters.
    """
    value = get_raw_value(data, key)
    if isinstance(value, str):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if lower.lstrip("+-").isdigit():
            return int(value)
    return value


def get_raw_value(data: Any, key: str) -> Any:
    """Like `get_child_value` but returns the raw value with no type coercion."""
    value: Any = data
    for x in key.split("."):
        try:
            value = value[x]
            continue
        except (KeyError, TypeError):
            pass

        try:
            value = value[int(x)]
            continue
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return value


def parse_datetime(
    value: Optional[str], timezone: datetime.tzinfo
) -> datetime.datetime:
    if value is None:
        return datetime.datetime(2000, 1, 1, tzinfo=timezone)

    value = value.replace("-", "").replace("T", "").replace(":", "").replace("Z", "")
    m = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", value)
    if m is None:
        return datetime.datetime(2000, 1, 1, tzinfo=timezone)
    return datetime.datetime(
        year=int(m.group(1)),
        month=int(m.group(2)),
        day=int(m.group(3)),
        hour=int(m.group(4)),
        minute=int(m.group(5)),
        second=int(m.group(6)),
        tzinfo=timezone,
    )


def take_closest(values: list, number: int) -> int:
    """Return the value in sorted `values` closest to `number`. Ties go to the
    smaller value. Used for volume mapping."""
    pos = bisect_left(values, number)
    if pos == 0:
        return values[0]
    if pos == len(values):
        return values[-1]
    before = values[pos - 1]
    after = values[pos]
    if after - number < number - before:
        return after
    else:
        return before
