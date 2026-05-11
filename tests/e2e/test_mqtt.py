"""MQTT read-only integration tests: connect, observe, never mutate.

Captures raw MQTT payloads to detect fields Yoto pushes but the lib
doesn't parse yet. Helpful to spot new firmware features.
"""

import json
import time
from typing import Any

import pytest

from yoto_api import YotoClient
from yoto_api.mqtt.client import YotoMqttClient

pytestmark = pytest.mark.e2e


# How long to wait for messages after connect. MQTT is async — the broker
# subscribe + initial state push takes a couple of seconds.
_WAIT_AFTER_CONNECT_S = 8.0
_WAIT_AFTER_PUSH_S = 3.0


@pytest.fixture(scope="module")
def online_device_id(client: YotoClient) -> str:
    """An online device id, since MQTT can't receive from offline players."""
    client.update_player_list()
    for device_id, player in client.players.items():
        if player.status.is_online:
            return device_id
    pytest.skip("no online devices on this account; MQTT tests need at least one")


@pytest.fixture(scope="module")
def captured_mqtt(
    client: YotoClient, online_device_id: str
) -> list[tuple[str, dict[str, Any]]]:
    """Connect to MQTT, capture raw payloads, then disconnect. Module-scoped:
    one connect/wait/disconnect cycle shared by all MQTT tests."""
    captured: list[tuple[str, dict[str, Any]]] = []
    original_on_message = YotoMqttClient._on_message

    def capturing(self, mqtt_client, userdata, message) -> None:
        try:
            body = json.loads(message.payload.decode("utf-8"))
            captured.append((message.topic, body))
        except (UnicodeDecodeError, ValueError):
            pass
        original_on_message(self, mqtt_client, userdata, message)

    YotoMqttClient._on_message = capturing
    try:
        client.connect_events([online_device_id])
        time.sleep(_WAIT_AFTER_CONNECT_S)
        # Force a fresh status push so we get at least one data/status
        client.request_status_push(online_device_id)
        time.sleep(_WAIT_AFTER_PUSH_S)
    finally:
        try:
            client.disconnect_events()
        finally:
            YotoMqttClient._on_message = original_on_message
    return captured


def test_mqtt_connects_and_receives_messages(
    client: YotoClient, captured_mqtt: list[tuple[str, dict[str, Any]]]
) -> None:
    """The simplest possible check: we got at least one MQTT message."""
    assert captured_mqtt, (
        f"no MQTT messages received in "
        f"{_WAIT_AFTER_CONNECT_S + _WAIT_AFTER_PUSH_S}s — broker auth or "
        f"subscription is broken"
    )


def test_mqtt_status_message_arrived(
    captured_mqtt: list[tuple[str, dict[str, Any]]],
) -> None:
    """request_status_push should yield at least one data/status message."""
    status_msgs = [
        body for topic, body in captured_mqtt if topic.endswith("/data/status")
    ]
    assert status_msgs, (
        "no data/status payload arrived — request_status_push or "
        "command/status/request didn't trigger a response"
    )


def test_mqtt_state_propagates_to_player(
    client: YotoClient,
    online_device_id: str,
    captured_mqtt: list[tuple[str, dict[str, Any]]],
) -> None:
    """After receiving messages, player.status should be populated and
    player.last_event_received_at should be non-None."""
    if not captured_mqtt:
        pytest.skip("no MQTT messages received")
    player = client.players[online_device_id]
    # presence proof: any message marked the player online
    assert player.status.is_online is True
    # And the dispatcher updated the timestamps
    has_event = any(t.endswith("/data/events") for t, _ in captured_mqtt)
    has_status = any(t.endswith("/data/status") for t, _ in captured_mqtt)
    if has_event:
        assert player.last_event_received_at is not None
    if has_status:
        assert player.status_refreshed_at is not None
