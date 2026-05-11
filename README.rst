Introduction
============

This is a Python wrapper for the Yoto API. It allows you to control your
Yoto players, refresh your card library, and react to live playback
events from the player.

You need a client ID to use this API. Get one from
https://yoto.dev/get-started/start-here/.

Credit
======

A big thank you to @buzzeddesign for helping to sniff some of the API
and make sense of it. Thank you to @fuatakgun for the original v2.x
architecture which was based on kia_uvo.

Quick start
===========

Authenticate via the device-code flow, list your players, and start
listening to live MQTT events::

    import logging
    import time
    from yoto_api import YotoClient

    logging.basicConfig(level=logging.DEBUG)

    client = YotoClient(client_id="your_client_id")

    # Device-code flow: present the verification URL to the user, then
    # poll until they complete it in their browser.
    auth = client.device_code_flow_start()
    print(auth["verification_uri_complete"])
    client.device_code_flow_complete(auth)

    # Save the refresh token for next time so you don't redo device-code.
    refresh_token = client.token.refresh_token

    # Pull the device list + per-player config (mac, firmware, alarms).
    client.refresh()
    for player_id, player in client.players.items():
        print(player_id, player.name, player.model)

    # Subscribe to MQTT for live state. on_update fires on each message.
    def on_update(player):
        print(player.id, player.last_event.playback_status, player.status.battery_level_percentage)

    client.connect_events(list(client.players), on_update=on_update)

    # Send a command (MQTT direct, low-latency).
    client.pause(next(iter(client.players)))

    time.sleep(60)
    client.disconnect_events()

If you already have a refresh token::

    client = YotoClient(client_id="your_client_id")
    client.set_refresh_token(refresh_token)
    client.check_and_refresh_token()
    client.refresh()

Or, if your consumer manages OAuth tokens externally (e.g. the Home
Assistant core integration), construct without a client_id and assign
the token directly::

    from yoto_api import YotoClient, Token
    client = YotoClient()  # client_id not required
    client.token = Token(access_token=..., refresh_token=..., ...)

Data model
==========

`YotoPlayer` aggregates four typed sub-objects, one per data source:

- ``player.device`` (``Device``): immutable identity (id, name, family,
  generation, etc.) from ``GET /devices/mine``.
- ``player.info`` (``PlayerInfo``): settings, mac, firmware from
  ``GET /config``. User-editable via ``set_player_config(...)``.
- ``player.status`` (``PlayerStatus``): runtime telemetry (battery,
  wifi, charging, online, etc.) updated by REST polling and MQTT push.
- ``player.last_event`` (``PlaybackEvent``): live playback state pushed
  on MQTT ``data/events`` (track, position, volume, sleep timer).

All four are always present (default-initialised); the per-source
``*_refreshed_at`` / ``last_event_received_at`` timestamps tell you
whether data has actually been received.

Common methods
==============

Refresh / setup::

    client.update_player_list()    # GET /devices/mine, identity + online
    client.update_player_info(id)  # GET /config, settings + mac + firmware
    client.update_library()        # GET /card/family/library
    client.refresh()               # convenience: list + all info

MQTT lifecycle::

    client.connect_events(player_ids, on_update=cb, on_disconnect=cb)
    client.is_mqtt_connected
    client.reconnect_events()
    client.disconnect_events()

Player commands (MQTT, ~50 ms)::

    client.play_card(player_id, "card_id", chapter_key="01", track_key="01")
    client.pause(player_id)
    client.resume(player_id)
    client.stop(player_id)
    client.set_volume(player_id, 50)        # 0-100 percentage
    client.set_sleep_timer(player_id, 600)  # seconds
    client.set_ambients(player_id, 255, 0, 0)  # RGB
    client.next_track(player_id)
    client.previous_track(player_id)
    client.seek(player_id, position=30)

Settings writes (REST PUT)::

    import datetime
    client.set_player_config(
        player_id,
        day_time=datetime.time(7, 30),
        night_max_volume_limit=8,
        day_ambient_colour="#40bfd9",
        repeat_all=True,
        day_display_brightness_auto=True,
        # or: day_display_brightness=80
    )
    client.set_alarms(player_id, alarms=[...])  # full list, replaces existing
    client.set_alarm_enabled(player_id, index=0, enabled=False)

Account identifier (no API call)::

    from yoto_api import get_account_id
    account_id = get_account_id(client.token.access_token)

Errors
======

All library failures raise a subclass of ``YotoError``::

    from yoto_api import YotoError, AuthenticationError, YotoAPIError, YotoMQTTError

    try:
        client.refresh()
    except AuthenticationError:
        ...  # token expired or invalid
    except YotoAPIError as err:
        ...  # transport / HTTP / parsing failure (err.status_code on 4xx/5xx)
    except YotoMQTTError:
        ...  # paho / MQTT failure
    except YotoError:
        ...  # catch-all

Migration from 2.x
==================

See ``MIGRATION_3.md`` for the full guide. Short version: ``YotoManager``
is replaced by ``YotoClient``, and ``YotoPlayer`` no longer has flat
fields (use ``player.device``, ``player.info``, ``player.status``,
``player.last_event``).

Development
===========

Install dependencies::

    pip install -r requirements.txt
    pip install -r requirements_dev.txt

Run tests (no credentials needed; pure unit tests)::

    python -m pytest tests/

Other notes
===========

This project is not associated or affiliated with Yoto Play in any way.
