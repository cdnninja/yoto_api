from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
    event_utc: int | None = None

    card_id: str | None = None
    chapter_key: str | None = None
    chapter_title: str | None = None
    track_key: str | None = None
    track_title: str | None = None
    track_length: int | None = None  # seconds
    position: int | None = None  # seconds
    source: str | None = None  # e.g. "remote", "card"

    playback_status: PlaybackStatus | None = None
    repeat_all: bool | None = None
    streaming: bool | None = None

    # Raw 0-volume_max scale (NOT percentage)
    volume: int | None = None
    volume_max: int | None = None

    sleep_timer_seconds: int | None = None
    sleep_timer_active: bool | None = None

    # Player is buffering / waiting between tracks (firmware-pushed bool).
    playback_wait: bool | None = None

    request_id: str | None = None

    @property
    def volume_percentage(self) -> float | None:
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
class EventPatch:
    """Partial PlaybackEvent update from MQTT `device/{id}/data/events`.

    Holds only the keys the payload carried, with values kept faithful to the
    wire (e.g. card_id "none"); the merge interprets them onto `last_event`.
    """

    player_id: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusPatch:
    """Partial status update from MQTT `data/status` or `status/full`.

    Only fields present in the payload are populated; consumers merge the
    non-None values into the current status object. `extended` selects the
    target: True → `status/full` → `PlayerExtendedStatus`;
    False → `data/status` → `PlayerStatus`.
    """

    player_id: str
    fields: dict[str, Any] = field(default_factory=dict)
    extended: bool = False


@dataclass
class PresenceEvent:
    """Online/offline transition from MQTT `device/{id}/presence`.

    The "offline" message is published by the broker's Last-Will, not the
    device, so receiving one does NOT prove the player is reachable — unlike
    every other topic. Consumers should set is_online from it directly.
    """

    player_id: str
    is_online: bool
    ts: int | None = None  # device-supplied epoch ms
