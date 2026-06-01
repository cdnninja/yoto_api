"""Read-only presence/offline validation listener.

Subscribes to a device's live topics and the `presence` topic, then just
listens — it NEVER publishes, so the AWS IoT Last-Will (offline) message
isn't masked. Power-cycle the device while it runs to validate that:

  - powering off yields  presence {"state":"offline"}  (LWT)
  - powering on  yields  presence {"state":"online"}   + data/status

    python scripts/probe_presence.py [device_id]

If device_id is omitted, lists devices and uses the first one.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

import aiomqtt
from dotenv import load_dotenv

from yoto_api import AuthenticationError, YotoClient
from yoto_api.mqtt.client import YotoMqttClient
from yoto_api.Token import Token

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_LISTEN_S = 180.0


async def main() -> int:
    load_dotenv(_ENV_PATH)
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        print("YOTO_CLIENT_ID missing from .env")
        return 1

    initial = os.environ.get("YOTO_REFRESH_TOKEN")
    yoto = YotoClient(client_id=client_id)
    if initial:
        yoto.token = Token(refresh_token=initial)
        try:
            await yoto.check_and_refresh_token()
        except AuthenticationError:
            auth = await yoto.device_code_flow_start()
            print(f"\n  Authorise:\n  {auth['verification_uri_complete']}\n")
            await yoto.device_code_flow_complete(auth)

    try:
        await yoto.update_player_list()
        if not yoto.players:
            print("No devices.")
            return 1

        device_id = sys.argv[1] if len(sys.argv) > 1 else None
        if device_id is None:
            for did, p in yoto.players.items():
                state = "online" if p.is_online else "offline"
                print(f"  {did}  {p.device.name}  ({state})")
            device_id = next(iter(yoto.players))
        player = yoto.players.get(device_id)
        name = player.device.name if player else device_id
        online = player.is_online if player else "?"
        print(f"\nTarget: {name} ({device_id}) — online(REST list)={online}")

        topics = [
            f"device/{device_id}/presence",
            f"device/{device_id}/data/status",
            f"device/{device_id}/data/events",
            f"device/{device_id}/status/full",
        ]

        start = time.monotonic()

        def stamp() -> str:
            return f"[t+{time.monotonic() - start:5.1f}s]"

        async with aiomqtt.Client(
            hostname=YotoMqttClient.URL,
            port=YotoMqttClient.PORT,
            username=f"_?x-amz-customauthorizer-name={YotoMqttClient.AUTH_NAME}",
            password=yoto.token.access_token,
            transport="websockets",
            tls_params=aiomqtt.TLSParameters(),
            keepalive=30,
            identifier=f"YOTOPRES{uuid.uuid4().hex}",
        ) as client:
            for t in topics:
                await client.subscribe(t)
            print(
                f"{stamp()} connected + subscribed. Listening {int(_LISTEN_S)}s — "
                f"POWER-CYCLE THE DEVICE NOW (off, wait ~20s, on).\n"
            )

            async def consume() -> None:
                async for m in client.messages:
                    topic = str(m.topic).rsplit("/", 2)[-2:]
                    suffix = "/".join(topic)
                    try:
                        body = json.loads(m.payload.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        body = m.payload.decode("utf-8", errors="replace")
                    if suffix.endswith("presence"):
                        print(f"{stamp()} >>> PRESENCE: {body}")
                    elif "status/full" in str(m.topic):
                        st = body.get("status", {}) if isinstance(body, dict) else {}
                        print(
                            f"{stamp()} status/full battery={st.get('batteryLevel')} "
                            f"mV={st.get('battery')} shutDown={st.get('shutDown')!r}"
                        )
                    elif suffix.endswith("data/status"):
                        st = body.get("status", {}) if isinstance(body, dict) else {}
                        print(f"{stamp()} data/status battery={st.get('batteryLevel')}")
                    else:
                        print(f"{stamp()} {suffix}")

            task = asyncio.create_task(consume())
            try:
                await asyncio.sleep(_LISTEN_S)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        print(f"\n{stamp()} done.")
    finally:
        if (
            yoto.token
            and yoto.token.refresh_token
            and yoto.token.refresh_token != initial
        ):
            lines = _ENV_PATH.read_text().splitlines() if _ENV_PATH.exists() else []
            nl = f"YOTO_REFRESH_TOKEN={yoto.token.refresh_token}"
            for i, line in enumerate(lines):
                if line.startswith("YOTO_REFRESH_TOKEN="):
                    lines[i] = nl
                    break
            else:
                lines.append(nl)
            _ENV_PATH.write_text("\n".join(lines) + "\n")
        await yoto.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
