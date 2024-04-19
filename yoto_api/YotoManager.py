"""YotoManager.py"""
import datetime
import logging
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
        self.players: list = None
        self.library: list = None

    def initialize(self) -> None:
        self.token: Token = self.api.login(self.username, self.password)
        self.update_player_status()
        self.update_cards()

    def update_player_status(self) -> None:
        # Updates the data with current player data.
        self.players = self.api.update_devices(self.token, self.players)

    def update_cards(self) -> None:
        # Updates library and all card data.  Typically only required on startup.
        # TODO: Should update the self.library object with a current dict of players. Should it do details for all cards too or separate?
        self.library = self.api.update_library(self.token)

    def check_and_refresh_token(self) -> bool:
        if self.token is None:
            self.initialize()
            return True
        # Check if valid and correct if not
        if self.token.valid_until <= datetime.datetime.now(pytz.utc):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            self.token: Token = self.api.refresh_token(self.token)
            return True
        return False
