"""Request body shapes for REST write endpoints.

Player commands (play/pause/volume/sleep/etc.) are published over MQTT
directly for low latency, so their payload shapes live in
`yoto_api.v3.mqtt.client`. Only settings writes go through REST.
"""

from typing import Any, Dict, Iterable

from ..exceptions import YotoError
from ..models.config import Alarm


def encode_alarm(alarm: Alarm) -> str:
    """Encode one Alarm to Yoto's comma-separated wire format.

    `<days_enabled>,<HHMM>,<sound_id>,<slot3>,<slot4>,<volume>,<enabled_int>`
    """
    if alarm.time is None:
        raise YotoError("Cannot encode alarm without a configured time")
    parts = list(alarm._raw_parts) if alarm._raw_parts else [""] * 7
    if len(parts) < 7:
        parts.extend([""] * (7 - len(parts)))
    parts[0] = alarm.days_enabled or ""
    parts[1] = alarm.time.strftime("%H%M")
    parts[2] = alarm.sound_id or ""
    parts[5] = str(alarm.volume) if alarm.volume is not None else ""
    parts[6] = "1" if alarm.enabled else "0"
    return ",".join(parts)


def encode_alarms_payload(alarms: Iterable[Alarm]) -> Dict[str, Any]:
    """Encode a full alarm list into Yoto's PUT /config payload shape.

    Yoto interprets `{"alarms": [...]}` as the new full list, so callers
    must always send every alarm they want to keep.
    """
    return {"alarms": [encode_alarm(a) for a in alarms]}
