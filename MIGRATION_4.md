# Migrating from yoto-api 3.x to 4.0

4.0 splits the player status by source. `player.status` used to be written
from MQTT, the REST `/config` shadow and presence all at once, so you couldn't
tell where a value came from or how fresh it was. It's now two objects, each
with a single writer, and online state moves onto the player.

## TL;DR

- `player.status` keeps only the basic live fields from MQTT `data/status`.
- The richer fields (network, disk, uptime, power source, detailed battery)
  move to `player.extended_status`, fed by MQTT `status/full` or the REST
  `/config` shadow.
- `player.status.is_online` → `player.is_online` (root level, instant, from
  MQTT presence).
- `client.update_player_status()` → `client.update_player_extended_status()`
  (REST) or `client.request_player_extended_status()` (MQTT).
- `client.request_status_push()` → `client.request_player_status()`.
- `device_id` removed from `PlayerStatus` and `PlayerInfo`. Use `player.id`.
- The REST `/status` endpoint is gone.

## Online state

```diff
-player.status.is_online
+player.is_online
```

It's now a root-level field on `YotoPlayer`, written by the MQTT `presence`
channel (and REST list/config). The player flips online the moment it connects
and offline the moment it drops, instead of waiting for a REST poll. A new
`PresenceEvent` is delivered to your `on_update` callback on each transition.

For entity availability, read `player.is_online` directly. It starts as `None`
until the first signal arrives.

## Status split

The basic fields stay on `player.status`. The rest move to
`player.extended_status` (a `PlayerExtendedStatus`, which subclasses
`PlayerStatus`, so the shared fields aren't duplicated and
`isinstance(ext, PlayerStatus)` still holds).

| 3.x                                            | 4.0                                                       |
| ---------------------------------------------- | --------------------------------------------------------- |
| `player.status.network_ssid`                   | `player.extended_status.network_ssid`                     |
| `player.status.wifi_strength`                  | `player.extended_status.wifi_strength`                    |
| `player.status.power_source`                   | `player.extended_status.power_source`                     |
| `player.status.battery_temperature`           | `player.extended_status.battery_temperature`              |
| `player.status.total_disk_space_bytes`         | `player.extended_status.total_disk_space_bytes`           |
| `player.status.uptime`                         | `player.extended_status.uptime`                           |
| `player.status.utc_time`                       | `player.extended_status.utc_time`                         |
| `player.status.utc_offset_seconds`             | `player.extended_status.utc_offset_seconds`               |
| `player.status.temperature_celcius`            | `player.extended_status.temperature_celcius`              |
| `player.status.is_background_download_active`  | `player.extended_status.is_background_download_active`     |
| `player.status.average_download_speed_bytes_second` | `player.extended_status.average_download_speed_bytes_second` |

`battery_level_percentage`, `is_charging`, `free_disk_space_bytes`,
`active_card`, `card_insertion_state`, the volume fields, headphone/bluetooth
flags, `nightlight_mode`, `day_mode`, `ambient_light_sensor_reading` and
`current_display_brightness` stay on `player.status`.

`extended_status` also adds raw-battery fields not on the basic status:
`battery_level_raw`, `battery_voltage_mv`, `battery_profile`.

## Refresh methods

```diff
-await client.update_player_status(device_id)   # REST, returned PlayerStatus
+await client.update_player_extended_status(device_id)   # REST /config shadow
+await client.request_player_extended_status(device_id)  # MQTT status/full
```

```diff
-await client.request_status_push(device_id)
+await client.request_player_status(device_id)
```

Two prefixes, two transports:

- `update_player_*` (REST): a one-shot snapshot, returned and stored.
- `request_player_*` (MQTT): asks the device to push fresh data, which arrives
  on your `on_update` callback (connect with `connect_events` first).

| What you want            | MQTT (live)                          | REST (snapshot)                       |
| ------------------------ | ------------------------------------ | ------------------------------------- |
| `player.status`          | `request_player_status(id)`          | not available                         |
| `player.extended_status` | `request_player_extended_status(id)` | `update_player_extended_status(id)`   |

Prefer MQTT for live values. The REST shadow can lag and carries no
device-side timestamp, so it's a fallback for cold start or while the device
is offline, and it won't overwrite fresher live data.

## Timestamps

```diff
-player.status_refreshed_at
+player.status.updated_at          # basic telemetry
+player.extended_status.updated_at # extended telemetry
+player.online_refreshed_at        # when is_online last changed
```

`updated_at` is when the telemetry was current device-side (the device clock
on `status/full`, the shadow's `updatedAt`, or receive time for `data/status`
which carries none). Gate on it if you care about freshness.

## Identity

```diff
-player.status.device_id
-player.info.device_id
+player.id                  # == player.device.device_id
```

Identity lives on `player.device` only. `PlayerStatus` and `PlayerInfo` no
longer carry it.

## Removed: REST /status

The documented `/device-v2/{id}/status` endpoint is gone, along with the
`endpoints.device_status()` helper. Yoto is dropping access to it, and the
same firmware fields are already in `/config.device.status` (the shadow), which
is what `update_player_extended_status` reads. The `family:device-status:view`
scope is no longer used anywhere.

## Unchanged

- `Card`, `Chapter`, `Track`, `Group` (library browsing).
- `player.last_event` (`PlaybackEvent`) and the playback fields on it.
- `player.info` settings and `player.info.config`.
- `Token`, errors, and the MQTT lifecycle (`connect_events`, subscribe/
  unsubscribe, reconnect).
