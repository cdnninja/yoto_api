"""One-shot MQTT discovery probe.

Subscribes to the documented topics for ~30s and reports which ones
delivered messages, with the raw payloads. Used to verify the broker
behaviour against new firmware versions.

    python scripts/probe_mqtt.py
"""

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import aiomqtt
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table

from yoto_api import AuthenticationError, YotoClient
from yoto_api.mqtt.client import YotoMqttClient
from yoto_api.Token import Token

console = Console()

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_LISTEN_S = 30.0


async def main() -> int:
    load_dotenv()
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        print("YOTO_CLIENT_ID missing from .env")
        return 1

    initial_refresh_token = os.environ.get("YOTO_REFRESH_TOKEN")
    yoto = await _authenticate(client_id, initial_refresh_token)

    try:
        return await _run(yoto)
    finally:
        if (
            initial_refresh_token != yoto.token.refresh_token
            and yoto.token.refresh_token
        ):
            _persist_refresh_token(yoto.token.refresh_token)
        await yoto.close()


async def _run(yoto: YotoClient) -> int:
    await yoto.update_player_list()
    if not yoto.players:
        print("No devices on this account.")
        return 1

    target = _pick_device(yoto)
    if target is None:
        return 0
    device_id = target.device.device_id

    samples: Dict[str, List[Any]] = defaultdict(list)
    counts: Dict[str, int] = defaultdict(int)
    full_log: List[Dict[str, Any]] = []
    diagnostics: List[str] = []
    probe_start = time.monotonic()

    def diag(msg: str) -> None:
        line = f"[t+{time.monotonic() - probe_start:.1f}s] {msg}"
        diagnostics.append(line)
        print(line)

    diag(
        f"target: {target.device.name} ({device_id}) "
        f"family={target.device.device_family}"
    )
    diag(f"is_online (per REST): {target.status.is_online}")

    topics = _probe_topics(device_id)

    listener_task = None
    try:
        async with aiomqtt.Client(
            hostname=YotoMqttClient.URL,
            port=YotoMqttClient.PORT,
            username=f"_?x-amz-customauthorizer-name={YotoMqttClient.AUTH_NAME}",
            password=yoto.token.access_token,
            transport="websockets",
            tls_params=aiomqtt.TLSParameters(),
            keepalive=15,
            identifier=f"YOTOPROBE{uuid.uuid4().hex}",
        ) as client:
            diag("connected")
            for topic in topics:
                await client.subscribe(topic)
                diag(f"SUB {topic}")
            await client.publish(f"device/{device_id}/command/events/request")
            await client.publish(f"device/{device_id}/command/status/request")
            diag("PUB command/events/request + command/status/request")

            async def consume() -> None:
                async for message in client.messages:
                    counts[str(message.topic)] += 1
                    try:
                        payload = json.loads(message.payload.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        payload = message.payload.decode("utf-8", errors="replace")
                    if len(samples[str(message.topic)]) < 2:
                        samples[str(message.topic)].append(payload)
                    full_log.append(
                        {
                            "ts": time.time(),
                            "topic": str(message.topic),
                            "payload": payload,
                        }
                    )

            listener_task = asyncio.create_task(consume())

            diag(
                f"listening for {int(_LISTEN_S)}s, MQTT status trigger at "
                f"t+5s and t+15s"
            )
            end = time.monotonic() + _LISTEN_S
            mqtt_pushes = [5.0, 15.0]
            while time.monotonic() < end:
                elapsed = time.monotonic() - probe_start
                if mqtt_pushes and elapsed >= mqtt_pushes[0]:
                    mqtt_pushes.pop(0)
                    await client.publish(
                        f"device/{device_id}/command/status/request"
                    )
                    diag("PUB command/status/request")
                await asyncio.sleep(0.5)
    except aiomqtt.MqttError as err:
        diag(f"DISCONNECT (MqttError): {err}")
    finally:
        if listener_task is not None:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    out_path = Path(__file__).resolve().parent.parent / "mqtt_probe.log"
    with out_path.open("w") as f:
        f.write(
            f"# MQTT probe — device {device_id} — {len(full_log)} messages\n\n"
        )
        f.write("=== Diagnostics ===\n\n")
        for line in diagnostics:
            f.write(line + "\n")
        f.write("\n=== Topics observed ===\n\n")
        if not counts:
            f.write("(no messages received on any subscribed topic)\n")
        else:
            for topic in sorted(counts):
                f.write(f"  {topic}  ({counts[topic]} msg)\n")
                for s in samples[topic]:
                    if isinstance(s, dict):
                        f.write(f"    keys: {sorted(s.keys())}\n")
                    else:
                        f.write(f"    raw: {s!r}\n")
        f.write("\n=== Full message log ===\n\n")
        for entry in full_log:
            f.write(json.dumps(entry, default=str) + "\n")

    print(f"\n[wrote {len(full_log)} messages to {out_path}]")
    return 0


def _pick_device(yoto: YotoClient):
    """Same picker as scripts/debug.py."""
    players = list(yoto.players.values())
    if len(players) == 1:
        return players[0]

    table = Table(title="Devices", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Name")
    table.add_column("Family", style="dim")
    table.add_column("Status")
    for i, p in enumerate(players, start=1):
        status = "[green]online[/]" if p.status.is_online else "[red]offline[/]"
        table.add_row(
            str(i), p.device.name, p.device.device_family or "?", status
        )
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


async def _authenticate(
    client_id: str, refresh_token: str | None
) -> YotoClient:
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


def _probe_topics(device_id: str) -> List[str]:
    # Documented topics only. Wildcards (device/{id}/#, device/+/...,
    # $aws/things/.../shadow/...) are denied by the IoT policy and the
    # broker closes the connection on subscribe.
    return [
        f"device/{device_id}/data/events",
        f"device/{device_id}/data/status",
        f"device/{device_id}/response",
    ]


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
