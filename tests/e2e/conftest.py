"""End-to-end tests against the real Yoto API.

Skipped by default. Opt in with `pytest tests/e2e -m e2e -s`.

Set up a `.env` file at the repo root with::

    YOTO_CLIENT_ID=your_client_id
    YOTO_REFRESH_TOKEN=your_refresh_token  # optional, prompted if missing

If the refresh token is missing or invalid (Yoto rotates them), the
fixture launches the device-code flow interactively: prints a URL,
waits for the user to complete the login, then writes the new token
back to `.env`. Use `-s` so the URL prompt isn't captured by pytest.

Tests are read-only and don't mutate device state.
"""

import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from yoto_api import AuthenticationError, YotoClient
from yoto_api.Token import Token

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "e2e: hits the real Yoto API; requires .env with "
        "YOTO_CLIENT_ID and YOTO_REFRESH_TOKEN",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip e2e tests unless the marker is explicitly requested."""
    if config.getoption("-m") and "e2e" in config.getoption("-m"):
        return
    skip = pytest.mark.skip(reason="e2e test; use `-m e2e` to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def env() -> dict[str, str | None]:
    load_dotenv()
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        pytest.skip("YOTO_CLIENT_ID missing from .env")
    return {
        "client_id": client_id,
        "refresh_token": os.environ.get("YOTO_REFRESH_TOKEN"),
    }


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(env: dict[str, str | None]) -> AsyncIterator[YotoClient]:
    """Authenticated client, ready to use.

    Tries the stored refresh token first. If it's missing or invalid
    (Yoto/Auth0 rotate them), falls back to the interactive device-code
    flow: prints the verification URL, waits for the user to complete
    it, then writes the new token back to `.env` so the next run won't
    need to prompt again.
    """
    c = YotoClient(client_id=env["client_id"])
    initial_refresh_token = env["refresh_token"]

    if initial_refresh_token:
        c.token = Token(refresh_token=initial_refresh_token)
        try:
            await c.check_and_refresh_token()
        except AuthenticationError:
            print(
                "\n[e2e] Stored refresh token is invalid; falling back to "
                "interactive device-code flow.",
                file=sys.stderr,
            )
            await _interactive_login(c)
    else:
        print(
            "\n[e2e] No YOTO_REFRESH_TOKEN in .env; starting interactive "
            "device-code flow.",
            file=sys.stderr,
        )
        await _interactive_login(c)

    try:
        yield c
    finally:
        if (
            c.token
            and c.token.refresh_token
            and c.token.refresh_token != initial_refresh_token
        ):
            _persist_refresh_token(c.token.refresh_token)
        await c.close()


async def _interactive_login(c: YotoClient) -> None:
    """Run the device-code flow, blocking until the user completes it."""
    auth = await c.device_code_flow_start()
    print(
        f"\n[e2e] Open this URL to authorise the test session:\n"
        f"      {auth['verification_uri_complete']}\n"
        f"      (waiting up to {auth.get('expires_in', 300)}s…)\n",
        file=sys.stderr,
    )
    sys.stderr.flush()
    await c.device_code_flow_complete(auth)


def _persist_refresh_token(new_token: str) -> None:
    """Update YOTO_REFRESH_TOKEN in `.env`, preserving other entries."""
    if not _ENV_PATH.exists():
        return
    lines = _ENV_PATH.read_text().splitlines()
    new_line = f"YOTO_REFRESH_TOKEN={new_token}"
    for i, line in enumerate(lines):
        if line.startswith("YOTO_REFRESH_TOKEN="):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    _ENV_PATH.write_text("\n".join(lines) + "\n")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def first_device_id(client: YotoClient) -> str:
    """A real device id from the account, for per-device tests."""
    await client.update_player_list()
    if not client.players:
        pytest.skip("no devices on this account")
    return next(iter(client.players))
