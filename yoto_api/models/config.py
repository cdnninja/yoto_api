from dataclasses import dataclass, field
from datetime import time
from typing import List, Optional


@dataclass
class Alarm:
    days_enabled: Optional[str] = None  # 7-char bitmap, e.g. "1111100"
    enabled: Optional[bool] = None
    time: Optional[time] = None
    sound_id: Optional[str] = None
    volume: Optional[int] = None


@dataclass
class PlayerConfig:
    """User-editable settings from /device-v2/{id}/config -> device.config.

    Yoto's API returns most numeric and boolean fields as strings (e.g.
    `"100"` for brightness, `"1"` for booleans). The lib coerces on read
    and serializes back on write so consumers see proper Python types.

    Display brightness is split into `_auto` + value because the API
    overloads one field for both: `"auto"` (sentinel) or an int. Consumers
    set one or the other, never both.
    """

    # Day mode
    day_time: Optional[time] = None
    day_display_brightness_auto: Optional[bool] = None
    day_display_brightness: Optional[int] = None
    day_ambient_colour: Optional[str] = None  # hex "#40bfd9"
    day_max_volume_limit: Optional[int] = None
    day_yoto_daily: Optional[str] = None  # card URI / ID
    day_yoto_radio: Optional[str] = None
    day_sounds_off: Optional[bool] = None

    # Night mode
    night_time: Optional[time] = None
    night_display_brightness_auto: Optional[bool] = None
    night_display_brightness: Optional[int] = None
    night_ambient_colour: Optional[str] = None
    night_max_volume_limit: Optional[int] = None
    night_yoto_daily: Optional[str] = None
    night_yoto_radio: Optional[str] = None
    night_sounds_off: Optional[bool] = None

    # Display + audio
    clock_face: Optional[str] = None  # sentinel "digital-sun"
    hour_format: Optional[int] = None  # 12 or 24
    bluetooth_enabled: Optional[bool] = None
    bt_headphones_enabled: Optional[bool] = None
    headphones_volume_limited: Optional[bool] = None
    repeat_all: Optional[bool] = None
    shutdown_timeout: Optional[int] = None  # seconds
    display_dim_timeout: Optional[int] = None  # seconds
    display_dim_brightness: Optional[int] = None  # 0-100
    locale: Optional[str] = None
    timezone: Optional[str] = None
    system_volume: Optional[int] = None
    volume_level: Optional[str] = None  # sentinel "safe" / etc.
    log_level: Optional[str] = None  # sentinel "error" / "none"
    show_diagnostics: Optional[bool] = None
    pause_volume_down: Optional[bool] = None
    pause_power_button: Optional[bool] = None

    alarms: List[Alarm] = field(default_factory=list)
