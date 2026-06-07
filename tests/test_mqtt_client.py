"""YotoMqttClient connect behaviour: the connect-time status push must
actually go out (regression: it was swallowed as "MQTT not connected" because
`_connected` was set after the push loop)."""

import unittest
from unittest.mock import AsyncMock, MagicMock

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

        async def record(topic, payload=None):
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


if __name__ == "__main__":
    unittest.main()
