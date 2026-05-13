"""Read-only smoke tests against the real Yoto API.

These don't mutate state — safe to re-run as often as you like.
"""

import pytest

from yoto_api import YotoClient
from yoto_api.models.info import PlayerInfo
from yoto_api.models.status import PlayerStatus


pytestmark = pytest.mark.e2e


async def test_token_refresh_works(client: YotoClient) -> None:
    """The conftest fixture already calls check_and_refresh_token; if we
    got here, the access token was issued."""
    assert client.token is not None
    assert client.token.access_token


async def test_list_devices_populates_players(client: YotoClient) -> None:
    await client.update_player_list()
    assert client.players, "no devices found on this account"
    for player_id, player in client.players.items():
        assert player.device.device_id == player_id
        assert player.device.name
        # Online state should land on status (not on identity)
        assert player.status.is_online in (True, False)


async def test_get_player_info(client: YotoClient, first_device_id: str) -> None:
    info = await client.update_player_info(first_device_id)
    assert isinstance(info, PlayerInfo)
    assert info.device_id == first_device_id
    # Hardware metadata should be populated by the /config response
    assert info.mac, "MAC missing from /config response"
    assert info.firmware_version, "firmware_version missing from /config"
    # Refreshed_at marker should be set
    player = client.players[first_device_id]
    assert player.info_refreshed_at is not None


async def test_get_player_status(client: YotoClient, first_device_id: str) -> None:
    """Works whether or not the token has the device-status:view scope —
    the lib falls back to /config.device.status on 403."""
    status = await client.update_player_status(first_device_id)
    assert isinstance(status, PlayerStatus)
    assert status.device_id == first_device_id
    # At least one telemetry field should be populated for an online player
    has_data = any(
        [
            status.battery_level_percentage is not None,
            status.is_charging is not None,
            status.network_ssid is not None,
            status.system_volume_percentage is not None,
        ]
    )
    assert has_data, "no telemetry returned from /status or /config fallback"


async def test_full_refresh(client: YotoClient) -> None:
    """`refresh()` chains list_devices + per-player info."""
    await client.refresh()
    assert client.players
    for player in client.players.values():
        assert player.info_refreshed_at is not None


async def test_account_id_from_token(client: YotoClient) -> None:
    """`get_account_id` decodes the Auth0 sub claim from the access token."""
    from yoto_api import get_account_id

    account_id = get_account_id(client.token.access_token)
    assert account_id
    # Auth0 sub claims look like "<provider>|<id>" — `auth0|...`,
    # `google-oauth2|...`, etc.
    assert "|" in account_id, f"unexpected account_id format: {account_id!r}"


async def test_caps_for_known_devices(client: YotoClient) -> None:
    """caps_for returns the right capability set for each family."""
    from yoto_api import caps_for

    await client.update_player_list()
    for player in client.players.values():
        caps = caps_for(player.device)
        if player.device.device_family == "mini":
            assert caps.has_ambient_light is False
        elif player.device.device_family in ("v1", "v2", "v3"):
            assert caps.has_ambient_light is True


async def test_update_library(client: YotoClient) -> None:
    """`update_library` populates self.library with cards."""
    await client.update_library()
    if not client.library:
        pytest.skip("no cards in this account's library")

    for card_id, card in client.library.items():
        assert card.id == card_id
        # Title is the most common field people read; should always be present
        assert card.title, f"card {card_id} has no title"


async def test_update_card_detail(client: YotoClient) -> None:
    """`update_card_detail` populates chapters + tracks for one card."""
    await client.update_library()
    if not client.library:
        pytest.skip("no cards in library")
    card_id = next(iter(client.library))

    await client.update_card_detail(card_id)
    card = client.library[card_id]
    assert card.chapters, f"no chapters loaded for card {card_id}"

    for chapter_key, chapter in card.chapters.items():
        assert chapter.key == chapter_key
        if chapter.tracks:
            for track_key, track in chapter.tracks.items():
                assert track.key == track_key
