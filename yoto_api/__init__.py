"""Top-level package for yoto_api."""
# flake8: noqa

from .Card import Card, Chapter, Track
from .Group import Group
from .Token import Token
from .account import get_account_id, has_scope
from .capabilities import Capabilities, caps_for
from .client import YotoClient
from .const import (
    AMBIENT_PRESET_KEYS,
    LEGACY_PRESETS,
    POWER_SOURCE,
    V3_PRESETS,
    VOLUME_MAPPING_INVERTED,
    ambient_hex_to_preset,
    ambient_preset_to_hex,
)
from .exceptions import (
    AuthenticationError,
    YotoAPIError,
    YotoError,
    YotoMQTTError,
)
from .models import (
    Alarm,
    CardInsertionState,
    DayMode,
    Device,
    EventPatch,
    PlaybackEvent,
    PlaybackStatus,
    PlayerConfig,
    PlayerExtendedStatus,
    PlayerInfo,
    PlayerStatus,
    PowerSource,
    PresenceEvent,
    StatusPatch,
    YotoPlayer,
)

__all__ = [
    "Alarm",
    "AuthenticationError",
    "Capabilities",
    "Card",
    "CardInsertionState",
    "Chapter",
    "AMBIENT_PRESET_KEYS",
    "DayMode",
    "Device",
    "EventPatch",
    "Group",
    "LEGACY_PRESETS",
    "V3_PRESETS",
    "ambient_hex_to_preset",
    "ambient_preset_to_hex",
    "POWER_SOURCE",
    "PlaybackEvent",
    "PlaybackStatus",
    "PlayerConfig",
    "PlayerExtendedStatus",
    "PlayerInfo",
    "PlayerStatus",
    "PowerSource",
    "PresenceEvent",
    "StatusPatch",
    "Token",
    "Track",
    "VOLUME_MAPPING_INVERTED",
    "YotoAPIError",
    "YotoClient",
    "YotoError",
    "YotoMQTTError",
    "YotoPlayer",
    "caps_for",
    "get_account_id",
    "has_scope",
]
