from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .device import Device
from .event import PlaybackEvent
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

    def __post_init__(self) -> None:
        # last_event keeps player_id — PlaybackEvent doubles as the routed
        # MQTT message, keyed by it. The status/info objects don't: identity
        # lives on `device`.
        self.info = PlayerInfo()
        self.status = PlayerStatus()
        self.extended_status = PlayerExtendedStatus()
        self.last_event = PlaybackEvent(player_id=self.device.device_id)

    @property
    def id(self) -> str:
        return self.device.device_id

    @property
    def name(self) -> str:
        return self.device.name

    @property
    def model(self) -> str:
        family = (self.device.device_family or "").lower()
        return "Yoto Mini" if family == "mini" else "Yoto Player"
