from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    """Identity from GET /device-v2/devices/mine. Immutable per device.

    Online state is tracked separately on `YotoPlayer.is_online` because it
    changes over time (REST list/config and MQTT presence update it both
    ways). Keeping `Device` frozen makes identity explicit and unambiguous.
    """

    device_id: str
    name: str
    description: str | None = None
    device_type: str | None = None  # short SKU code, e.g. "minie", "v3e"
    device_family: str | None = None  # product line, e.g. "mini", "v3"
    device_group: str | None = None
    generation: str | None = None  # e.g. "gen3"
    form_factor: str | None = None  # e.g. "mini", "standard"
    release_channel: str | None = None  # e.g. "general", "internal"
    has_user_given_name: bool = False
