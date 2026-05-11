"""MQTT client for Yoto's AWS IoT broker.

Wraps `paho.mqtt.client` with:
- AWS IoT custom-authorizer JWT auth (same pattern as 2.x)
- Multi-player subscribe + dynamic add/remove
- Typed callback dispatching `PlaybackEvent` or `StatusPatch`
- All player commands published over MQTT (matches 2.x latency, ~50-100ms
  vs ~500ms for REST commands)
- Error wrapping into `YotoMQTTError`
"""

import json
import logging
import uuid
from typing import Callable, List, Optional, Set, Union

import paho.mqtt.client as mqtt

from ..const import DOMAIN, VOLUME_MAPPING_INVERTED
from ..exceptions import YotoMQTTError
from ..Token import Token
from ..utils import take_closest
from ..models.event import PlaybackEvent, StatusPatch
from .parser import parse_message

_LOGGER = logging.getLogger(__name__)


Message = Union[PlaybackEvent, StatusPatch]
Callback = Callable[[Message], None]
DisconnectCallback = Callable[[int], None]


class YotoMqttClient:
    URL = "aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"
    PORT = 443
    KEEPALIVE = 120
    AUTH_NAME = "PublicJWTAuthorizer"

    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._subscribed: Set[str] = set()
        self._callback: Optional[Callback] = None
        self._on_disconnect_cb: Optional[DisconnectCallback] = None
        # volume_max per player; needed to clamp set_volume requests.
        self._volume_max: dict[str, int] = {}

    # ─── Connection lifecycle ────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """True if the underlying paho client thinks it's connected."""
        return self._client is not None and self._client.is_connected()

    def connect(
        self,
        token: Token,
        player_ids: List[str],
        callback: Callback,
        on_disconnect: Optional[DisconnectCallback] = None,
    ) -> None:
        """Open the MQTT connection and subscribe for each player.

        `on_disconnect(rc)` is invoked from paho's network thread when the
        broker drops us. Useful to drive a reconnect from the consumer.
        """
        self._callback = callback
        self._on_disconnect_cb = on_disconnect
        self._subscribed = set(player_ids)
        try:
            self._client = mqtt.Client(
                client_id=f"YOTOAPI{uuid.uuid4().hex}",
                transport="websockets",
            )
            self._client.username_pw_set(
                username=f"_?x-amz-customauthorizer-name={self.AUTH_NAME}",
                password=token.access_token,
            )
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.tls_set()
            self._client.connect(host=self.URL, port=self.PORT, keepalive=self.KEEPALIVE)
            self._client.loop_start()
        except Exception as err:
            raise YotoMQTTError(f"MQTT connect failed: {err}") from err

    def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception as err:
            raise YotoMQTTError(f"MQTT disconnect failed: {err}") from err

    def add_player(self, player_id: str) -> None:
        """Subscribe to a player added after the initial connect."""
        if player_id in self._subscribed:
            return
        self._subscribed.add(player_id)
        if self._client is None or not self._client.is_connected():
            return  # will be picked up on next connect
        self._subscribe_player(player_id)
        self.request_status_push(player_id)

    def remove_player(self, player_id: str) -> None:
        """Unsubscribe from a player that's no longer in the family."""
        self._subscribed.discard(player_id)
        self._volume_max.pop(player_id, None)
        if self._client is None or not self._client.is_connected():
            return
        for suffix in ("data/events", "data/status", "response"):
            try:
                self._client.unsubscribe(f"device/{player_id}/{suffix}")
            except Exception as err:
                _LOGGER.debug("MQTT unsubscribe failed for %s: %s", player_id, err)

    # ─── Status refresh ──────────────────────────────────────────

    def request_status_push(self, player_id: str) -> None:
        """Ask the player to push its current status + events on the bus.

        Equivalent to the official app's empty publish to
        `device/{id}/command/events` after subscribe; gets us a fresh
        snapshot without waiting for the player to emit on its own.
        """
        self._publish(f"device/{player_id}/command/events/request")
        self._publish(f"device/{player_id}/command/status/request")

    # ─── Player commands ─────────────────────────────────────────

    def set_volume(self, player_id: str, volume: int) -> None:
        max_pct = self._max_volume_percentage(player_id)
        if max_pct is not None:
            volume = min(volume, max_pct)
        closest_volume = take_closest(VOLUME_MAPPING_INVERTED, volume)
        self._publish(
            f"device/{player_id}/command/volume/set",
            json.dumps({"volume": closest_volume}),
        )
        self.request_status_push(player_id)

    def set_sleep_timer(self, player_id: str, seconds: int) -> None:
        self._publish(
            f"device/{player_id}/command/sleep-timer/set",
            json.dumps({"seconds": int(seconds)}),
        )
        self.request_status_push(player_id)

    def card_stop(self, player_id: str) -> None:
        self._publish(f"device/{player_id}/command/card/stop")
        self.request_status_push(player_id)

    def card_pause(self, player_id: str) -> None:
        self._publish(f"device/{player_id}/command/card/pause")
        self.request_status_push(player_id)

    def card_resume(self, player_id: str) -> None:
        self._publish(f"device/{player_id}/command/card/resume")
        self.request_status_push(player_id)

    def card_play(
        self,
        player_id: str,
        card_id: str,
        seconds_in: Optional[int] = None,
        cutoff: Optional[int] = None,
        chapter_key: Optional[str] = None,
        track_key: Optional[str] = None,
    ) -> None:
        payload: dict = {"uri": f"https://yoto.io/{card_id}"}
        if cutoff is not None:
            payload["cutOff"] = int(cutoff)
        if chapter_key is not None:
            payload["chapterKey"] = str(chapter_key)
        if track_key is not None:
            payload["trackKey"] = str(track_key)
        if seconds_in is not None:
            payload["secondsIn"] = int(seconds_in)
        self._publish(
            f"device/{player_id}/command/card/start", json.dumps(payload)
        )
        self.request_status_push(player_id)

    def restart(self, player_id: str) -> None:
        self._publish(f"device/{player_id}/command/reboot")

    def set_ambients(self, player_id: str, r: int, g: int, b: int) -> None:
        self._publish(
            f"device/{player_id}/command/ambients/set",
            json.dumps({"r": int(r), "g": int(g), "b": int(b)}),
        )

    def bluetooth(
        self, player_id: str, action: str, name: str = "", mac: str = ""
    ) -> None:
        suffix = "on" if action == "on" else "off"
        self._publish(
            f"device/{player_id}/command/bluetooth/{suffix}",
            json.dumps({"action": action, "name": name, "mac": mac}),
        )

    # ─── Per-player metadata fed in by the consumer ──────────────

    def set_volume_max(self, player_id: str, volume_max: Optional[int]) -> None:
        """Tell the client the player's hardware volume cap (0-16 raw),
        used to clamp percentage requests in set_volume."""
        if volume_max is None:
            self._volume_max.pop(player_id, None)
        else:
            self._volume_max[player_id] = volume_max

    # ─── Internals ────────────────────────────────────────────────

    def _publish(self, topic: str, payload: Optional[str] = None) -> None:
        if self._client is None:
            raise YotoMQTTError("MQTT not connected")
        try:
            if payload is None:
                self._client.publish(topic)
            else:
                self._client.publish(topic, payload)
        except Exception as err:
            raise YotoMQTTError(f"MQTT publish to {topic} failed: {err}") from err

    def _subscribe_player(self, player_id: str) -> None:
        if self._client is None:
            return
        for suffix in ("data/events", "data/status", "response"):
            self._client.subscribe(f"device/{player_id}/{suffix}")
        _LOGGER.debug("%s - subscribed to player %s", DOMAIN, player_id)

    def _max_volume_percentage(self, player_id: str) -> Optional[int]:
        volume_max = self._volume_max.get(player_id)
        if volume_max is None:
            return None
        return round(volume_max / 16 * 100)

    def _on_connect(self, client, userdata, flags, rc) -> None:
        for player_id in list(self._subscribed):
            self._subscribe_player(player_id)
            self.request_status_push(player_id)

    def _on_disconnect(self, client, userdata, rc) -> None:
        _LOGGER.debug("%s - MQTT disconnected: rc=%s", DOMAIN, rc)
        if self._on_disconnect_cb is not None:
            try:
                self._on_disconnect_cb(rc)
            except Exception:
                _LOGGER.exception("%s - on_disconnect callback raised", DOMAIN)

    def _on_message(self, client, userdata, message: mqtt.MQTTMessage) -> None:
        parsed = parse_message(message.topic, message.payload)
        if parsed is None or self._callback is None:
            return
        try:
            self._callback(parsed)
        except Exception:
            _LOGGER.exception("%s - MQTT callback raised", DOMAIN)
