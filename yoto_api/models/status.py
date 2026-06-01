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
    """The player's basic live status, from the MQTT `data/status` topic.

    Holds ONLY the fields that topic actually delivers — the firmware's
    minimal set. The richer fields the player sends on `status/full` (wifi,
    ssid, power source, temperature, raw battery, …) live on
    `PlayerFullStatus`, so each object stays coherent with its source.

    Connection state (`is_online`) and identity live on `YotoPlayer`, not here.
    """

    # When this telemetry was current device-side: the device clock
    # (status/full `utcTime`, shadow `updatedAt`), or our receive time when the
    # payload carries none (data/status).
    updated_at: Optional[datetime] = None

    battery_level_percentage: Optional[int] = None
    is_charging: Optional[bool] = None
    free_disk_space_bytes: Optional[int] = None

    # Snapshot only — live playback updates arrive via PlaybackEvent.
    active_card: Optional[str] = None
    card_insertion_state: Optional[CardInsertionState] = None

    system_volume_percentage: Optional[int] = None
    user_volume_percentage: Optional[int] = None
    is_audio_device_connected: Optional[bool] = None
    is_bluetooth_audio_connected: Optional[bool] = None

    nightlight_mode: Optional[str] = None  # hex code or "off"
    day_mode: Optional[DayMode] = None
    ambient_light_sensor_reading: Optional[int] = None
    # Effective brightness now (0-100): tracks auto-dim, ALS, day/night.
    current_display_brightness: Optional[int] = None


@dataclass
class PlayerFullStatus(PlayerStatus):
    """The player's full status, from the MQTT `status/full` topic or the REST
    `/config.device.status` shadow. Superset of `PlayerStatus`: adds the
    fields the `data/status` topic doesn't carry.
    """

    battery_temperature: Optional[int] = None
    power_source: Optional[PowerSource] = None
    # Raw fuel-gauge reading before the firmware's profile smoothing — can
    # differ from battery_level_percentage.
    battery_level_raw: Optional[int] = None
    # Millivolts. Only reported while live; None in an offline shadow read.
    battery_voltage_mv: Optional[int] = None
    battery_profile: Optional[str] = None  # e.g. "LJDX30X-4500"

    network_ssid: Optional[str] = None
    wifi_strength: Optional[int] = None  # dBm
    is_background_download_active: Optional[bool] = None
    average_download_speed_bytes_second: Optional[int] = None
    total_disk_space_bytes: Optional[int] = None
    temperature_celcius: Optional[int] = None  # Yoto's typo preserved

    uptime: Optional[int] = None  # seconds
    utc_time: Optional[int] = None
    utc_offset_seconds: Optional[int] = None
