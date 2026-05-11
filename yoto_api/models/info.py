from dataclasses import dataclass, field
from typing import Optional

from .config import PlayerConfig


@dataclass
class PlayerInfo:
    """Wraps GET /device-v2/{id}/config — settings + identity + hardware."""

    device_id: str
    name: Optional[str] = None
    firmware_version: Optional[str] = None    # from device.releaseChannelVersion
    pop_code: Optional[str] = None
    activation_pop_code: Optional[str] = None
    release_channel_id: Optional[str] = None
    device_type: Optional[str] = None
    device_family: Optional[str] = None
    device_group: Optional[str] = None
    mac: Optional[str] = None
    geo_timezone: Optional[str] = None
    error_code: Optional[str] = None
    config: PlayerConfig = field(default_factory=PlayerConfig)
