"""Parse incoming MQTT messages into typed patches.

Returns an `EventPatch` for `device/{id}/data/events`, a `StatusPatch` for
`device/{id}/data/status` (v1) and `device/{id}/status/full` (v3, extended=True),
a `PresenceEvent` for `device/{id}/presence`, or None for anything else
(command acks, unknown topics). Each patch carries only the fields its payload
sent, so callers can merge selectively into the current snapshot.
"""

import json
import logging
from typing import Any, Dict, Optional, Union

from .._coerce import (
    as_bool,
    as_bool_int,
    as_int,
    coerce_active_card,
    parse_enum,
    parse_temp_pair,
)
from ..models.event import EventPatch, PlaybackStatus, PresenceEvent, StatusPatch
from ..models.status import CardInsertionState, DayMode, PowerSource

_LOGGER = logging.getLogger(__name__)


Message = Union[EventPatch, StatusPatch, PresenceEvent]


def parse_message(topic: str, payload: bytes) -> Optional[Message]:
    """Route `device/{id}/<suffix>` to its parser. None for ignored/bad."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "device":
        _LOGGER.debug("MQTT topic %r doesn't match device/{id}/* shape", topic)
        return None
    device_id = parts[1]
    suffix = "/".join(parts[2:])

    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        _LOGGER.debug("MQTT payload not JSON on %s", topic)
        return None

    if suffix == "data/events":
        return _parse_events(device_id, body)
    if suffix == "data/status":
        return _parse_status(device_id, body)
    if suffix == "status/full":
        return _parse_extended_status(device_id, body)
    if suffix == "presence":
        return _parse_presence(device_id, body)
    _LOGGER.debug("MQTT topic %r ignored", topic)
    return None


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_playback_status(value: Any) -> Optional[PlaybackStatus]:
    if value is None:
        return None
    try:
        return PlaybackStatus(str(value))
    except ValueError:
        _LOGGER.debug("Unknown playbackStatus value: %r", value)
        return None


# (raw_key, PlaybackEvent field name, coercer) for the data/events payload.
_EVENT_FIELDS = (
    ("eventUtc", "event_utc", as_int),
    ("cardId", "card_id", _optional_str),
    ("chapterKey", "chapter_key", _optional_str),
    ("chapterTitle", "chapter_title", _optional_str),
    ("trackKey", "track_key", _optional_str),
    ("trackTitle", "track_title", _optional_str),
    ("trackLength", "track_length", as_int),
    ("position", "position", as_int),
    ("source", "source", _optional_str),
    ("playbackStatus", "playback_status", _parse_playback_status),
    ("repeatAll", "repeat_all", as_bool),
    ("streaming", "streaming", as_bool),
    ("volume", "volume", as_int),
    ("volumeMax", "volume_max", as_int),
    ("sleepTimerSeconds", "sleep_timer_seconds", as_int),
    ("sleepTimerActive", "sleep_timer_active", as_bool),
    ("playbackWait", "playback_wait", as_bool),
    ("requestId", "request_id", _optional_str),
)


def _parse_events(device_id: str, body: Dict[str, Any]) -> EventPatch:
    fields: Dict[str, Any] = {}
    for raw_key, dest_key, coerce in _EVENT_FIELDS:
        if raw_key not in body:
            continue
        value = coerce(body[raw_key])
        # None only comes from a failed coercion: the device never clears with
        # a null, it uses a value (e.g. card_id "none"). So it's just noise.
        if value is None:
            continue
        fields[dest_key] = value
    return EventPatch(player_id=device_id, fields=fields)


# (raw_key, dest_key, coercer). Same naming as `/config.device.status`.
#
# The fields the `data/status` topic actually delivers — the firmware's
# minimal set. `status/full` is a superset, so the extended parser reuses
# these then adds the extended-only extras below.
_V1_VALUE_FIELDS = (
    ("nightlightMode", "nightlight_mode", lambda v: v),
    ("batteryLevel", "battery_level_percentage", as_int),
    ("volume", "system_volume_percentage", as_int),
    ("userVolume", "user_volume_percentage", as_int),
    ("als", "ambient_light_sensor_reading", as_int),
    ("freeDisk", "free_disk_space_bytes", as_int),
    ("dnowBrightness", "current_display_brightness", as_int),
)

_V1_BOOL_FIELDS = (
    ("charging", "is_charging"),
    ("headphones", "is_audio_device_connected"),
    ("bluetoothHp", "is_bluetooth_audio_connected"),
)

# Extras only the `status/full` payload (and the REST shadow) carry, never
# `data/status`. Live only on PlayerExtendedStatus.
_EXTENDED_VALUE_FIELDS = (
    ("ssid", "network_ssid", lambda v: v),
    ("wifiStrength", "wifi_strength", as_int),
    ("totalDisk", "total_disk_space_bytes", as_int),
    ("upTime", "uptime", as_int),
    ("utcTime", "utc_time", as_int),
    ("utcOffset", "utc_offset_seconds", as_int),
    ("batteryLevelRaw", "battery_level_raw", as_int),
    ("battery", "battery_voltage_mv", as_int),
    ("batteryProfile", "battery_profile", lambda v: v),
    ("bytesPS", "average_download_speed_bytes_second", as_int),
)

_EXTENDED_BOOL_FIELDS = (("bgDownload", "is_background_download_active"),)


def _v1_status_fields(status: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the data/status fields actually present."""
    fields: Dict[str, Any] = {}

    if "activeCard" in status:
        fields["active_card"] = coerce_active_card(status["activeCard"])

    for raw_key, dest_key, coerce in _V1_VALUE_FIELDS:
        if raw_key in status:
            fields[dest_key] = coerce(status[raw_key])

    for raw_key, dest_key in _V1_BOOL_FIELDS:
        if raw_key in status:
            fields[dest_key] = as_bool_int(status[raw_key])

    if "cardInserted" in status:
        fields["card_insertion_state"] = parse_enum(
            CardInsertionState, status["cardInserted"]
        )
    if "day" in status:
        fields["day_mode"] = parse_enum(DayMode, status["day"])

    return fields


def _parse_status(device_id: str, body: Dict[str, Any]) -> StatusPatch:
    """Parse `data/status` → PlayerStatus patch."""
    status = body.get("status") or body
    return StatusPatch(
        player_id=device_id, fields=_v1_status_fields(status), extended=False
    )


def _parse_extended_status(device_id: str, body: Dict[str, Any]) -> StatusPatch:
    """Parse `status/full` → PlayerExtendedStatus patch.

    The basic `data/status` fields plus the extras only `status/full` carries:
    power source, network, total disk, uptime/clock, raw battery (level,
    voltage, profile) and a direct battery temperature (`temperature_celcius`
    comes from the `temp` pair).
    """
    status = body.get("status") or body
    fields = _v1_status_fields(status)

    for raw_key, dest_key, coerce in _EXTENDED_VALUE_FIELDS:
        if raw_key in status:
            fields[dest_key] = coerce(status[raw_key])

    for raw_key, dest_key in _EXTENDED_BOOL_FIELDS:
        if raw_key in status:
            fields[dest_key] = as_bool_int(status[raw_key])

    if "powerSrc" in status:
        fields["power_source"] = parse_enum(PowerSource, status["powerSrc"])

    if "temp" in status:
        battery_temp, device_temp = parse_temp_pair(status["temp"])
        if battery_temp is not None:
            fields["battery_temperature"] = battery_temp
        if device_temp is not None:
            fields["temperature_celcius"] = device_temp

    # status/full exposes battery temperature directly; prefer it over the
    # value derived from the `temp` pair.
    if "batteryTemp" in status:
        battery_temp = as_int(status["batteryTemp"])
        if battery_temp is not None:
            fields["battery_temperature"] = battery_temp

    return StatusPatch(player_id=device_id, fields=fields, extended=True)


def _parse_presence(device_id: str, body: Dict[str, Any]) -> PresenceEvent:
    """Parse `device/{id}/presence`: {"state": "online"|"offline", "ts": ms}."""
    return PresenceEvent(
        player_id=device_id,
        is_online=body.get("state") == "online",
        ts=as_int(body.get("ts")),
    )


# Known keys per topic, imported by `scripts/check_unmapped.py` to flag new
# fields Yoto starts sending. Update when adding fields to the parsers.
KNOWN_EVENT_KEYS = frozenset(raw_key for raw_key, _, _ in _EVENT_FIELDS)

# Shared by data/status (v1) and status/full (v3): the flat set covers both.
KNOWN_STATUS_KEYS = frozenset(
    {
        # Mapped (to PlayerStatus / PlayerExtendedStatus)
        "activeCard",
        "ssid",
        "wifiStrength",
        "nightlightMode",
        "batteryLevel",
        "volume",
        "userVolume",
        "als",
        "freeDisk",
        "totalDisk",
        "upTime",
        "utcTime",
        "utcOffset",
        "dnowBrightness",
        "charging",
        "headphones",
        "bluetoothHp",
        "bgDownload",
        "powerSrc",
        "cardInserted",
        "day",
        "temp",
        "battery",
        "batteryLevelRaw",
        "batteryProfile",
        "batteryTemp",
        "bytesPS",
        # Known but intentionally not mapped: firmware diagnostics / config echoes.
        "statusVersion",
        "fwVersion",
        "productType",
        "shutDown",
        "batteryData",
        "batteryRemaining",
        "batteryFullPct",
        "chgStatLevel",
        "powerCaps",
        "free",
        "freeDMA",
        "free32",
        "sd_info",
        "aliveTime",
        "lastSeenAt",
        "accelTemp",
        "rtcResetReasonPRO",
        "rtcResetReasonAPP",
        "rtcWakeupCause",
        "espResetReason",
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
    }
)
