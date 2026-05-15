"""Shared fixtures + helpers for v3 tests."""

import base64
import datetime
import json

import pytz

from yoto_api.Token import Token


def fake_jwt(payload: dict) -> str:
    """Build a JWT-shaped string with the given payload (no signature check)."""
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"header.{encoded}.signature"


def fresh_token() -> Token:
    """Token whose validity is well in the future, so check_and_refresh_token
    skips the refresh path."""
    return Token(
        access_token="access",
        refresh_token="refresh",
        token_type="Bearer",
        scope="x",
        valid_until=datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=2),
    )
