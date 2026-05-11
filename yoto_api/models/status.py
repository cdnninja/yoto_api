from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional


class PowerSource(IntEnum):
    BATTERY = 0
    V2_DOCK = 1
    USB_C = 2
    QI_DOCK = 3


class CardInsertionState(IntEnum):
    # 0/1/2 are documented at https://yoto.dev/api/getdevicestatus/.
    NONE = 0
    PHYSICAL = 1
    REMOTE = 2
    # 3 isn't in Yoto's documented spec but the firmware pushes it on MQTT
    # when Yoto Radio (or another streaming source) is playing. Best guess
    # of the semantics; rename if Yoto documents it later.
    STREAMING = 3


class DayMode(IntEnum):
    UNKNOWN = -1
    NIGHT = 0
    DAY = 1


@dataclass
class PlayerStatus:
    """Runtime telemetry. Source is GET /status when scoped, otherwise the
    /config response's device.status sub-block (see status_adapter).
    """

    device_id: str
    is_online: Optional[bool] = None
    updated_at: Optional[datetime] = None
    uptime: Optional[int] = None  # seconds
    utc_time: Optional[int] = None
    utc_offset_seconds: Optional[int] = None

    # Power
    battery_level_percentage: Optional[int] = None
    battery_temperature: Optional[int] = None
    is_charging: Optional[bool] = None
    power_source: Optional[PowerSource] = None

    # Network
    network_ssid: Optional[str] = None
    wifi_strength: Optional[int] = None  # dBm
    average_download_speed_bytes_second: Optional[int] = None
    is_background_download_active: Optional[bool] = None

    # Storage
    free_disk_space_bytes: Optional[int] = None
    total_disk_space_bytes: Optional[int] = None

    # Card / playback snapshot (live updates come via PlaybackEvent)
    active_card: Optional[str] = None
    card_insertion_state: Optional[CardInsertionState] = None

    # Audio
    system_volume_percentage: Optional[int] = None
    user_volume_percentage: Optional[int] = None
    is_audio_device_connected: Optional[bool] = None
    is_bluetooth_audio_connected: Optional[bool] = None

    # Display + ambient
    nightlight_mode: Optional[str] = None  # hex code or "off"
    day_mode: Optional[DayMode] = None
    ambient_light_sensor_reading: Optional[int] = None
    temperature_celcius: Optional[int] = None  # Yoto's typo preserved
