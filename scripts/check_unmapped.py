"""Print API/MQTT fields the lib doesn't currently parse.

Helpful to spot new Yoto firmware features early. Reads `.env` for
`YOTO_CLIENT_ID` and `YOTO_REFRESH_TOKEN` (falls back to device-code
flow if either is missing/invalid). Read-only — never mutates state.

    python scripts/check_unmapped.py
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from yoto_api import AuthenticationError, YotoAPIError, YotoClient
from yoto_api.mqtt.client import YotoMqttClient
from yoto_api.mqtt.parser import KNOWN_EVENT_KEYS, KNOWN_STATUS_KEYS
from yoto_api.rest.client import (
    KNOWN_CONFIG_KEYS,
    KNOWN_DEVICE_KEYS,
    KNOWN_STATUS_ENDPOINT_KEYS,
)
from yoto_api.status_adapter import KNOWN_RAW_STATUS_KEYS
from yoto_api.Token import Token

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# How long to listen on MQTT after connect. The broker subscribe + initial
# state push takes a couple of seconds.
_MQTT_LISTEN_S = 8.0
_MQTT_AFTER_PUSH_S = 3.0


def main() -> int:
    load_dotenv()
    client_id = os.environ.get("YOTO_CLIENT_ID")
    if not client_id:
        print("YOTO_CLIENT_ID missing from .env", file=sys.stderr)
        return 1

    initial_refresh_token = os.environ.get("YOTO_REFRESH_TOKEN")
    client = _authenticate(client_id, initial_refresh_token)

    try:
        return _run(client)
    finally:
        if (
            client.token
            and client.token.refresh_token
            and client.token.refresh_token != initial_refresh_token
        ):
            _persist_refresh_token(client.token.refresh_token)


def _run(client: YotoClient) -> int:
    client.update_player_list()
    if not client.players:
        print("No devices on this account.", file=sys.stderr)
        return 1

    # REST: hit every device — different hardware/firmware can surface
    # different fields (e.g. Mini doesn't have ALS).
    for device_id, player in client.players.items():
        print(f"\n=== {player.device.name} ({device_id}) ===")
        _check_rest(client, device_id)

    # MQTT: any one online device is enough — the broker payload shape
    # doesn't vary by device.
    online_id = next(
        (did for did, p in client.players.items() if p.status.is_online), None
    )
    if online_id is None:
        print("\n[skip] MQTT: no online devices on this account", file=sys.stderr)
        return 0
    online_player = client.players[online_id]
    print(f"\n=== MQTT via {online_player.device.name} ({online_id}) ===")
    _check_mqtt(client, online_id)

    return 0


def _authenticate(client_id: str, refresh_token: str | None) -> YotoClient:
    client = YotoClient(client_id=client_id)
    if refresh_token:
        client.token = Token(refresh_token=refresh_token)
        try:
            client.check_and_refresh_token()
            return client
        except AuthenticationError:
            print(
                "Stored refresh token is invalid; falling back to device-code flow.",
                file=sys.stderr,
            )

    auth = client.device_code_flow_start()
    print(f"\n  Open this URL to authorise:\n  {auth['verification_uri_complete']}\n")
    client.device_code_flow_complete(auth)
    return client


def _persist_refresh_token(new_token: str) -> None:
    """Write the rotated YOTO_REFRESH_TOKEN back to `.env`."""
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


def _check_rest(client: YotoClient, device_id: str) -> None:
    config = client._rest._get(
        client.token,
        f"/device-v2/{device_id}/config",
        "unmapped probe",
    )
    device = config.get("device") or {}
    flat_metadata = {k: v for k, v in device.items() if not isinstance(v, dict)}
    raw_config = device.get("config") or {}
    raw_status = device.get("status") or {}

    _print_unmapped("device (metadata)", flat_metadata, KNOWN_DEVICE_KEYS)
    _print_unmapped("device.config", raw_config, KNOWN_CONFIG_KEYS)
    _print_unmapped("device.status", raw_status, KNOWN_RAW_STATUS_KEYS)

    try:
        status = client._rest._get(
            client.token,
            f"/device-v2/{device_id}/status",
            "unmapped probe",
        )
    except YotoAPIError as err:
        if err.status_code == 403:
            print(
                "\n[skip] /status: token lacks family:device-status:view scope",
                file=sys.stderr,
            )
            return
        raise
    _print_unmapped("/status", status, KNOWN_STATUS_ENDPOINT_KEYS)


def _check_mqtt(client: YotoClient, device_id: str) -> None:
    captured: list[tuple[str, dict[str, Any]]] = []
    original_on_message = YotoMqttClient._on_message

    def capturing(self, mqtt_client, userdata, message) -> None:
        try:
            body = json.loads(message.payload.decode("utf-8"))
            captured.append((message.topic, body))
        except (UnicodeDecodeError, ValueError):
            pass
        original_on_message(self, mqtt_client, userdata, message)

    YotoMqttClient._on_message = capturing
    try:
        client.connect_events([device_id])
        time.sleep(_MQTT_LISTEN_S)
        client.request_status_push(device_id)
        time.sleep(_MQTT_AFTER_PUSH_S)
    finally:
        try:
            client.disconnect_events()
        finally:
            YotoMqttClient._on_message = original_on_message

    _print_unmapped_samples(
        "data/events",
        _collect(captured, "/data/events", KNOWN_EVENT_KEYS),
    )
    _print_unmapped_samples(
        "data/status",
        _collect(captured, "/data/status", KNOWN_STATUS_KEYS, unwrap_status=True),
    )


def _collect(
    captured: list[tuple[str, dict[str, Any]]],
    topic_suffix: str,
    known_keys: frozenset[str],
    unwrap_status: bool = False,
) -> dict[str, list[Any]]:
    samples: dict[str, list[Any]] = {}
    for topic, body in captured:
        if not topic.endswith(topic_suffix):
            continue
        payload = body.get("status", body) if unwrap_status else body
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if key in known_keys:
                continue
            samples.setdefault(key, []).append(value)
    return samples


def _print_unmapped(label: str, payload: dict, known_keys: frozenset[str]) -> None:
    unmapped = {k: v for k, v in payload.items() if k not in known_keys}
    if not unmapped:
        print(f"\n[ok] {label}: no unmapped fields")
        return
    print(f"\n[unmapped] {label}:")
    for key in sorted(unmapped):
        print(f"  {key} = {unmapped[key]!r}")


def _print_unmapped_samples(label: str, samples: dict[str, list[Any]]) -> None:
    if not samples:
        print(f"\n[ok] {label}: no unmapped fields")
        return
    print(f"\n[unmapped] {label}:")
    for key, values in sorted(samples.items()):
        seen: list[Any] = []
        for v in values:
            if v not in seen:
                seen.append(v)
            if len(seen) >= 3:
                break
        formatted = ", ".join(repr(v) for v in seen)
        print(f"  {key} = {formatted}")


if __name__ == "__main__":
    raise SystemExit(main())
