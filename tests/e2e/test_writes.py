"""End-to-end write tests: change settings, verify, revert.

Picks different values, writes them, re-reads to confirm Yoto applied
them, then writes the originals back. Catches the class of bug that
unit tests can't see: where the lib serializes something the backend
rejects or silently ignores.

Only touches cosmetic fields — even a failed revert won't visibly
disrupt the device. The revert lives in `finally` so a mid-test crash
still attempts to restore state.
"""

import asyncio
import datetime

import pytest

from yoto_api import PlayerConfig, YotoClient

pytestmark = pytest.mark.e2e

# Pause between change and revert. Lets you watch the screen update.
# Set to 0 in CI; bump to 5+ when poking at the device manually.
_VISUAL_PAUSE_S = 2.0


async def test_settings_change_and_revert(client: YotoClient) -> None:
    """One batch PUT exercising the time, int, and bool serializers.
    Skips fields not set on this device.

    Picks the first non-Mini device so cosmetic changes (hour_format)
    are visible on screen during the visual pause."""
    await client.update_player_list()
    device_id = next(
        (
            did
            for did, p in client.players.items()
            if p.device.device_family != "mini"
        ),
        None,
    )
    if device_id is None:
        pytest.skip("no non-Mini device on this account")
    config = await _config(client, device_id)

    changes: dict = {}
    if config.day_time is not None:
        # +1 minute — the day-mode trigger shifts by 60s, harmless.
        new_minute = (config.day_time.minute + 1) % 60
        changes["day_time"] = datetime.time(config.day_time.hour, new_minute)
    if config.hour_format is not None:
        # Cosmetic: 12h <-> 24h clock display.
        changes["hour_format"] = 12 if config.hour_format == 24 else 24
    if config.day_sounds_off is not None:
        # System sounds (button beeps) muted state during day mode.
        changes["day_sounds_off"] = not config.day_sounds_off

    if not changes:
        pytest.skip("none of the probed settings are set on this device")

    originals = {key: getattr(config, key) for key in changes}
    try:
        await client.set_player_config(device_id, **changes)
        updated = await _config(client, device_id)
        for key, expected in changes.items():
            assert getattr(updated, key) == expected, f"{key} did not update"
        if _VISUAL_PAUSE_S > 0:
            await asyncio.sleep(_VISUAL_PAUSE_S)
    finally:
        await client.set_player_config(device_id, **originals)


async def _config(client: YotoClient, device_id: str) -> PlayerConfig:
    info = await client.update_player_info(device_id)
    return info.config
