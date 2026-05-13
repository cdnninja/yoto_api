"""OAuth flows: device code, token refresh.

Lives outside `rest/` because these endpoints aren't data endpoints —
they hit Auth0, not Yoto's API server, and they have their own scope rules.
"""

import asyncio
import datetime
import logging
from datetime import timedelta
from typing import Optional

import aiohttp
import pytz

from .const import DOMAIN
from .exceptions import AuthenticationError, YotoAPIError, YotoError
from .Token import Token
from .rest import endpoints

_LOGGER = logging.getLogger(__name__)


class Auth:
    """Handles OAuth flows. Stateless: takes the token in/out."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: Optional[str] = None,
    ) -> None:
        self._session = session
        self.client_id = client_id

    # ─── Device-code flow ─────────────────────────────────────────

    async def device_code_flow_start(self) -> dict:
        """Get the verification URL the user needs to visit."""
        self._require_client_id("device code authorization")
        data = {
            "audience": endpoints.BASE_URL,
            "client_id": self.client_id,
            "scope": "offline_access",
        }
        try:
            async with self._session.post(
                endpoints.AUTH_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    text = await response.text()
                    raise AuthenticationError(
                        f"Authorization failed: {response.status} {text}"
                    )
                try:
                    return await response.json(content_type=None)
                except ValueError as err:
                    raise YotoAPIError(
                        f"Authorization response malformed: {err}"
                    ) from err
        except aiohttp.ClientError as err:
            raise YotoAPIError(f"Authorization request failed: {err}") from err

    async def poll_for_token(self, auth_result: dict) -> Token:
        """Poll until the user completes the device-code flow in their browser."""
        self._require_client_id("device code token polling")
        device_code = auth_result["device_code"]
        interval = int(auth_result.get("interval", 5))
        expires_in = int(auth_result.get("expires_in", 300))
        deadline = datetime.datetime.now() + timedelta(seconds=expires_in)

        while datetime.datetime.now() < deadline:
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": self.client_id,
                "audience": endpoints.BASE_URL,
            }
            try:
                async with self._session.post(
                    endpoints.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    body = await response.json(content_type=None)
                    status = response.status
                    ok = response.ok
                    text = await response.text() if not ok else ""
            except (aiohttp.ClientError, ValueError) as err:
                raise YotoAPIError(f"Token poll request failed: {err}") from err

            if ok:
                _LOGGER.debug("%s - Authorization successful", DOMAIN)
                return _build_token(
                    body, scope=body.get("scope", "openid profile offline_access")
                )

            if status == 403:
                error = body.get("error")
                if error == "authorization_pending":
                    await asyncio.sleep(interval)
                    continue
                if error == "slow_down":
                    interval += 5
                    _LOGGER.debug(
                        "%s - slow_down, increasing interval to %ss",
                        DOMAIN,
                        interval,
                    )
                    await asyncio.sleep(interval)
                    continue
                if error == "expired_token":
                    raise AuthenticationError(
                        "Authorization code expired. Restart the flow."
                    )
                raise AuthenticationError(
                    body.get("error_description", body.get("error", "Unknown error"))
                )

            raise AuthenticationError(
                f"Token request failed: {status} {text}"
            )

        raise AuthenticationError("Authentication timed out. Please try again.")

    # ─── Token refresh ────────────────────────────────────────────

    async def refresh(self, token: Token) -> Token:
        """Exchange the refresh token for a new access token."""
        self._require_client_id("refresh_token")
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "audience": endpoints.BASE_URL,
        }
        try:
            async with self._session.post(
                endpoints.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError) as err:
            raise YotoAPIError(f"Refresh token request failed: {err}") from err
        _LOGGER.debug("%s - Refresh Token Response %s", DOMAIN, body)
        if body.get("error"):
            raise AuthenticationError("Refresh token invalid")
        return _build_token(body, scope=token.scope)

    # ─── Internals ────────────────────────────────────────────────

    def _require_client_id(self, operation: str) -> None:
        if self.client_id is None:
            raise YotoError(f"client_id required for {operation}")


def _build_token(body: dict, scope: Optional[str]) -> Token:
    try:
        valid_until = datetime.datetime.now(pytz.utc) + timedelta(
            seconds=int(body["expires_in"])
        )
        return Token(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            token_type=body.get("token_type", "Bearer"),
            scope=scope,
            valid_until=valid_until,
        )
    except (KeyError, TypeError) as err:
        raise YotoAPIError(f"Token response malformed: {err}") from err
