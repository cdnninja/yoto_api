"""REST client for the Yoto API.

Wraps `requests` with the v2 exception hierarchy. Returns typed models
from `yoto_api.v3.models` rather than raw dicts.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from ..const import DOMAIN
from ..exceptions import AuthenticationError, YotoAPIError
from ..Token import Token
from .._coerce import (
    as_bool,
    as_int,
    coerce_active_card,
    parse_brightness,
    parse_enum,
    parse_hhmm,
    parse_iso,
)
from ..models.config import Alarm, PlayerConfig
from ..models.device import Device
from ..models.info import PlayerInfo
from ..models.status import (
    CardInsertionState,
    DayMode,
    PlayerStatus,
    PowerSource,
)
from ..status_adapter import adapt_raw_status
from . import endpoints

_LOGGER = logging.getLogger(__name__)

_USER_AGENT = "Yoto/2.73 (com.yotoplay.Yoto; build:10405; iOS 17.4.0) Alamofire/5.6.4"


DEFAULT_TIMEOUT_SECONDS = 30.0


class RestClient:
    """Stateless wrapper around the Yoto REST API. Token is passed per call."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = endpoints.BASE_URL
        self.timeout = timeout

    # ─── Inventory ────────────────────────────────────────────────

    def list_devices(self, token: Token) -> List[tuple[Device, bool]]:
        """Return (Device, online) pairs from /devices/mine.

        `online` is split out because it's mutable state — it belongs on
        `PlayerStatus.is_online`, not on the immutable `Device` identity.
        """
        response = self._get(token, endpoints.DEVICES_MINE, "list devices")
        try:
            items = response["devices"]
        except (KeyError, TypeError) as err:
            raise YotoAPIError(f"List devices response malformed: {err}") from err
        return [
            (_parse_device(item), bool(item.get("online", False))) for item in items
        ]

    # ─── Player config + status ───────────────────────────────────

    def get_player_info(self, token: Token, device_id: str) -> tuple[PlayerInfo, bool]:
        """Return (PlayerInfo, online) from /config.

        `online` is split out because it's mutable state — it belongs on
        `PlayerStatus.is_online`, not on the otherwise stable `PlayerInfo`.
        """
        response = self._get(
            token, endpoints.device_config(device_id), f"get player {device_id} config"
        )
        try:
            info = _parse_player_info(response)
            online = bool((response.get("device") or {}).get("online", False))
            return info, online
        except (KeyError, TypeError, ValueError) as err:
            raise YotoAPIError(
                f"Player {device_id} config response malformed: {err}"
            ) from err

    def get_player_status(self, token: Token, device_id: str) -> PlayerStatus:
        """Force a fresh telemetry snapshot.

        Tries the documented /status endpoint first. If the token doesn't
        carry `family:device-status:view` (HTTP 403), falls back to reading
        the `device.status` sub-block out of /config.
        """
        try:
            raw = self._get(
                token,
                endpoints.device_status(device_id),
                f"get player {device_id} status",
            )
            return _parse_status_response(raw, device_id)
        except YotoAPIError as err:
            if not _is_scope_403(err):
                raise
            _LOGGER.debug(
                "%s - /status forbidden, falling back to /config.device.status",
                DOMAIN,
            )

        config = self._get(
            token,
            endpoints.device_config(device_id),
            f"get player {device_id} config (status fallback)",
        )
        device_block = config.get("device") or {}
        status = adapt_raw_status(device_block.get("status") or {}, device_id)
        is_online = device_block.get("online")
        if isinstance(is_online, bool):
            status.is_online = is_online
        return status

    # ─── Settings writes ──────────────────────────────────────────

    def update_settings(
        self, token: Token, device_id: str, payload: Dict[str, Any]
    ) -> None:
        body = {"deviceId": device_id, "config": payload}
        self._put(
            token,
            endpoints.device_config(device_id),
            f"update player {device_id} settings",
            body,
        )

    # ─── Status push (documented command endpoint) ───────────────
    #
    # The other player commands (play/pause/volume/etc.) are published
    # directly over MQTT for low latency. See YotoMqttClient.

    def request_status_push(self, token: Token, device_id: str) -> None:
        """Tell the player to push its current status onto MQTT now."""
        self._post(
            token,
            endpoints.command_status(device_id),
            f"request status push {device_id}",
            {},
        )

    # ─── Library ──────────────────────────────────────────────────

    def get_card_library(self, token: Token) -> Dict[str, Any]:
        return self._get(token, endpoints.CARDS_LIBRARY, "get card library")

    def get_card_detail(self, token: Token, card_id: str) -> Dict[str, Any]:
        return self._get(
            token, endpoints.card_detail(card_id), f"get card {card_id} detail"
        )

    # ─── Internals ────────────────────────────────────────────────

    def _headers(self, token: Token) -> Dict[str, str]:
        return {
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token.access_token}",
        }

    def _get(self, token: Token, path: str, what: str) -> Dict[str, Any]:
        return self._request(token, "GET", path, what)

    def _put(
        self, token: Token, path: str, what: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request(token, "PUT", path, what, body=body)

    def _post(
        self, token: Token, path: str, what: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request(token, "POST", path, what, body=body)

    def _request(
        self,
        token: Token,
        method: str,
        path: str,
        what: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self.base_url + path
        kwargs: Dict[str, Any] = {
            "headers": self._headers(token),
            "timeout": self.timeout,
        }
        if body is not None:
            kwargs["data"] = json.dumps(body)
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except requests.HTTPError as err:
            status = err.response.status_code if err.response is not None else None
            text = err.response.text if err.response is not None else ""
            if status == 401:
                raise AuthenticationError(f"{what} unauthorized: {text}") from err
            raise YotoAPIError(
                f"{what} failed (HTTP {status}): {text or err}",
                status_code=status,
            ) from err
        except (requests.RequestException, ValueError) as err:
            raise YotoAPIError(f"{what} failed: {err}") from err


# ─── Response parsers (private helpers) ──────────────────────────────


def _parse_device(item: Dict[str, Any]) -> Device:
    # `online` is intentionally not on Device — it's mutable state
    # tracked via PlayerStatus.is_online; YotoClient.update_player_list
    # propagates the value from this same payload onto the status.
    return Device(
        device_id=item["deviceId"],
        name=item.get("name") or "",
        description=item.get("description"),
        device_type=item.get("deviceType"),
        device_family=item.get("deviceFamily"),
        device_group=item.get("deviceGroup"),
        generation=item.get("generation"),
        form_factor=item.get("formFactor"),
        release_channel=item.get("releaseChannel"),
        has_user_given_name=bool(item.get("hasUserGivenName", False)),
    )


def _parse_player_info(response: Dict[str, Any]) -> PlayerInfo:
    device = response.get("device") or {}
    raw_config = device.get("config") or {}

    return PlayerInfo(
        device_id=device["deviceId"],
        name=device.get("name"),
        firmware_version=device.get("releaseChannelVersion"),
        pop_code=device.get("popCode"),
        activation_pop_code=device.get("activationPopCode"),
        release_channel_id=device.get("releaseChannelId"),
        device_type=device.get("deviceType"),
        device_family=device.get("deviceFamily"),
        device_group=device.get("deviceGroup"),
        mac=device.get("mac"),
        geo_timezone=device.get("geoTimezone"),
        error_code=device.get("errorCode"),
        config=_parse_player_config(raw_config),
    )


def _parse_player_config(raw: Dict[str, Any]) -> PlayerConfig:
    day_brightness_auto, day_brightness = parse_brightness(
        raw.get("dayDisplayBrightness")
    )
    night_brightness_auto, night_brightness = parse_brightness(
        raw.get("nightDisplayBrightness")
    )
    config = PlayerConfig(
        # Day mode
        day_time=parse_hhmm(raw.get("dayTime")),
        day_display_brightness_auto=day_brightness_auto,
        day_display_brightness=day_brightness,
        day_ambient_colour=raw.get("ambientColour"),
        day_max_volume_limit=as_int(raw.get("maxVolumeLimit")),
        day_yoto_daily=raw.get("dayYotoDaily"),
        day_yoto_radio=raw.get("dayYotoRadio"),
        day_sounds_off=as_bool(raw.get("daySoundsOff")),
        # Night mode
        night_time=parse_hhmm(raw.get("nightTime")),
        night_display_brightness_auto=night_brightness_auto,
        night_display_brightness=night_brightness,
        night_ambient_colour=raw.get("nightAmbientColour"),
        night_max_volume_limit=as_int(raw.get("nightMaxVolumeLimit")),
        night_yoto_daily=raw.get("nightYotoDaily"),
        night_yoto_radio=raw.get("nightYotoRadio"),
        night_sounds_off=as_bool(raw.get("nightSoundsOff")),
        # Display + audio
        clock_face=raw.get("clockFace"),
        hour_format=as_int(raw.get("hourFormat")),
        bluetooth_enabled=as_bool(raw.get("bluetoothEnabled")),
        bt_headphones_enabled=as_bool(raw.get("btHeadphonesEnabled")),
        headphones_volume_limited=as_bool(raw.get("headphonesVolumeLimited")),
        repeat_all=as_bool(raw.get("repeatAll")),
        shutdown_timeout=as_int(raw.get("shutdownTimeout")),
        display_dim_timeout=as_int(raw.get("displayDimTimeout")),
        display_dim_brightness=as_int(raw.get("displayDimBrightness")),
        locale=raw.get("locale"),
        timezone=raw.get("timezone"),
        system_volume=as_int(raw.get("systemVolume")),
        volume_level=raw.get("volumeLevel"),
        log_level=raw.get("logLevel"),
        show_diagnostics=as_bool(raw.get("showDiagnostics")),
        pause_volume_down=as_bool(raw.get("pauseVolumeDown")),
        pause_power_button=as_bool(raw.get("pausePowerButton")),
    )
    config.alarms = [_parse_alarm(s) for s in (raw.get("alarms") or [])]
    return config


def _parse_alarm(encoded: str) -> Alarm:
    parts = encoded.split(",")
    enabled: Optional[bool] = None
    if len(parts) > 6:
        enabled = parts[6] != "0"
    return Alarm(
        days_enabled=parts[0] if len(parts) > 0 else None,
        time=parse_hhmm(parts[1]) if len(parts) > 1 else None,
        sound_id=parts[2] if len(parts) > 2 else None,
        volume=as_int(parts[5]) if len(parts) > 5 else None,
        enabled=enabled if enabled is not None else True,
    )


def _parse_status_response(raw: Dict[str, Any], device_id: str) -> PlayerStatus:
    """Parse the documented /status response (long field names, typed)."""
    return PlayerStatus(
        device_id=device_id,
        is_online=raw.get("isOnline"),
        updated_at=parse_iso(raw.get("updatedAt")),
        uptime=raw.get("uptime"),
        utc_time=raw.get("utcTime"),
        utc_offset_seconds=raw.get("utcOffsetSeconds"),
        battery_level_percentage=raw.get("batteryLevelPercentage"),
        is_charging=raw.get("isCharging"),
        power_source=parse_enum(PowerSource, raw.get("powerSource")),
        network_ssid=raw.get("networkSsid"),
        wifi_strength=raw.get("wifiStrength"),
        average_download_speed_bytes_second=raw.get("averageDownloadSpeedBytesSecond"),
        is_background_download_active=raw.get("isBackgroundDownloadActive"),
        free_disk_space_bytes=raw.get("freeDiskSpaceBytes"),
        total_disk_space_bytes=raw.get("totalDiskSpaceBytes"),
        active_card=coerce_active_card(raw.get("activeCard")),
        card_insertion_state=parse_enum(
            CardInsertionState, raw.get("cardInsertionState")
        ),
        system_volume_percentage=raw.get("systemVolumePercentage"),
        user_volume_percentage=raw.get("userVolumePercentage"),
        is_audio_device_connected=raw.get("isAudioDeviceConnected"),
        is_bluetooth_audio_connected=raw.get("isBluetoothAudioConnected"),
        nightlight_mode=raw.get("nightlightMode"),
        day_mode=parse_enum(DayMode, raw.get("dayMode")),
        ambient_light_sensor_reading=raw.get("ambientLightSensorReading"),
        temperature_celcius=_parse_documented_temp(raw.get("temperatureCelcius")),
    )


def _parse_documented_temp(value: Any) -> Optional[int]:
    """`/status` returns temp as a string int like "20", or "notSupported".

    The raw `/config.device.status` form (`"battery:device"`) uses
    `parse_temp_pair` instead.
    """
    if value in (None, "notSupported", ""):
        return None
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced != 0 else None


def _is_scope_403(err: YotoAPIError) -> bool:
    """Did we get a 403 because of a missing OAuth scope?

    Yoto returns 403 for both unauthorized routes and missing scopes;
    we treat any 403 as "fall back to /config", which is the only
    actionable case anyway.
    """
    return err.status_code == 403
