"""YotoManager.py"""

import datetime
import logging
import pytz

from .YotoAPI import YotoAPI
from .YotoMQTTClient import YotoMQTTClient
from .Token import Token
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class YotoManager:
    def __init__(self, username: str, password: str) -> None:
        self.username: str = username
        self.password: str = password
        self.api: YotoAPI = YotoAPI()
        self.players: dict = {}
        self.token: Token = None
        self.library: list = {}
        self.mqtt_client = None

    def initialize(self) -> None:
        self.token: Token = self.api.login(self.username, self.password)
        self.update_players_status()
        self.update_cards()
        # self.connect_to_events()

    def update_players_status(self) -> None:
        # Updates the data with current player data.
        self.api.update_players(self.token, self.players)

    def connect_to_events(self, callback=None) -> None:
        # Starts and connects to MQTT.  Runs a loop to receive events. Callback is called when event has been processed and player updated.
        for player in self.players.values():
            # Needs to be correct to handle multiple devices. 1 client per device
            self.mqtt_client: YotoMQTTClient = YotoMQTTClient()
            self.mqtt_client.connect_mqtt(self.token, player, callback)

    def set_player_config(self, player, settings):
        self.api.set_player_config(self.token, player, settings)

    def disconnect(self) -> None:
        # Should be used when shutting down
        self.mqtt_client.disconnect_mqtt()

    def update_cards(self) -> None:
        # Updates library and all card data.  Typically only required on startup.
        # TODO: Should update the self.library object with a current dict of players. Should it do details for all cards too or separate?
        self.api.update_library(self.token, self.library)

    def pause_player(self, player_id: str):
        self.mqtt_client.card_pause(deviceId=player_id)

    def stop_player(self, player_id: str):
        self.mqtt_client.card_stop(deviceId=player_id)

    def resume_player(self, player_id: str):
        self.mqtt_client.card_resume(deviceId=player_id)

    def play_card(
        self,
        player_id: str,
        card: str,
        secondsIn: int,
        cutoff: int,
        chapterKey: int,
        trackKey: int,
    ):
        self.mqtt_client.card_play(
            deviceId=player_id,
            card=card,
            secondsIn=secondsIn,
            cutoff=cutoff,
            chapterKey=chapterKey,
            trackKey=trackKey,
        )

    def set_volume(self, player_id: str, volume: int):
        self.mqtt_client.set_volume(deviceId=player_id, volume=volume)

    def set_ambients_color(self, player_id: str, r: int, g: int, b: int):
        self.mqtt_client.set_ambients(self, deviceId=player_id, r=r, g=g, b=b)

    def check_and_refresh_token(self) -> bool:
        if self.token is None:
            self.initialize()
            return True
        # Check if valid and correct if not
        if self.token.valid_until <= datetime.datetime.now(pytz.utc):
            _LOGGER.debug(f"{DOMAIN} - access token expired")
            self.token: Token = self.api.refresh_token(self.token)
            return True
        return False
