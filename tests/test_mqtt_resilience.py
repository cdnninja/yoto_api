"""Tests for MQTT connection resilience improvements."""

import unittest
from unittest.mock import MagicMock, patch
from yoto_api.YotoMQTTClient import YotoMQTTClient
from yoto_api.Token import Token


class TestMQTTClientInit(unittest.TestCase):
    """Test paho-mqtt v1/v2 compatibility in connect_mqtt."""

    def _make_token(self):
        t = Token()
        t.access_token = "fake-token"
        return t

    @patch("yoto_api.YotoMQTTClient.mqtt")
    def test_connect_uses_callback_api_version_when_available(self, mock_mqtt):
        """paho-mqtt 2.x path: CallbackAPIVersion.VERSION1 is passed."""
        mock_mqtt.CallbackAPIVersion.VERSION1 = "VERSION1"
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        client = YotoMQTTClient()
        client.connect_mqtt(self._make_token(), {"player-1": MagicMock()}, None)

        args = mock_mqtt.Client.call_args
        self.assertEqual(args[0][0], "VERSION1")

    @patch("yoto_api.YotoMQTTClient.mqtt")
    def test_connect_falls_back_when_no_callback_api(self, mock_mqtt):
        """paho-mqtt 1.x path: no CallbackAPIVersion, falls back gracefully."""
        del mock_mqtt.CallbackAPIVersion
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        client = YotoMQTTClient()
        client.connect_mqtt(self._make_token(), {"player-1": MagicMock()}, None)

        mock_mqtt.Client.assert_called_once()

    @patch("yoto_api.YotoMQTTClient.mqtt")
    def test_connect_sets_keepalive(self, mock_mqtt):
        """Explicit keepalive=60 is passed to connect()."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        client = YotoMQTTClient()
        client.connect_mqtt(self._make_token(), {"player-1": MagicMock()}, None)

        mock_client.connect.assert_called_once_with(
            host=client.MQTT_URL, port=443, keepalive=60
        )

    @patch("yoto_api.YotoMQTTClient.mqtt")
    def test_connect_registers_on_subscribe(self, mock_mqtt):
        """on_subscribe callback is registered."""
        mock_client = MagicMock()
        mock_mqtt.Client.return_value = mock_client

        client = YotoMQTTClient()
        client.connect_mqtt(self._make_token(), {"player-1": MagicMock()}, None)

        self.assertEqual(mock_client.on_subscribe, client._on_subscribe)


class TestOnDisconnect(unittest.TestCase):
    """Test improved disconnect logging."""

    def test_clean_disconnect_logs_debug_only(self):
        """rc=0 (clean disconnect) should not warn."""
        client = YotoMQTTClient()
        mock_mqtt_client = MagicMock()
        mock_mqtt_client._client_id = b"YOTOAPI123"

        with patch("yoto_api.YotoMQTTClient._LOGGER") as mock_logger:
            client._on_disconnect(mock_mqtt_client, None, 0)
            mock_logger.debug.assert_called_once()
            mock_logger.warning.assert_not_called()

    def test_unexpected_disconnect_logs_warning(self):
        """rc!=0 (unexpected) should warn."""
        client = YotoMQTTClient()
        mock_mqtt_client = MagicMock()
        mock_mqtt_client._client_id = b"YOTOAPI123"

        with patch("yoto_api.YotoMQTTClient._LOGGER") as mock_logger:
            client._on_disconnect(mock_mqtt_client, None, 7)
            mock_logger.debug.assert_called_once()
            mock_logger.warning.assert_called_once()


class TestOnConnect(unittest.TestCase):
    """Test that _on_connect subscribes and requests status."""

    def test_subscribes_to_all_topics_per_player(self):
        """Each player gets 3 subscriptions + status request."""
        client = YotoMQTTClient()
        client.client = MagicMock()
        players = {"device-abc": MagicMock(), "device-xyz": MagicMock()}
        userdata = (players, None)

        client._on_connect(client.client, userdata, {}, 0)

        self.assertEqual(client.client.subscribe.call_count, 6)
        self.assertEqual(client.client.publish.call_count, 4)


if __name__ == "__main__":
    unittest.main()
