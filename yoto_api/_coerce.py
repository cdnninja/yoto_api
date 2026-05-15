"""Shared coercion helpers for parsing Yoto's REST and MQTT payloads.

The Yoto API is loosely typed: numbers can come as ints OR strings,
booleans can come as `true`/`false` OR `0`/`1` OR `"1"`/`"0"`. These
helpers all return `None` when the input can't be coerced rather than
raising, because the right thing to do for a missing/odd field is
"don't update the model" not "crash the whole refresh".
"""

import logging
from datetime import datetime, time
from enum import IntEnum
from typing import Any, Optional, Tuple, Type, TypeVar

_LOGGER = logging.getLogger(__name__)

_E = TypeVar("_E", bound=IntEnum)


def as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> Optional[bool]:
    """Best-effort bool: handles JSON `true`/`false`, `0`/`1` ints, and
    `"true"`/`"1"`/`"yes"` strings. Returns `None` for anything else."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return None


def as_bool_int(value: Any) -> Optional[bool]:
    """For 0/1 booleans specifically (most of Yoto's MQTT status flags)."""
    coerced = as_int(value)
    if coerced is None:
        return None
    return coerced != 0


def coerce_active_card(value: Any) -> Optional[str]:
    """Yoto sends "none" instead of null when no card is inserted."""
    if value in (None, "none", ""):
        return None
    return str(value)


def parse_enum(enum_cls: Type[_E], value: Any) -> Optional[_E]:
    if value is None:
        return None
    coerced = as_int(value)
    if coerced is None:
        return None
    try:
        return enum_cls(coerced)
    except ValueError:
        _LOGGER.debug("Unknown %s value: %r", enum_cls.__name__, value)
        return None


def parse_temp_pair(value: Any) -> Tuple[Optional[int], Optional[int]]:
    """Parse `"battery:device"` °C strings (e.g. `"24:18"`).

    Each side may be an int, `"0"` (unknown), `"notSupported"`, or empty.
    Returns `(battery_temp, device_temp)`.
    """
    if not isinstance(value, str) or ":" not in value:
        return None, None
    battery_part, _, device_part = value.partition(":")
    return _temp_part(battery_part), _temp_part(device_part)


def _temp_part(part: str) -> Optional[int]:
    if part in ("", "0", "notSupported"):
        return None
    try:
        return int(part)
    except ValueError:
        return None


def parse_iso(value: Any) -> Optional[datetime]:
    """Parse ISO8601 timestamps with the trailing-Z that Yoto sends."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.rstrip("Z"))
    except ValueError:
        return None


def parse_hhmm(value: Any) -> Optional[time]:
    """Parse "HH:MM" strings (used by Yoto's day_time / night_time)."""
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        hours_str, minutes_str = value.split(":", 1)
        return time(hour=int(hours_str), minute=int(minutes_str))
    except (TypeError, ValueError):
        return None


def parse_brightness(value: Any) -> Tuple[Optional[bool], Optional[int]]:
    """Yoto encodes display brightness as either `"auto"` or a stringified int.

    Returns `(is_auto, value)`:
      - `("auto", None)` → `(True, None)`
      - `("100", None)` → `(False, 100)`
      - missing / unparsable → `(None, None)`
    """
    if value is None:
        return None, None
    if value == "auto":
        return True, None
    coerced = as_int(value)
    if coerced is None:
        return None, None
    return False, coerced
