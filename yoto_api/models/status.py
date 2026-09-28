from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


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
    # 3 isn't documented, but the firmware pushes it on MQTT when Yoto Radio
    # (or another streaming source) is playing.
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
    `PlayerExtendedStatus`, so each object stays coherent with its source.

    Connection state (`is_online`) and identity live on `YotoPlayer`, not here.
    """

    # When this telemetry was current device-side: the device clock
    # (status/full `utcTime`, shadow `updatedAt`), or our receive time when the
    # payload carries none (data/status).
    updated_at: datetime | None = None

    battery_level_percentage: int | None = None
    is_charging: bool | None = None
    free_disk_space_bytes: int | None = None

    # Snapshot only — live playback updates arrive via PlaybackEvent.
    active_card: str | None = None
    card_insertion_state: CardInsertionState | None = None

    system_volume_percentage: int | None = None
    user_volume_percentage: int | None = None
    is_audio_device_connected: bool | None = None
    is_bluetooth_audio_connected: bool | None = None

    nightlight_mode: str | None = None  # hex code or "off"
    day_mode: DayMode | None = None
    ambient_light_sensor_reading: int | None = None
    # Effective brightness now (0-100): tracks auto-dim, ALS, day/night.
    current_display_brightness: int | None = None


@dataclass
class PlayerExtendedStatus(PlayerStatus):
    """The player's extended status, from the MQTT `status/full` topic or the
    REST `/config.device.status` shadow. Superset of `PlayerStatus`: adds the
    fields the `data/status` topic doesn't carry.
    """

    battery_temperature: int | None = None
    power_source: PowerSource | None = None
    # Raw fuel-gauge reading before the firmware's profile smoothing — can
    # differ from battery_level_percentage.
    battery_level_raw: int | None = None
    # Millivolts. Only reported while live; None in an offline shadow read.
    battery_voltage_mv: int | None = None
    battery_profile: str | None = None  # e.g. "LJDX30X-4500"

    network_ssid: str | None = None
    wifi_strength: int | None = None  # dBm
    is_background_download_active: bool | None = None
    average_download_speed_bytes_second: int | None = None
    total_disk_space_bytes: int | None = None
    temperature_celcius: int | None = None  # Yoto's typo preserved

    uptime: int | None = None  # seconds
    utc_time: int | None = None
    utc_offset_seconds: int | None = None
