import unittest
from dotenv import load_dotenv
import os
import pytz
from yoto_api.YotoAPI import YotoAPI
from datetime import datetime


class login(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()

        cls.token = YotoAPI().login(
            os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD")
        )

    def test_access_token(self):
        self.assertIsNotNone(self.token.access_token)

    def test_refresh_token(self):
        self.assertIsNotNone(self.token.refresh_token)

    def test_token_type(self):
        self.assertIsNotNone(self.token.token_type)

    def test_scope(self):
        self.assertIsNotNone(self.token.scope)

    def test_valid_until_is_greater_than_now(self):
        self.assertGreater(self.token.valid_until, datetime.now(pytz.utc))


class login_invalid(unittest.TestCase):
    def test_it_throws_an_error(self):
        api = YotoAPI()

        with self.assertRaises(Exception) as error:
            api.login("invalid", "invalid")

        self.assertEqual(str(error.exception), "Wrong email or password.")


class get_family(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        api = YotoAPI()
        token = api.login(os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD"))
        cls.family = api.get_family(token)

    def test_it_has_members(self):
        self.assertIsNotNone(self.family.members)

    def test_it_has_devices(self):
        self.assertIsNotNone(self.family.devices)


if __name__ == "__main__":
    unittest.main()
