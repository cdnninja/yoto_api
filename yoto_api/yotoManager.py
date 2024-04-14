from .YotoAPI import YotoAPI
from .Token import Token


class YotoManager:
    def __init__(self, username: str, password: str) -> None:
        self.username: str = username
        self.password: str = password
        self.api: YotoAPI = YotoAPI()
        self.players: dict = {}
        self.token: Token = None

    def initialize(self) -> None:
        self.token: Token = self.YotoAPI.login(self.username, self.password)
        self.players = self.api.get_devices(self.token)
