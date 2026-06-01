"""Top-level package for yoto_api."""
# flake8: noqa

from .Card import Card, Chapter, Track
from .Group import Group
from .Token import Token
from .account import get_account_id, has_scope
from .capabilities import Capabilities, caps_for
from .client import YotoClient
from .const import HEX_COLORS, LIGHT_COLORS, POWER_SOURCE, VOLUME_MAPPING_INVERTED
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
    PlayerFullStatus,
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
    "DayMode",
    "Device",
    "EventPatch",
    "Group",
    "HEX_COLORS",
    "LIGHT_COLORS",
    "POWER_SOURCE",
    "PlaybackEvent",
    "PlaybackStatus",
    "PlayerConfig",
    "PlayerFullStatus",
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
