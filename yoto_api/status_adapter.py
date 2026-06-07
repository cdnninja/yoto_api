"""Adapt the `device.status` block from /config into a PlayerExtendedStatus.

This block is the AWS IoT shadow, read over REST as the offline / cold-start
fallback — live telemetry comes over MQTT. It carries the same fields as the
MQTT `status/full` payload, so it maps to PlayerExtendedStatus.

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
    kib_to_bytes,
    parse_enum,
    parse_iso,
    parse_temp_pair,
)
from .models.status import (
    CardInsertionState,
    DayMode,
    PlayerExtendedStatus,
    PowerSource,
)


# Raw `device.status` keys we know about. Kept here (next to the parser)
# so `scripts/check_unmapped.py` can import it without duplicating the
# list. Update when adding fields to `adapt_raw_status`.
KNOWN_RAW_STATUS_KEYS = frozenset(
    {
        # Mapped
        "activeCard",
        "ssid",
        "wifiStrength",
        "nightlightMode",
        "batteryLevel",
        "batteryLevelRaw",
        "battery",
        "batteryProfile",
        "batteryTemp",
        "volume",
        "userVolume",
        "als",
        "freeDisk",
        "totalDisk",
        "upTime",
        "utcTime",
        "utcOffset",
        "charging",
        "headphones",
        "bluetoothHp",
        "bgDownload",
        "bytesPS",
        "powerSrc",
        "cardInserted",
        "day",
        "temp",
        "updatedAt",
        # Known but intentionally not mapped (firmware diagnostics)
        "deviceId",
        "statusVersion",
        "fwVersion",
        "shutDown",
        "batteryData",
        "batteryRemaining",
        "chgStatLevel",
        "powerCaps",
        "free",
        "freeDMA",
        "free32",
        "sd_info",
        "aliveTime",
        "lastSeenAt",
        "accelTemp",
        "wifiRestarts",
        "errorsLogged",
        "buzzErrors",
        "nfcErrs",
        "nfcLock",
        "qiOtp",
        "failReason",
        "failData",
        "twdt",
        "missedLogs",
        "playingStatus",
        "shutdownTimeout",
        "dbatTimeout",
        "dayBright",
        "nightBright",
        "timeFormat",
        "dnowBrightness",
    }
)


def adapt_raw_status(raw: Dict[str, Any]) -> PlayerExtendedStatus:
    """Map a `device.status` dict from /config into a typed PlayerExtendedStatus."""
    battery_temp, device_temp = parse_temp_pair(raw.get("temp"))
    # batteryTemp is the direct reading; prefer it over the `temp` pair.
    if raw.get("batteryTemp") is not None:
        battery_temp = as_int(raw.get("batteryTemp"))
    return PlayerExtendedStatus(
        updated_at=parse_iso(raw.get("updatedAt")),
        active_card=coerce_active_card(raw.get("activeCard")),
        network_ssid=raw.get("ssid"),
        wifi_strength=as_int(raw.get("wifiStrength")),
        nightlight_mode=raw.get("nightlightMode"),
        battery_level_percentage=as_int(raw.get("batteryLevel")),
        battery_level_raw=as_int(raw.get("batteryLevelRaw")),
        battery_voltage_mv=as_int(raw.get("battery")),
        battery_profile=raw.get("batteryProfile"),
        system_volume_percentage=as_int(raw.get("volume")),
        user_volume_percentage=as_int(raw.get("userVolume")),
        ambient_light_sensor_reading=as_int(raw.get("als")),
        free_disk_space_bytes=kib_to_bytes(raw.get("freeDisk")),
        total_disk_space_bytes=kib_to_bytes(raw.get("totalDisk")),
        uptime=as_int(raw.get("upTime")),
        utc_time=as_int(raw.get("utcTime")),
        utc_offset_seconds=as_int(raw.get("utcOffset")),
        is_charging=as_bool_int(raw.get("charging")),
        is_audio_device_connected=as_bool_int(raw.get("headphones")),
        is_bluetooth_audio_connected=as_bool_int(raw.get("bluetoothHp")),
        is_background_download_active=as_bool_int(raw.get("bgDownload")),
        average_download_speed_bytes_second=as_int(raw.get("bytesPS")),
        power_source=parse_enum(PowerSource, raw.get("powerSrc")),
        card_insertion_state=parse_enum(CardInsertionState, raw.get("cardInserted")),
        day_mode=parse_enum(DayMode, raw.get("day")),
        battery_temperature=battery_temp,
        temperature_celcius=device_temp,
        # is_online isn't in the status block — the caller sets it from device.online.
    )
