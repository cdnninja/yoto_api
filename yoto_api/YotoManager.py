"""YotoManager.py"""

import logging
import datetime as dt
import pytz
from .YotoAPI import YotoAPI
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

        self.token: Token = self.api.login(self.username, self.password)
        self.players: list = None
        self.library: list = None
        self.initialize()

    def initialize(self) -> None:
        self.update_player_status(self.token)
        self.update_cards(self.token)

    def update_player_status(self, token) -> None:
        # TODO: Should update the self.players object with a current dict of players. Below isn't complete
        self.players = self.api.update_devices(self.token)

    def update_cards(self, token) -> None:
        # TODO: Should update the self.library object with a current dict of players. Should it do details for all cards too or separate?
        self.library = self.api.update_library(self.token)

    def check_and_refresh_token(self) -> bool:
        if self.token is None:
            self.initialize()
        if self.token.valid_until <= dt.datetime.now(pytz.utc):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            self.token: Token = self.api.refresh_token(self.token)
            return True
        return False
