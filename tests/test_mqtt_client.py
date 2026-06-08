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


class OnConnectedStatusPushTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_basic_and_extended_status_on_connect(self) -> None:
        client, broker = _connected_client("dev1")

        await client._on_connected()

        self.assertTrue(client.is_connected)
        topics = [call.args[0] for call in broker.publish.await_args_list]
        # request_player_status -> events/request + status/request (basic)
        self.assertIn("device/dev1/command/events/request", topics)
        self.assertIn("device/dev1/command/status/request", topics)
        # request_player_extended_status -> command/status (extended)
        self.assertIn("device/dev1/command/status", topics)

    async def test_pushes_happen_while_connected_not_swallowed(self) -> None:
        # Regression guard: `_connected` must be set before the push loop, so
        # `_publish`'s is_connected gate passes. If it weren't, every publish
        # would raise YotoMQTTError before reaching the broker and the list
        # below would be empty.
        client, broker = _connected_client("dev1")
        seen_connected: list[bool] = []

        async def record(topic, payload=None, qos=0):
            seen_connected.append(client.is_connected)

        broker.publish = AsyncMock(side_effect=record)

        await client._on_connected()

        self.assertTrue(seen_connected, "no publish reached the broker")
        self.assertTrue(all(seen_connected), "a push ran while not connected")

    async def test_subscribes_every_player_before_pushing(self) -> None:
        client, broker = _connected_client("dev1", "dev2")

        await client._on_connected()

        subscribed = {call.args[0] for call in broker.subscribe.await_args_list}
        for device_id in ("dev1", "dev2"):
            self.assertIn(f"device/{device_id}/data/status", subscribed)
            self.assertIn(f"device/{device_id}/status/full", subscribed)


class QoSTests(unittest.IsolatedAsyncioTestCase):
    """QoS 1 closes the silent-drop gap a QoS-0 publish/reply leaves open."""

    async def test_publishes_at_qos_1(self) -> None:
        client, broker = _connected_client("dev1")
        client._connected.set()

        await client.request_player_status("dev1")

        self.assertTrue(broker.publish.await_args_list)
        for call in broker.publish.await_args_list:
            self.assertEqual(call.kwargs.get("qos"), 1)

    async def test_subscribes_at_qos_1(self) -> None:
        client, broker = _connected_client("dev1")

        await client._on_connected()

        self.assertTrue(broker.subscribe.await_args_list)
        for call in broker.subscribe.await_args_list:
            self.assertEqual(call.kwargs.get("qos"), 1)


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
