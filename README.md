# yoto_api

Async Python wrapper for the Yoto API: control players, browse the card
library, react to live MQTT playback events.

Get a client ID at <https://yoto.dev/get-started/start-here/>.

## Credit

Thanks to @buzzeddesign for help sniffing the API and @fuatakgun for
the original v2.x architecture (based on kia_uvo). Credit to piitaya for version 3.

## Quick start

```python
import asyncio
from yoto_api import YotoClient

async def main():
    async with YotoClient(client_id="your_client_id") as client:
        auth = await client.device_code_flow_start()
        print(auth["verification_uri_complete"])
        await client.device_code_flow_complete(auth)

        await client.refresh()
        for pid, player in client.players.items():
            print(pid, player.device.name, player.model)

        async def on_update(player):
            print(player.last_event.playback_status,
                  player.status.battery_level_percentage)

        await client.connect_events(list(client.players), on_update=on_update)
        await client.pause(next(iter(client.players)))
        await asyncio.sleep(60)
        await client.disconnect_events()

asyncio.run(main())
```

If you already have a refresh token:

```python
async with YotoClient(client_id="your_client_id") as client:
    client.set_refresh_token(refresh_token)
    await client.refresh()
```

For consumers managing OAuth + session externally (e.g. HA core):

```python
client = YotoClient(session=my_aiohttp_session)
client.token = Token(access_token=..., refresh_token=..., ...)
# caller owns the session — won't be closed by client.close()
```

## Data model

`YotoPlayer` aggregates typed sub-objects (one per data source) plus a
root-level `is_online`:

- `player.device` (`Device`): immutable identity from `/devices/mine`.
- `player.info` (`PlayerInfo`): settings, mac, firmware from `/config`.
- `player.status` (`PlayerStatus`): basic live telemetry from MQTT
  `data/status` (battery, volume, charging, day mode).
- `player.extended_status` (`PlayerExtendedStatus`): the richer telemetry from
  MQTT `status/full` or the REST `/config` shadow (network, disk, uptime,
  raw battery). A superset of `PlayerStatus`. Yoto doesn't document this one,
  so treat it as best-effort.
- `player.last_event` (`PlaybackEvent`): live playback state pushed
  via MQTT (track, position, volume).
- `player.is_online` (`bool`): connection state, from MQTT presence and
  REST.

All are always present (default-initialised). The `*_refreshed_at`,
`last_event_received_at` and `online_refreshed_at` timestamps tell you
whether data has actually been received. On top of that, `status` and
`extended_status` carry `updated_at`: when that telemetry was current
device-side. Gate on it if you care about freshness.

## Common methods

All public methods are async.

Refresh over REST (`update_*`): a one-shot snapshot, returned and stored,
works even when the device is offline.

```python
await client.update_player_list()           # /devices/mine
await client.update_player_info(device_id)  # /config — info + info.config
await client.update_player_extended_status(device_id)  # /config shadow — extended_status
await client.update_library()               # /card/family/library — client.library
await client.update_groups()                # /card/family/library/groups — client.groups
await client.refresh()                      # list + all info
```

Refresh over MQTT (`request_*`): ask the device to push fresh data. It
arrives on your `on_update` callback, so connect first with `connect_events`.

```python
await client.request_player_status(device_id)           # -> player.status
await client.request_player_extended_status(device_id)  # -> player.extended_status
```

Groups are user-defined labels over library cards (a card can sit in
several groups at once). Each `Group` in `client.groups` carries the
card IDs in `card_ids`; cross-reference them against `client.library`
for the card metadata.

MQTT:

```python
await client.connect_events(player_ids, on_update=cb, on_disconnect=cb)
await client.subscribe_player_events(device_id)
await client.unsubscribe_player_events(device_id)
client.is_mqtt_connected
await client.reconnect_events()
await client.disconnect_events()
```

Callbacks may be sync or async.

Player commands (MQTT, ~50 ms):

```python
await client.play_card(player_id, "card_id", chapter_key="01", track_key="01")
await client.pause(player_id)
await client.resume(player_id)
await client.stop(player_id)
await client.set_volume(player_id, 50)            # 0-100
await client.set_sleep_timer(player_id, 600)      # seconds
await client.set_ambients(player_id, 255, 0, 0)   # RGB
await client.next_track(player_id)
await client.previous_track(player_id)
await client.seek(player_id, position=30)
```

Settings (REST PUT):

```python
import datetime
await client.set_player_config(
    player_id,
    day_time=datetime.time(7, 30),
    night_max_volume_limit=8,
    day_ambient_colour="#40bfd9",
    repeat_all=True,
    day_display_brightness_auto=True,  # or day_display_brightness=80
)
await client.set_alarms(player_id, alarms=[...])
await client.set_alarm_enabled(player_id, index=0, enabled=False)
```

JWT helpers (no API call):

```python
from yoto_api import get_account_id, has_scope
account_id = get_account_id(client.token.access_token)
can_status = has_scope(client.token.access_token, "family:device-status:view")
```

## Errors

All failures raise a subclass of `YotoError`:

```python
from yoto_api import YotoError, AuthenticationError, YotoAPIError, YotoMQTTError

try:
    await client.refresh()
except AuthenticationError:        # token expired or invalid
    ...
except YotoAPIError as err:        # HTTP / parse error (err.status_code on 4xx/5xx)
    ...
except YotoMQTTError:              # MQTT broker / aiomqtt error
    ...
except YotoError:                  # catch-all
    ...
```

## Migration from 2.x

See [MIGRATION_3.md](MIGRATION_3.md). Short version: `YotoManager` →
`YotoClient`, flat fields on `YotoPlayer` → sub-objects, and every
method is now async.

## Development

```bash
pip install -r requirements.txt -r requirements_dev.txt
python -m pytest tests/                      # unit, no creds
```

End-to-end tests need a `.env` at the repo root:

```bash
YOTO_CLIENT_ID=your_client_id
YOTO_REFRESH_TOKEN=optional_refresh_token
```

Then:

```bash
python -m pytest tests/e2e -m e2e -s
```

The first run prompts for a verification URL and writes the new refresh
token back to `.env`. `-s` keeps the prompt visible. E2E tests are
read-only and opt-in (`-m e2e`).

Scripts:

```bash
python scripts/check_unmapped.py   # list API/MQTT keys we don't parse
python scripts/debug.py            # rich TUI: pick a device, watch live state
python scripts/probe_mqtt.py       # 30s MQTT capture → mqtt_probe.log
```

### MQTT vs REST notes

- `data/events` is pushed in real time. Subscribe and react.
- `data/status` is **never** pushed spontaneously. The firmware
  responds to MQTT `command/status/request` within ~150ms. The REST
  `POST /command/status` is acked but doesn't trigger an MQTT push —
  use `client.request_player_status` (which routes through MQTT).
- `data/status` (v1) is a subset: `powerSrc`, `wifiStrength`, `ssid`,
  `temp`, `upTime`, `utcTime`, `utcOffset`, `totalDisk` arrive only via
  MQTT `status/full` or the REST `/config` shadow. Use
  `client.request_player_extended_status` (MQTT) or poll
  `client.update_player_extended_status()` on a slower timer; both feed
  `player.extended_status`.

## Other notes

Not affiliated with Yoto Play in any way.
