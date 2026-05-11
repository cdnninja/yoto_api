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


_CAPABILITIES = {
    "v1":   Capabilities(has_ambient_light=True),
    "v2":   Capabilities(has_ambient_light=True),
    "v3":   Capabilities(has_ambient_light=True),
    "mini": Capabilities(has_ambient_light=False),
}


def caps_for(device: Device) -> Capabilities:
    family = (device.device_family or "").lower()
    if family in _CAPABILITIES:
        return _CAPABILITIES[family]
    _LOGGER.warning(
        "Unknown device_family %r for %s — falling back to v2 capabilities",
        device.device_family, device.device_id,
    )
    return _CAPABILITIES["v2"]
