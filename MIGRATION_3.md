# Migrating from yoto-api 2.x to 3.0

3.0 is a full rewrite. This guide covers the consumer-facing changes
you need to make.

## TL;DR

- Replace `YotoManager` with `YotoClient`.
- `YotoPlayer` no longer has flat fields. Read from `player.device`,
  `player.info`, `player.status`, `player.last_event` depending on the
  data source.
- Most config setters are unified into a single
  `client.set_player_config(device_id, **fields)`.
- `set_alarm` is removed; use `set_alarms` (full list) or
  `set_alarm_enabled` (toggle one).
- `Family` and the `update_family` flow are gone. Use `get_account_id`
  to derive a stable per-account identifier from the access token.
- The library no longer requires the `family:device-status:view` OAuth
  scope.

## Imports

```diff
-from yoto_api import YotoManager, YotoAPI, YotoMQTTClient
+from yoto_api import YotoClient
```

`YotoAPI` and `YotoMQTTClient` are gone (consolidated inside
`YotoClient`). All exceptions still importable from `yoto_api`.

## Construction

```diff
-manager = YotoManager(client_id="...")
+client = YotoClient(client_id="...")
+
+# Or, if you manage tokens externally (e.g. HA core OAuth):
+client = YotoClient()
+client.token = Token(access_token=..., refresh_token=..., ...)
```

## Reading player data

The flat `YotoPlayer` is split by source. Same data, more honest about
where it comes from.

| 2.x access            | 3.0 access                                 | Source        |
|-----------------------|--------------------------------------------|---------------|
| `player.id`           | `player.id` (still works as a property)    | identity      |
| `player.name`         | `player.name` (property)                   | identity      |
| `player.online`       | `player.status.is_online`                  | REST + MQTT   |
| `player.firmware_version` | `player.info.firmware_version`         | REST `/config`|
| `player.device_type`  | `player.device.device_type`                | identity      |
| `player.battery_level_percentage` | `player.status.battery_level_percentage` | REST + MQTT |
| `player.charging`     | `player.status.is_charging`                | REST + MQTT   |
| `player.is_playing`   | `player.last_event.playback_status == PlaybackStatus.PLAYING` | MQTT |
| `player.volume`       | `player.last_event.volume` (raw 0-16)      | MQTT          |
| `player.system_volume`| `player.status.system_volume_percentage` (0-100) | REST + MQTT |
| `player.track_position` | `player.last_event.position`             | MQTT          |
| `player.track_title`  | `player.last_event.track_title`            | MQTT          |
| `player.chapter_title`| `player.last_event.chapter_title`          | MQTT          |
| `player.card_id`      | `player.last_event.card_id`                | MQTT          |
| `player.config.alarms`| `player.info.config.alarms`                | REST `/config`|
| `player.night_light_mode` | `player.status.nightlight_mode`        | REST + MQTT (occasionally) |

The `player.X` shortcuts you used to use for telemetry (battery,
charging, etc.) are intentionally not added back: each platform should
read from the layer that owns the data, so it's clear which refresh
cadence applies (REST poll vs MQTT push vs `/devices/mine` rediscovery).

## Refresh + lifecycle

```diff
-manager.update_players_status()
-manager.connect_to_events(callback)
+client.refresh()                              # /devices/mine + /config for all
+client.connect_events(
+    list(client.players),
+    on_update=on_update,                      # called per-message
+    on_disconnect=on_disconnect,              # for watchdog/reconnect
+)
+# ...
+if not client.is_mqtt_connected:
+    client.reconnect_events()
```

`update_players_status` is removed. Equivalent in 3.0 is
`client.refresh()` (REST) plus `client.connect_events(...)` (MQTT).

## Settings

Most `set_*_config` getters/setters consolidate into one method:

```diff
-manager.set_player_config(device_id, day_time="07:30")
-manager.set_max_volume(device_id, 8, mode="day")
+import datetime
+client.set_player_config(
+    device_id,
+    day_time=datetime.time(7, 30),     # was str "07:30"
+    day_max_volume_limit=8,            # was str "8"
+    day_ambient_colour="#40bfd9",
+    repeat_all=True,
+)
```

`PlayerConfig` is now properly typed. Time fields are `datetime.time`,
volume/brightness limits are `int`, booleans are `bool`. The brightness
field is split into a `_auto: bool` + `: int` pair (mutually exclusive
in a single call).

## Alarms

```diff
-manager.set_alarm(device_id, alarm)            # silently wiped other alarms
+client.set_alarms(device_id, alarms=[...])     # full list, replaces existing
+client.set_alarm_enabled(device_id, index=0, enabled=False)  # toggle one
```

`set_alarm` is removed because it overwrote the entire alarm list with
a single entry. `set_alarms` makes that semantics explicit; use
`set_alarm_enabled` for the common "toggle one without losing the
others" case (it does the read-modify-write automatically).

## Account identifier

If you used `manager.update_family()` followed by `manager.family.familyId`
to identify a config entry, switch to:

```python
from yoto_api import get_account_id
account_id = get_account_id(client.token.access_token)
```

This decodes the Auth0 `sub` claim from the JWT, no API call required.
The `/user/family` endpoint and `Family` dataclass are gone.

## Errors

```diff
-from yoto_api import AuthenticationError
-try:
-    manager.update_players_status()
-except requests.RequestException as err:
-    ...
-except AuthenticationError:
-    ...
+from yoto_api import YotoError, AuthenticationError, YotoAPIError, YotoMQTTError
+try:
+    client.refresh()
+except AuthenticationError:
+    ...                          # 401, token expired
+except YotoAPIError as err:
+    if err.status_code == 403:
+        ...                      # missing scope
+    ...                          # other transport / parsing failure
+except YotoMQTTError:
+    ...                          # paho / MQTT failure
+except YotoError:
+    ...                          # catch-all
```

`requests.RequestException` is no longer raised by the library; all
transport failures are wrapped in `YotoAPIError` (chained via
`__cause__`).

## OAuth scope

If your consumer doesn't have `family:device-status:view`, 3.0 handles
that transparently. Telemetry that was previously unreachable (battery,
wifi, charging, temperature) is read from the `device.status` sub-block
of `GET /config` instead. No code change required on your side.

## Things that didn't change

- `Card`, `Chapter`, `Track` (library browsing) keep the same shape.
- `Token` keeps the same shape.
- The constants in `yoto_api.const` (`HEX_COLORS`, `LIGHT_COLORS`, etc.)
  are still exported.
