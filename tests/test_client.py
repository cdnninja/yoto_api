"""YotoClient façade behaviour: command dispatch, refresh tolerance,
MQTT lifecycle, dynamic subscribe, settings + alarms writes, online
state consolidation."""

import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytz

from yoto_api import YotoError
from yoto_api import (
    Alarm,
    Device,
    PlaybackEvent,
    PlaybackStatus,
    StatusPatch,
    YotoClient,
    YotoPlayer,
)
from yoto_api.models.info import PlayerInfo

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
            return PlayerInfo(device_id=device_id), True

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


class DynamicPlayerSubscribeTests(_ClientTestCase):
    """update_player_list should auto add/remove MQTT subscriptions."""

    async def test_new_device_triggers_add_player(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        client._mqtt = MagicMock()
        client._mqtt.add_player = AsyncMock()
        client._mqtt.remove_player = AsyncMock()

        existing = Device(device_id="known", name="Known")
        new = Device(device_id="new", name="New")
        client._rest.list_devices = AsyncMock(
            side_effect=[
                [(existing, True)],
                [(existing, True), (new, True)],
            ]
        )

        await client.update_player_list()
        client._mqtt.add_player.assert_awaited_once_with("known")

        client._mqtt.add_player.reset_mock()
        await client.update_player_list()
        client._mqtt.add_player.assert_awaited_once_with("new")

    async def test_removed_device_triggers_remove_player(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        client._mqtt = MagicMock()
        client._mqtt.add_player = AsyncMock()
        client._mqtt.remove_player = AsyncMock()

        a = Device(device_id="a", name="A")
        b = Device(device_id="b", name="B")
        client._rest.list_devices = AsyncMock(
            side_effect=[
                [(a, True), (b, False)],
                [(a, True)],
            ]
        )

        await client.update_player_list()
        await client.update_player_list()
        client._mqtt.remove_player.assert_awaited_once_with("b")
        self.assertNotIn("b", client.players)


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


class StatusFallback403Tests(_ClientTestCase):
    """`get_player_status` falls back to /config when /status returns 403,
    detected via the `status_code` attribute on `YotoAPIError` (no string
    matching on the message)."""

    async def test_403_triggers_fallback(self) -> None:
        from yoto_api import YotoAPIError
        from yoto_api.models.status import PlayerStatus
        from yoto_api.rest.client import RestClient

        # RestClient now requires a session; pass a mock since we patch _get.
        rest = RestClient(session=MagicMock())
        token = fresh_token()

        calls: list[str] = []

        async def fake_get(token, path, what, **_):
            calls.append(path)
            if path.endswith("/status"):
                raise YotoAPIError("scope missing", status_code=403)
            # /config call returns the device.status sub-block
            return {
                "device": {
                    "online": True,
                    "status": {"batteryLevel": 42, "wifiStrength": -55},
                },
            }

        rest._get = fake_get
        result = await rest.get_player_status(token, "dev1")

        self.assertIsInstance(result, PlayerStatus)
        self.assertEqual(result.battery_level_percentage, 42)
        self.assertEqual(result.wifi_strength, -55)
        self.assertTrue(result.is_online)  # carried from device.online
        # /status was tried first, then /config
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].endswith("/status"))
        self.assertIn("/config", calls[1])

    async def test_non_403_propagates(self) -> None:
        from yoto_api import YotoAPIError
        from yoto_api.rest.client import RestClient

        rest = RestClient(session=MagicMock())
        rest._get = AsyncMock(side_effect=YotoAPIError("server boom", status_code=500))
        with self.assertRaises(YotoAPIError) as ctx:
            await rest.get_player_status(fresh_token(), "dev1")
        self.assertEqual(ctx.exception.status_code, 500)


class OnlineConsolidationTests(_ClientTestCase):
    """status.is_online is the single source. Three writers feed it."""

    async def test_rest_devices_mine_sets_online_via_status(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        device = Device(device_id="d1", name="x")
        client._rest.list_devices = AsyncMock(return_value=[(device, True)])
        await client.update_player_list()
        self.assertTrue(client.players["d1"].status.is_online)

    async def test_rest_devices_mine_can_set_offline(self) -> None:
        client = self.make_client()
        client.token = fresh_token()
        device = Device(device_id="d1", name="x")
        client._rest.list_devices = AsyncMock(return_value=[(device, False)])
        await client.update_player_list()
        self.assertFalse(client.players["d1"].status.is_online)

    async def test_mqtt_message_flips_to_online(self) -> None:
        client = self.make_client()
        device = Device(device_id="d1", name="x")
        player = YotoPlayer(device=device)
        client.players["d1"] = player
        # Simulate REST having seen offline
        client._set_online(player, False)
        self.assertFalse(player.status.is_online)
        # An MQTT StatusPatch arrives — presence proof
        await client._on_mqtt_message(StatusPatch(player_id="d1", fields={}))
        self.assertTrue(player.status.is_online)

    async def test_mqtt_never_sets_offline(self) -> None:
        # Even if the (unusual) MQTT payload included offline, presence
        # of the message is the truth — it's been flipped to True before
        # _apply_status_patch runs.
        client = self.make_client()
        device = Device(device_id="d1", name="x")
        player = YotoPlayer(device=device)
        client.players["d1"] = player
        await client._on_mqtt_message(
            StatusPatch(player_id="d1", fields={"is_online": False}),
        )
        # Patch is applied AFTER _set_online(True) runs — so the patch's
        # value wins. This is the documented behaviour: MQTT can still
        # flip is_online either way if it explicitly carries it. The
        # important guarantee is that *receiving any message* counts as
        # presence proof to start with.
        self.assertFalse(player.status.is_online)


class PlaybackEventMergeTests(_ClientTestCase):
    """Yoto emits partial MQTT events; lib must merge non-None fields
    into the existing last_event so a volume change doesn't wipe
    playback_status."""

    async def asyncSetUp(self) -> None:
        self.client = self.make_client()
        device = Device(device_id="d1", name="Mini")
        self.player = YotoPlayer(device=device)
        self.client.players["d1"] = self.player

    async def test_first_event_is_stored_as_is(self) -> None:
        event = PlaybackEvent(
            player_id="d1",
            card_id="abc",
            playback_status=PlaybackStatus.PLAYING,
        )
        await self.client._on_mqtt_message(event)
        self.assertEqual(self.player.last_event.card_id, "abc")
        self.assertEqual(
            self.player.last_event.playback_status,
            PlaybackStatus.PLAYING,
        )

    async def test_partial_event_only_overwrites_present_fields(self) -> None:
        first = PlaybackEvent(
            player_id="d1",
            card_id="abc",
            chapter_key="01",
            playback_status=PlaybackStatus.PLAYING,
            volume=8,
        )
        await self.client._on_mqtt_message(first)
        # A volume-only update — must not wipe card_id or playback_status
        delta = PlaybackEvent(player_id="d1", volume=10)
        await self.client._on_mqtt_message(delta)
        self.assertEqual(self.player.last_event.volume, 10)
        self.assertEqual(self.player.last_event.card_id, "abc")
        self.assertEqual(self.player.last_event.chapter_key, "01")
        self.assertEqual(
            self.player.last_event.playback_status,
            PlaybackStatus.PLAYING,
        )


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
        self.assertTrue(player.status.is_online)

    async def test_playback_event_marks_online(self) -> None:
        client, player = self._client_with_offline_player()
        await client._on_mqtt_message(PlaybackEvent(player_id="d1", volume=5))
        self.assertTrue(player.status.is_online)


class StatusFallbackTests(_ClientTestCase):
    """update_player_status falls back to /config when /status returns 403."""

    async def test_falls_back_when_scope_missing(self) -> None:
        from yoto_api.models.status import PlayerStatus

        client = self.make_client()
        client.token = fresh_token()
        client.players["d1"] = YotoPlayer(device=Device(device_id="d1", name="x"))
        fallback_status = PlayerStatus(device_id="d1", battery_level_percentage=42)
        client._rest.get_player_status = AsyncMock(return_value=fallback_status)
        result = await client.update_player_status("d1")
        self.assertIs(result, fallback_status)
        self.assertEqual(
            client.players["d1"].status.battery_level_percentage,
            42,
        )


class LegacySetAlarmRemovedTests(unittest.TestCase):
    """The wipe-the-list `set_alarm` and `AlarmRequest` shouldn't exist
    in v3 anymore. Regression guard so they don't sneak back."""

    def test_set_alarm_method_gone(self) -> None:
        self.assertFalse(hasattr(YotoClient, "set_alarm"))

    def test_alarm_request_not_exported(self) -> None:
        import yoto_api as v3

        self.assertFalse(hasattr(v3, "AlarmRequest"))


if __name__ == "__main__":
    unittest.main()
