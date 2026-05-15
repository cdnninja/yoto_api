"""Strict shape validation against the real Yoto API.

These tests check that what Yoto actually returns matches what the lib
declares. They catch two kinds of regression:

1. Parser bugs (we typed something as `int` but the API sends `str`).
2. API changes (Yoto removes or renames a field we depend on).

If a test here breaks, either the lib needs a fix or Yoto changed
something. Both worth knowing before users hit it.

To list fields Yoto sends that the lib doesn't currently parse, see
`scripts/check_unmapped.py`.
"""

import datetime
import re

import pytest

from yoto_api import (
    CardInsertionState,
    DayMode,
    Device,
    PlayerConfig,
    PlayerInfo,
    PlayerStatus,
    PowerSource,
    YotoClient,
)
from yoto_api.models.config import Alarm

pytestmark = pytest.mark.e2e


# ─── Device (from /devices/mine) ─────────────────────────────────────


_KNOWN_FAMILIES = {"v1", "v2", "v3", "mini"}
_KNOWN_GENERATIONS = {"gen1", "gen2", "gen3"}
_KNOWN_FORM_FACTORS = {"mini", "standard"}


async def test_device_shape(client: YotoClient) -> None:
    await client.update_player_list()
    assert client.players

    for device_id, player in client.players.items():
        device = player.device
        assert isinstance(device, Device)

        # Identity
        assert device.device_id == device_id
        assert device.device_id.startswith("y"), (
            f"unexpected device_id format: {device.device_id!r}"
        )
        assert isinstance(device.name, str) and device.name

        # Family / type / generation
        assert device.device_family in _KNOWN_FAMILIES, (
            f"unknown device_family: {device.device_family!r}"
        )
        if device.generation is not None:
            assert device.generation in _KNOWN_GENERATIONS, (
                f"unknown generation: {device.generation!r}"
            )
        if device.form_factor is not None:
            assert device.form_factor in _KNOWN_FORM_FACTORS, (
                f"unknown form_factor: {device.form_factor!r}"
            )

        # Booleans must be actual bool, not 0/1 leaking through
        assert isinstance(device.has_user_given_name, bool)


# ─── PlayerInfo + PlayerConfig (from /config) ────────────────────────


_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
_FIRMWARE_RE = re.compile(r"^v?\d+\.\d+\.\d+(-\d+)?$")


async def test_player_info_shape(client: YotoClient, first_device_id: str) -> None:
    info = await client.update_player_info(first_device_id)
    assert isinstance(info, PlayerInfo)

    # Hardware metadata must be present and well-formed
    assert info.device_id == first_device_id
    assert info.mac and _MAC_RE.match(info.mac.lower()), (
        f"invalid MAC format: {info.mac!r}"
    )
    assert info.firmware_version and _FIRMWARE_RE.match(info.firmware_version), (
        f"invalid firmware version: {info.firmware_version!r}"
    )
    if info.geo_timezone is not None:
        # Loose check: timezone should look like "Region/City"
        assert "/" in info.geo_timezone, (
            f"unexpected geo_timezone: {info.geo_timezone!r}"
        )


async def test_player_config_field_types(
    client: YotoClient, first_device_id: str
) -> None:
    """The whole point of v3 typing: settings must be proper Python types,
    not strings."""
    await client.update_player_info(first_device_id)
    config = client.players[first_device_id].info.config
    assert isinstance(config, PlayerConfig)

    # Times — datetime.time, not str
    if config.day_time is not None:
        assert isinstance(config.day_time, datetime.time)
    if config.night_time is not None:
        assert isinstance(config.night_time, datetime.time)

    # Numerics — int, not str
    for name in (
        "day_max_volume_limit",
        "night_max_volume_limit",
        "shutdown_timeout",
        "display_dim_timeout",
        "display_dim_brightness",
        "system_volume",
        "hour_format",
    ):
        value = getattr(config, name)
        if value is not None:
            assert isinstance(value, int), (
                f"{name} should be int, got {type(value).__name__}"
            )

    # Booleans — bool, not "1"/"0" string
    for name in (
        "bt_headphones_enabled",
        "headphones_volume_limited",
        "repeat_all",
        "show_diagnostics",
        "pause_volume_down",
        "pause_power_button",
        "day_sounds_off",
        "night_sounds_off",
        "bluetooth_enabled",
    ):
        value = getattr(config, name)
        if value is not None:
            assert isinstance(value, bool), (
                f"{name} should be bool, got {type(value).__name__}"
            )

    # Brightness split — auto/value mutually consistent
    for prefix in ("day", "night"):
        auto = getattr(config, f"{prefix}_display_brightness_auto")
        value = getattr(config, f"{prefix}_display_brightness")
        if auto is True:
            assert value is None, (
                f"{prefix}_display_brightness should be None when auto=True"
            )
        if value is not None:
            assert auto is False, (
                f"{prefix}_display_brightness_auto should be False when value is set"
            )
            assert isinstance(value, int)


async def test_alarm_shape(client: YotoClient, first_device_id: str) -> None:
    """If alarms exist, their fields are correctly typed."""
    await client.update_player_info(first_device_id)
    alarms = client.players[first_device_id].info.config.alarms

    if not alarms:
        pytest.skip("no alarms set on this device")

    for alarm in alarms:
        assert isinstance(alarm, Alarm)
        if alarm.time is not None:
            assert isinstance(alarm.time, datetime.time)
        if alarm.volume is not None:
            assert isinstance(alarm.volume, int)
        if alarm.days_enabled is not None:
            assert re.match(r"^[01]{7}$", alarm.days_enabled), (
                f"days_enabled should be a 7-char bitmap: {alarm.days_enabled!r}"
            )
        assert isinstance(alarm.enabled, bool)


# ─── PlayerStatus (from /status or /config.device.status fallback) ───


async def test_player_status_shape(client: YotoClient, first_device_id: str) -> None:
    status = await client.update_player_status(first_device_id)
    assert isinstance(status, PlayerStatus)

    if status.battery_level_percentage is not None:
        assert 0 <= status.battery_level_percentage <= 100

    if status.wifi_strength is not None:
        assert isinstance(status.wifi_strength, int)
        # dBm: typically negative, somewhere between -90 and -30
        assert -100 <= status.wifi_strength <= 0, (
            f"wifi_strength {status.wifi_strength} dBm is out of normal range"
        )

    if status.system_volume_percentage is not None:
        assert 0 <= status.system_volume_percentage <= 100
    if status.user_volume_percentage is not None:
        assert 0 <= status.user_volume_percentage <= 100

    # Booleans must be actual bool (not 0/1 leaking through)
    for name in (
        "is_online",
        "is_charging",
        "is_audio_device_connected",
        "is_bluetooth_audio_connected",
        "is_background_download_active",
    ):
        value = getattr(status, name)
        if value is not None:
            assert isinstance(value, bool), (
                f"{name} should be bool, got {type(value).__name__}: {value!r}"
            )

    # Enums must be the typed enum, not raw int
    if status.power_source is not None:
        assert isinstance(status.power_source, PowerSource)
    if status.card_insertion_state is not None:
        assert isinstance(status.card_insertion_state, CardInsertionState)
    if status.day_mode is not None:
        assert isinstance(status.day_mode, DayMode)


# ─── Raw response shape (catches Yoto removing/renaming fields) ──────


async def test_devices_mine_top_level_keys(client: YotoClient) -> None:
    """Catches Yoto removing or renaming the top-level `devices` array."""
    raw = await client._rest._get(
        client.token, "/device-v2/devices/mine", "raw shape probe"
    )
    assert "devices" in raw
    assert isinstance(raw["devices"], list)
    if raw["devices"]:
        item = raw["devices"][0]
        # The fields we depend on
        for key in ("deviceId", "name", "deviceType", "deviceFamily"):
            assert key in item, f"`{key}` missing from /devices/mine item"


async def test_config_top_level_keys(client: YotoClient, first_device_id: str) -> None:
    """Catches Yoto removing or renaming the `device`/`config` blocks."""
    raw = await client._rest._get(
        client.token,
        f"/device-v2/{first_device_id}/config",
        "raw shape probe",
    )
    assert "device" in raw
    device = raw["device"]
    for key in ("deviceId", "mac", "releaseChannelVersion", "config"):
        assert key in device, f"`device.{key}` missing from /config response"
    assert isinstance(device["config"], dict)
