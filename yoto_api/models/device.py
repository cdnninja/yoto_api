from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Device:
    """Identity from GET /device-v2/devices/mine. Immutable per device.

    Online state is tracked separately on `PlayerStatus.is_online`
    because it changes over time (REST poll updates it both ways, MQTT
    presence sets it to True). Keeping `Device` frozen makes identity
    explicit and unambiguous.
    """

    device_id: str
    name: str
    description: Optional[str] = None
    device_type: Optional[str] = None        # short SKU code, e.g. "minie", "v3e"
    device_family: Optional[str] = None      # product line, e.g. "mini", "v3"
    device_group: Optional[str] = None
    generation: Optional[str] = None         # e.g. "gen3"
    form_factor: Optional[str] = None        # e.g. "mini", "standard"
    release_channel: Optional[str] = None    # e.g. "general", "internal"
    has_user_given_name: bool = False
