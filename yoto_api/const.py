"""const.py"""

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

HEX_COLORS = {
    "#40bfd9": "Sky Blue",
    "#41c0f0": "Sky Blue",
    "#9eff00": "Apple Green",
    "#e6ff00": "Apple Green",
    "#f57399": "Lilac",
    "#f72a69": "Lilac",
    "#ff0000": "Tambourine Red",
    "#ff3900": "Orange Peel",
    "#ff8500": "Bumblebee Yellow",
    "#ff8c00": "Orange Peel",
    "#ffb800": "Bumblebee Yellow",
    "#ffffff": "white",
    "#0": "Off",
}

VOLUME_MAPPING = {
    0: 0,
    1: 7,
    2: 12,
    3: 19,
    4: 25,
    5: 32,
    6: 38,
    7: 44,
    8: 50,
    9: 57,
    10: 63,
    11: 69,
    12: 75,
    13: 82,
    14: 88,
    15: 94,
    16: 100,
}


POWER_SOURCE = {
    # Guessing on this.
    0: "Battery Power",
    1: "Battery Power",
    2: "USB Power",
    3: "USB Power",
    5: "USB Power",
}
