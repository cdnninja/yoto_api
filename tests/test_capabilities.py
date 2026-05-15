"""Per-device-family capabilities lookup."""

import unittest

from yoto_api import Device, caps_for


class CapabilitiesTests(unittest.TestCase):
    def test_known_families(self) -> None:
        mini = Device(device_id="x", name="Mini", device_family="mini")
        v3 = Device(device_id="y", name="Player V3", device_family="v3")
        self.assertFalse(caps_for(mini).has_ambient_light)
        self.assertTrue(caps_for(v3).has_ambient_light)

    def test_unknown_falls_back_to_v2(self) -> None:
        future = Device(device_id="z", name="?", device_family="v4")
        caps = caps_for(future)
        self.assertTrue(caps.has_ambient_light)

    def test_missing_family_falls_back_to_v2(self) -> None:
        unknown = Device(device_id="z", name="?", device_family=None)
        caps = caps_for(unknown)
        self.assertTrue(caps.has_ambient_light)


if __name__ == "__main__":
    unittest.main()
