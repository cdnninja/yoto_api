import unittest
from dotenv import load_dotenv
import os
import pytz
from yoto_api.YotoManager import YotoManager
from datetime import datetime


class login(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()

        cls.ym = YotoManager(os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD"))
        cls.ym.initialize()

    def test_access_token(self):
        self.assertIsNotNone(self.ym.token.access_token)

    def test_refresh_token(self):
        self.assertIsNotNone(self.ym.token.refresh_token)

    def test_token_type(self):
        self.assertIsNotNone(self.ym.token.token_type)

    def test_scope(self):
        self.assertIsNotNone(self.ym.token.scope)

    def test_valid_until_is_greater_than_now(self):
        self.assertGreater(self.ym.token.valid_until, datetime.now(pytz.utc))


class login_invalid(unittest.TestCase):
    def test_it_throws_an_error(self):
        with self.assertRaises(Exception) as error:
            ym = YotoManager("invalid", "invalid")
            ym.initialize()

        self.assertEqual(str(error.exception), "Wrong email or password.")


class update_family(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.ym = YotoManager(os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD"))
        cls.ym.initialize()
        cls.ym.update_family()

    def test_it_has_members(self):
        self.assertIsNotNone(self.ym.family.members)

    def test_it_has_devices(self):
        self.assertIsNotNone(self.ym.family.devices)


class update_players_status(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.ym = YotoManager(os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD"))
        cls.ym.initialize()
        cls.ym.update_players_status()

    def test_it_has_players(self):
        self.assertIsNotNone(self.ym.players)

    def test_it_has_player_configs(self):
        for player in self.ym.players.values():
            self.assertIsNotNone(player.config)


class update_library(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.ym = YotoManager(os.getenv("YOTO_USERNAME"), os.getenv("YOTO_PASSWORD"))
        cls.ym.initialize()
        cls.ym.update_library()

    def test_it_has_players(self):
        self.assertIsNotNone(self.ym.library)


if __name__ == "__main__":
    unittest.main()
