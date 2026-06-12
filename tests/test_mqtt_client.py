"""YotoMqttClient connect behaviour: the connect-time status push must
actually go out (regression: it was swallowed as "MQTT not connected" because
`_connected` was set after the push loop). Also covers the reliability fixes:
QoS 1 on publishes/subscriptions and a fresh access token on every reconnect."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import aiomqtt

from yoto_api.Token import Token
from yoto_api.exceptions import YotoMQTTError
from yoto_api.mqtt import YotoMqttClient


def _connected_client(*player_ids: str) -> tuple[YotoMqttClient, MagicMock]:
    """A client wired to a mock broker, as if the aiomqtt context is live
    (i.e. `_client` is set) but `_on_connected` hasn't run yet."""
    client = YotoMqttClient()
    broker = MagicMock()
    broker.subscribe = AsyncMock()
    broker.publish = AsyncMock()
    client._client = broker
    client._subscribed = set(player_ids)
    return client, broker


class _FakeMsg:
    def __init__(self, topic: str, payload: bytes) -> None:
        self.topic = topic
        self.payload = payload


class OnConnectedStatusPushTests(unittest.IsolatedAsyncioTestCase):
    async def test_pushes_basic_then_extended_on_connect(self) -> None:
        client, broker = _connected_client("dev1")
        client._STATUS_REPLY_TIMEOUT = 0.0  # skip the inter-request gap

        await client._on_connected()

        self.assertTrue(client.is_connected)
        topics = [call.args[0] for call in broker.publish.await_args_list]
        self.assertIn("device/dev1/command/events/request", topics)  # playback
        self.assertIn("device/dev1/command/status/request", topics)  # basic
        self.assertIn("device/dev1/command/status", topics)  # extended
        # Basic goes out before extended (spaced by the gap, not back-to-back).
        self.assertLess(
            topics.index("device/dev1/command/status/request"),
            topics.index("device/dev1/command/status"),
        )

    async def test_pushes_happen_while_connected_not_swallowed(self) -> None:
        # Regression guard: `_connected` must be set before the push loop, so
        # `_publish`'s is_connected gate passes. If it weren't, every publish
        # would raise YotoMQTTError before reaching the broker and the list
        # below would be empty.
        client, broker = _connected_client("dev1")
        client._STATUS_REPLY_TIMEOUT = 0.0
        seen_connected: list[bool] = []

        async def record(topic, payload=None, qos=0):
            seen_connected.append(client.is_connected)

        broker.publish = AsyncMock(side_effect=record)

        await client._on_connected()

        self.assertTrue(seen_connected, "no publish reached the broker")
        self.assertTrue(all(seen_connected), "a push ran while not connected")

    async def test_subscribes_every_player_before_pushing(self) -> None:
        client, broker = _connected_client("dev1", "dev2")
        client._STATUS_REPLY_TIMEOUT = 0.0

        await client._on_connected()

        subscribed = {call.args[0] for call in broker.subscribe.await_args_list}
        for device_id in ("dev1", "dev2"):
            self.assertIn(f"device/{device_id}/data/status", subscribed)
            self.assertIn(f"device/{device_id}/status/full", subscribed)


class StatusEventsSplitTests(unittest.IsolatedAsyncioTestCase):
    """`request_player_status` refreshes only `data/status`. `data/events` is
    requested separately: at connect/add_player and on the heartbeat that keeps
    Yoto's push alive (it stops pushing ~5min after the last events/request)."""

    async def test_request_player_status_is_status_only(self) -> None:
        client, broker = _connected_client("dev1")
        client._connected.set()
        client._STATUS_REPLY_TIMEOUT = 0.0

        await client.request_player_status("dev1")

        topics = [c.args[0] for c in broker.publish.await_args_list]
        self.assertEqual(topics, ["device/dev1/command/status/request"])

    async def test_command_does_not_request_events(self) -> None:
        client, broker = _connected_client("dev1")
        client._connected.set()

        await client.card_stop("dev1")

        topics = [c.args[0] for c in broker.publish.await_args_list]
        self.assertIn("device/dev1/command/card/stop", topics)
        self.assertIn("device/dev1/command/status/request", topics)
        self.assertNotIn("device/dev1/command/events/request", topics)

    async def test_add_player_requests_events_basic_and_extended(self) -> None:
        client, broker = _connected_client()
        client._connected.set()
        client._STATUS_REPLY_TIMEOUT = 0.0

        await client.add_player("dev1")

        topics = [c.args[0] for c in broker.publish.await_args_list]
        self.assertIn("device/dev1/command/events/request", topics)
        self.assertIn("device/dev1/command/status/request", topics)
        self.assertIn("device/dev1/command/status", topics)  # extended

    async def test_events_heartbeat_rearms_every_player(self) -> None:
        client, broker = _connected_client("dev1", "dev2")
        client._connected.set()
        client._EVENTS_HEARTBEAT_S = 0

        task = asyncio.create_task(client._events_heartbeat())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        topics = {c.args[0] for c in broker.publish.await_args_list}
        self.assertIn("device/dev1/command/events/request", topics)
        self.assertIn("device/dev2/command/events/request", topics)


class QoSTests(unittest.IsolatedAsyncioTestCase):
    """QoS 1 closes the silent-drop gap a QoS-0 publish/reply leaves open."""

    async def test_publishes_at_qos_1(self) -> None:
        client, broker = _connected_client("dev1")
        client._connected.set()
        client._STATUS_REPLY_TIMEOUT = 0.0  # don't wait for a reply the mock won't send

        await client.request_player_status("dev1")

        self.assertTrue(broker.publish.await_args_list)
        for call in broker.publish.await_args_list:
            self.assertEqual(call.kwargs.get("qos"), 1)

    async def test_subscribes_at_qos_1(self) -> None:
        client, broker = _connected_client("dev1")
        client._STATUS_REPLY_TIMEOUT = 0.0

        await client._on_connected()

        self.assertTrue(broker.subscribe.await_args_list)
        for call in broker.subscribe.await_args_list:
            self.assertEqual(call.kwargs.get("qos"), 1)


class StatusReplyWaitTests(unittest.IsolatedAsyncioTestCase):
    """A status request waits for its own reply, so chained basic+extended
    requests serialise instead of racing the firmware back-to-back."""

    async def test_blocks_until_reply_then_returns(self) -> None:
        client, _ = _connected_client("dev1")
        client._connected.set()
        returned: list[bool] = []

        async def run() -> None:
            await client.request_player_status("dev1")
            returned.append(True)

        task = asyncio.create_task(run())
        await asyncio.sleep(0.02)
        self.assertFalse(returned, "returned before the reply arrived")

        await client._handle_message(_FakeMsg("device/dev1/data/status", b"{}"))
        await asyncio.wait_for(task, 1.0)
        self.assertTrue(returned)

    async def test_times_out_without_reply(self) -> None:
        client, _ = _connected_client("dev1")
        client._connected.set()
        client._STATUS_REPLY_TIMEOUT = 0.02
        await asyncio.wait_for(client.request_player_status("dev1"), 1.0)

    async def test_basic_reply_does_not_satisfy_extended_wait(self) -> None:
        client, _ = _connected_client("dev1")
        client._connected.set()
        returned: list[bool] = []

        async def run() -> None:
            await client.request_player_extended_status("dev1")
            returned.append(True)

        task = asyncio.create_task(run())
        await asyncio.sleep(0.02)
        await client._handle_message(_FakeMsg("device/dev1/data/status", b"{}"))
        await asyncio.sleep(0.02)
        self.assertFalse(returned, "extended request woke on a basic reply")

        await client._handle_message(_FakeMsg("device/dev1/status/full", b"{}"))
        await asyncio.wait_for(task, 1.0)
        self.assertTrue(returned)


class AccessTokenResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefers_async_getter(self) -> None:
        client = YotoMqttClient()

        async def getter() -> str:
            return "fresh"

        client._token_getter = getter
        self.assertEqual(await client._current_access_token(), "fresh")

    async def test_accepts_sync_getter(self) -> None:
        client = YotoMqttClient()
        client._token_getter = lambda: "sync-fresh"
        self.assertEqual(await client._current_access_token(), "sync-fresh")

    async def test_falls_back_to_static_token(self) -> None:
        client = YotoMqttClient()
        client._token = Token(access_token="static")
        self.assertEqual(await client._current_access_token(), "static")

    async def test_raises_when_no_token_available(self) -> None:
        client = YotoMqttClient()
        client._token = Token(access_token=None)
        with self.assertRaises(YotoMQTTError):
            await client._current_access_token()


class ReconnectUsesFreshTokenTests(unittest.IsolatedAsyncioTestCase):
    """Bug 1 regression: each reconnect must authenticate with a current token,
    not the snapshot captured at the first connect."""

    async def test_reconnect_fetches_a_new_token(self) -> None:
        client = YotoMqttClient()
        client._BACKOFF_MIN = 0.0
        client._BACKOFF_MAX = 0.0
        client._STATUS_REPLY_TIMEOUT = 0.0

        tokens = iter(["tok1", "tok2", "tok3"])

        async def getter() -> str:
            return next(tokens)

        passwords: list[str] = []
        second_connect = asyncio.Event()

        class FakeMessages:
            def __init__(self, drop: bool) -> None:
                self._drop = drop

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._drop:
                    raise aiomqtt.MqttError("connection dropped")
                await asyncio.sleep(3600)  # second connect stays up

        class FakeClient:
            def __init__(self, drop: bool) -> None:
                self.messages = FakeMessages(drop)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_a):
                return False

            async def subscribe(self, *_a, **_k):
                return None

            async def publish(self, *_a, **_k):
                return None

        def fake_make_client(access_token: str) -> FakeClient:
            passwords.append(access_token)
            if len(passwords) >= 2:
                second_connect.set()
                return FakeClient(drop=False)
            return FakeClient(drop=True)  # first connect drops to force reconnect

        client._make_client = fake_make_client

        await client.connect(
            token=None,
            player_ids=["dev1"],
            callback=lambda _m: None,
            token_getter=getter,
        )
        try:
            await asyncio.wait_for(second_connect.wait(), timeout=2.0)
        finally:
            await client.disconnect()

        self.assertEqual(passwords[0], "tok1")
        self.assertEqual(passwords[1], "tok2")  # reconnect used the next token


if __name__ == "__main__":
    unittest.main()
