"""Account identification helpers.

Yoto uses Auth0 for OAuth, so the access token is a JWT whose `sub` claim
uniquely identifies the user account. Decoding it locally avoids hitting
the undocumented `/user/family` endpoint just to get an identifier for
HA's config entry.
"""

import base64
import json

from .exceptions import YotoError


def get_account_id(access_token: str) -> str:
    """Return the Auth0 `sub` claim from the access token's JWT.

    Stable per-account identifier, no API call. Raises YotoError if the
    token is malformed.
    """
    try:
        payload_b64 = access_token.split(".")[1]
    except (AttributeError, IndexError) as err:
        raise YotoError(f"access_token is not a JWT: {err}") from err

    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, UnicodeDecodeError) as err:
        raise YotoError(f"access_token payload not decodable: {err}") from err

    sub = payload.get("sub")
    if not sub:
        raise YotoError("access_token missing `sub` claim")
    return sub
