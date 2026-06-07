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
_LISTEN_S = 38.0

# Trigger schedule (seconds from probe start). Each phase fires a different
# status-refresh mechanism so we can attribute downstream messages to the
# trigger that caused them. See PR #187 discussion.
_PHASE_BASELINE = "baseline"
_PHASE_MQTT_REQUEST = "mqtt:command/status/request"
_PHASE_REST_POST = "rest:POST /command/status"
_PHASE_MQTT_DIRECT = "mqtt:command/status+requestId"


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
    diag(f"is_online (per REST): {target.is_online}")

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

            phase = [_PHASE_BASELINE]

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
                            "phase": phase[0],
                            "topic": str(message.topic),
                            "payload": payload,
                        }
                    )

            listener_task = asyncio.create_task(consume())

            # Each tuple: (fire_at_seconds, phase_label, coroutine factory).
            # A clean baseline window first, then one trigger per phase with
            # ~10s of quiet after each so its replies are unambiguous.
            async def _mqtt_request() -> None:
                await client.publish(f"device/{device_id}/command/events/request")
                await client.publish(f"device/{device_id}/command/status/request")

            async def _rest_post() -> None:
                # The lib's *unused* REST trigger: POST /command/status. This
                # is what should refresh the AWS IoT shadow and reply on
                # device/<id>/status/full.
                await yoto._rest.request_player_status(yoto.token, device_id)

            async def _mqtt_direct() -> None:
                # Hypothesis: the cloud's command/status publish can be sent
                # directly over MQTT. The requestId echoes back on /response.
                await client.publish(
                    f"device/{device_id}/command/status",
                    json.dumps({"requestId": uuid.uuid4().hex}),
                )

            schedule = [
                (5.0, _PHASE_MQTT_REQUEST, _mqtt_request),
                (18.0, _PHASE_REST_POST, _rest_post),
                (30.0, _PHASE_MQTT_DIRECT, _mqtt_direct),
            ]

            diag(
                f"listening for {int(_LISTEN_S)}s; triggers at "
                + ", ".join(f"t+{t:.0f}s ({label})" for t, label, _ in schedule)
            )
            end = time.monotonic() + _LISTEN_S
            while time.monotonic() < end:
                elapsed = time.monotonic() - probe_start
                if schedule and elapsed >= schedule[0][0]:
                    _, label, fire = schedule.pop(0)
                    phase[0] = label
                    try:
                        await fire()
                        diag(f"TRIGGER {label}")
                    except Exception as err:
                        diag(f"TRIGGER {label} FAILED: {err}")
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
        f.write(f"# MQTT probe — device {device_id} — {len(full_log)} messages\n\n")
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

        # Which trigger produced which topic? This is the whole point of the
        # phased schedule — e.g. did status/full only show up after the REST
        # POST, never after the MQTT command/status/request?
        f.write("\n=== Topic x phase matrix ===\n\n")
        by_phase: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for entry in full_log:
            by_phase[entry["phase"]][entry["topic"]] += 1
        for phase_label in sorted(by_phase):
            f.write(f"  [{phase_label}]\n")
            for topic in sorted(by_phase[phase_label]):
                f.write(f"    {topic}  ({by_phase[phase_label][topic]} msg)\n")
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


def _probe_topics(device_id: str) -> List[str]:
    # Wildcards (device/{id}/#, device/+/..., $aws/things/.../shadow/...)
    # are denied by the IoT policy and the broker closes the connection on
    # subscribe, so every topic must be named explicitly.
    #
    # The first three are the lib's documented set. The rest are the
    # candidate topics from @sethfitz's investigation on PR #187 — notably
    # `status/full`, which carries the richest payload (statusVersion 3,
    # raw battery mV, powerSrc, shutDown reason) and is the device's reply
    # to a POST /device-v2/{id}/command/status. If a subscribe is denied
    # the broker drops the connection; comment out the offending line.
    return [
        f"device/{device_id}/data/events",
        f"device/{device_id}/data/status",
        f"device/{device_id}/response",
        f"device/{device_id}/status",
        f"device/{device_id}/status/full",
        f"device/{device_id}/presence",
        f"device/{device_id}/events",
        f"device/{device_id}/progress",
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
