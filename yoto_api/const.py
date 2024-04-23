"""const.py"""

DOMAIN: str = "yoto_api"

# Blue night_light_mode 0x194a55
# off is 0x000000

LIGHT_COLORS = {
    None: None,
    "0x000000": "Off",
    "0x194a55": "On"
}

POWER_SOURCE = {
    # Guessing on this. 
    1: False,
    2: True
}