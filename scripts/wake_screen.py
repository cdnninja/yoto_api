"""Wake a player's screen via the library's `wake_screen()`.

    python scripts/wake_screen.py

Connects over MQTT and calls `client.wake_screen(device_id)`. Watch the device.

Needs YOTO_CLIENT_ID (+ optional YOTO_REFRESH_TOKEN) in .env.
"""

import asyncio

from yoto_api import YotoClient, YotoError

from _common import console, pick_device, yoto_session


async def main() -> int:
    async with yoto_session() as yoto:
        return await _run(yoto)


async def _run(yoto: YotoClient) -> int:
    await yoto.update_player_list()
    if not yoto.players:
        console.print("No devices on this account.")
        return 1

    target = pick_device(yoto)
    if target is None:
        return 0
    device_id = target.device.device_id

    await yoto.connect_events([device_id])
    try:
        await yoto.wake_screen(device_id)
        console.print("[green]wake_screen sent[/] — check the device")
        await asyncio.sleep(1)  # let the command reach the device before disconnect
    except YotoError as err:
        console.print(f"[red]{err}[/]")
        return 1
    finally:
        await yoto.disconnect_events()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
