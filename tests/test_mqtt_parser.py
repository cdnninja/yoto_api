"""MQTT topic dispatch + payload → typed message parser."""

import unittest

from yoto_api import (
    DayMode,
    EventPatch,
    PlaybackStatus,
    StatusPatch,
)
from yoto_api.mqtt.parser import parse_message


class MqttParserTests(unittest.TestCase):
    def test_events_topic_returns_event_patch(self) -> None:
        payload = (
            b'{"repeatAll":false,"volume":8,"volumeMax":16,"cardId":"abc",'
            b'"playbackStatus":"playing","streaming":false,'
            b'"sleepTimerActive":false,"eventUtc":1778361678,'
            b'"chapterKey":"03","trackKey":"03","trackLength":315,"position":12}'
        )
        result = parse_message("device/dev1/data/events", payload)
        self.assertIsInstance(result, EventPatch)
        self.assertEqual(result.player_id, "dev1")
        self.assertEqual(result.fields["card_id"], "abc")
        self.assertEqual(result.fields["volume"], 8)
        self.assertEqual(result.fields["volume_max"], 16)
        self.assertEqual(result.fields["playback_status"], PlaybackStatus.PLAYING)
        self.assertEqual(result.fields["position"], 12)

    def test_events_card_none_is_present_and_cleared(self) -> None:
        # cardId:"none" is an explicit clear: the key is present, value None.
        payload = b'{"cardId":"none","volume":0,"volumeMax":16}'
        result = parse_message("device/d/data/events", payload)
        self.assertIn("card_id", result.fields)
        self.assertIsNone(result.fields["card_id"])

    def test_events_omits_absent_fields(self) -> None:
        payload = b'{"volume":5,"volumeMax":16}'
        result = parse_message("device/d/data/events", payload)
        self.assertEqual(set(result.fields.keys()), {"volume", "volume_max"})

    def test_events_includes_titles_and_source(self) -> None:
        payload = (
            b'{"cardId":"abc","chapterTitle":"Snow and Tell",'
            b'"trackTitle":"Snow and Tell",'
            b'"source":"remote","volume":5,"volumeMax":16}'
        )
        result = parse_message("device/d/data/events", payload)
        self.assertEqual(result.fields["chapter_title"], "Snow and Tell")
        self.assertEqual(result.fields["track_title"], "Snow and Tell")
        self.assertEqual(result.fields["source"], "remote")

    def test_status_topic_returns_status_patch(self) -> None:
        payload = (
            b'{"status":{"batteryLevel":73,"charging":1,"volume":50,'
            b'"userVolume":40,"als":12,"day":0,"temp":"24:18",'
            b'"nightlightMode":"off","headphones":1}}'
        )
        result = parse_message("device/dev1/data/status", payload)
        self.assertIsInstance(result, StatusPatch)
        self.assertEqual(result.player_id, "dev1")
        self.assertEqual(result.fields["battery_level_percentage"], 73)
        self.assertTrue(result.fields["is_charging"])
        self.assertTrue(result.fields["is_audio_device_connected"])
        self.assertEqual(result.fields["system_volume_percentage"], 50)
        self.assertEqual(result.fields["user_volume_percentage"], 40)
        self.assertEqual(result.fields["ambient_light_sensor_reading"], 12)
        self.assertEqual(result.fields["day_mode"], DayMode.NIGHT)
        self.assertEqual(result.fields["battery_temperature"], 24)
        self.assertEqual(result.fields["temperature_celcius"], 18)
        self.assertEqual(result.fields["nightlight_mode"], "off")

    def test_status_patch_omits_absent_fields(self) -> None:
        payload = b'{"status":{"batteryLevel":50}}'
        result = parse_message("device/d/data/status", payload)
        self.assertEqual(set(result.fields.keys()), {"battery_level_percentage"})

    def test_response_topic_is_ignored(self) -> None:
        result = parse_message("device/d/response", b'{"status":{"x":1}}')
        self.assertIsNone(result)

    def test_unknown_topic_is_ignored(self) -> None:
        self.assertIsNone(parse_message("random/topic", b"{}"))

    def test_garbage_payload_is_ignored(self) -> None:
        self.assertIsNone(parse_message("device/d/data/events", b"<not json>"))

    def test_events_coerce_int_booleans(self) -> None:
        # Yoto sometimes sends `0`/`1` ints where the type expects bool.
        # The parser must coerce so the typed dataclass stays honest.
        payload = (
            b'{"repeatAll":1,"streaming":0,"sleepTimerActive":1,'
            b'"volume":5,"volumeMax":16}'
        )
        result = parse_message("device/d/data/events", payload)
        self.assertIs(result.fields["repeat_all"], True)
        self.assertIs(result.fields["streaming"], False)
        self.assertIs(result.fields["sleep_timer_active"], True)

    def test_events_native_booleans(self) -> None:
        payload = (
            b'{"repeatAll":true,"streaming":false,"sleepTimerActive":false,'
            b'"volume":5,"volumeMax":16}'
        )
        result = parse_message("device/d/data/events", payload)
        self.assertIs(result.fields["repeat_all"], True)
        self.assertIs(result.fields["streaming"], False)
        self.assertIs(result.fields["sleep_timer_active"], False)


if __name__ == "__main__":
    unittest.main()
