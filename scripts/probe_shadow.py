"""One-shot probe: is there an MQTT-accessible cache for an OFFLINE device?

Targets an offline device and tries three things:
  1. subscribe to its status topics (status/full, data/status) — does a
     retained last-status arrive?
  2. subscribe + GET the AWS IoT Device Shadow ($aws/things/<id>/shadow/get)
     — is the shadow reachable over MQTT, or does the policy deny it?
  3. publish command/status(/request) — confirm an offline device doesn't
     reply.

Read-only w.r.t. device state (shadow/get + status nudges don't mutate).

    python scripts/probe_shadow.py <device_id>
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
_LISTEN_S = 20.0


async def main() -> int:
    load_dotenv(_ENV_PATH)
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        print("YOTO_CLIENT_ID missing from .env")
        return 1

    initial = os.environ.get("YOTO_REFRESH_TOKEN")
    yoto = YotoClient(client_id=client_id)
    yoto.token = Token(refresh_token=initial)
    try:
        await yoto.check_and_refresh_token()
    except AuthenticationError:
        auth = await yoto.device_code_flow_start()
        print(f"\n  AUTHORISE:\n  {auth['verification_uri_complete']}\n", flush=True)
        await yoto.device_code_flow_complete(auth)

    try:
        await yoto.update_player_list()
        device_id = sys.argv[1] if len(sys.argv) > 1 else next(iter(yoto.players))
        player = yoto.players.get(device_id)
        online = player.is_online if player else "?"
        name = player.device.name if player else device_id
        print(f"Target: {name} ({device_id}) — online(REST)={online}")

        start = time.monotonic()

        def stamp() -> str:
            return f"[t+{time.monotonic() - start:4.1f}s]"

        # Separate connections so a denied $aws subscribe (which drops the
        # connection) doesn't kill the device-topic capture.
        device_topics = [
            f"device/{device_id}/status/full",
            f"device/{device_id}/data/status",
            f"device/{device_id}/presence",
        ]
        shadow_topics = [
            f"$aws/things/{device_id}/shadow/get/accepted",
            f"$aws/things/{device_id}/shadow/get/rejected",
        ]

        async def run_capture(topics, label, publishes):
            try:
                async with aiomqtt.Client(
                    hostname=YotoMqttClient.URL,
                    port=YotoMqttClient.PORT,
                    username=f"_?x-amz-customauthorizer-name={YotoMqttClient.AUTH_NAME}",
                    password=yoto.token.access_token,
                    transport="websockets",
                    tls_params=aiomqtt.TLSParameters(),
                    keepalive=30,
                    identifier=f"YOTOSHDW{uuid.uuid4().hex}",
                ) as client:
                    for t in topics:
                        await client.subscribe(t)
                        print(f"{stamp()} [{label}] SUB {t}")
                    for topic, payload in publishes:
                        await client.publish(topic, payload=payload)
                        print(f"{stamp()} [{label}] PUB {topic} {payload or ''}")

                    async def consume():
                        async for m in client.messages:
                            try:
                                body = json.loads(m.payload.decode("utf-8"))
                            except (UnicodeDecodeError, ValueError):
                                body = m.payload.decode("utf-8", errors="replace")
                            keys = (
                                sorted(body.keys()) if isinstance(body, dict) else body
                            )
                            print(f"{stamp()} [{label}] <<< {m.topic} :: {keys}")

                    task = asyncio.create_task(consume())
                    try:
                        await asyncio.sleep(_LISTEN_S)
                    finally:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
            except aiomqtt.MqttError as err:
                print(f"{stamp()} [{label}] MqttError (likely policy-denied): {err}")

        await asyncio.gather(
            run_capture(
                device_topics,
                "device",
                [
                    (f"device/{device_id}/command/status/request", None),
                    (
                        f"device/{device_id}/command/status",
                        json.dumps({"requestId": uuid.uuid4().hex}),
                    ),
                ],
            ),
            run_capture(
                shadow_topics,
                "shadow",
                [(f"$aws/things/{device_id}/shadow/get", "")],
            ),
        )
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
