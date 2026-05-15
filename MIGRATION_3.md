# Migrating from yoto-api 2.x to 3.0

3.0 is a full rewrite.

## TL;DR

- **Async.** Every public method on `YotoClient` is a coroutine.
  `requests` → `aiohttp`, `paho-mqtt` → `aiomqtt`.
- `YotoManager` → `YotoClient`. Use as `async with` so the session +
  MQTT task are closed for you.
- `YotoPlayer` no longer has flat fields. Use `player.device`,
  `player.info`, `player.status`, `player.last_event`.
- Settings consolidated into `set_player_config(device_id, **fields)`
  with proper Python types.
- `set_alarm` removed. Use `set_alarms` (full list) or
  `set_alarm_enabled` (toggle one).
- `Family` / `update_family` gone. Use `get_account_id(token.access_token)`.
- The `family:device-status:view` OAuth scope is no longer required.

## Imports

```diff
-from yoto_api import YotoManager, YotoAPI, YotoMQTTClient
+from yoto_api import YotoClient
```

## Construction

```diff
-manager = YotoManager(client_id="...")
+async with YotoClient(client_id="...") as client:
+    ...
```

For HA core (or any consumer managing OAuth + session externally):

```python
client = YotoClient(session=my_aiohttp_session)
client.token = Token(access_token=..., refresh_token=..., ...)
# caller owns the session — won't be closed by client.close()
```

## Reading player data

The flat `YotoPlayer` is split by source.

| 2.x                               | 3.0                                                           |
| --------------------------------- | ------------------------------------------------------------- |
| `player.online`                   | `player.status.is_online`                                     |
| `player.firmware_version`         | `player.info.firmware_version`                                |
| `player.device_type`              | `player.device.device_type`                                   |
| `player.battery_level_percentage` | `player.status.battery_level_percentage`                      |
| `player.charging`                 | `player.status.is_charging`                                   |
| `player.is_playing`               | `player.last_event.playback_status == PlaybackStatus.PLAYING` |
| `player.volume`                   | `player.last_event.volume` (raw 0-16)                         |
| `player.system_volume`            | `player.status.system_volume_percentage` (0-100)              |
| `player.track_position`           | `player.last_event.position`                                  |
| `player.track_title`              | `player.last_event.track_title`                               |
| `player.chapter_title`            | `player.last_event.chapter_title`                             |
| `player.card_id`                  | `player.last_event.card_id`                                   |
| `player.config.alarms`            | `player.info.config.alarms`                                   |
| `player.night_light_mode`         | `player.status.nightlight_mode`                               |

No flat shortcuts. Each platform reads from the layer that owns the data
so the refresh cadence (REST poll vs MQTT push) is explicit.

## Refresh + lifecycle

```diff
-manager.update_players_status()
-manager.connect_to_events(callback)
+await client.refresh()
+await client.connect_events(player_ids, on_update=cb, on_disconnect=cb)
```

MQTT auto-reconnects with exponential backoff. `on_disconnect(err)`
fires on each drop with the underlying exception. Both callbacks may be
sync or async.

## Settings

```diff
-manager.set_player_config(device_id, day_time="07:30")
-manager.set_max_volume(device_id, 8, mode="day")
+import datetime
+await client.set_player_config(
+    device_id,
+    day_time=datetime.time(7, 30),     # was str
+    day_max_volume_limit=8,            # was str
+    day_ambient_colour="#40bfd9",
+    repeat_all=True,
+)
```

`PlayerConfig` is properly typed: `datetime.time`, `int`, `bool`.
Brightness is split into a `_auto: bool` + `: int` pair (mutually
exclusive in a single call).

## Alarms

```diff
-manager.set_alarm(device_id, alarm)            # silently wiped others
+await client.set_alarms(device_id, alarms=[...])
+await client.set_alarm_enabled(device_id, index=0, enabled=False)
```

`set_alarms` requires the full list (Yoto's `PUT /config` interprets it
as a replacement). `set_alarm_enabled` does the read-modify-write so
you can toggle one without re-sending the others.

## Account ID

```diff
-manager.update_family()
-account_id = manager.family.familyId
+from yoto_api import get_account_id
+account_id = get_account_id(client.token.access_token)
```

Decodes the Auth0 `sub` claim. No API call. The `Family` dataclass and
`/user/family` endpoint are gone.

## Errors

```diff
-from yoto_api import AuthenticationError
-try:
-    manager.update_players_status()
-except requests.RequestException:
-    ...
+from yoto_api import YotoError, AuthenticationError, YotoAPIError, YotoMQTTError
+try:
+    await client.refresh()
+except AuthenticationError:        # 401, token expired
+    ...
+except YotoAPIError as err:        # err.status_code on 4xx/5xx
+    ...
+except YotoMQTTError:
+    ...
+except YotoError:
+    ...
```

Transport errors from `aiohttp` / `aiomqtt` are wrapped into
`YotoAPIError` / `YotoMQTTError` (chained via `__cause__`).

## OAuth scope

3.0 no longer needs `family:device-status:view`. When `/status` returns
403, the lib transparently reads `device.status` from `/config`.

## Unchanged

- `Card`, `Chapter`, `Track` (library browsing).
- `Token`.
- Constants in `yoto_api.const`.
