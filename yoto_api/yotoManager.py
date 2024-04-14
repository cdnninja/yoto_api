from .YotoAPI import YotoAPI

class YotoManager:
    def __init__(self, username: str, password: str) -> None:
        self.username: str = username
        self.password: str = password
        self.api: YotoAPI = YotoAPI(self)
        self.players: dict = {}
        self.token: GetToken = None

    def initialize(self) -> None:
        self.token: GetToken = self.YotoAPI.login(self.username, self.password)
        self.players = self.api.get_devices(self.token)
