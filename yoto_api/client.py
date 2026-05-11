"""YotoClient — façade exposing the v3 API.

Wires Auth + RestClient + MqttClient together. Holds the player dict and
applies MQTT events to the right `YotoPlayer`.
"""

import datetime
import logging
from dataclasses import fields
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Union

import pytz

from .Card import Card, Chapter, Track
from .const import DOMAIN
from .exceptions import YotoError
from .Token import Token
from .utils import get_child_value, get_raw_value
from .auth import Auth
from .models.event import PlaybackEvent, StatusPatch
from .models.info import PlayerInfo
from .models.player import YotoPlayer
from .models.status import PlayerStatus
from .mqtt import YotoMqttClient
from .models.config import Alarm
from .rest import RestClient
from .rest.requests import encode_alarms_payload

_LOGGER = logging.getLogger(__name__)

UpdateCallback = Callable[[YotoPlayer], None]
DisconnectCallback = Callable[[int], None]


def _serialize_hhmm(value: Any) -> str:
    if isinstance(value, datetime.time):
        return value.strftime("%H:%M")
    raise YotoError(f"expected datetime.time, got {type(value).__name__}")


def _serialize_int(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise YotoError(f"expected int, got {type(value).__name__}")
    return str(value)


def _serialize_bool_01(value: Any) -> str:
    if not isinstance(value, bool):
        raise YotoError(f"expected bool, got {type(value).__name__}")
    return "1" if value else "0"


def _serialize_passthrough(value: Any) -> Any:
    return value


# (snake_case PlayerConfig field) -> (Yoto camelCase API key, serializer).
# Mirror of `_parse_player_config` in rest/client.py. Keep in sync.
# Note two asymmetries: Yoto treats day_ambient_colour as the default
# `ambientColour`, and day_max_volume_limit as the default `maxVolumeLimit`.
# `display_brightness` is special-cased below — auto/value pair maps to
# one API field.
_CONFIG_FIELD_MAP: Dict[str, tuple] = {
    # Day mode
    "day_time": ("dayTime", _serialize_hhmm),
    "day_ambient_colour": ("ambientColour", _serialize_passthrough),
    "day_max_volume_limit": ("maxVolumeLimit", _serialize_int),
    "day_yoto_daily": ("dayYotoDaily", _serialize_passthrough),
    "day_yoto_radio": ("dayYotoRadio", _serialize_passthrough),
    "day_sounds_off": ("daySoundsOff", _serialize_bool_01),
    # Night mode
    "night_time": ("nightTime", _serialize_hhmm),
    "night_ambient_colour": ("nightAmbientColour", _serialize_passthrough),
    "night_max_volume_limit": ("nightMaxVolumeLimit", _serialize_int),
    "night_yoto_daily": ("nightYotoDaily", _serialize_passthrough),
    "night_yoto_radio": ("nightYotoRadio", _serialize_passthrough),
    "night_sounds_off": ("nightSoundsOff", _serialize_bool_01),
    # Display + audio
    "clock_face": ("clockFace", _serialize_passthrough),
    "hour_format": ("hourFormat", _serialize_int),
    "bluetooth_enabled": ("bluetoothEnabled", _serialize_bool_01),
    "bt_headphones_enabled": ("btHeadphonesEnabled", _serialize_passthrough),
    "headphones_volume_limited": ("headphonesVolumeLimited", _serialize_passthrough),
    "repeat_all": ("repeatAll", _serialize_passthrough),
    "shutdown_timeout": ("shutdownTimeout", _serialize_int),
    "display_dim_timeout": ("displayDimTimeout", _serialize_int),
    "display_dim_brightness": ("displayDimBrightness", _serialize_int),
    "locale": ("locale", _serialize_passthrough),
    "timezone": ("timezone", _serialize_passthrough),
    "system_volume": ("systemVolume", _serialize_int),
    "volume_level": ("volumeLevel", _serialize_passthrough),
    "log_level": ("logLevel", _serialize_passthrough),
    "show_diagnostics": ("showDiagnostics", _serialize_passthrough),
    "pause_volume_down": ("pauseVolumeDown", _serialize_passthrough),
    "pause_power_button": ("pausePowerButton", _serialize_passthrough),
}

# These four kwargs share two API keys via the brightness encoding:
# either send "auto" or send a stringified int — never both.
_BRIGHTNESS_PAIRS = (
    ("day_display_brightness_auto", "day_display_brightness", "dayDisplayBrightness"),
    (
        "night_display_brightness_auto",
        "night_display_brightness",
        "nightDisplayBrightness",
    ),
)


class YotoClient:
    """High-level client. One instance per Yoto account."""

    def __init__(self, client_id: Optional[str] = None) -> None:
        self._auth = Auth(client_id=client_id)
        self._rest = RestClient()
        self._mqtt: Optional[YotoMqttClient] = None
        self._update_callback: Optional[UpdateCallback] = None
        self._disconnect_callback: Optional[DisconnectCallback] = None
        self._connected_player_ids: List[str] = []

        self.token: Optional[Token] = None
        self.players: Dict[str, YotoPlayer] = {}
        self.library: Dict[str, Card] = {}

    # ─── Auth ─────────────────────────────────────────────────────

    def set_refresh_token(self, refresh_token: str) -> None:
        self.token = Token(refresh_token=refresh_token)

    def device_code_flow_start(self) -> dict:
        return self._auth.device_code_flow_start()

    def device_code_flow_complete(self, auth_result: dict) -> Token:
        self.token = self._auth.poll_for_token(auth_result)
        return self.token

    def check_and_refresh_token(self) -> Token:
        """Refresh the access token if it's expired or about to expire."""
        if self.token is None:
            raise YotoError("No token available; authenticate first")
        if (
            self.token.access_token is None
            or self.token.valid_until is None
            or self.token.valid_until - timedelta(hours=1)
            <= datetime.datetime.now(pytz.utc)
        ):
            _LOGGER.debug("%s - access token expired or near, refreshing", DOMAIN)
            self.token = self._auth.refresh(self.token)
            if self._mqtt is not None:
                # MQTT auth uses the access token; rotate the connection
                # while preserving the player list and callbacks.
                self.reconnect_events()
        return self.token

    # ─── Inventory ────────────────────────────────────────────────

    def update_player_list(self) -> None:
        """GET /devices/mine. Adds new players, updates identity + online state.

        If MQTT is connected, new players are auto-subscribed and removed
        ones are unsubscribed.
        """
        token = self.check_and_refresh_token()
        devices_with_online = self._rest.list_devices(token)
        now = datetime.datetime.now(pytz.utc)
        seen_ids: set[str] = set()
        for device, online in devices_with_online:
            seen_ids.add(device.device_id)
            existing = self.players.get(device.device_id)
            if existing is None:
                player = YotoPlayer(device=device, devices_refreshed_at=now)
                self.players[device.device_id] = player
                if self._mqtt is not None:
                    self._mqtt.add_player(device.device_id)
            else:
                existing.device = device
                existing.devices_refreshed_at = now
                player = existing
            self._set_online(player, online)

        # Players removed from the family upstream
        for stale_id in set(self.players) - seen_ids:
            self.players.pop(stale_id, None)
            if self._mqtt is not None:
                self._mqtt.remove_player(stale_id)

    # ─── Per-player config + status ───────────────────────────────

    def update_player_info(self, device_id: str) -> PlayerInfo:
        """GET /config for one device. Updates `players[device_id].info`
        and `players[device_id].status.is_online`."""
        token = self.check_and_refresh_token()
        info, online = self._rest.get_player_info(token, device_id)
        player = self.players.get(device_id)
        if player is not None:
            player.info = info
            player.info_refreshed_at = datetime.datetime.now(pytz.utc)
            self._set_online(player, online)
        return info

    def update_all_player_info(self) -> None:
        """Refresh /config for every known player.

        Per-player failures (offline device, transient 5xx) are logged
        and skipped so one bad device doesn't block the rest.
        """
        for device_id in list(self.players):
            try:
                self.update_player_info(device_id)
            except YotoError as err:
                _LOGGER.warning(
                    "%s - update_player_info failed for %s: %s",
                    DOMAIN,
                    device_id,
                    err,
                )

    def refresh(self) -> None:
        """Convenience: list devices, then refresh each player's config.

        Equivalent to `update_player_list()` followed by
        `update_all_player_info()`. Use this from a HA coordinator
        update tick. `request_status_push` is intentionally not chained:
        refresh should stay idempotent and read-only.
        """
        self.update_player_list()
        self.update_all_player_info()

    # ─── Library ─────────────────────────────────────────────────

    def update_library(self) -> None:
        """GET /card/family/library — populate self.library with card metadata.

        Doesn't fetch chapters/tracks; call update_card_detail(card_id) for that.
        """
        token = self.check_and_refresh_token()
        response = self._rest.get_card_library(token)
        for item in response.get("cards", []):
            card_id = get_child_value(item, "cardId")
            if card_id is None:
                continue
            card = self.library.get(card_id)
            if card is None:
                card = Card(id=card_id)
                card.chapters = {}
                self.library[card_id] = card
            card.title = get_child_value(item, "card.title")
            card.description = get_child_value(item, "card.metadata.description")
            card.author = get_child_value(item, "card.metadata.author")
            card.category = get_child_value(item, "card.metadata.stories")
            card.cover_image_large = get_child_value(item, "card.metadata.cover.imageL")
            card.series_order = get_child_value(item, "card.metadata.cover.seriesorder")
            card.series_title = get_child_value(item, "card.metadata.cover.seriestitle")

    def update_card_detail(self, card_id: str) -> None:
        """GET /card/{cardId} — populate chapters/tracks on the card."""
        token = self.check_and_refresh_token()
        if card_id not in self.library:
            self.library[card_id] = Card(id=card_id)
        card = self.library[card_id]
        if card.chapters is None:
            card.chapters = {}
        response = self._rest.get_card_detail(token, card_id)
        chapters = response.get("card", {}).get("content", {}).get("chapters", [])
        for chapter_item in chapters:
            key = get_raw_value(chapter_item, "key")
            if key is None:
                continue
            chapter = card.chapters.get(key)
            if chapter is None:
                chapter = Chapter(key=key)
                card.chapters[key] = chapter
            chapter.icon = get_child_value(chapter_item, "display.icon16x16")
            chapter.title = get_child_value(chapter_item, "title")
            chapter.duration = get_child_value(chapter_item, "duration")
            for track_item in chapter_item.get("tracks", []):
                track_key = get_raw_value(track_item, "key")
                if track_key is None:
                    continue
                if chapter.tracks is None:
                    chapter.tracks = {}
                if track_key not in chapter.tracks:
                    chapter.tracks[track_key] = Track(key=track_key)
                track = chapter.tracks[track_key]
                track.icon = get_child_value(track_item, "display.icon16x16")
                track.title = get_child_value(track_item, "title")
                track.duration = get_child_value(track_item, "duration")
                track.format = get_child_value(track_item, "format")
                track.channels = get_child_value(track_item, "channels")
                track.type = get_child_value(track_item, "type")
                track.trackUrl = get_child_value(track_item, "trackUrl")

    def update_player_status(self, device_id: str) -> PlayerStatus:
        """Force a fresh telemetry snapshot. Falls back to /config on 403."""
        token = self.check_and_refresh_token()
        status = self._rest.get_player_status(token, device_id)
        player = self.players.get(device_id)
        if player is not None:
            player.status = status
            player.status_refreshed_at = datetime.datetime.now(pytz.utc)
        return status

    # ─── Settings writes ──────────────────────────────────────────

    def set_player_config(self, device_id: str, **fields: Any) -> None:
        """Update PlayerConfig settings on the device.

        Pass any subset of `PlayerConfig`'s field names as kwargs, with
        proper Python types — e.g.:
            client.set_player_config(
                "dev1",
                day_time=datetime.time(7, 30),
                night_max_volume_limit=8,
                day_ambient_colour="#40bfd9",
                repeat_all=True,
                day_display_brightness_auto=True,        # mode auto
                night_display_brightness=80,             # mode manual
            )

        `None` values are dropped — Yoto's `PUT /config` merges with the
        existing settings, so omitted fields stay unchanged.

        For each side (day / night), `display_brightness_auto` and
        `display_brightness` are mutually exclusive in a single call:
        either turn auto on, or set a manual value.

        Alarms aren't accepted here; use `set_alarms` or
        `set_alarm_enabled` for those.
        """
        if "alarms" in fields:
            raise YotoError(
                "alarms cannot be set via set_player_config; "
                "use set_alarms() or set_alarm_enabled() instead"
            )

        payload: Dict[str, Any] = {}

        # Brightness pairs share one API key — handle first so the
        # generic mapping below doesn't see them as unknown fields.
        for auto_key, value_key, api_key in _BRIGHTNESS_PAIRS:
            auto = fields.pop(auto_key, None)
            value = fields.pop(value_key, None)
            if auto is True and value is not None:
                raise YotoError(f"{auto_key} and {value_key} are mutually exclusive")
            if auto is True:
                payload[api_key] = "auto"
            elif value is not None:
                payload[api_key] = _serialize_int(value)

        for snake, value in fields.items():
            if value is None:
                continue
            try:
                api_key, serialize = _CONFIG_FIELD_MAP[snake]
            except KeyError:
                known = sorted(
                    set(_CONFIG_FIELD_MAP)
                    | {auto for auto, _, _ in _BRIGHTNESS_PAIRS}
                    | {val for _, val, _ in _BRIGHTNESS_PAIRS}
                )
                raise YotoError(
                    f"Unknown PlayerConfig field: {snake!r}. Known: {known}"
                ) from None
            payload[api_key] = serialize(value)

        if not payload:
            return
        token = self.check_and_refresh_token()
        self._rest.update_settings(token, device_id, payload)

    def set_alarms(self, device_id: str, alarms: List[Alarm]) -> None:
        """Replace the device's full alarm list.

        Yoto's PUT /config interprets `{"alarms": [...]}` as the new
        complete list — anything omitted is dropped. Always pass every
        alarm you want to keep.
        """
        token = self.check_and_refresh_token()
        payload = encode_alarms_payload(alarms)
        self._rest.update_settings(token, device_id, payload)
        # Reflect the write locally so callers don't have to re-fetch.
        player = self.players.get(device_id)
        if player is not None:
            player.info.config.alarms = list(alarms)

    def set_alarm_enabled(self, device_id: str, index: int, enabled: bool) -> None:
        """Toggle one alarm's enabled flag while preserving the others.

        Reads `players[device_id].info.config.alarms`, mutates the entry
        at `index`, and PUTs the full list back. Requires that
        `update_player_info(device_id)` has run at least once so the
        alarm list is loaded — raises `YotoError` otherwise.
        """
        player = self.players.get(device_id)
        if player is None or player.info_refreshed_at is None:
            raise YotoError(
                f"set_alarm_enabled({device_id!r}): info not loaded; "
                "call update_player_info first"
            )
        alarms = player.info.config.alarms
        if not 0 <= index < len(alarms):
            raise YotoError(
                f"set_alarm_enabled({device_id!r}): no alarm at index {index} "
                f"(have {len(alarms)})"
            )
        alarms[index].enabled = enabled
        self.set_alarms(device_id, alarms)

    # ─── Player commands (MQTT direct, low latency) ──────────────

    def play_card(
        self,
        device_id: str,
        card_id: str,
        *,
        seconds_in: Optional[int] = None,
        cutoff: Optional[int] = None,
        chapter_key: Optional[str] = None,
        track_key: Optional[str] = None,
    ) -> None:
        # Optional args are kwargs-only on purpose: they're easy to mix up
        # positionally and the failure mode is silent (wrong track plays).
        self._require_mqtt().card_play(
            device_id,
            card_id,
            seconds_in=seconds_in,
            cutoff=cutoff,
            chapter_key=chapter_key,
            track_key=track_key,
        )

    def pause(self, device_id: str) -> None:
        self._require_mqtt().card_pause(device_id)

    def resume(self, device_id: str) -> None:
        self._require_mqtt().card_resume(device_id)

    def stop(self, device_id: str) -> None:
        self._require_mqtt().card_stop(device_id)

    def set_volume(self, device_id: str, volume: int) -> None:
        """Set the player's user volume.

        `volume` is a percentage (0-100). The lib maps it to the player's
        raw 0-16 hardware scale internally and clamps against
        `last_event.volume_max` when known.

        Note the asymmetry: `set_volume()` takes a percentage, but
        `player.last_event.volume` and `volume_max` from MQTT are in the
        raw 0-16 scale. Convert to percentage as `volume / volume_max`
        if you need a HA-style `volume_level` between 0.0 and 1.0.
        """
        self._require_mqtt().set_volume(device_id, volume)

    def set_sleep_timer(self, device_id: str, seconds: int) -> None:
        self._require_mqtt().set_sleep_timer(device_id, seconds)

    def set_ambients(self, device_id: str, r: int, g: int, b: int) -> None:
        self._require_mqtt().set_ambients(device_id, r, g, b)

    def restart(self, device_id: str) -> None:
        self._require_mqtt().restart(device_id)

    def request_status_push(self, device_id: str) -> None:
        """Documented HTTP trigger to make the player push its current status.
        Useful right after an action when you want a fresh /status on MQTT."""
        token = self.check_and_refresh_token()
        self._rest.request_status_push(token, device_id)

    def seek(self, device_id: str, position: int) -> None:
        """Resume the current card at `position` seconds in."""
        last = self._current_event(device_id)
        if last is None or last.card_id is None:
            return
        self.play_card(
            device_id=device_id,
            card_id=last.card_id,
            seconds_in=position,
            chapter_key=last.chapter_key,
            track_key=last.track_key,
        )

    def next_track(self, device_id: str) -> None:
        self._skip_track(device_id, direction=1)

    def previous_track(self, device_id: str) -> None:
        self._skip_track(device_id, direction=-1)

    def _skip_track(self, device_id: str, direction: int) -> None:
        last = self._current_event(device_id)
        if last is None or last.card_id is None:
            return
        card = self.library.get(last.card_id)
        if card is None or not card.chapters:
            self.update_card_detail(last.card_id)
            card = self.library.get(last.card_id)
        if card is None or not card.chapters:
            return

        playlist = [
            (chapter_key, track_key)
            for chapter_key, chapter in card.chapters.items()
            for track_key in (chapter.tracks or {})
        ]
        current = (last.chapter_key, last.track_key)
        if current not in playlist:
            return
        new_idx = playlist.index(current) + direction
        if not 0 <= new_idx < len(playlist):
            return
        new_chapter_key, new_track_key = playlist[new_idx]
        self.play_card(
            device_id=device_id,
            card_id=last.card_id,
            chapter_key=new_chapter_key,
            track_key=new_track_key,
        )

    def _current_event(self, device_id: str) -> Optional[PlaybackEvent]:
        player = self.players.get(device_id)
        return player.last_event if player is not None else None

    def _require_mqtt(self) -> YotoMqttClient:
        if self._mqtt is None:
            raise YotoError(
                "MQTT not connected; call connect_events() before sending commands"
            )
        return self._mqtt

    # ─── MQTT ─────────────────────────────────────────────────────

    def connect_events(
        self,
        device_ids: List[str],
        on_update: Optional[UpdateCallback] = None,
        on_disconnect: Optional[DisconnectCallback] = None,
    ) -> None:
        """Subscribe to MQTT for the given players.

        - `on_update(player)`: fired each time a message updates a player's state.
        - `on_disconnect(rc)`: fired from paho's network thread when the
          broker drops us. Use it to schedule a reconnect_events() from the
          consumer's event loop.

        The broker subscribe completes asynchronously — `connect_events`
        returns before the first MQTT message arrives. Player commands
        (pause, set_volume, etc.) issued before subscribe completes will
        raise `YotoError("MQTT not connected; ...")`. Either gate command
        calls on `is_mqtt_connected` or wrap them in try/except + retry.
        """
        if self.token is None:
            raise YotoError("No token; authenticate before connecting MQTT")
        self._update_callback = on_update
        self._disconnect_callback = on_disconnect
        self._connected_player_ids = list(device_ids)
        self._mqtt = YotoMqttClient()
        self._mqtt.connect(
            self.token,
            device_ids,
            self._on_mqtt_message,
            on_disconnect=on_disconnect,
        )

    def disconnect_events(self) -> None:
        if self._mqtt is None:
            return
        self._mqtt.disconnect()
        self._mqtt = None

    def reconnect_events(self) -> None:
        """Tear down and re-establish the MQTT connection with the same
        player set + callbacks. Refreshes the token first if expired —
        the access token is the MQTT credential."""
        on_update = self._update_callback
        on_disconnect = self._disconnect_callback
        device_ids = list(self._connected_player_ids)
        self.disconnect_events()
        self.check_and_refresh_token()
        self.connect_events(
            device_ids,
            on_update=on_update,
            on_disconnect=on_disconnect,
        )

    @property
    def is_mqtt_connected(self) -> bool:
        """True if MQTT is currently connected to the broker."""
        return self._mqtt is not None and self._mqtt.is_connected

    def _on_mqtt_message(self, message: Union[PlaybackEvent, StatusPatch]) -> None:
        player = self.players.get(message.player_id)
        if player is None:
            return
        # Any MQTT message is proof of presence; mark the player online.
        # MQTT never pushes "offline" because a disconnected player can't
        # publish — only REST `/devices/mine` and `/config` can flip it
        # back to False.
        self._set_online(player, True)
        now = datetime.datetime.now(pytz.utc)
        if isinstance(message, StatusPatch):
            self._apply_status_patch(player, message)
        elif isinstance(message, PlaybackEvent):
            self._apply_playback_event(player, message)
            player.last_event_received_at = now
            # Hand the hardware cap to the MQTT client so set_volume clamps
            # against it.
            if self._mqtt is not None and message.volume_max is not None:
                self._mqtt.set_volume_max(message.player_id, message.volume_max)
        if self._update_callback is not None:
            try:
                self._update_callback(player)
            except Exception:
                _LOGGER.exception("%s - update callback raised", DOMAIN)

    def _apply_playback_event(self, player: YotoPlayer, event: PlaybackEvent) -> None:
        """Merge an MQTT PlaybackEvent into the player's `last_event`.

        Yoto emits partial events (e.g. a volume change carries only
        `volume`); replacing wholesale would wipe playback_status and
        flicker the state. Only non-None fields overwrite.
        """
        for f in fields(event):
            if f.name == "player_id":
                continue
            value = getattr(event, f.name)
            if value is not None:
                setattr(player.last_event, f.name, value)

    def _apply_status_patch(self, player: YotoPlayer, patch: StatusPatch) -> None:
        for field_name, value in patch.fields.items():
            if value is None:
                continue
            setattr(player.status, field_name, value)
        player.status_refreshed_at = datetime.datetime.now(pytz.utc)

    def _set_online(self, player: YotoPlayer, online: bool) -> None:
        player.status.is_online = online
        player.status_refreshed_at = datetime.datetime.now(pytz.utc)
