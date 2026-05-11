"""YotoPlayer aggregate + StatusPatch merging + computed properties."""

import unittest

from yoto_api import Device, PlaybackEvent, StatusPatch, YotoClient, YotoPlayer


class StatusPatchMergeTests(unittest.TestCase):
    def test_apply_patch_merges_only_present_fields(self) -> None:
        client = YotoClient()
        device = Device(device_id="d1", name="Mini", device_family="mini")
        player = YotoPlayer(device=device)
        client.players["d1"] = player
        patch = StatusPatch(
            player_id="d1",
            fields={"battery_level_percentage": 80, "is_charging": True},
        )
        client._apply_status_patch(player, patch)
        self.assertEqual(player.status.battery_level_percentage, 80)
        self.assertTrue(player.status.is_charging)
        self.assertIsNone(player.status.wifi_strength)


class YotoPlayerTests(unittest.TestCase):
    def test_model_property(self) -> None:
        mini = YotoPlayer(
            device=Device(device_id="x", name="Mini", device_family="mini")
        )
        v3 = YotoPlayer(device=Device(device_id="y", name="V3", device_family="v3"))
        unknown = YotoPlayer(device=Device(device_id="z", name="?", device_family=None))
        self.assertEqual(mini.model, "Yoto Mini")
        self.assertEqual(v3.model, "Yoto Player")
        self.assertEqual(unknown.model, "Yoto Player")

    def test_sub_objects_default_to_empty_with_matching_id(self) -> None:
        """info / status / last_event are always present after construction
        so consumers don't need defensive `is None` guards."""
        player = YotoPlayer(device=Device(device_id="abc", name="X"))
        self.assertEqual(player.info.device_id, "abc")
        self.assertEqual(player.status.device_id, "abc")
        self.assertEqual(player.last_event.player_id, "abc")
        # Empty: every payload field is None
        self.assertIsNone(player.info.mac)
        self.assertIsNone(player.status.battery_level_percentage)
        self.assertIsNone(player.last_event.position)

    def test_refreshed_at_signals_remain_None_at_construction(self) -> None:
        """The 'have we received data?' signal lives on the timestamps,
        not on the sub-objects (which are always present)."""
        player = YotoPlayer(device=Device(device_id="abc", name="X"))
        self.assertIsNone(player.devices_refreshed_at)
        self.assertIsNone(player.info_refreshed_at)
        self.assertIsNone(player.status_refreshed_at)
        self.assertIsNone(player.last_event_received_at)


class PlaybackEventVolumePercentageTests(unittest.TestCase):
    """volume_percentage divides by the absolute hardware max (16),
    NOT volume_max (which is a user-configured cap)."""

    def test_returns_None_when_volume_unset(self) -> None:
        event = PlaybackEvent(player_id="d1")
        self.assertIsNone(event.volume_percentage)

    def test_divides_by_16_not_volume_max(self) -> None:
        # volume=4 with cap=8 must not return 0.5 (relative to cap) —
        # HA volume_level is absolute output, so 0.25.
        event = PlaybackEvent(player_id="d1", volume=4, volume_max=8)
        self.assertEqual(event.volume_percentage, 0.25)

    def test_full_range(self) -> None:
        self.assertEqual(
            PlaybackEvent(player_id="d", volume=0).volume_percentage,
            0.0,
        )
        self.assertEqual(
            PlaybackEvent(player_id="d", volume=16).volume_percentage,
            1.0,
        )


class PlayerConfigParseTests(unittest.TestCase):
    """Yoto returns most numeric values as strings; the parser coerces
    them on read so the dataclass stays honest."""

    def _parse(self, raw):
        from yoto_api.rest.client import _parse_player_config

        return _parse_player_config(raw)

    def test_parses_real_payload(self) -> None:
        # Snapshot taken from the integrator's HA debug log.
        raw = {
            "locale": "fr",
            "bluetoothEnabled": "1",
            "repeatAll": False,
            "showDiagnostics": True,
            "btHeadphonesEnabled": True,
            "pauseVolumeDown": True,
            "pausePowerButton": True,
            "displayDimTimeout": "180",
            "shutdownTimeout": "3600",
            "headphonesVolumeLimited": False,
            "dayTime": "07:30",
            "maxVolumeLimit": "8",
            "ambientColour": "#ff0000",
            "dayDisplayBrightness": "100",
            "nightTime": "19:00",
            "nightMaxVolumeLimit": "16",
            "nightAmbientColour": "#ff0000",
            "nightDisplayBrightness": "auto",
            "hourFormat": "24",
            "systemVolume": "100",
            "alarms": [],
        }
        from datetime import time

        config = self._parse(raw)
        self.assertEqual(config.day_time, time(7, 30))
        self.assertEqual(config.night_time, time(19, 0))
        self.assertEqual(config.day_max_volume_limit, 8)
        self.assertEqual(config.night_max_volume_limit, 16)
        self.assertEqual(config.shutdown_timeout, 3600)
        self.assertEqual(config.display_dim_timeout, 180)
        self.assertEqual(config.system_volume, 100)
        self.assertEqual(config.hour_format, 24)
        self.assertTrue(config.bluetooth_enabled)
        self.assertFalse(config.headphones_volume_limited)
        self.assertEqual(config.day_ambient_colour, "#ff0000")
        # Brightness split: "100" → manual=100, "auto" → auto=True
        self.assertEqual(config.day_display_brightness_auto, False)
        self.assertEqual(config.day_display_brightness, 100)
        self.assertEqual(config.night_display_brightness_auto, True)
        self.assertIsNone(config.night_display_brightness)

    def test_missing_brightness_yields_None_pair(self) -> None:
        config = self._parse({})
        self.assertIsNone(config.day_display_brightness_auto)
        self.assertIsNone(config.day_display_brightness)


if __name__ == "__main__":
    unittest.main()
