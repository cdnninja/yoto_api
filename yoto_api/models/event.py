from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# Yoto's player hardware uses a 0..16 raw volume scale. `volume_max` in
# MQTT events is the user-configured cap (often == 16, can be lower in
# "limited" mode), not the absolute ceiling.
HARDWARE_VOLUME_MAX = 16


class PlaybackStatus(str, Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    # Extend as more values surface in real MQTT payloads.


@dataclass
class PlaybackEvent:
    """Live playback delta from MQTT `device/{id}/data/events`."""

    player_id: str
    event_utc: Optional[int] = None

    card_id: Optional[str] = None
    chapter_key: Optional[str] = None
    chapter_title: Optional[str] = None
    track_key: Optional[str] = None
    track_title: Optional[str] = None
    track_length: Optional[int] = None  # seconds
    position: Optional[int] = None  # seconds
    source: Optional[str] = None  # e.g. "remote", "card"

    playback_status: Optional[PlaybackStatus] = None
    repeat_all: Optional[bool] = None
    streaming: Optional[bool] = None

    # Raw 0-volume_max scale (NOT percentage)
    volume: Optional[int] = None
    volume_max: Optional[int] = None

    sleep_timer_seconds: Optional[int] = None
    sleep_timer_active: Optional[bool] = None

    # Player is buffering / waiting between tracks (firmware-pushed bool).
    playback_wait: Optional[bool] = None

    request_id: Optional[str] = None

    @property
    def volume_percentage(self) -> Optional[float]:
        """`volume` as a 0.0-1.0 ratio of the absolute hardware max (16).

        Suitable for HA `media_player.volume_level`. Note: this is NOT
        normalised against `volume_max` (which is a user-configurable
        cap, not the absolute ceiling). A `volume=4` on a player with
        `volume_max=8` returns `0.25` — the actual sound output level —
        not `0.5`.
        """
        if self.volume is None:
            return None
        return self.volume / HARDWARE_VOLUME_MAX


@dataclass
class StatusPatch:
    """Partial PlayerStatus update from MQTT `device/{id}/data/status`.

    Only fields that were present in the payload are populated; consumers
    should merge non-None values into the current PlayerStatus.
    """

    player_id: str
    fields: Dict[str, Any] = field(default_factory=dict)
