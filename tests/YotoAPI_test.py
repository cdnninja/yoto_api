
import unittest
from dotenv import load_dotenv
import os
import pytz
from yoto_api.YotoAPI import YotoAPI
from datetime import datetime, timedelta

class ValidLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv() 
        username = os.getenv("USERNAME")
        password = os.getenv("PASSWORD")
        api = YotoAPI()
        cls.token = api.login(username, password)

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

class InvalidLogin(unittest.TestCase):
    def test_it_throws_an_error(self):
        api = YotoAPI()

        with self.assertRaises(Exception) as error:
            api.login("invalid", "invalid")
        
        self.assertEqual(str(error.exception), "Wrong email or password.")

if __name__ == '__main__':
    unittest.main()