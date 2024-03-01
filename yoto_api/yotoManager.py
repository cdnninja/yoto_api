from .Yoto import Yoto
from .YotoAPI import YotoAPI
from auth0.authentication import GetToken


class YotoManager:
    def __init__(self, username: str, password: str) -> None:
        self.username: str = username
        self.password: str = password
        self.api: YotoAPI = YotoAPI(self)
      
    def initialize(self) -> None:
        self.token: GetToken = self.YotoAPI.login(self.username, self.password)

