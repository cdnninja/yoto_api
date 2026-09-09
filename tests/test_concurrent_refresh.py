"""Test concurrent refreshes don't cause session invalidation"""

from yoto_api.Token import Token
import asyncio
import pytz
from datetime import datetime, timedelta
from yoto_api import YotoClient
import unittest

last_seen_refresh_token = 0


async def mock_refresh(token) -> Token:
    """Generates a new refresh token to use and keeps a memory of the maximum last value of the token"""
    global last_seen_refresh_token
    int_refresh_token = int(token.refresh_token)
    if int_refresh_token != last_seen_refresh_token + 1:
        raise Exception(
            f"Concurrent refresh not handled correctly: expected{last_seen_refresh_token + 1}, got {int_refresh_token}"
        )
    last_seen_refresh_token = int_refresh_token
    await asyncio.sleep(0.5)
    return Token(
        access_token="test",
        refresh_token=str(int_refresh_token + 1),
        valid_until=datetime.now(pytz.utc) + timedelta(days=30),
    )


class TestConcurrentRefresh(unittest.IsolatedAsyncioTestCase):
    """Creates a new YotoClient and tries to refresh the token 100 times in parallel. The lock on the token ensure that only one token refresh can be in flight at once"""

    async def test_concurrent_refresh(self):
        global last_seen_refresh_token
        last_seen_refresh_token = 0
        token = Token(
            access_token="expired",
            refresh_token="1",
            valid_until=datetime.now(pytz.utc) - timedelta(days=30),
        )
        client = YotoClient()
        client.token = token
        client._auth.client_id = "test_client_id"  # Ensure we try to refresh

        client._auth.refresh = mock_refresh

        tasks = [
            asyncio.create_task(client.check_and_refresh_token()) for _ in range(100)
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    unittest.main()
