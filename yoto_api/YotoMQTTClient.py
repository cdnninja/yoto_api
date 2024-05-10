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
            client_id="DASH" + player.id, transport="websockets", userdata=player
        )
        self.client.username_pw_set(
            username=player.id + "?x-amz-customauthorizer-name=" + self.MQTT_AUTH_NAME,
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
        self._publish_command(topic, payload)

    def update_status(self, deviceId):
        topic = "device/" + deviceId + "/command/events"
        payload = ""
        self._publish_command(topic, payload)

    def card_resume(self, deviceId):
        topic = "device/" + deviceId + "/command/card-resume"
        payload = ""
        self._publish_command(topic, payload)
        # MQTT Message: {"status":{"card-pause":"OK","req_body":""}}

    def card_play(self, deviceId, card: str, secondsIn: int, cutoff: int, chapterKey: int):
        topic = "device/" + deviceId + "/command/card-play"
        self._publish_command(topic, "card-play")
        # MQTT Message: {"status":{"card-play":"OK","req_body":"{\"uri\":\"https://yoto.io/7JtVV\",\"secondsIn\":0,\"cutOff\":0,\"chapterKey\":\"01\",\"trackKey\":\"01\",\"requestId\":\"5385910e-f853-4f34-99a4-d2ed94f02f6d\"}"}}

    def _publish_command(self, topic, payload):
        self.client.publish(topic, payload)

    def _parse_status_message(self, message, player):
        pass

    def _parse_events_message(self, message, player):
        player.repeat_all = get_child_value(message, "repeatAll")
        player.volume = get_child_value(message, "volume")
        player.volume_max = get_child_value(message, "volumeMax")
        player.online = get_child_value(message, "online")
        player.chapter_title = get_child_value(message, "chapterTitle")
        player.track_title = get_child_value(message, "trackTitle")
        player.track_length = get_child_value(message, "trackLength")
        player.track_position = get_child_value(message, "position")
        player.source = get_child_value(message, "source")
        player.playback_status = get_child_value(message, "playbackStatus")
        player.sleep_timer_active = get_child_value(message, "sleepTimerActive")
        player.card_id = get_child_value(message, "cardId")

    # {"trackLength":315,"position":0,"cardId":"7JtVV","repeatAll":true,"source":"remote","cardUpdatedAt":"2021-07-13T14:51:26.576Z","chapterTitle":"Snow and Tell","chapterKey":"03","trackTitle":"Snow and Tell","trackKey":"03","streaming":false,"volume":5,"volumeMax":8,"playbackStatus":"playing","playbackWait":false,"sleepTimerActive":false,"eventUtc":1715133271}

    def _on_message(self, client, player, message):
        # Process MQTT Message
        _LOGGER.debug(f"{DOMAIN} - MQTT Topic: {message.topic}")
        _LOGGER.debug(
            f"{DOMAIN} - MQTT Message: {str(message.payload.decode('utf-8'))}"
        )
        # _LOGGER.debug(f"{DOMAIN} - MQTT QOS: {message.qos}")
        # _LOGGER.debug(f"{DOMAIN} - MQTT Retain: {message.retain}")
        parts = message.topic.split("/")
        base, device, topic = parts
        if topic == "status":
            self._parse_status_message(
                json.loads(str(message.payload.decode("utf-8"))), player
            )
        elif topic == "events":
            self._parse_events_message(
                json.loads(str(message.payload.decode("utf-8"))), player
            )
