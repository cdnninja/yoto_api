"""Capabilities by device family.

Centralised so callers don't sprinkle `if family == "mini"` across the codebase.
Unknown families fall back to V2 caps with a logged warning, mirroring the
fallback the official Yoto Android app uses.
"""

import logging
from dataclasses import dataclass

from .models.device import Device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Capabilities:
    has_ambient_light: bool


# Family used as a fallback when the API returns an unknown device_family.
# v2 is the most common modern Player and is the safest superset.
FAMILY_DEFAULT = "v2"

_CAPABILITIES = {
    "v1": Capabilities(has_ambient_light=True),
    "v2": Capabilities(has_ambient_light=True),
    "v3": Capabilities(has_ambient_light=True),
    "mini": Capabilities(has_ambient_light=False),
}

assert FAMILY_DEFAULT in _CAPABILITIES, "FAMILY_DEFAULT must be a known family"


def caps_for(device: Device) -> Capabilities:
    family = (device.device_family or "").lower()
    if family in _CAPABILITIES:
        return _CAPABILITIES[family]
    _LOGGER.warning(
        "Unknown device_family %r for %s — falling back to %s capabilities",
        device.device_family,
        device.device_id,
        FAMILY_DEFAULT,
    )
    return _CAPABILITIES[FAMILY_DEFAULT]
