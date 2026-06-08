"""Shared helpers for the scripts: a YotoClient session and a device picker.

Not runnable on its own. Imported by the sibling scripts — running
`python scripts/<name>.py` puts this directory on `sys.path`.
"""

import contextlib
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table

from yoto_api import AuthenticationError, YotoClient
from yoto_api.Token import Token

console = Console()
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@contextlib.asynccontextmanager
async def yoto_session():
    """Authenticate from .env and yield a YotoClient.

    Persists a refreshed token back to .env and closes the client on exit.
    Raises SystemExit if YOTO_CLIENT_ID is missing.
    """
    load_dotenv()
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        raise SystemExit("YOTO_CLIENT_ID missing from .env")
    initial = os.environ.get("YOTO_REFRESH_TOKEN")
    yoto = await _authenticate(client_id, initial)
    try:
        yield yoto
    finally:
        if initial != yoto.token.refresh_token and yoto.token.refresh_token:
            _persist_refresh_token(yoto.token.refresh_token)
        await yoto.close()


def pick_device(yoto: YotoClient):
    """Return the only device, or prompt to pick one. None if cancelled."""
    players = list(yoto.players.values())
    if len(players) == 1:
        return players[0]

    table = Table(title="Devices", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Name")
    table.add_column("Family", style="dim")
    table.add_column("Status")
    for i, p in enumerate(players, start=1):
        status = "[green]online[/]" if p.is_online else "[red]offline[/]"
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
    return players[choice - 1]


async def _authenticate(client_id: str, refresh_token: str | None) -> YotoClient:
    yoto = YotoClient(client_id=client_id)
    if refresh_token:
        yoto.token = Token(refresh_token=refresh_token)
        try:
            await yoto.check_and_refresh_token()
            return yoto
        except AuthenticationError:
            print("Stored refresh token invalid; using device-code flow.")
    auth = await yoto.device_code_flow_start()
    print(f"\n  Open this URL to authorise:\n  {auth['verification_uri_complete']}\n")
    await yoto.device_code_flow_complete(auth)
    return yoto


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
