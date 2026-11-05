from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .device import Device
from .event import PlaybackEvent, PlaybackStatus
from .info import PlayerInfo
from .status import PlayerExtendedStatus, PlayerStatus


@dataclass
class YotoPlayer:
    """Stable per-device handle. Mutable: gets updated as data arrives.

    Each telemetry object has a single writer, so values never get mixed
    across sources:
      - `status` (PlayerStatus)          ← MQTT `data/status`
      - `extended_status` (PlayerExtendedStatus) ← MQTT `status/full`,
        or the REST `/config.device.status` shadow when pulled explicitly
      - `is_online`                      ← MQTT `presence` + REST list/config
      - `last_event` (PlaybackEvent)     ← MQTT `data/events`

    `info`, `status`, `extended_status`, and `last_event` are always present —
    initialized empty by `__post_init__` so consumers don't need defensive
    `is None` guards. "Have we received data?" is signalled by the
    `*_refreshed_at` timestamps (and `status.updated_at` for telemetry).
    """

    device: Device
    info: PlayerInfo = field(init=False)
    status: PlayerStatus = field(init=False)
    extended_status: PlayerExtendedStatus = field(init=False)
    last_event: PlaybackEvent = field(init=False)

    # Connection state — distinct from telemetry. Written by presence (MQTT)
    # and REST list/config; never lives inside a status object.
    is_online: Optional[bool] = None

    devices_refreshed_at: Optional[datetime] = None
    info_refreshed_at: Optional[datetime] = None
    online_refreshed_at: Optional[datetime] = None
    last_event_received_at: Optional[datetime] = None

    # When the running sleep timer stops playback, or None when no timer runs.
    # Only moves when an event reports the timer, not on every event.
    sleep_timer_ends_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        # last_event keeps player_id — PlaybackEvent doubles as the routed
        # MQTT message, keyed by it. The status/info objects don't: identity
        # lives on `device`.
        self.info = PlayerInfo()
        self.status = PlayerStatus()
        self.extended_status = PlayerExtendedStatus()
        self.last_event = PlaybackEvent(player_id=self.device.device_id)

    @property
    def track_time_left(self) -> Optional[int]:
        """Seconds left in the current track, or None when nothing is loaded.

        While playing, the time elapsed since the last event is subtracted,
        since the player only reports its position with each event.
        """
        event = self.last_event
        if (
            event.card_id is None
            or event.track_length is None
            or event.position is None
        ):
            return None
        remaining = event.track_length - event.position
        received_at = self.last_event_received_at
        if event.playback_status == PlaybackStatus.PLAYING and received_at is not None:
            elapsed = datetime.now(timezone.utc) - received_at
            remaining -= int(elapsed.total_seconds())
        return max(remaining, 0)

    @property
    def id(self) -> str:
        return self.device.device_id

    @property
    def name(self) -> str:
        return self.device.name

    @property
    def model(self) -> str:
        family = (self.device.device_family or "").lower()
        device_type = (self.device.device_type or "").lower()
        is_mini = family == "mini" or device_type == "miniv4"
        return "Yoto Mini" if is_mini else "Yoto Player"
