"""Async MQTT client for Yoto's AWS IoT broker.

Holds one long-lived connection per account, multiplexes subscribes
across players, and reconnects with exponential backoff. Custom JWT
auth via the AWS IoT authorizer named `PublicJWTAuthorizer`.
"""

import asyncio
import inspect
import json
import logging
import uuid
from typing import Awaitable, Callable, List, Optional, Set, Union

import aiomqtt

from ..const import DOMAIN, VOLUME_MAPPING_INVERTED
from ..exceptions import YotoMQTTError
from ..Token import Token
from ..utils import take_closest
from ..models.event import PlaybackEvent, StatusPatch
from .parser import parse_message

_LOGGER = logging.getLogger(__name__)


Message = Union[PlaybackEvent, StatusPatch]
Callback = Callable[[Message], Union[None, Awaitable[None]]]
DisconnectCallback = Callable[[Optional[Exception]], Union[None, Awaitable[None]]]


async def _maybe_await(result) -> None:
    """Await `result` if it's a coroutine, drop it otherwise."""
    if inspect.isawaitable(result):
        await result


class YotoMqttClient:
    URL = "aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"
    PORT = 443
    # 60s keepalive: short enough to traverse aggressive NATs/firewalls
    # that drop idle connections after 60-90s, long enough to avoid
    # spamming the broker. The official app uses 15s.
    KEEPALIVE = 60
    AUTH_NAME = "PublicJWTAuthorizer"

    # Reconnect backoff bounds.
    _BACKOFF_MIN = 1.0
    _BACKOFF_MAX = 60.0

    def __init__(self) -> None:
        self._client: Optional[aiomqtt.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._connected = asyncio.Event()
        self._subscribed: Set[str] = set()
        self._callback: Optional[Callback] = None
        self._on_disconnect_cb: Optional[DisconnectCallback] = None
        self._token: Optional[Token] = None
        # volume_max per player; needed to clamp set_volume requests.
        self._volume_max: dict[str, int] = {}

    # ─── Connection lifecycle ────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._connected.is_set()

    async def connect(
        self,
        token: Token,
        player_ids: List[str],
        callback: Callback,
        on_disconnect: Optional[DisconnectCallback] = None,
    ) -> None:
        """Connect, subscribe for each player, and start the message loop.

        Returns once the first connect + subscribe completes. Raises
        `YotoMQTTError` if the first attempt fails. Subsequent drops
        trigger an auto-reconnect with exponential backoff.
        """
        if self._task is not None and not self._task.done():
            raise YotoMQTTError("MQTT already connected; call disconnect() first")
        self._callback = callback
        self._on_disconnect_cb = on_disconnect
        self._subscribed = set(player_ids)
        self._token = token
        self._connected.clear()

        first_done = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run(first_done))
        try:
            await first_done
        except Exception as err:
            await self._cancel_task()
            raise YotoMQTTError(f"MQTT connect failed: {err}") from err

    async def disconnect(self) -> None:
        """Stop the background task and close the connection."""
        await self._cancel_task()
        self._client = None
        self._connected.clear()

    async def add_player(self, player_id: str) -> None:
        """Subscribe to a player added after the initial connect."""
        if player_id in self._subscribed:
            return
        self._subscribed.add(player_id)
        if not self.is_connected:
            return  # picked up on next connect
        await self._subscribe_player(player_id)
        await self.request_status_push(player_id)

    async def remove_player(self, player_id: str) -> None:
        """Unsubscribe from a player that's no longer in the family."""
        self._subscribed.discard(player_id)
        self._volume_max.pop(player_id, None)
        if not self.is_connected:
            return
        for suffix in ("data/events", "data/status", "response"):
            try:
                await self._client.unsubscribe(f"device/{player_id}/{suffix}")
            except Exception as err:
                _LOGGER.debug(
                    "%s - MQTT unsubscribe failed for %s: %s",
                    DOMAIN,
                    player_id,
                    err,
                )

    # ─── Status refresh ──────────────────────────────────────────

    async def request_status_push(self, player_id: str) -> None:
        """Ask the player to push fresh `data/events` + `data/status`.

        The firmware never publishes `data/status` spontaneously; this
        is the only way to refresh telemetry over MQTT.
        """
        await self._publish(f"device/{player_id}/command/events/request")
        await self._publish(f"device/{player_id}/command/status/request")

    # ─── Player commands ─────────────────────────────────────────

    async def set_volume(self, player_id: str, volume: int) -> None:
        max_pct = self._max_volume_percentage(player_id)
        if max_pct is not None:
            volume = min(volume, max_pct)
        closest_volume = take_closest(VOLUME_MAPPING_INVERTED, volume)
        await self._publish(
            f"device/{player_id}/command/volume/set",
            json.dumps({"volume": closest_volume}),
        )
        await self.request_status_push(player_id)

    async def set_sleep_timer(self, player_id: str, seconds: int) -> None:
        await self._publish(
            f"device/{player_id}/command/sleep-timer/set",
            json.dumps({"seconds": int(seconds)}),
        )
        await self.request_status_push(player_id)

    async def card_stop(self, player_id: str) -> None:
        await self._publish(f"device/{player_id}/command/card/stop")
        await self.request_status_push(player_id)

    async def card_pause(self, player_id: str) -> None:
        await self._publish(f"device/{player_id}/command/card/pause")
        await self.request_status_push(player_id)

    async def card_resume(self, player_id: str) -> None:
        await self._publish(f"device/{player_id}/command/card/resume")
        await self.request_status_push(player_id)

    async def card_play(
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
        await self._publish(
            f"device/{player_id}/command/card/start", json.dumps(payload)
        )
        await self.request_status_push(player_id)

    async def restart(self, player_id: str) -> None:
        await self._publish(f"device/{player_id}/command/reboot")

    async def set_ambients(self, player_id: str, r: int, g: int, b: int) -> None:
        await self._publish(
            f"device/{player_id}/command/ambients/set",
            json.dumps({"r": int(r), "g": int(g), "b": int(b)}),
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

    async def _run(self, first_done: asyncio.Future) -> None:
        """Background task: own the aiomqtt connection, dispatch messages,
        reconnect on error with exponential backoff."""
        backoff = self._BACKOFF_MIN
        while True:
            try:
                async with self._make_client() as client:
                    self._client = client
                    backoff = self._BACKOFF_MIN
                    await self._on_connected()
                    if not first_done.done():
                        first_done.set_result(None)
                    async for message in client.messages:
                        await self._handle_message(message)
            except asyncio.CancelledError:
                self._client = None
                self._connected.clear()
                raise
            except Exception as err:
                self._client = None
                self._connected.clear()
                if not first_done.done():
                    # First connect failed: surface to caller and stop;
                    # auto-reconnect only kicks in once we've been up.
                    first_done.set_exception(err)
                    return
                _LOGGER.debug(
                    "%s - MQTT error: %s; reconnecting in %.1fs",
                    DOMAIN,
                    err,
                    backoff,
                )
                await self._fire_disconnect(err)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._BACKOFF_MAX)

    def _make_client(self) -> aiomqtt.Client:
        return aiomqtt.Client(
            hostname=self.URL,
            port=self.PORT,
            username=f"_?x-amz-customauthorizer-name={self.AUTH_NAME}",
            password=self._token.access_token,
            transport="websockets",
            tls_params=aiomqtt.TLSParameters(),
            keepalive=self.KEEPALIVE,
            identifier=f"YOTOAPI{uuid.uuid4().hex}",
        )

    async def _on_connected(self) -> None:
        """Subscribe + initial status push for every known player."""
        for player_id in list(self._subscribed):
            await self._subscribe_player(player_id)
        for player_id in list(self._subscribed):
            try:
                await self.request_status_push(player_id)
            except Exception as err:
                _LOGGER.debug(
                    "%s - request_status_push at connect failed for %s: %s",
                    DOMAIN,
                    player_id,
                    err,
                )
        self._connected.set()

    async def _handle_message(self, message: aiomqtt.Message) -> None:
        parsed = parse_message(str(message.topic), message.payload)
        if parsed is None or self._callback is None:
            return
        try:
            await _maybe_await(self._callback(parsed))
        except Exception:
            _LOGGER.exception("%s - MQTT callback raised", DOMAIN)

    async def _fire_disconnect(self, err: Optional[Exception]) -> None:
        if self._on_disconnect_cb is None:
            return
        try:
            await _maybe_await(self._on_disconnect_cb(err))
        except Exception:
            _LOGGER.exception("%s - on_disconnect callback raised", DOMAIN)

    async def _publish(self, topic: str, payload: Optional[str] = None) -> None:
        if not self.is_connected:
            raise YotoMQTTError("MQTT not connected")
        try:
            await self._client.publish(topic, payload=payload)
        except Exception as err:
            raise YotoMQTTError(f"MQTT publish to {topic} failed: {err}") from err

    async def _subscribe_player(self, player_id: str) -> None:
        if self._client is None:
            return
        for suffix in ("data/events", "data/status", "response"):
            await self._client.subscribe(f"device/{player_id}/{suffix}")
        _LOGGER.debug("%s - subscribed to player %s", DOMAIN, player_id)

    async def _cancel_task(self) -> None:
        """Cancel the background task and wait for it to unwind."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:
            # The task crashed before we asked it to stop; surface it
            # as a log so the failure isn't silently swallowed.
            _LOGGER.exception("%s - MQTT background task failed", DOMAIN)
        self._task = None

    def _max_volume_percentage(self, player_id: str) -> Optional[int]:
        volume_max = self._volume_max.get(player_id)
        if volume_max is None:
            return None
        return round(volume_max / 16 * 100)
