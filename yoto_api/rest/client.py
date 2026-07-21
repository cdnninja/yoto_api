"""REST client for the Yoto API.

Thin wrapper around `aiohttp` that wraps transport errors into the
`YotoError` hierarchy and returns typed models from `yoto_api.models`
rather than raw dicts.
"""

import json
from typing import Any, Dict, List, Optional

import aiohttp

from ..exceptions import AuthenticationError, YotoAPIError
from ..Token import Token
from .._coerce import (
    as_bool,
    as_int,
    parse_brightness,
    parse_hhmm,
)
from ..models.config import Alarm, PlayerConfig
from ..models.device import Device
from ..models.info import PlayerInfo
from ..models.status import PlayerExtendedStatus
from ..status_adapter import adapt_raw_status
from . import endpoints

DEFAULT_TIMEOUT_SECONDS = 30.0


class RestClient:
    """Async wrapper around the Yoto REST API. Token is passed per call."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._session = session
        self.base_url = endpoints.BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    # ─── Inventory ────────────────────────────────────────────────

    async def list_devices(self, token: Token) -> List[tuple[Device, bool]]:
        """Return (Device, online) pairs from /devices/mine.

        `online` is split out because it's mutable state — it belongs on
        `YotoPlayer.is_online`, not on the immutable `Device` identity.
        """
        response = await self._get(token, endpoints.DEVICES_MINE, "list devices")
        try:
            items = response["devices"]
        except (KeyError, TypeError) as err:
            raise YotoAPIError(f"List devices response malformed: {err}") from err
        return [
            (_parse_device(item), bool(item.get("online", False))) for item in items
        ]

    # ─── Player config + status ───────────────────────────────────

    async def get_player_info(
        self, token: Token, device_id: str
    ) -> tuple[PlayerInfo, bool]:
        """Return (PlayerInfo, online) from /config.

        `online` is split out because it's mutable state — it belongs on
        `YotoPlayer.is_online`, not on the otherwise stable `PlayerInfo`.
        """
        response = await self._get(
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

    async def get_player_status(
        self, token: Token, device_id: str
    ) -> tuple[PlayerExtendedStatus, Optional[bool]]:
        """Read the last-known telemetry snapshot from the device shadow.

        Returns `(PlayerExtendedStatus, online)`. Reads the `device.status`
        sub-block out of /config — the AWS IoT shadow, which can lag until
        refreshed (live) or hold the last-reported state (offline). Live
        telemetry is sourced over MQTT (see YotoMqttClient); this is the
        offline / cold-start fallback. `online` is split out because it's
        connection state, tracked on `YotoPlayer.is_online`.

        We deliberately don't use the documented /status endpoint: it needs
        the `family:device-status:view` scope (which HA core's token lacks,
        and Yoto is deprecating) and `/config.device.status` carries the same
        firmware status block.
        """
        config = await self._get(
            token,
            endpoints.device_config(device_id),
            f"get player {device_id} status",
        )
        device_block = config.get("device") or {}
        extended_status = adapt_raw_status(device_block.get("status") or {})
        online = device_block.get("online")
        return extended_status, online if isinstance(online, bool) else None

    # ─── Settings writes ──────────────────────────────────────────

    async def get_raw_config(self, token: Token, device_id: str) -> Dict[str, Any]:
        """Unparsed so `update_settings` can merge onto it: a
        parse-then-reserialise drops the keys the lib doesn't map yet.
        """
        response = await self._get(
            token,
            endpoints.device_config(device_id),
            f"get player {device_id} raw config",
        )
        raw = (response.get("device") or {}).get("config")
        return raw if isinstance(raw, dict) else {}

    async def update_settings(
        self, token: Token, device_id: str, payload: Dict[str, Any]
    ) -> None:
        """Merge `payload` (API keys) into the device's current config.

        `PUT /config` replaces the whole block and the firmware refills
        missing keys with its defaults, so a partial write resets every
        setting it omits. Re-read on each write rather than cached: the
        config also changes from the Yoto app.
        """
        raw = await self.get_raw_config(token, device_id)
        body = {"deviceId": device_id, "config": {**raw, **payload}}
        await self._put(
            token,
            endpoints.device_config(device_id),
            f"update player {device_id} settings",
            body,
        )

    # ─── Status push (documented command endpoint) ───────────────
    #
    # The other player commands (play/pause/volume/etc.) are published
    # directly over MQTT for low latency. See YotoMqttClient.

    async def request_player_status(self, token: Token, device_id: str) -> None:
        """Tell the player to push its current status onto MQTT now."""
        await self._post(
            token,
            endpoints.command_status(device_id),
            f"request status push {device_id}",
            {},
        )

    # ─── Library ──────────────────────────────────────────────────

    async def get_card_library(self, token: Token) -> Dict[str, Any]:
        return await self._get(token, endpoints.CARDS_LIBRARY, "get card library")

    async def get_card_detail(self, token: Token, card_id: str) -> Dict[str, Any]:
        return await self._get(
            token, endpoints.card_detail(card_id), f"get card {card_id} detail"
        )

    async def get_card_groups(self, token: Token) -> List[Dict[str, Any]]:
        """GET /card/family/library/groups — a top-level JSON array of groups
        (unlike the other endpoints, which return objects)."""
        raw: Any = await self._get(
            token, endpoints.CARDS_LIBRARY_GROUPS, "get card groups"
        )
        return raw if isinstance(raw, list) else []

    # ─── Internals ────────────────────────────────────────────────

    def _headers(self, token: Token) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token.access_token}",
        }

    async def _get(self, token: Token, path: str, what: str) -> Dict[str, Any]:
        return await self._request(token, "GET", path, what)

    async def _put(
        self, token: Token, path: str, what: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._request(token, "PUT", path, what, body=body)

    async def _post(
        self, token: Token, path: str, what: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._request(token, "POST", path, what, body=body)

    async def _request(
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
            async with self._session.request(method, url, **kwargs) as response:
                status = response.status
                if status >= 400:
                    text = await response.text()
                    if status == 401:
                        raise AuthenticationError(f"{what} unauthorized: {text}")
                    raise YotoAPIError(
                        f"{what} failed (HTTP {status}): {text}",
                        status_code=status,
                    )
                raw = await response.read()
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except ValueError as err:
                    raise YotoAPIError(f"{what} returned invalid JSON: {err}") from err
        except aiohttp.ClientError as err:
            raise YotoAPIError(f"{what} failed: {err}") from err


# ─── Known keys (for unmapped-keys detection) ────────────────────────
#
# Co-located with the parsers below so they're easy to keep in sync.
# `scripts/check_unmapped.py` imports these to flag new fields Yoto
# starts sending.

KNOWN_DEVICE_KEYS = frozenset(
    {
        "deviceId",
        "name",
        "errorCode",
        "fwVersion",
        "popCode",
        "releaseChannelId",
        "releaseChannelVersion",
        "activationPopCode",
        "registrationCode",
        "deviceType",
        "deviceFamily",
        "deviceGroup",
        "generation",
        "formFactor",
        "mac",
        "online",
        "geoTimezone",
        "getPosix",
    }
)

KNOWN_CONFIG_KEYS = frozenset(
    {
        "dayTime",
        "dayDisplayBrightness",
        "ambientColour",
        "maxVolumeLimit",
        "dayYotoDaily",
        "dayYotoRadio",
        "daySoundsOff",
        "nightTime",
        "nightDisplayBrightness",
        "nightAmbientColour",
        "nightMaxVolumeLimit",
        "nightYotoDaily",
        "nightYotoRadio",
        "nightSoundsOff",
        "clockFace",
        "hourFormat",
        "bluetoothEnabled",
        "btHeadphonesEnabled",
        "headphonesVolumeLimited",
        "repeatAll",
        "shutdownTimeout",
        "displayDimTimeout",
        "displayDimBrightness",
        "locale",
        "timezone",
        "systemVolume",
        "volumeLevel",
        "logLevel",
        "showDiagnostics",
        "pauseVolumeDown",
        "pausePowerButton",
        "alarms",
    }
)

# ─── Response parsers (private helpers) ──────────────────────────────


def _parse_device(item: Dict[str, Any]) -> Device:
    # `online` is intentionally not on Device — it's mutable state
    # tracked via YotoPlayer.is_online; YotoClient.update_player_list
    # propagates the value from this same payload onto the player.
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
