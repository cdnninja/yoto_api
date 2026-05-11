from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .device import Device
from .event import PlaybackEvent
from .info import PlayerInfo
from .status import PlayerStatus


@dataclass
class YotoPlayer:
    """Stable per-device handle. Mutable: gets updated as data arrives.

    `info`, `status`, and `last_event` are always present — they're
    initialized empty (all fields `None` except the device_id binding)
    by `__post_init__` so consumers don't need defensive `is None`
    guards. The "have we actually received data?" signal lives on the
    `*_refreshed_at` / `last_event_received_at` timestamps, which stay
    `Optional[datetime]`.
    """

    device: Device
    info: PlayerInfo = field(init=False)
    status: PlayerStatus = field(init=False)
    last_event: PlaybackEvent = field(init=False)

    devices_refreshed_at: Optional[datetime] = None
    info_refreshed_at: Optional[datetime] = None
    status_refreshed_at: Optional[datetime] = None
    last_event_received_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        device_id = self.device.device_id
        self.info = PlayerInfo(device_id=device_id)
        self.status = PlayerStatus(device_id=device_id)
        self.last_event = PlaybackEvent(player_id=device_id)

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
