"""Show an icon on a player's screen, via the library's `show_icon()`.

    python scripts/show_icon.py <uri> [timeout] [--wake] [--animated]
    python scripts/show_icon.py "https://.../icon.png" 15

`uri` is the URL of the icon image. `timeout` is the display duration in
seconds, required by the firmware (default 10). Pass `--wake` to light the
screen first. Watch the device to see whether the icon shows.

Needs YOTO_CLIENT_ID (+ optional YOTO_REFRESH_TOKEN) in .env.
"""

import argparse
import asyncio

from yoto_api import YotoClient, YotoError

from _common import console, pick_device, yoto_session


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Show an icon on a Yoto player via client.show_icon()."
    )
    p.add_argument("uri", help="URL of the icon image to display")
    p.add_argument(
        "timeout",
        nargs="?",
        type=int,
        default=10,
        help="display duration in seconds, required by the firmware (default: 10)",
    )
    p.add_argument(
        "--animated",
        action="store_true",
        help="mark the icon as animated (default: static)",
    )
    p.add_argument("--wake", action="store_true", help="wake the screen first")
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    async with yoto_session() as yoto:
        return await _run(yoto, args)


async def _run(yoto: YotoClient, args: argparse.Namespace) -> int:
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
        await yoto.show_icon(
            device_id,
            args.uri,
            timeout=args.timeout,
            animated=args.animated,
            wake=args.wake,
        )
        console.print(f"[green]show_icon sent[/]: {args.uri} for {args.timeout}s")
        await asyncio.sleep(1)  # let the command reach the device before disconnect
    except YotoError as err:
        console.print(f"[red]{err}[/]")
        return 1
    finally:
        await yoto.disconnect_events()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
