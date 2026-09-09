from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

from ..const import ambient_hex_to_preset


@dataclass
class Alarm:
    days_enabled: str | None = None  # 7-char bitmap, e.g. "1111100"
    enabled: bool | None = None
    time: time | None = None
    sound_id: str | None = None
    volume: int | None = None


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
    day_time: time | None = None
    day_display_brightness_auto: bool | None = None
    day_display_brightness: int | None = None
    day_ambient_colour: str | None = None  # hex "#40bfd9"
    day_max_volume_limit: int | None = None
    day_yoto_daily: str | None = None  # card URI / ID
    day_yoto_radio: str | None = None
    day_sounds_off: bool | None = None

    # Night mode
    night_time: time | None = None
    night_display_brightness_auto: bool | None = None
    night_display_brightness: int | None = None
    night_ambient_colour: str | None = None
    night_max_volume_limit: int | None = None
    night_yoto_daily: str | None = None
    night_yoto_radio: str | None = None
    night_sounds_off: bool | None = None

    # Display + audio
    clock_face: str | None = None  # sentinel "digital-sun"
    hour_format: int | None = None  # 12 or 24
    bluetooth_enabled: bool | None = None
    bt_headphones_enabled: bool | None = None
    headphones_volume_limited: bool | None = None
    repeat_all: bool | None = None
    shutdown_timeout: int | None = None  # seconds
    display_dim_timeout: int | None = None  # seconds
    display_dim_brightness: int | None = None  # 0-100
    locale: str | None = None
    timezone: str | None = None
    system_volume: int | None = None
    volume_level: str | None = None  # sentinel "safe" / etc.
    log_level: str | None = None  # sentinel "error" / "none"
    show_diagnostics: bool | None = None
    pause_volume_down: bool | None = None
    pause_power_button: bool | None = None

    alarms: list[Alarm] = field(default_factory=list)

    @property
    def day_ambient_preset(self) -> str | None:
        """Day ambient colour as an app preset key, or None if custom."""
        return ambient_hex_to_preset(self.day_ambient_colour)

    @property
    def night_ambient_preset(self) -> str | None:
        """Night ambient colour as an app preset key, or None if custom."""
        return ambient_hex_to_preset(self.night_ambient_colour)
