"""Live TUI inspector for a Yoto player.

Auth → pick device → live debug. Connects to MQTT and refreshes a rich
TUI as messages arrive, so you can poke at a device and watch the lib's
view of state change in real time.

    python scripts/debug.py

Read-only — never mutates device state. Ctrl+C to exit.
"""

import asyncio
import os
import time
from collections import deque
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table
from rich.text import Text

from yoto_api import AuthenticationError, YotoClient, YotoPlayer
from yoto_api.Token import Token

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

console = Console()


async def main() -> int:
    load_dotenv()
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        console.print("[red]YOTO_CLIENT_ID missing from .env[/]")
        return 1

    initial_refresh_token = os.environ.get("YOTO_REFRESH_TOKEN")
    client = await _authenticate(client_id, initial_refresh_token)

    try:
        return await _run(client)
    finally:
        if (
            client.token
            and client.token.refresh_token
            and client.token.refresh_token != initial_refresh_token
        ):
            _persist_refresh_token(client.token.refresh_token)
        await client.close()


async def _run(client: YotoClient) -> int:
    with console.status("Loading devices…"):
        await client.update_player_list()
    if not client.players:
        console.print("[red]No devices on this account.[/]")
        return 1

    device_id = _pick_device(client)
    if device_id is None:
        return 0

    with console.status("Hydrating state…"):
        try:
            await client.update_player_info(device_id)
        except Exception as err:
            console.print(f"[yellow]warn: update_player_info failed: {err}[/]")
        try:
            await client.update_player_status(device_id)
        except Exception as err:
            console.print(f"[yellow]warn: update_player_status failed: {err}[/]")

    log: Deque[Tuple[str, str]] = deque(maxlen=15)

    async def on_update(player: YotoPlayer) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        snapshot = _snapshot(player)
        # Diff against the previous snapshot to log only what changed.
        prev = on_update.snapshot  # type: ignore[attr-defined]
        for key, value in snapshot.items():
            if prev.get(key) != value:
                log.append((ts, f"{key}: {prev.get(key)!r} → {value!r}"))
        on_update.snapshot = snapshot  # type: ignore[attr-defined]

    on_update.snapshot = _snapshot(client.players[device_id])  # type: ignore[attr-defined]

    await client.connect_events([device_id], on_update=on_update)

    # The firmware never pushes data/status spontaneously, but it does
    # respond to MQTT command/status/request with a fresh push within
    # ~150ms (verified via scripts/probe_mqtt.py). REST POST /command/status
    # is acked but doesn't trigger an MQTT push. So nudge MQTT directly.
    push_interval_s = 2.0
    last_push = 0.0

    try:
        with Live(
            _render(client.players[device_id], log),
            console=console,
            refresh_per_second=4,
            screen=True,
        ) as live:
            while True:
                now = time.monotonic()
                if client._mqtt is not None and now - last_push >= push_interval_s:
                    try:
                        await client._mqtt.request_status_push(device_id)
                    except Exception:
                        pass
                    last_push = now
                live.update(_render(client.players[device_id], log))
                await asyncio.sleep(0.25)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await client.disconnect_events()
    return 0


# ─── Rendering ───────────────────────────────────────────────────────


def _render(player: YotoPlayer, log: Deque[Tuple[str, str]]) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(_header(player), name="header", size=3),
        Layout(name="body"),
        Layout(_log_panel(log), name="log", size=10),
    )
    layout["body"].split_row(
        Layout(_section_panel("Status", player.status), name="status"),
        Layout(name="right"),
    )
    # Last event is small (~12 useful fields); config takes the rest.
    layout["right"].split_column(
        Layout(_section_panel("Last event", player.last_event), name="event", size=16),
        Layout(_section_panel("Config", player.info.config), name="config"),
    )
    return layout


def _header(player: YotoPlayer) -> Panel:
    online = (
        Text("● online", style="bold green")
        if player.status.is_online
        else Text("● offline", style="bold red")
    )
    fw = player.info.firmware_version or "?"
    text = Text.assemble(
        ("Yoto Debug  ", "bold cyan"),
        (player.device.name or "?", "bold"),
        f"  ({player.device.device_id})  [{player.device.device_family} · fw {fw}]  ",
        online,
    )
    return Panel(text, border_style="cyan")


def _section_panel(title: str, obj: Any, skip: set[str] | None = None) -> Panel:
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(style="dim", no_wrap=True)
    table.add_column(overflow="fold")

    rows = list(_flatten(obj, skip=skip or set()))
    if not rows:
        table.add_row("[dim italic]<empty>[/]", "")
    else:
        for key, value in rows:
            table.add_row(key, _format_value(value))
    return Panel(table, title=title, border_style="white", title_align="left")


def _flatten(obj: Any, prefix: str = "", skip: set[str] = frozenset()) -> Any:
    """Flatten a dataclass into [(dotted.key, value)], skipping None and
    any field name in `skip` (top-level only)."""
    if not is_dataclass(obj):
        return
    for f in fields(obj):
        if f.name in skip:
            continue
        value = getattr(obj, f.name)
        if value is None:
            continue
        key = f"{prefix}{f.name}"
        if is_dataclass(value):
            yield from _flatten(value, prefix=f"{key}.")
        elif isinstance(value, list) and value and is_dataclass(value[0]):
            yield (key, f"<{len(value)} item(s)>")
        else:
            yield (key, value)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "[green]true[/]" if value else "[red]false[/]"
    if isinstance(value, (int, float)):
        return f"[yellow]{value}[/]"
    if isinstance(value, str):
        return f"[white]{value}[/]"
    return repr(value)


def _log_panel(log: Deque[Tuple[str, str]]) -> Panel:
    if not log:
        body = Text("waiting for MQTT messages…", style="dim italic")
    else:
        body = Text()
        for ts, line in log:
            body.append(f"{ts}  ", style="dim")
            body.append(line + "\n")
    return Panel(body, title="Recent updates", border_style="white", title_align="left")


def _snapshot(player: YotoPlayer) -> dict:
    return dict(_flatten(player.status, prefix="status.")) | dict(
        _flatten(player.last_event, prefix="event.")
    )


# ─── Auth + device picker ────────────────────────────────────────────


async def _authenticate(client_id: str, refresh_token: str | None) -> YotoClient:
    client = YotoClient(client_id=client_id)
    if refresh_token:
        client.token = Token(refresh_token=refresh_token)
        try:
            await client.check_and_refresh_token()
            return client
        except AuthenticationError:
            console.print(
                "[yellow]Stored refresh token invalid; using device-code flow.[/]"
            )

    auth = await client.device_code_flow_start()
    console.print(
        f"\n[bold cyan]Open this URL to authorise:[/]\n  "
        f"{auth['verification_uri_complete']}\n"
    )
    await client.device_code_flow_complete(auth)
    return client


def _pick_device(client: YotoClient) -> str | None:
    players = list(client.players.values())
    if len(players) == 1:
        return players[0].device.device_id

    table = Table(title="Devices", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Name")
    table.add_column("Family", style="dim")
    table.add_column("Status")
    for i, p in enumerate(players, start=1):
        status = "[green]online[/]" if p.status.is_online else "[red]offline[/]"
        table.add_row(str(i), p.device.name, p.device.device_family or "?", status)
    console.print(table)

    try:
        choice = IntPrompt.ask(
            "Pick a device",
            choices=[str(i) for i in range(1, len(players) + 1)],
            default=1,
        )
    except (KeyboardInterrupt, EOFError):
        return None
    return players[choice - 1].device.device_id


def _persist_refresh_token(new_token: str) -> None:
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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
