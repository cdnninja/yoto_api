from dataclasses import dataclass, field

from .config import PlayerConfig


@dataclass
class PlayerInfo:
    """Wraps GET /device-v2/{id}/config — settings + hardware.

    Identity (which device) lives on `YotoPlayer` / `Device`, not here.
    """

    name: str | None = None
    firmware_version: str | None = None  # from device.releaseChannelVersion
    pop_code: str | None = None
    activation_pop_code: str | None = None
    release_channel_id: str | None = None
    device_type: str | None = None
    device_family: str | None = None
    device_group: str | None = None
    mac: str | None = None
    geo_timezone: str | None = None
    error_code: str | None = None
    config: PlayerConfig = field(default_factory=PlayerConfig)
