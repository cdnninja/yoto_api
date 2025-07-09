"""YotoManager.py"""

from datetime import datetime, timedelta
import logging
import pytz

from .YotoAPI import YotoAPI
from .YotoMQTTClient import YotoMQTTClient
from .Family import Family
from .Token import Token
from .const import DOMAIN
from .YotoPlayer import YotoPlayerConfig
from .Card import Card

_LOGGER = logging.getLogger(__name__)


class YotoManager:
    def __init__(self, username: str, password: str, client_id: str = None) -> None:
        self.username: str = username
        self.password: str = password
        if client_id is None:
            self.client_id = "zQtHNRUAEKoBXGyC05FYyV01WY7P4nhg"
        else:
            self.client_id: str = client_id
        self.api: YotoAPI = YotoAPI()
        self.players: dict = {}
        self.token: Token = None
        self.library: dict = {}
        self.mqtt_client: YotoMQTTClient = None
        self.callback: None
        self.family: Family = None

    def initialize(self) -> None:
        self.token: Token = self.api.login(self.username, self.password, self.client_id)
        self.update_players_status()

    def update_players_status(self) -> None:
        # Updates the data with current player data.
        self.api.update_players(self.token, self.players)
        if self.mqtt_client:
            for player in self.players:
                self.mqtt_client.update_status(player)

    def connect_to_events(self, callback=None) -> None:
        # Starts and connects to MQTT.  Runs a loop to receive events. Callback is called when event has been processed and player updated.
        self.callback = callback
        self.mqtt_client = YotoMQTTClient()
        self.mqtt_client.connect_mqtt(self.token, self.players, callback)

    def set_player_config(self, player_id: str, config: YotoPlayerConfig):
        self.api.set_player_config(token=self.token, player_id=player_id, config=config)
        self.update_players_status()

    def disconnect(self) -> None:
        # Should be used when shutting down
        if self.mqtt_client:
            self.mqtt_client.disconnect_mqtt()
            self.mqtt_client = None

    def update_library(self) -> None:
        # Updates library and all card data.  Typically only required on startup.
        self.api.update_library(self.token, self.library)

    def update_family(self) -> None:
        # Updates the family object with family details
        self.family = self.api.get_family(self.token)

    def update_card_detail(self, cardId: str) -> None:
        # Used to get more details for a specific card.   update_cards must be run first to get the basic library details.  Could be called in a loop for all cards but this is a lot of API calls when the data may not be needed.
        if cardId not in self.library:
            self.library[cardId] = Card(id=cardId)
        self.api.update_card_detail(token=self.token, card=self.library[cardId])

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
        chapterKey: str,
        trackKey: int,
    ):
        self.mqtt_client.card_play(
            deviceId=player_id,
            cardId=card,
            secondsIn=secondsIn,
            cutoff=cutoff,
            chapterKey=chapterKey,
            trackKey=trackKey,
        )

    def set_volume(self, player_id: str, volume: int):
        # Takes a range from 0-100.  Maps it to the nearest 0-16 value from the constant file and sends that
        self.mqtt_client.set_volume(deviceId=player_id, volume=volume)

    def set_ambients_color(self, player_id: str, r: int, g: int, b: int):
        self.mqtt_client.set_ambients(deviceId=player_id, r=r, g=g, b=b)

    def set_sleep(self, player_id: str, seconds: int):
        # Set sleep time for playback.  0 Disables sleep.
        self.mqtt_client.set_sleep(deviceId=player_id, seconds=seconds)

    def check_and_refresh_token(self) -> bool:
        if self.token is None:
            self.initialize()
            return True
        # Check if valid and correct if not
        if self.token.valid_until - timedelta(hours=1) <= datetime.now(pytz.utc):
            _LOGGER.debug(f"{DOMAIN} - access token expired")
            self.token: Token = self.api.refresh_token(self.token)
            if self.mqtt_client:
                self.disconnect()
                self.connect_to_events(self.callback)
            return True
        return False
