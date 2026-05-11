"""Parse incoming MQTT messages into typed events.

Returns a `PlaybackEvent` for `device/{id}/data/events` topics, a
`StatusPatch` for `device/{id}/data/status`, or None for anything else
(command acks, unknown topics).
"""

import json
import logging
from typing import Any, Dict, Literal, Optional, Tuple, Union

from .._coerce import (
    as_bool,
    as_bool_int,
    as_int,
    coerce_active_card,
    parse_enum,
    parse_temp_pair,
)
from ..models.event import PlaybackEvent, PlaybackStatus, StatusPatch
from ..models.status import CardInsertionState, DayMode, PowerSource

_LOGGER = logging.getLogger(__name__)


Message = Union[PlaybackEvent, StatusPatch]
TopicKind = Literal["events", "status"]


def parse_message(topic: str, payload: bytes) -> Optional[Message]:
    """Dispatch on topic. Returns None for ignored topics or bad payloads."""
    parsed_topic = _parse_topic(topic)
    if parsed_topic is None:
        return None
    device_id, kind = parsed_topic

    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        _LOGGER.debug("MQTT payload not JSON on %s", topic)
        return None

    if kind == "events":
        return _parse_events(device_id, body)
    if kind == "status":
        return _parse_status(device_id, body)
    return None


def _parse_topic(topic: str) -> Optional[Tuple[str, TopicKind]]:
    """Expect `device/{device_id}/data/{events|status}`."""
    parts = topic.split("/")
    if len(parts) != 4 or parts[0] != "device" or parts[2] != "data":
        return None
    if parts[3] not in ("events", "status"):
        return None
    return parts[1], parts[3]


def _parse_events(device_id: str, body: Dict[str, Any]) -> PlaybackEvent:
    return PlaybackEvent(
        player_id=device_id,
        event_utc=as_int(body.get("eventUtc")),
        card_id=_coerce_card_id(body.get("cardId")),
        chapter_key=_optional_str(body.get("chapterKey")),
        chapter_title=_optional_str(body.get("chapterTitle")),
        track_key=_optional_str(body.get("trackKey")),
        track_title=_optional_str(body.get("trackTitle")),
        track_length=as_int(body.get("trackLength")),
        position=as_int(body.get("position")),
        source=_optional_str(body.get("source")),
        playback_status=_parse_playback_status(body.get("playbackStatus")),
        repeat_all=as_bool(body.get("repeatAll")),
        streaming=as_bool(body.get("streaming")),
        volume=as_int(body.get("volume")),
        volume_max=as_int(body.get("volumeMax")),
        sleep_timer_seconds=as_int(body.get("sleepTimerSeconds")),
        sleep_timer_active=as_bool(body.get("sleepTimerActive")),
        playback_wait=as_bool(body.get("playbackWait")),
        request_id=_optional_str(body.get("requestId")),
    )


# Known keys per topic. Co-located with the parsers so
# `scripts/check_unmapped.py` can import them without duplicating the
# lists. Update when adding fields to `_parse_events` / `_parse_status`.
KNOWN_EVENT_KEYS = frozenset(
    {
        "eventUtc",
        "cardId",
        "chapterKey",
        "chapterTitle",
        "trackKey",
        "trackTitle",
        "trackLength",
        "position",
        "source",
        "playbackStatus",
        "repeatAll",
        "streaming",
        "volume",
        "volumeMax",
        "sleepTimerSeconds",
        "sleepTimerActive",
        "playbackWait",
        "requestId",
    }
)

KNOWN_STATUS_KEYS = frozenset(
    {
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
    }
)


# (raw_key, dest_key, coercer) for the data/status payload.
# Same naming as `/config.device.status` (Yoto's two endpoints share the
# raw firmware shape — see yoto_api/v3/status_adapter.py).
_STATUS_VALUE_FIELDS = (
    ("ssid", "network_ssid", lambda v: v),
    ("nightlightMode", "nightlight_mode", lambda v: v),
    ("wifiStrength", "wifi_strength", as_int),
    ("batteryLevel", "battery_level_percentage", as_int),
    ("volume", "system_volume_percentage", as_int),
    ("userVolume", "user_volume_percentage", as_int),
    ("als", "ambient_light_sensor_reading", as_int),
    ("freeDisk", "free_disk_space_bytes", as_int),
    ("totalDisk", "total_disk_space_bytes", as_int),
    ("upTime", "uptime", as_int),
    ("utcTime", "utc_time", as_int),
    ("utcOffset", "utc_offset_seconds", as_int),
    ("dnowBrightness", "current_display_brightness", as_int),
)

_STATUS_BOOL_FIELDS = (
    ("charging", "is_charging"),
    ("headphones", "is_audio_device_connected"),
    ("bluetoothHp", "is_bluetooth_audio_connected"),
    ("bgDownload", "is_background_download_active"),
)


def _parse_status(device_id: str, body: Dict[str, Any]) -> StatusPatch:
    """Pull a partial PlayerStatus update from the MQTT data/status payload.

    Same field naming as `/config.device.status`. Only includes keys that
    were present, so callers can selectively merge into the existing state.
    """
    status = body.get("status") or body
    fields: Dict[str, Any] = {}

    if "activeCard" in status:
        fields["active_card"] = coerce_active_card(status["activeCard"])

    for raw_key, dest_key, coerce in _STATUS_VALUE_FIELDS:
        if raw_key in status:
            fields[dest_key] = coerce(status[raw_key])

    for raw_key, dest_key in _STATUS_BOOL_FIELDS:
        if raw_key in status:
            fields[dest_key] = as_bool_int(status[raw_key])

    if "powerSrc" in status:
        fields["power_source"] = parse_enum(PowerSource, status["powerSrc"])
    if "cardInserted" in status:
        fields["card_insertion_state"] = parse_enum(
            CardInsertionState, status["cardInserted"]
        )
    if "day" in status:
        fields["day_mode"] = parse_enum(DayMode, status["day"])

    if "temp" in status:
        battery_temp, device_temp = parse_temp_pair(status["temp"])
        if battery_temp is not None:
            fields["battery_temperature"] = battery_temp
        if device_temp is not None:
            fields["temperature_celcius"] = device_temp

    return StatusPatch(player_id=device_id, fields=fields)


def _coerce_card_id(value: Any) -> Optional[str]:
    if value in (None, "none", ""):
        return None
    return str(value)


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
