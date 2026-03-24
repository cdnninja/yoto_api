import json
import unittest
from types import SimpleNamespace

from yoto_api.YotoMQTTClient import YotoMQTTClient
from yoto_api.YotoPlayer import YotoPlayer


class FakeClient:
    def __init__(self):
        self.subscriptions = []
        self.published = []

    def subscribe(self, topic):
        self.subscriptions.append(topic)

    def publish(self, topic, payload=None):
        self.published.append((topic, payload))


class YotoMQTTClientTest(unittest.TestCase):
    def test_on_connect_subscribes_to_documented_topics(self):
        mqtt_client = YotoMQTTClient()
        fake_client = FakeClient()
        mqtt_client.client = fake_client

        mqtt_client._on_connect(
            fake_client, ({"device-1": YotoPlayer(id="device-1")}, None), None, 0
        )

        self.assertEqual(
            fake_client.subscriptions,
            [
                "device/device-1/data/events",
                "device/device-1/data/status",
                "device/device-1/response",
            ],
        )
        self.assertEqual(
            fake_client.published,
            [
                ("device/device-1/command/events/request", None),
                ("device/device-1/command/status/request", None),
            ],
        )

    def test_parse_status_message_updates_playback_state(self):
        mqtt_client = YotoMQTTClient()
        player = YotoPlayer(id="device-1")

        mqtt_client._parse_status_message(
            {
                "status": {
                    "nightlightMode": "off",
                    "batteryLevel": 66,
                    "activeCard": "3nC80",
                    "volume": 18,
                    "userVolume": 37,
                    "playingStatus": 2,
                }
            },
            player,
        )

        self.assertEqual(player.night_light_mode, "off")
        self.assertEqual(player.battery_level_percentage, 66)
        self.assertEqual(player.active_card, "3nC80")
        self.assertEqual(player.card_id, "3nC80")
        self.assertEqual(player.volume, 18)
        self.assertEqual(player.user_volume, 37)
        self.assertEqual(player.playback_status, "playing")
        self.assertTrue(player.is_playing)

    def test_on_message_routes_documented_data_topics(self):
        mqtt_client = YotoMQTTClient()
        player = YotoPlayer(id="device-1")
        callback_calls = []

        message = SimpleNamespace(
            topic="device/device-1/data/status",
            payload=json.dumps(
                {
                    "status": {
                        "activeCard": "none",
                        "playingStatus": 0,
                    }
                }
            ).encode("utf-8"),
        )

        mqtt_client._on_message(
            None,
            ({"device-1": player}, lambda: callback_calls.append(True)),
            message,
        )

        self.assertEqual(player.playback_status, "stopped")
        self.assertFalse(player.is_playing)
        self.assertIsNone(player.card_id)
        self.assertEqual(len(callback_calls), 1)


if __name__ == "__main__":
    unittest.main()
