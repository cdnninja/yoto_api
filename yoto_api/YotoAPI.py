"""API Methods"""

import requests
import logging
from auth0.authentication import GetToken
import paho.mqtt.client as mqtt 


_LOGGER = logging.getLogger(__name__)


class YotoAPI(self):
    def __init__(self) -> None:
        self.AUDIENCE: str = "https://api.yotoplay.com"
        self.CLIENT_ID: str = "cIQ241O2gouOOAwFFvxuGVkHGT3LL6rn"
        self.LOGIN_URL: str = "login.yotoplay.com"
        self.SCOPE: str = "YOUR_SCOPE"
        self.MQTT_AUTH_NAME: str = "JwtAuthorizer_mGDDmvLsocFY"
        self.MQTT_URL: str  = "wss://aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"

    def login(self, username: str, password: str) -> Token:
        token = GetToken(self.LOGIN_URL, self.CLIENT_ID, client_secret=self.CLIENT_ID)
        token.login(username=username, password=password, realm="Username-Password-Authentication")
        return token
    
    def getDevices(self) -> None:
        #`${BASE_URL}/device-v2/devices/mine`;

