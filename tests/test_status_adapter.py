"""/config.device.status fallback path → typed PlayerStatus."""

import unittest

from yoto_api import CardInsertionState, DayMode, PowerSource
from yoto_api.status_adapter import adapt_raw_status


class StatusAdapterTests(unittest.TestCase):
    def test_real_mini_payload(self) -> None:
        # Exact shape captured from a live HA debug log.
        raw = {
            "activeCard": "8A3Lr",
            "als": 0,
            "batteryLevel": 73,
            "bluetoothHp": 0,
            "cardInserted": 1,
            "charging": 0,
            "day": 1,
            "freeDisk": 24333760,
            "headphones": 0,
            "nightlightMode": "off",
            "playingStatus": 5,
            "powerSrc": 0,
            "ssid": "Crocodile",
            "temp": "0:0",
            "totalDisk": 30535680,
            "upTime": 703,
            "userVolume": 0,
            "volume": 0,
            "wifiStrength": -75,
        }
        status = adapt_raw_status(raw, device_id="d1")

        self.assertEqual(status.device_id, "d1")
        self.assertEqual(status.active_card, "8A3Lr")
        self.assertEqual(status.battery_level_percentage, 73)
        self.assertFalse(status.is_charging)
        self.assertFalse(status.is_audio_device_connected)
        self.assertFalse(status.is_bluetooth_audio_connected)
        self.assertEqual(status.network_ssid, "Crocodile")
        self.assertEqual(status.wifi_strength, -75)
        self.assertEqual(status.power_source, PowerSource.BATTERY)
        self.assertEqual(status.card_insertion_state, CardInsertionState.PHYSICAL)
        self.assertEqual(status.day_mode, DayMode.DAY)
        self.assertIsNone(status.battery_temperature)  # "0" → None
        self.assertIsNone(status.temperature_celcius)  # "0" → None
        self.assertEqual(status.uptime, 703)

    def test_temperature_parsing(self) -> None:
        cases = [
            ({"temp": "0:0"}, (None, None)),
            ({"temp": "0:notSupported"}, (None, None)),
            ({"temp": "0:24"}, (None, 24)),
            ({"temp": "25:24"}, (25, 24)),
            ({"temp": "notSupported:notSupported"}, (None, None)),
        ]
        for raw, (expected_battery, expected_device) in cases:
            status = adapt_raw_status(raw, device_id="d")
            self.assertEqual(status.battery_temperature, expected_battery, msg=raw)
            self.assertEqual(status.temperature_celcius, expected_device, msg=raw)

    def test_active_card_none_string_becomes_None(self) -> None:
        status = adapt_raw_status({"activeCard": "none"}, device_id="d")
        self.assertIsNone(status.active_card)

    def test_unknown_power_source_is_None(self) -> None:
        status = adapt_raw_status({"powerSrc": 99}, device_id="d")
        self.assertIsNone(status.power_source)


if __name__ == "__main__":
    unittest.main()
