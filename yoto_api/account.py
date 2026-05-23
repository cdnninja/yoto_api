"""Access token helpers: decode JWT claims locally."""

import base64
import json
from typing import Any, Dict

from .exceptions import YotoError


def get_account_id(access_token: str) -> str:
    """Return the Auth0 `sub` claim. Raises `YotoError` if malformed."""
    sub = _decode_jwt_payload(access_token).get("sub")
    if not sub:
        raise YotoError("access_token missing `sub` claim")
    return sub


def has_scope(access_token: str, scope: str) -> bool:
    """True if the access token grants `scope`.

    Fails open on malformed tokens so the caller still attempts the API
    call and gets the real 403 if relevant.
    """
    try:
        granted = _decode_jwt_payload(access_token).get("scope", "")
    except YotoError:
        return True
    return scope in str(granted).split()


def _decode_jwt_payload(access_token: str) -> Dict[str, Any]:
    try:
        payload_b64 = access_token.split(".")[1]
    except (AttributeError, IndexError) as err:
        raise YotoError(f"access_token is not a JWT: {err}") from err
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, UnicodeDecodeError) as err:
        raise YotoError(f"access_token payload not decodable: {err}") from err
