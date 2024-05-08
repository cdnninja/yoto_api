"""MQTT Client for Yoto"""

import logging
import paho.mqtt.client as mqtt
import json

from .const import DOMAIN
from .Token import Token
from .utils import get_child_value
from .YotoPlayer import YotoPlayer

_LOGGER = logging.getLogger(__name__)


class YotoMQTTClient:
    def __init__(self) -> None:
        self.CLIENT_ID: str = "4P2do5RhHDXvCDZDZ6oti27Ft2XdRrzr"
        self.MQTT_AUTH_NAME: str = "JwtAuthorizer_mGDDmvLsocFY"
        self.MQTT_URL: str = "aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"
        self.client = None

    def connect_mqtt(self, token: Token, player: YotoPlayer):
        #             mqtt.CallbackAPIVersion.VERSION1,
        self.client = mqtt.Client(
            client_id="DASH" + player.id,
            transport="websockets",
            userdata=player
        )
        self.client.username_pw_set(
            username=player.id
            + "?x-amz-customauthorizer-name="
            + self.MQTT_AUTH_NAME,
            password=token.access_token,
        )
        # client.on_connect = on_message
        self.client.on_message = self._on_message
        self.client.tls_set()
        self.client.connect(host=self.MQTT_URL, port=443)
        self.client.loop_start()
        self.client.subscribe("device/" + player.id + "/events")
        self.client.subscribe("device/" + player.id + "/status")
        self.client.subscribe("device/" + player.id + "/response")
        # Command not needed but helps sniffing traffic
        self.client.subscribe("device/" + player.id + "/command")
        # time.sleep(60)
        # client.loop_stop()

    def card_pause(self, deviceId):
        topic = "device/" + deviceId + "/command/card-pause"
        payload = ""
        self._publish_command(self.client, topic, payload)
        # MQTT Message: {"status":{"card-pause":"OK","req_body":""}}

    def card_play(self, deviceId):
        topic = "device/" + deviceId + "/command/card-play"
        self._publish_command(self, self.client, topic, "card-play")
        # MQTT Message: {"status":{"card-play":"OK","req_body":"{\"uri\":\"https://yoto.io/7JtVV\",\"secondsIn\":0,\"cutOff\":0,\"chapterKey\":\"01\",\"trackKey\":\"01\",\"requestId\":\"5385910e-f853-4f34-99a4-d2ed94f02f6d\"}"}}

    def _publish_command(self, topic, payload):
        self.client.publish(topic, payload)

    def _parse_status_message(self, message, player):
        _LOGGER.debug(f"{DOMAIN} - Parsing Status: {message}")

    def _parse_events_message(self, message, player):
        _LOGGER.debug(f"{DOMAIN} - Parsing Event: {message}")
        player.repeat_all = get_child_value(message, "repeatAll")

    # {"repeatAll":true,"volume":6,"volumeMax":6,"cardId":"none","playbackStatus":"stopped","streaming":false,"playbackWait":false,"sleepTimerActive":false,"eventUtc":1714960275}

    def _on_message(self, client, player, message):
        # Process MQTT Message
        _LOGGER.debug(
            f"{DOMAIN} - MQTT Message: {str(message.payload.decode('utf-8'))}"
        )
        _LOGGER.debug(f"{DOMAIN} - MQTT Topic: {message.topic}")
        # _LOGGER.debug(f"{DOMAIN} - MQTT QOS: {message.qos}")
        # _LOGGER.debug(f"{DOMAIN} - MQTT Retain: {message.retain}")
        parts = message.topic.split("/")
        base, device, topic = parts
        _LOGGER.debug(f"{DOMAIN} - UserData: {player}")
        if topic == "status":
            self._parse_status_message(
                json.loads(str(message.payload.decode("utf-8"))), player
            )
        elif topic == "events":
            self._parse_events_message(
                json.loads(str(message.payload.decode("utf-8"))), player
            )