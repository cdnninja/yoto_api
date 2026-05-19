"""Access token helpers — decode JWT claims locally.

Yoto uses Auth0 for OAuth, so the access token is a JWT. Decoding it
in-process avoids extra API calls for things that are already in the
token (user identity, granted scopes).
"""

import base64
import json
from typing import Any, Dict

from .exceptions import YotoError


def get_account_id(access_token: str) -> str:
    """Return the Auth0 `sub` claim from the access token.

    Stable per-account identifier, no API call. Raises `YotoError` if
    the token is malformed.
    """
    sub = _decode_jwt_payload(access_token).get("sub")
    if not sub:
        raise YotoError("access_token missing `sub` claim")
    return sub


def has_scope(access_token: str, scope: str) -> bool:
    """True if the access token grants the given OAuth scope.

    Fail-open on malformed tokens (returns True) so the caller still
    attempts the call — the API will reject it with 403 if the scope is
    actually missing. Use to skip known-doomed calls (e.g. HA core
    typically lacks `family:device-status:view`).
    """
    try:
        granted = _decode_jwt_payload(access_token).get("scope", "")
    except YotoError:
        return True
    return scope in str(granted).split()


def _decode_jwt_payload(access_token: str) -> Dict[str, Any]:
    """Decode and return the payload (middle segment) of a JWT."""
    try:
        payload_b64 = access_token.split(".")[1]
    except (AttributeError, IndexError) as err:
        raise YotoError(f"access_token is not a JWT: {err}") from err
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, UnicodeDecodeError) as err:
        raise YotoError(f"access_token payload not decodable: {err}") from err
