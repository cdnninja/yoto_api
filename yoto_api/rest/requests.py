"""Request body shapes for REST write endpoints.

Player commands (play/pause/volume/sleep/etc.) are published over MQTT
directly for low latency, so their payload shapes live in
`yoto_api.v3.mqtt.client`. Only settings writes go through REST.
"""

from typing import Any, Dict, Iterable

from ..models.config import Alarm


def encode_alarm(alarm: Alarm) -> str:
    """Encode one Alarm to Yoto's comma-separated wire format.

    `<days_enabled>,<time>,<sound_id>,,,<volume>,<enabled_int>`
    """
    return ",".join(
        [
            alarm.days_enabled or "",
            alarm.time.strftime("%H:%M") if alarm.time is not None else "",
            alarm.sound_id or "",
            "",
            "",
            str(alarm.volume) if alarm.volume is not None else "",
            "1" if alarm.enabled else "0",
        ]
    )


def encode_alarms_payload(alarms: Iterable[Alarm]) -> Dict[str, Any]:
    """Encode a full alarm list into Yoto's PUT /config payload shape.

    Yoto interprets `{"alarms": [...]}` as the new full list, so callers
    must always send every alarm they want to keep.
    """
    return {"alarms": [encode_alarm(a) for a in alarms]}
