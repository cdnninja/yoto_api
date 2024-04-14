"""YotoManager.py"""

import logging
from .YotoAPI import YotoAPI
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class YotoManager:
    def __init__(self, username: str, password: str) -> None:
        self.username: str = username
        self.password: str = password
        self.api: YotoAPI = YotoAPI()
        self.players: dict = {}
        self.token: Token = None 

        self.token: Token = self.api.login(self.username, self.password)
        self.players = self.api.get_devices(self.token)
