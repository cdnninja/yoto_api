"""Adapt the undocumented `device.status` block from /config to PlayerStatus.

Used as a fallback when the documented `/status` endpoint is unavailable
(missing `family:device-status:view` scope, e.g. for HA core today).

Field-by-field mapping notes:
- Most names are shorter (`fwVersion`, `batteryLevel`, `wifiStrength`).
- `0` / `1` integers replace booleans for `charging`, `headphones`,
  `bluetoothHp`, `day`.
- `temp` is "{battery}:{device}" string with each side either an int,
  "0" (unknown), or "notSupported".
"""

from typing import Any, Dict

from ._coerce import (
    as_bool_int,
    as_int,
    coerce_active_card,
    parse_enum,
    parse_iso,
    parse_temp_pair,
)
from .models.status import (
    CardInsertionState,
    DayMode,
    PlayerStatus,
    PowerSource,
)


def adapt_raw_status(raw: Dict[str, Any], device_id: str) -> PlayerStatus:
    """Map a `device.status` dict from /config into a typed PlayerStatus."""
    battery_temp, device_temp = parse_temp_pair(raw.get("temp"))
    return PlayerStatus(
        device_id=device_id,
        # Direct passthroughs (numeric or string)
        active_card=coerce_active_card(raw.get("activeCard")),
        network_ssid=raw.get("ssid"),
        wifi_strength=as_int(raw.get("wifiStrength")),
        nightlight_mode=raw.get("nightlightMode"),
        battery_level_percentage=as_int(raw.get("batteryLevel")),
        system_volume_percentage=as_int(raw.get("volume")),
        user_volume_percentage=as_int(raw.get("userVolume")),
        ambient_light_sensor_reading=as_int(raw.get("als")),
        free_disk_space_bytes=as_int(raw.get("freeDisk")),
        total_disk_space_bytes=as_int(raw.get("totalDisk")),
        uptime=as_int(raw.get("upTime")),
        utc_time=as_int(raw.get("utcTime")),
        utc_offset_seconds=as_int(raw.get("utcOffset")),
        # 0/1 booleans
        is_charging=as_bool_int(raw.get("charging")),
        is_audio_device_connected=as_bool_int(raw.get("headphones")),
        is_bluetooth_audio_connected=as_bool_int(raw.get("bluetoothHp")),
        is_background_download_active=as_bool_int(raw.get("bgDownload")),
        # Enums
        power_source=parse_enum(PowerSource, raw.get("powerSrc")),
        card_insertion_state=parse_enum(CardInsertionState, raw.get("cardInserted")),
        day_mode=parse_enum(DayMode, raw.get("day")),
        # Temperature pair
        battery_temperature=battery_temp,
        temperature_celcius=device_temp,
        # Last-seen
        updated_at=parse_iso(raw.get("updatedAt")),
        # is_online isn't in the raw status block — caller (which knows
        # device.online from the /config top level) sets it.
    )
