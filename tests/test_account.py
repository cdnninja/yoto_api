"""JWT helper for extracting the Auth0 `sub` claim."""

import unittest

from yoto_api import YotoError
from yoto_api import get_account_id

from .conftest import fake_jwt


class JWTHelperTests(unittest.TestCase):
    def test_extracts_sub_claim(self) -> None:
        token = fake_jwt({"sub": "auth0|abc123", "iat": 1234567890})
        self.assertEqual(get_account_id(token), "auth0|abc123")

    def test_handles_unpadded_base64(self) -> None:
        token = fake_jwt({"sub": "x"})
        self.assertEqual(get_account_id(token), "x")

    def test_raises_on_missing_sub(self) -> None:
        token = fake_jwt({"iat": 1234567890})
        with self.assertRaises(YotoError):
            get_account_id(token)

    def test_raises_on_garbage(self) -> None:
        with self.assertRaises(YotoError):
            get_account_id("not-a-jwt")


if __name__ == "__main__":
    unittest.main()
