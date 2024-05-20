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
        self.flag_connected = 0

    def connect_mqtt(self, token: Token, player: YotoPlayer, callback):
        #             mqtt.CallbackAPIVersion.VERSION1,
        userdata = (player, callback)
        self.client = mqtt.Client(
            client_id="DASH" + player.id, transport="websockets", userdata=userdata
        )
        self.client.username_pw_set(
            username=player.id + "?x-amz-customauthorizer-name=" + self.MQTT_AUTH_NAME,
            password=token.access_token,
        )
        # client.on_connect = on_message
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
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

    def disconnect_mqtt(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        self.flag_connected = 1
        _LOGGER.debug(f"{DOMAIN} - MQTT connected: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.flag_connected = 0
        _LOGGER.debug(f"{DOMAIN} - MQTT Disconnected: {rc}")

    def update_status(self, deviceId):
        topic = f"device/{deviceId}/command/events"
        self.client.publish(topic)

    def set_volume(self, deviceId: str, volume: int):
        topic = f"device/{deviceId}/command/set-volume"
        payload = json.dumps({"volume": volume})
        self.client.publish(topic, str(payload))
        # {"status":{"set-volume":"OK","req_body":"{\"volume\":25,\"requestId\":\"39804a13-988d-43d2-b30f-1f3b9b5532f0\"}"}}

    def card_stop(self, deviceId):
        topic = f"device/{deviceId}/command/card-stop"
        self.client.publish(topic)

    def card_pause(self, deviceId):
        topic = f"device/{deviceId}/command/card-pause"
        self.client.publish(topic)

    def card_resume(self, deviceId):
        topic = f"device/{deviceId}/command/card-resume"
        self.client.publish(topic)
        # MQTT Message: {"status":{"card-pause":"OK","req_body":""}}

    def card_play(
        self,
        deviceId,
        cardId: str,
        secondsIn: int,
        cutoff: int,
        chapterKey: str,
        trackKey: str,
    ):
        topic = f"device/{deviceId}/command/card-play"
        payload = json.dumps(
            {
                "uri": f"https://yoto.io/{cardId}",
                "chapterKey": chapterKey,
                "trackKey": trackKey,
                "secondsIn": secondsIn,
                "cutOff": cutoff,
            }
        )
        self.client.publish(topic, str(payload))
        # MQTT Message: {"status":{"card-play":"OK","req_body":"{\"uri\":\"https://yoto.io/7JtVV\",\"secondsIn\":0,\"cutOff\":0,\"chapterKey\":\"01\",\"trackKey\":\"01\",\"requestId\":\"5385910e-f853-4f34-99a4-d2ed94f02f6d\"}"}}

    # restart the player
    def restart(self, deviceId):
        topic = f"device/{deviceId}/command/restart"
        self.client.publish(topic)

    # control bluetooth on the player
    # action: "on" (turn on), "off" (turn off), "is-on" (check if bluetooth is on)
    # name: (optional) the name of the target device to connect to when action is "on"
    # mac: (optional) the MAC address of the target device to connect to when action is "on"
    def bluetooth(self, deviceId, action: str, name: str, mac: str):
        topic = f"device/{deviceId}/command/bt"
        payload = json.dumps(
            {
                "action": action,
                "name": name,
                "mac": mac,
            }
        )
        self.client.publish(topic, str(payload))

    # set the ambient light of the player
    # red, blue, green values of intensity from 0-255
    def set_ambients(self, deviceId, r: int, g: int, b: int):
        topic = f"device/{deviceId}/command/ambients"
        payload = json.dumps({"r": r, "g": g, "b": b})
        self.client.publish(topic, str(payload))

    def _parse_status_message(self, message, player):
        player.night_light_mode = get_child_value(message, "nightlightMode")
        player.battery_level_percentage = get_child_value(message, "batteryLevel")

    def _parse_events_message(self, message, player):
        player.repeat_all = get_child_value(message, "repeatAll") or player.repeat_all
        player.volume = get_child_value(message, "volume") or player.volume
        player.volume_max = get_child_value(message, "volumeMax") or player.volume_max
        player.online = get_child_value(message, "online") or player.online
        player.chapter_title = get_child_value(message, "chapterTitle") or player.chapter_title
        player.track_title = get_child_value(message, "trackTitle") or player.track_title
        player.track_length = get_child_value(message, "trackLength") or player.track_length
        player.track_position = get_child_value(message, "position") or player.track_position
        player.source = get_child_value(message, "source") or player.source
        player.playback_status = get_child_value(message, "playbackStatus") or player.playback_status
        player.sleep_timer_active = get_child_value(message, "sleepTimerActive") or player.sleep_timer_active
        player.card_id = get_child_value(message, "cardId") or player.card_id

    # {"trackLength":315,"position":0,"cardId":"7JtVV","repeatAll":true,"source":"remote","cardUpdatedAt":"2021-07-13T14:51:26.576Z","chapterTitle":"Snow and Tell","chapterKey":"03","trackTitle":"Snow and Tell","trackKey":"03","streaming":false,"volume":5,"volumeMax":8,"playbackStatus":"playing","playbackWait":false,"sleepTimerActive":false,"eventUtc":1715133271}

    def _on_message(self, client, userdata, message):
        # Process MQTT Message
        _LOGGER.debug(f"{DOMAIN} - MQTT Topic: {message.topic}")
        _LOGGER.debug(
            f"{DOMAIN} - MQTT Message: {str(message.payload.decode('utf-8'))}"
        )
        # _LOGGER.debug(f"{DOMAIN} - MQTT QOS: {message.qos}")
        # _LOGGER.debug(f"{DOMAIN} - MQTT Retain: {message.retain}")
        player = userdata[0]
        callback = userdata[1]
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
            if callback:
                callback()
