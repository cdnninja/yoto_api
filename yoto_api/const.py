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
    None: None,
}

HEX_COLORS = {
    None: None,
}

POWER_SOURCE = {
    # Guessing on this.
    0: "Battery Power",
    1: "Battery Power",
    2: "USB Power",
    3: "USB Power",
    5: "USB Power",
}
