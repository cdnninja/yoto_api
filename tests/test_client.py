"""YotoClient façade behaviour: command dispatch, refresh tolerance,
MQTT lifecycle, dynamic subscribe, settings + alarms writes, online
state consolidation."""

import datetime
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytz

from yoto_api import YotoError
from yoto_api import (
    Alarm,
    Device,
    EventPatch,
    PlaybackStatus,
    PresenceEvent,
    StatusPatch,
    Token,
    YotoClient,
    YotoPlayer,
)
from yoto_api.models.info import PlayerInfo
from yoto_api.mqtt.parser import parse_message

from .conftest import fresh_token


class _ClientTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class: cleans up the aiohttp session on teardown."""

    async def asyncTearDown(self) -> None:
        for client in getattr(self, "_clients", []):
            # Tests mock `_mqtt` with plain MagicMock; null it before
            # close() so we don't try to await `mock.disconnect()`.
            client._mqtt = None
            await client.close()

    def make_client(self) -> YotoClient:
        """Create a YotoClient and track it for teardown."""
        client = YotoClient()
        self._clients = getattr(self, "_clients", []) + [client]
        return client


class PlayCardKwargsOnlyTests(_ClientTestCase):
    """Optional args on play_card are kwargs-only — they're easy to mix
    up positionally and the failure mode is silent (wrong track plays)."""

    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        self.client._mqtt = MagicMock()
        self.client._mqtt.card_play = AsyncMock()
        self.client._mqtt.card_pause = AsyncMock()

    async def test_positional_optional_args_raise(self) -> None:
        with self.assertRaises(TypeError):
            await self.client.play_card("dev1", "card1", 5)

    async def test_kwargs_work(self) -> None:
        await self.client.play_card("dev1", "card1", chapter_key="01", track_key="02")
        self.client._mqtt.card_play.assert_awaited_once_with(
            "dev1",
            "card1",
            seconds_in=None,
            cutoff=None,
            chapter_key="01",
            track_key="02",
        )

    async def test_command_without_mqtt_raises(self) -> None:
        client = self.make_client()
        with self.assertRaises(YotoError):
            await client.pause("dev1")


class UpdateAllPlayerInfoToleranceTests(_ClientTestCase):
    """One offline device must not block the rest of the refresh."""

    async def test_per_player_failure_is_logged_and_skipped(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        client.players["good"] = YotoPlayer(device=Device(device_id="good", name="ok"))
        client.players["bad"] = YotoPlayer(device=Device(device_id="bad", name="bad"))
        client.players["also_good"] = YotoPlayer(
            device=Device(device_id="also_good", name="ok2")
        )

        async def fake_get_player_info(token, device_id):
            if device_id == "bad":
                raise YotoError("boom")
            return PlayerInfo(), True

        client._rest.get_player_info = fake_get_player_info

        await client.update_all_player_info()

        # info is always present (default-empty); the signal is the
        # refreshed_at timestamp.
        self.assertIsNotNone(client.players["good"].info_refreshed_at)
        self.assertIsNone(client.players["bad"].info_refreshed_at)
        self.assertIsNotNone(client.players["also_good"].info_refreshed_at)


class MqttSurfaceTests(_ClientTestCase):
    async def test_is_mqtt_connected_false_without_mqtt(self) -> None:
        client = self.make_client()
        self.assertFalse(client.is_mqtt_connected)

    async def test_is_mqtt_connected_delegates_to_underlying(self) -> None:
        client = self.make_client()
        client._mqtt = MagicMock()
        client._mqtt.is_connected = True
        self.assertTrue(client.is_mqtt_connected)
        client._mqtt.is_connected = False
        self.assertFalse(client.is_mqtt_connected)

    async def test_reconnect_preserves_player_list_and_callbacks(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        update_cb = MagicMock()
        disconnect_cb = MagicMock()
        connect_calls: list[tuple] = []

        async def fake_connect(token, ids, callback, on_disconnect=None):
            connect_calls.append((list(ids), callback, on_disconnect))

        with patch("yoto_api.client.YotoMqttClient") as MqttClass:
            instance = MagicMock()
            instance.connect = AsyncMock(side_effect=fake_connect)
            instance.disconnect = AsyncMock()
            MqttClass.return_value = instance

            await client.connect_events(
                ["a", "b", "c"],
                on_update=update_cb,
                on_disconnect=disconnect_cb,
            )
            await client.reconnect_events()

        self.assertEqual(len(connect_calls), 2)
        self.assertEqual(connect_calls[0][0], ["a", "b", "c"])
        self.assertEqual(connect_calls[1][0], ["a", "b", "c"])
        self.assertIs(connect_calls[1][2], disconnect_cb)


class UpdatePlayerListDoesNotTouchMqttTests(_ClientTestCase):
    """Regression guard: update_player_list manages `self.players` only,
    never the MQTT subscription set."""

    async def test_no_auto_subscribe_on_new_device(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        client._mqtt = MagicMock()
        client._mqtt.add_player = AsyncMock()
        client._mqtt.remove_player = AsyncMock()
        client._rest.list_devices = AsyncMock(
            return_value=[(Device(device_id="new", name="New"), True)]
        )

        await client.update_player_list()

        client._mqtt.add_player.assert_not_awaited()
        client._mqtt.remove_player.assert_not_awaited()
        self.assertIn("new", client.players)


class SetPlayerConfigTests(_ClientTestCase):
    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        self.client.token = fresh_token()
        self.client._rest.update_settings = AsyncMock()

    async def test_drops_none_values(self) -> None:
        await self.client.set_player_config(
            "dev1",
            day_time=datetime.time(7, 30),
            night_time=None,
            repeat_all=True,
        )
        self.client._rest.update_settings.assert_awaited_once_with(
            self.client.token,
            "dev1",
            {"dayTime": "07:30", "repeatAll": True},
        )

    async def test_maps_snake_to_camel_with_yoto_quirks(self) -> None:
        # day_ambient_colour and day_max_volume_limit map to non-day-prefixed
        # API keys (Yoto treats them as the defaults).
        await self.client.set_player_config(
            "dev1",
            day_ambient_colour="#40bfd9",
            day_max_volume_limit=8,
            night_ambient_colour="#f57399",
            night_max_volume_limit=16,
        )
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["ambientColour"], "#40bfd9")
        self.assertEqual(payload["maxVolumeLimit"], "8")
        self.assertEqual(payload["nightAmbientColour"], "#f57399")
        self.assertEqual(payload["nightMaxVolumeLimit"], "16")

    async def test_unknown_field_raises(self) -> None:
        with self.assertRaises(YotoError):
            await self.client.set_player_config("dev1", made_up_field="x")

    async def test_alarms_kwarg_rejected(self) -> None:
        with self.assertRaises(YotoError):
            await self.client.set_player_config("dev1", alarms=[])

    async def test_empty_call_is_noop(self) -> None:
        await self.client.set_player_config("dev1")
        self.client._rest.update_settings.assert_not_awaited()

    async def test_serializes_time_to_hhmm(self) -> None:
        await self.client.set_player_config(
            "dev1",
            day_time=datetime.time(6, 5),
            night_time=datetime.time(19, 0),
        )
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["dayTime"], "06:05")
        self.assertEqual(payload["nightTime"], "19:00")

    async def test_serializes_int_fields_as_strings(self) -> None:
        await self.client.set_player_config(
            "dev1",
            day_max_volume_limit=8,
            shutdown_timeout=3600,
            display_dim_timeout=60,
            hour_format=24,
        )
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["maxVolumeLimit"], "8")
        self.assertEqual(payload["shutdownTimeout"], "3600")
        self.assertEqual(payload["displayDimTimeout"], "60")
        self.assertEqual(payload["hourFormat"], "24")

    async def test_serializes_bool_to_01_string(self) -> None:
        await self.client.set_player_config(
            "dev1",
            day_sounds_off=True,
            bluetooth_enabled=False,
        )
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["daySoundsOff"], "1")
        self.assertEqual(payload["bluetoothEnabled"], "0")

    async def test_brightness_auto_sends_auto_string(self) -> None:
        await self.client.set_player_config("dev1", day_display_brightness_auto=True)
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["dayDisplayBrightness"], "auto")

    async def test_brightness_value_sends_stringified_int(self) -> None:
        await self.client.set_player_config("dev1", night_display_brightness=80)
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(payload["nightDisplayBrightness"], "80")

    async def test_brightness_auto_and_value_are_mutually_exclusive(self) -> None:
        with self.assertRaises(YotoError):
            await self.client.set_player_config(
                "dev1",
                day_display_brightness_auto=True,
                day_display_brightness=80,
            )

    async def test_brightness_auto_false_alone_is_noop(self) -> None:
        # Setting auto=False without a value would mean "leave manual mode
        # but don't change the value" — Yoto can't express that, so the
        # lib drops it silently. The consumer has to pass a value to set
        # manual mode.
        await self.client.set_player_config("dev1", day_display_brightness_auto=False)
        self.client._rest.update_settings.assert_not_awaited()

    async def test_serialize_int_rejects_string(self) -> None:
        # Make sure we don't accidentally accept str inputs for int fields.
        with self.assertRaises(YotoError):
            await self.client.set_player_config("dev1", day_max_volume_limit="8")


class SetAlarmsTests(_ClientTestCase):
    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        self.client.token = fresh_token()
        self.client._rest.update_settings = AsyncMock()

    async def test_sends_full_alarm_list_encoded(self) -> None:
        alarms = [
            Alarm(
                days_enabled="1111100",
                time=datetime.time(7, 30),
                sound_id="s1",
                volume=8,
                enabled=True,
            ),
            Alarm(
                days_enabled="0000011",
                time=datetime.time(9, 0),
                sound_id="s2",
                volume=4,
                enabled=False,
            ),
        ]
        await self.client.set_alarms("dev1", alarms)
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(
            payload["alarms"],
            [
                "1111100,07:30,s1,,,8,1",
                "0000011,09:00,s2,,,4,0",
            ],
        )

    async def test_writes_through_to_local_state(self) -> None:
        device = Device(device_id="dev1", name="A")
        # info is auto-created empty by __post_init__; we just need a
        # player object to write through.
        self.client.players["dev1"] = YotoPlayer(device=device)
        new_alarms = [
            Alarm(
                days_enabled="1111111",
                time=datetime.time(6, 0),
                sound_id="s",
                volume=5,
                enabled=True,
            )
        ]
        await self.client.set_alarms("dev1", new_alarms)
        self.assertEqual(
            self.client.players["dev1"].info.config.alarms,
            new_alarms,
        )


class SetAlarmEnabledTests(_ClientTestCase):
    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        self.client.token = fresh_token()
        self.client._rest.update_settings = AsyncMock()
        device = Device(device_id="dev1", name="A")
        player = YotoPlayer(device=device)
        player.info.config.alarms = [
            Alarm(
                days_enabled="1111100",
                time=datetime.time(7, 30),
                sound_id="s1",
                volume=8,
                enabled=True,
            ),
            Alarm(
                days_enabled="0000011",
                time=datetime.time(9, 0),
                sound_id="s2",
                volume=4,
                enabled=True,
            ),
        ]
        # The lib gates on info_refreshed_at, so simulate update_player_info
        # having actually run.
        player.info_refreshed_at = datetime.datetime.now(pytz.utc)
        self.client.players["dev1"] = player

    async def test_toggles_only_target_index(self) -> None:
        await self.client.set_alarm_enabled("dev1", 1, False)
        payload = self.client._rest.update_settings.call_args.args[2]
        self.assertEqual(
            payload["alarms"],
            [
                "1111100,07:30,s1,,,8,1",
                "0000011,09:00,s2,,,4,0",
            ],
        )

    async def test_requires_info_loaded(self) -> None:
        device = Device(device_id="dev2", name="B")
        # info is auto-created empty, but info_refreshed_at stays None
        # until update_player_info has run.
        self.client.players["dev2"] = YotoPlayer(device=device)
        with self.assertRaises(YotoError):
            await self.client.set_alarm_enabled("dev2", 0, False)

    async def test_invalid_index_raises(self) -> None:
        with self.assertRaises(YotoError):
            await self.client.set_alarm_enabled("dev1", 5, False)


class RefreshTests(_ClientTestCase):
    async def test_chains_list_then_info(self) -> None:
        client = self.make_client()
        order: list[str] = []

        async def fake_list():
            order.append("list")

        async def fake_info():
            order.append("info")

        client.update_player_list = fake_list
        client.update_all_player_info = fake_info
        await client.refresh()
        self.assertEqual(order, ["list", "info"])


class CheckAndRefreshTokenTests(_ClientTestCase):
    """Two ownership models, gated on whether a client_id was passed:
    self-managed auth refreshes here; consumer-managed auth (e.g. HA's
    OAuth2Session) syncs the token in and must not be self-refreshed."""

    def make_client_with_id(self) -> YotoClient:
        client = YotoClient(client_id="cid")
        self._clients = getattr(self, "_clients", []) + [client]
        return client

    def near_expiry_token(self) -> Token:
        # Inside the 1h self-refresh window but not actually expired.
        return Token(
            access_token="access",
            refresh_token="refresh",
            token_type="Bearer",
            valid_until=datetime.datetime.now(pytz.utc) + datetime.timedelta(minutes=5),
        )

    async def test_no_client_id_trusts_token(self) -> None:
        # Consumer-managed auth: a near-expiry token is returned as-is and
        # refresh is never attempted — there's no client_id to refresh with.
        client = self.make_client()  # YotoClient() -> client_id None
        client._auth.refresh = AsyncMock()
        token = self.near_expiry_token()
        client.token = token
        result = await client.check_and_refresh_token()
        self.assertIs(result, token)
        client._auth.refresh.assert_not_awaited()

    async def test_no_client_id_missing_access_token_raises(self) -> None:
        client = self.make_client()
        client.set_refresh_token("refresh")  # access_token stays None
        with self.assertRaises(YotoError):
            await client.check_and_refresh_token()

    async def test_client_id_refreshes_near_expiry(self) -> None:
        client = self.make_client_with_id()
        client._auth.refresh = AsyncMock(return_value=fresh_token())
        client.token = self.near_expiry_token()
        await client.check_and_refresh_token()
        client._auth.refresh.assert_awaited_once()

    async def test_client_id_skips_when_fresh(self) -> None:
        client = self.make_client_with_id()
        client._auth.refresh = AsyncMock()
        client.token = fresh_token()
        await client.check_and_refresh_token()
        client._auth.refresh.assert_not_awaited()


class StatusFromConfigTests(_ClientTestCase):
    """`get_player_status` reads the device.status sub-block from /config —
    no scoped /status endpoint, no fallback dance. /config.device.status
    carries the same firmware status block (incl. statusVersion-3 battery
    extras) and works for offline devices via the shadow."""

    async def test_reads_config_device_status(self) -> None:
        from yoto_api.models.status import PlayerExtendedStatus
        from yoto_api.rest.client import RestClient

        rest = RestClient(session=MagicMock())
        calls: list[str] = []

        async def fake_get(token, path, what, **_):
            calls.append(path)
            return {
                "device": {
                    "online": True,
                    "status": {
                        "batteryLevel": 42,
                        "batteryLevelRaw": 38,
                        "battery": 3650,
                        "batteryProfile": "LJDX30X-4500",
                        "wifiStrength": -55,
                    },
                },
            }

        rest._get = fake_get
        result, online = await rest.get_player_status(fresh_token(), "dev1")

        self.assertIsInstance(result, PlayerExtendedStatus)
        self.assertEqual(result.battery_level_percentage, 42)
        self.assertEqual(result.battery_level_raw, 38)
        self.assertEqual(result.battery_voltage_mv, 3650)
        self.assertEqual(result.battery_profile, "LJDX30X-4500")
        self.assertEqual(result.wifi_strength, -55)
        self.assertTrue(online)  # carried from device.online, split out
        # Exactly one call, to /config — never /status.
        self.assertEqual(len(calls), 1)
        self.assertIn("/config", calls[0])
        self.assertFalse(calls[0].endswith("/status"))

    async def test_offline_keeps_last_known_battery(self) -> None:
        from yoto_api.rest.client import RestClient

        rest = RestClient(session=MagicMock())

        async def fake_get(token, path, what, **_):
            # Offline shadow: online False, battery still present (last seen).
            return {"device": {"online": False, "status": {"batteryLevel": 100}}}

        rest._get = fake_get
        result, online = await rest.get_player_status(fresh_token(), "dev1")
        self.assertFalse(online)
        self.assertEqual(result.battery_level_percentage, 100)


class OnlineConsolidationTests(_ClientTestCase):
    """`YotoPlayer.is_online` (root) is the single connection-state field.
    Writers: REST list/config, MQTT presence, and live-message presence proof."""

    async def test_rest_devices_mine_sets_online(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        device = Device(device_id="d1", name="x")
        client._rest.list_devices = AsyncMock(return_value=[(device, True)])
        await client.update_player_list()
        self.assertTrue(client.players["d1"].is_online)

    async def test_rest_devices_mine_can_set_offline(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        device = Device(device_id="d1", name="x")
        client._rest.list_devices = AsyncMock(return_value=[(device, False)])
        await client.update_player_list()
        self.assertFalse(client.players["d1"].is_online)

    async def test_mqtt_message_flips_to_online(self) -> None:
        client = self.make_client()
        device = Device(device_id="d1", name="x")
        player = YotoPlayer(device=device)
        client.players["d1"] = player
        # Simulate REST having seen offline
        client._set_online(player, False)
        self.assertFalse(player.is_online)
        # An MQTT StatusPatch arrives — presence proof
        await client._on_mqtt_message(StatusPatch(player_id="d1", fields={}))
        self.assertTrue(player.is_online)

    async def test_presence_offline_sets_offline_without_blanking_battery(
        self,
    ) -> None:
        # The presence topic is the authoritative offline signal (broker
        # Last-Will). It must NOT count as presence proof, and must NOT
        # wipe the last-known battery.
        client = self.make_client()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        player.is_online = True
        player.status.battery_level_percentage = 73
        client.players["d1"] = player

        await client._on_mqtt_message(PresenceEvent(player_id="d1", is_online=False))

        self.assertFalse(player.is_online)
        self.assertEqual(player.status.battery_level_percentage, 73)

    async def test_presence_online_sets_online(self) -> None:
        client = self.make_client()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        client._set_online(player, False)
        client.players["d1"] = player

        await client._on_mqtt_message(PresenceEvent(player_id="d1", is_online=True))

        self.assertTrue(player.is_online)

    async def test_status_full_patch_routes_to_extended_status_and_marks_online(
        self,
    ) -> None:
        client = self.make_client()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        client._set_online(player, False)
        client.players["d1"] = player

        await client._on_mqtt_message(
            StatusPatch(
                player_id="d1",
                fields={"battery_voltage_mv": 3775, "battery_level_raw": 59},
                extended=True,
            )
        )
        self.assertTrue(player.is_online)
        # Battery extras land on extended_status, not the v1 status object.
        self.assertEqual(player.extended_status.battery_voltage_mv, 3775)
        self.assertEqual(player.extended_status.battery_level_raw, 59)


class PlaybackEventMergeTests(_ClientTestCase):
    """Yoto emits partial MQTT events; the lib applies each EventPatch onto
    last_event so a volume-only update doesn't wipe playback_status, while an
    explicit clear (cardId:"none") still empties the field."""

    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        device = Device(device_id="d1", name="Mini")
        self.player = YotoPlayer(device=device)
        self.client.players["d1"] = self.player

    async def test_first_event_is_stored_as_is(self) -> None:
        patch = EventPatch(
            player_id="d1",
            fields={"card_id": "abc", "playback_status": PlaybackStatus.PLAYING},
        )
        await self.client._on_mqtt_message(patch)
        self.assertEqual(self.player.last_event.card_id, "abc")
        self.assertEqual(
            self.player.last_event.playback_status,
            PlaybackStatus.PLAYING,
        )

    async def test_partial_event_keeps_omitted_fields(self) -> None:
        first = EventPatch(
            player_id="d1",
            fields={
                "card_id": "abc",
                "chapter_key": "01",
                "playback_status": PlaybackStatus.PLAYING,
                "volume": 8,
            },
        )
        await self.client._on_mqtt_message(first)
        # A volume-only update — must not wipe card_id or playback_status
        delta = EventPatch(player_id="d1", fields={"volume": 10})
        await self.client._on_mqtt_message(delta)
        self.assertEqual(self.player.last_event.volume, 10)
        self.assertEqual(self.player.last_event.card_id, "abc")
        self.assertEqual(self.player.last_event.chapter_key, "01")
        self.assertEqual(
            self.player.last_event.playback_status,
            PlaybackStatus.PLAYING,
        )

    async def test_unparsable_field_does_not_clobber(self) -> None:
        first = EventPatch(
            player_id="d1",
            fields={"playback_status": PlaybackStatus.PLAYING, "volume": 8},
        )
        await self.client._on_mqtt_message(first)
        # Unknown playbackStatus coerces to None; the key is present but must
        # not wipe the known status (only card_id treats None as a clear).
        patch = parse_message(
            "device/d1/data/events",
            json.dumps({"playbackStatus": "weird", "volume": 9}).encode(),
        )
        await self.client._on_mqtt_message(patch)
        self.assertEqual(self.player.last_event.playback_status, PlaybackStatus.PLAYING)
        self.assertEqual(self.player.last_event.volume, 9)

    async def test_stopped_clears_card_and_now_playing(self) -> None:
        playing = EventPatch(
            player_id="d1",
            fields={
                "card_id": "abc",
                "chapter_title": "Chapter",
                "track_title": "Track",
                "position": 42,
                "volume": 8,
                "playback_status": PlaybackStatus.PLAYING,
            },
        )
        await self.client._on_mqtt_message(playing)

        # A real stop sends cardId:"none" but leaves chapter/track/position
        # stale (or omits them). Clearing card_id must clear those too.
        stopped = parse_message(
            "device/d1/data/events",
            json.dumps({"cardId": "none", "playbackStatus": "stopped"}).encode(),
        )
        await self.client._on_mqtt_message(stopped)

        last = self.player.last_event
        self.assertEqual(last.playback_status, PlaybackStatus.STOPPED)
        self.assertIsNone(last.card_id)  # explicit "none" cleared it
        self.assertIsNone(last.chapter_title)  # card-scoped, cleared with card
        self.assertIsNone(last.track_title)
        self.assertIsNone(last.position)
        self.assertEqual(last.volume, 8)  # not card-scoped, kept

    async def test_empty_card_id_clears_like_none(self) -> None:
        await self.client._on_mqtt_message(
            EventPatch(player_id="d1", fields={"card_id": "abc", "chapter_title": "X"})
        )
        # "" is the device's other "no card" form, same as "none".
        await self.client._on_mqtt_message(
            EventPatch(player_id="d1", fields={"card_id": ""})
        )
        last = self.player.last_event
        self.assertIsNone(last.card_id)
        self.assertIsNone(last.chapter_title)


class OnlinePresenceOnEveryMqttMessageTests(_ClientTestCase):
    """Every MQTT message — event OR status patch — must mark the
    player online (presence proof)."""

    def _client_with_offline_player(self) -> tuple[YotoClient, YotoPlayer]:
        client = self.make_client()
        device = Device(device_id="d1", name="x")
        player = YotoPlayer(device=device)
        client.players["d1"] = player
        client._set_online(player, False)
        return client, player

    async def test_status_patch_marks_online(self) -> None:
        client, player = self._client_with_offline_player()
        await client._on_mqtt_message(StatusPatch(player_id="d1", fields={}))
        self.assertTrue(player.is_online)

    async def test_playback_event_marks_online(self) -> None:
        client, player = self._client_with_offline_player()
        await client._on_mqtt_message(EventPatch(player_id="d1", fields={"volume": 5}))
        self.assertTrue(player.is_online)


class UpdatePlayerStatusTests(_ClientTestCase):
    """update_player_extended_status reads the REST /config shadow into extended_status
    and sets is_online; it never touches the v1 status object."""

    async def test_feeds_extended_status_and_online(self) -> None:
        from yoto_api.models.status import PlayerExtendedStatus

        client = self.make_client()
        client.token = fresh_token()
        client.players["d1"] = YotoPlayer(device=Device(device_id="d1", name="x"))
        shadow = PlayerExtendedStatus(battery_level_percentage=42)
        client._rest.get_player_status = AsyncMock(return_value=(shadow, False))
        result = await client.update_player_extended_status("d1")
        self.assertIs(result, shadow)
        player = client.players["d1"]
        self.assertIs(player.extended_status, shadow)
        self.assertEqual(player.extended_status.battery_level_percentage, 42)
        self.assertFalse(player.is_online)
        # The v1 status object is untouched by the REST shadow read.
        self.assertIsNone(player.status.battery_level_percentage)

    async def test_live_mqtt_wins_while_online(self) -> None:
        from yoto_api.models.status import PlayerExtendedStatus

        client = self.make_client()
        client.token = fresh_token()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        # MQTT already pushed a live value; updated_at marks "MQTT has spoken".
        player.extended_status.battery_level_percentage = 80
        player.extended_status.updated_at = datetime.datetime.now(pytz.utc)
        client.players["d1"] = player
        # A REST shadow poll while the device is online must not clobber it —
        # the shadow lags live MQTT and carries no timestamp to arbitrate with.
        shadow = PlayerExtendedStatus(battery_level_percentage=50)
        client._rest.get_player_status = AsyncMock(return_value=(shadow, True))

        await client.update_player_extended_status("d1")

        self.assertEqual(player.extended_status.battery_level_percentage, 80)

    async def test_offline_shadow_takes_over_from_stale_live(self) -> None:
        from yoto_api.models.status import PlayerExtendedStatus

        client = self.make_client()
        client.token = fresh_token()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        # MQTT spoke while the device was online, then the device dropped.
        player.extended_status.battery_level_percentage = 80
        player.extended_status.updated_at = datetime.datetime.now(pytz.utc)
        client.players["d1"] = player
        # Now offline: the shadow is the only source left and must take over,
        # even though MQTT had populated extended_status earlier. (The shadow
        # carries no updated_at, so a timestamp gate would wrongly drop it.)
        shadow = PlayerExtendedStatus(battery_level_percentage=55)
        client._rest.get_player_status = AsyncMock(return_value=(shadow, False))

        await client.update_player_extended_status("d1")

        self.assertIs(player.extended_status, shadow)
        self.assertEqual(player.extended_status.battery_level_percentage, 55)
        self.assertFalse(player.is_online)


class UpdateGroupsTests(_ClientTestCase):
    """update_groups maps the /library/groups array into self.groups,
    pulling card IDs from `items`, and drops groups deleted upstream."""

    def _make_client(self, groups_payload: list) -> YotoClient:
        client = self.make_client()
        client.token = fresh_token()
        client._rest.get_card_groups = AsyncMock(return_value=groups_payload)
        return client

    async def test_maps_fields_and_card_ids(self) -> None:
        client = self._make_client(
            [
                {
                    "id": "g1",
                    "name": "Bedtime",
                    "familyId": "fam1",
                    "imageId": "img1",
                    "imageUrl": "https://example/img.png",
                    "createdAt": "2024-01-02T03:04:05Z",
                    "lastModifiedAt": "2024-02-03T04:05:06Z",
                    "items": [
                        {"contentId": "cardA", "addedAt": "2024-01-02T03:04:05Z"},
                        {"contentId": "cardB", "addedAt": "2024-01-03T03:04:05Z"},
                    ],
                }
            ]
        )
        await client.update_groups()

        group = client.groups["g1"]
        self.assertEqual(group.name, "Bedtime")
        self.assertEqual(group.family_id, "fam1")
        self.assertEqual(group.image_id, "img1")
        self.assertEqual(group.image_url, "https://example/img.png")
        utc = datetime.timezone.utc
        self.assertEqual(
            group.created_at, datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=utc)
        )
        self.assertEqual(
            group.last_modified_at, datetime.datetime(2024, 2, 3, 4, 5, 6, tzinfo=utc)
        )
        self.assertEqual(group.card_ids, ["cardA", "cardB"])

    async def test_skips_entries_without_id(self) -> None:
        client = self._make_client([{"name": "no id here"}, {"id": "g2"}])
        await client.update_groups()
        self.assertEqual(set(client.groups), {"g2"})

    async def test_empty_group_has_no_card_ids(self) -> None:
        # A group with no cards: items empty or absent -> card_ids == [].
        client = self._make_client([{"id": "g1", "items": []}, {"id": "g2"}])
        await client.update_groups()
        self.assertEqual(client.groups["g1"].card_ids, [])
        self.assertEqual(client.groups["g2"].card_ids, [])

    async def test_updates_existing_group_in_place(self) -> None:
        client = self._make_client([{"id": "g1", "name": "Old"}])
        await client.update_groups()
        original = client.groups["g1"]

        client._rest.get_card_groups = AsyncMock(
            return_value=[{"id": "g1", "name": "New"}]
        )
        await client.update_groups()
        self.assertIs(client.groups["g1"], original)
        self.assertEqual(client.groups["g1"].name, "New")

    async def test_drops_groups_deleted_upstream(self) -> None:
        client = self._make_client([{"id": "g1"}, {"id": "g2"}])
        await client.update_groups()
        self.assertEqual(set(client.groups), {"g1", "g2"})

        client._rest.get_card_groups = AsyncMock(return_value=[{"id": "g1"}])
        await client.update_groups()
        self.assertEqual(set(client.groups), {"g1"})


class GetCardGroupsResponseShapeTests(_ClientTestCase):
    """get_card_groups returns the top-level array, or [] if the response
    isn't a list."""

    def _rest(self):
        from yoto_api.rest.client import RestClient

        return RestClient(session=MagicMock())

    async def test_top_level_array(self) -> None:
        rest = self._rest()
        rest._get = AsyncMock(return_value=[{"id": "g1"}])
        self.assertEqual(await rest.get_card_groups(fresh_token()), [{"id": "g1"}])

    async def test_non_list_yields_empty(self) -> None:
        rest = self._rest()
        rest._get = AsyncMock(return_value={})
        self.assertEqual(await rest.get_card_groups(fresh_token()), [])


class LegacySetAlarmRemovedTests(unittest.TestCase):
    """The wipe-the-list `set_alarm` and `AlarmRequest` shouldn't exist
    in v3 anymore. Regression guard so they don't sneak back."""

    def test_set_alarm_method_gone(self) -> None:
        self.assertFalse(hasattr(YotoClient, "set_alarm"))

    def test_alarm_request_not_exported(self) -> None:
        import yoto_api as v3

        self.assertFalse(hasattr(v3, "AlarmRequest"))


class WakeAndShowIconTests(_ClientTestCase):
    """`wake_screen` reads the raw volume from the last event and forwards it to
    the mqtt client (which maps it to the send step); `show_icon` wakes first
    only if asked."""

    _URL = "https://www.yotoicons.com/static/uploads/123.png"

    def _client_at_cran(self, cran) -> tuple[YotoClient, MagicMock]:
        client = self.make_client()
        client._mqtt = MagicMock()
        client._mqtt.is_connected = True
        client._mqtt.wake_screen = AsyncMock()
        client._mqtt.show_icon = AsyncMock()
        client._mqtt.request_player_status = AsyncMock()
        player = YotoPlayer(device=Device(device_id="d1", name="x"))
        if cran is not None:
            # last_event carries the raw 0-16 cran.
            player.last_event.volume = cran
        client.players["d1"] = player
        return client, client._mqtt

    async def test_wake_screen_forwards_reported_volume(self) -> None:
        # the raw cran is already on last_event, so no status request is needed.
        client, mqtt = self._client_at_cran(3)
        await client.wake_screen("d1")
        mqtt.request_player_status.assert_not_awaited()
        mqtt.wake_screen.assert_awaited_once_with("d1", 3)

    async def test_wake_screen_waits_for_the_status_volume(self) -> None:
        client, mqtt = self._client_at_cran(None)

        async def arrive(_device_id):
            client.players["d1"].last_event.volume = 2

        mqtt.request_player_status.side_effect = arrive
        await client.wake_screen("d1")
        mqtt.wake_screen.assert_awaited_once_with("d1", 2)

    async def test_wake_screen_raises_when_no_volume_arrives(self) -> None:
        client, mqtt = self._client_at_cran(None)
        with patch("yoto_api.client._WAKE_VOLUME_TIMEOUT_S", 0.1):
            with self.assertRaises(YotoError):
                await client.wake_screen("d1")
        mqtt.wake_screen.assert_not_awaited()

    async def test_show_icon_does_not_wake_by_default(self) -> None:
        client, mqtt = self._client_at_cran(3)
        await client.show_icon("d1", self._URL, timeout=5)
        mqtt.wake_screen.assert_not_awaited()
        mqtt.show_icon.assert_awaited_once_with("d1", self._URL, 5, False)

    async def test_show_icon_wakes_first_when_requested(self) -> None:
        client, mqtt = self._client_at_cran(3)
        await client.show_icon("d1", self._URL, wake=True)
        mqtt.wake_screen.assert_awaited_once_with("d1", 3)
        mqtt.show_icon.assert_awaited_once_with("d1", self._URL, 10, False)


if __name__ == "__main__":
    unittest.main()
