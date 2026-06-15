"""const.py"""

from typing import Optional

DOMAIN: str = "yoto_api"

# Blue night_light_mode 0x194a55
# off is 0x000000
# 0x643600 is a valid response too. I think this is day.

LIGHT_COLORS = {
    None: None,
    "0x000000": "Off",
    "0x194a55": "On",
    "0x643600": "On Day",
    "off": "Off",
    "0x5a6400": "On Night",
    "0x640000": "Orange Peel",
    "0x602d3c": "Lilac",
    "0x641600": "",
    "0x646464": "White",
}

# Keys (stable, HA-translatable) and order mirror the app's light picker.
# v3 players are calibrated differently from v1/v2, so the same colour writes
# a different hex per generation — hence two maps. mini has no ambient light;
# gate on caps_for(device).has_ambient_light before exposing these.
V3_PRESETS = {
    "orange_peel": "#ff8c00",
    "tambourine_red": "#ff0000",
    "lilac": "#f57399",
    "apple_green": "#e6ff00",
    "bumblebee_yellow": "#ffb800",
    "sky_blue": "#40bfd9",
    "white": "#ffffff",
    "off": "#0",
}
LEGACY_PRESETS = {
    "orange_peel": "#ff3900",
    "tambourine_red": "#ff0000",
    "lilac": "#f72a69",
    "apple_green": "#9eff00",
    "bumblebee_yellow": "#ff8500",
    "sky_blue": "#41c0f0",
    "white": "#ffffff",
    "off": "#0",
}
assert V3_PRESETS.keys() == LEGACY_PRESETS.keys(), "preset maps must share keys"

AMBIENT_PRESET_KEYS = tuple(V3_PRESETS)

# Reads accept either generation's hex, plus the off sentinels a device
# may echo back.
AMBIENT_PRESET_BY_HEX = {
    hex_.lower(): key
    for presets in (V3_PRESETS, LEGACY_PRESETS)
    for key, hex_ in presets.items()
}
AMBIENT_PRESET_BY_HEX.update({"#000000": "off", "off": "off"})


def ambient_preset_to_hex(key: str, *, is_v3: bool) -> str:
    """Resolve a preset key to the hex the app writes for this generation.

    `is_v3` selects the v3 calibration; v1/v2 share the legacy hex.
    Raises ValueError for an unknown preset key.
    """
    presets = V3_PRESETS if is_v3 else LEGACY_PRESETS
    try:
        return presets[key]
    except KeyError:
        raise ValueError(
            f"Unknown ambient preset {key!r}. Known: {list(AMBIENT_PRESET_KEYS)}"
        ) from None


def ambient_hex_to_preset(hex_colour: Optional[str]) -> Optional[str]:
    """Map a stored ambientColour hex back to a preset key, or None.

    Returns None for an unrecognised (e.g. custom) hex, so a consumer can
    treat it as "not one of the presets".
    """
    if not hex_colour:
        return None
    return AMBIENT_PRESET_BY_HEX.get(hex_colour.lower())


VOLUME_MAPPING_INVERTED = [
    0,
    7,
    13,
    19,
    25,
    32,
    38,
    44,
    50,
    57,
    63,
    69,
    75,
    82,
    88,
    94,
    100,
]


POWER_SOURCE = {
    # Guessing on this.
    None: None,
    0: "Battery Power",
    1: "Battery Power",
    2: "USB Power",
    3: "USB Power",
    4: "USB Power",
    5: "USB Power",
}
