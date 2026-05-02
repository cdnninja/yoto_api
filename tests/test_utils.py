import unittest

from yoto_api.utils import get_child_value


class TestUtils(unittest.TestCase):
    def test_get_child_value_returns_bool_for_true_string(self):
        data = {"device": {"config": {"enabled": "True"}}}
        self.assertIs(get_child_value(data, "device.config.enabled"), True)

    def test_get_child_value_returns_bool_for_false_string(self):
        data = {"device": {"config": {"enabled": "False"}}}
        self.assertIs(get_child_value(data, "device.config.enabled"), False)

    def test_get_child_value_returns_raw_boolean(self):
        data = {"device": {"status": {"isOnline": False}}}
        self.assertIs(get_child_value(data, "device.status.isOnline"), False)

    def test_get_child_value_returns_int_for_numeric_string(self):
        data = {"device": {"config": {"maxVolumeLimit": "15"}}}
        self.assertEqual(get_child_value(data, "device.config.maxVolumeLimit"), 15)
        self.assertIsInstance(
            get_child_value(data, "device.config.maxVolumeLimit"), int
        )

    def test_get_child_value_returns_none_for_missing_key(self):
        data = {"device": {"status": {"isOnline": False}}}
        self.assertIsNone(get_child_value(data, "device.status.isConnected"))


if __name__ == "__main__":
    unittest.main()
