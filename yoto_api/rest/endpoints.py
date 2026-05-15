"""URL constants for the Yoto REST API."""

BASE_URL = "https://api.yotoplay.com"
AUTH_URL = "https://login.yotoplay.com/oauth/device/code"
TOKEN_URL = "https://login.yotoplay.com/oauth/token"

DEVICES_MINE = "/device-v2/devices/mine"


def device_config(device_id: str) -> str:
    return f"/device-v2/{device_id}/config"


def device_status(device_id: str) -> str:
    return f"/device-v2/{device_id}/status"


def command_status(device_id: str) -> str:
    """POST trigger to make the player push its current status onto MQTT.
    The other player commands (play/pause/volume/etc.) go via MQTT direct."""
    return f"/device-v2/{device_id}/command/status"


CARDS_LIBRARY = "/card/family/library"


def card_detail(card_id: str) -> str:
    return f"/card/{card_id}"
