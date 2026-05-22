"""JWT helpers: account id + scope check."""

import unittest

from yoto_api import YotoError, get_account_id, has_scope

from .conftest import fake_jwt


class GetAccountIdTests(unittest.TestCase):
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


class HasScopeTests(unittest.TestCase):
    def test_present_scope_returns_true(self) -> None:
        token = fake_jwt({"scope": "openid family:device-status:view profile"})
        self.assertTrue(has_scope(token, "family:device-status:view"))

    def test_missing_scope_returns_false(self) -> None:
        token = fake_jwt({"scope": "openid profile"})
        self.assertFalse(has_scope(token, "family:device-status:view"))

    def test_no_scope_claim_returns_false(self) -> None:
        token = fake_jwt({"sub": "x"})
        self.assertFalse(has_scope(token, "family:device-status:view"))

    def test_malformed_token_fails_open(self) -> None:
        # We can't decode → assume the scope is there and let the API decide.
        self.assertTrue(has_scope("not-a-jwt", "family:device-status:view"))

    def test_partial_scope_match_does_not_count(self) -> None:
        # Must be a whole-word match — "view" should not match "view-all".
        token = fake_jwt({"scope": "family:device-status:view-all"})
        self.assertFalse(has_scope(token, "family:device-status:view"))


if __name__ == "__main__":
    unittest.main()
