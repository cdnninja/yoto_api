"""API Methods"""

import requests
import logging
import datetime
import re
import paho.mqtt.client as mqtt

from datetime import timedelta
import pytz
from .const import DOMAIN, LIGHT_COLORS, POWER_SOURCE
from .Token import Token
from .Card import Card
from .YotoPlayer import YotoPlayer

_LOGGER = logging.getLogger(__name__)


class YotoAPI:
    def __init__(self) -> None:
        self.BASE_URL: str = "https://api.yotoplay.com"
        self.CLIENT_ID: str = "4P2do5RhHDXvCDZDZ6oti27Ft2XdRrzr"
        self.LOGIN_URL: str = "login.yotoplay.com"
        self.TOKEN_URL: str = "https://api.yotoplay.com/auth/token"
        self.SCOPE: str = "YOUR_SCOPE"
        self.MQTT_AUTH_NAME: str = "JwtAuthorizer_mGDDmvLsocFY"
        self.MQTT_URL: str = "aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"

    def login(self, username: str, password: str) -> Token:
        url = self.TOKEN_URL
        payload = {}
        payload["audience"] = self.BASE_URL
        payload["client_id"] = self.CLIENT_ID
        payload["grant_type"] = "password"
        payload["password"] = password
        payload["scope"] = "openid email profile offline_access"
        payload["username"] = username
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response}")
        valid_until = datetime.datetime.now(pytz.utc) + timedelta(
            seconds=response["expires_in"]
        )

        return Token(
            username=username,
            password=password,
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            token_type=response["token_type"],
            scope=response["scope"],
            valid_until=valid_until,
        )
        ############## ${BASE_URL}/auth/token #############
        # Request POST contents:
        # audience=https%3A//api.yotoplay.com&client_id=i42noid4b2oiboi4bo&grant_type=password&password=sndoinoinscoif&scope=openid%20email%20profile%20offline_access&username=anonymous%40gmail.com
        #
        # Response to above:
        # {
        #    "access_token": "kalfkbalsbljagsl",
        #    "refresh_token":"akklabflkablksf",
        #    "id_token":"klasblgkablksgb",
        #    "scope":"openid email profile user-cards users offline_access",
        #    "expires_in":86400,
        #    "token_type":"Bearer"
        # }
        # Requests to endpoints below use contents of "access_token" in the header ->
        # Authorization: Bearer access_token
        # User-Agent: Yoto/2.73 (com.yotoplay.Yoto; build:10405; iOS 17.4.0) Alamofire/5.6.4

    # pass='audience=https%3A//api.yotoplay.com&client_id=FILL_THIS_IN&grant_type=password&password=FILL_THIS_IN&scope=openid%20email%20profile%20offline_access&username=FILL_THIS_IN%40gmail.com'
    # curl -d "$pass" https://api.yotoplay.com/auth/token | jq '.access_token'

    def update_players(self, token: Token, players: list[YotoPlayer]) -> None:
        response = self._get_devices(token)
        for item in response["devices"]:
            if self.get_child_value(item, "deviceId") not in players:
                player: YotoPlayer = YotoPlayer(
                    id=self.get_child_value(item, "deviceId"),
                )
                players[player.id] = player
            deviceId = self.get_child_value(item, "deviceId")
            players[deviceId].name = self.get_child_value(item, "name")
            players[deviceId].device_type = self.get_child_value(item, "deviceType")
            players[deviceId].online = self.get_child_value(item, "online")

            # Should we call here or make this a separate call from YM?  This could help us reduce API calls.
            player_status_response = self._get_device_status(token, deviceId)
            players[deviceId].last_updated_at = self._parse_datetime(
                self.get_child_value(player_status_response, "updatedAt"), pytz.utc
            )
            if self.get_child_value(player_status_response, "activeCard") != "none":
                players[deviceId].is_playing = True
            else:
                players[deviceId].is_playing = False
            players[deviceId].active_card = self.get_child_value(
                player_status_response, "activeCard"
            )
            players[deviceId].ambient_light_sensor_reading = self.get_child_value(
                player_status_response, "ambientLightSensorReading"
            )
            players[deviceId].battery_level_percentage = self.get_child_value(
                player_status_response, "batteryLevelPercentage"
            )
            players[deviceId].day_mode_on = self.get_child_value(
                player_status_response, "dayMode"
            )
            players[deviceId].user_volume = self.get_child_value(
                player_status_response, "userVolumePercentage"
            )
            players[deviceId].system_volume = self.get_child_value(
                player_status_response, "systemVolumePercentage"
            )
            players[deviceId].temperature_celcius = self.get_child_value(
                player_status_response, "temperatureCelcius"
            )
            players[deviceId].bluetooth_audio_connected = self.get_child_value(
                player_status_response, "isBluetoothAudioConnected"
            )
            players[deviceId].charging = self.get_child_value(
                player_status_response, "isCharging"
            )
            players[deviceId].audio_device_connected = self.get_child_value(
                player_status_response, "isAudioDeviceConnected"
            )
            players[deviceId].firmware_version = self.get_child_value(
                player_status_response, "firmwareVersion"
            )
            players[deviceId].wifi_strength = self.get_child_value(
                player_status_response, "wifiStrength"
            )
            players[deviceId].playing_source = self.get_child_value(
                player_status_response, "playingSource"
            )
            players[deviceId].night_light_mode = LIGHT_COLORS[
                self.get_child_value(player_status_response, "nightlightMode")
            ]
            players[deviceId].power_source = POWER_SOURCE[
                self.get_child_value(player_status_response, "powerSource")
            ]

    def update_library(self, token: Token, library: dict[Card]) -> list[Card]:
        response = self._get_cards(token)
        for item in response["cards"]:
            if self.get_child_value(item, "cardId") not in library:
                card: Card = Card(
                    id=self.get_child_value(item, "cardId"),
                )
                library[card.id] = card
            cardId = self.get_child_value(item, "cardId")
            library[cardId].title = self.get_child_value(item, "card.title")
            library[cardId].description = self.get_child_value(
                item, "card.metadata.description"
            )
            library[self.get_child_value(item, "cardId")].author = self.get_child_value(
                item, "card.metadata.author"
            )
            library[cardId].category = self.get_child_value(
                item, "card.metadata.stories"
            )
            library[cardId].coverImageL = self.get_child_value(
                item, "card.metadata.cover.imageL"
            )
            library[cardId].seriesOrder = self.get_child_value(
                item, "card.metadata.cover.seriesorder"
            )
            library[cardId].seriesTitle = self.get_child_value(
                item, "card.metadata.cover.seriestitle"
            )

    def refresh_token(self, token: Token) -> Token:
        # audience=https%3A//api.yotoplay.com&client_id=FILL_THIS_IN&grant_type=refresh_token&refresh_token=FILL_THIS_IN&scope=openid%20email%20profile%20offline_access
        url = self.TOKEN_URL
        payload = {}
        payload["audience"] = self.BASE_URL
        payload["client_id"] = self.CLIENT_ID
        payload["grant_type"] = "refresh_token"
        payload["refresh_token"] = token.refresh_token
        payload["scope"] = "openid email profile offline_access"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response}")
        valid_until = datetime.datetime.now(pytz.utc) + timedelta(
            seconds=response["expires_in"]
        )
        return Token(
            username=token.username,
            password=token.password,
            access_token=response["access_token"],
            refresh_token=response["id_token"],
            token_type=response["token_type"],
            scope=token.scope,
            valid_until=valid_until,
        )

    def _get_devices(self, token: Token) -> None:
        url = self.BASE_URL + "/device-v2/devices/mine"

        headers = self._get_authenticated_headers(token)

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Devices Response: {response}")
        return response

    def _get_device_status(self, token: Token, player_id: str) -> None:
        url = self.BASE_URL + "/device-v2/" + player_id + "/status"

        headers = self._get_authenticated_headers(token)

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Device Status Response: {response}")
        return response

    def _get_cards(self, token: Token) -> dict:
        ############## ${BASE_URL}/card/family/library #############
        url = self.BASE_URL + "/card/family/library"

        headers = self._get_authenticated_headers(token)

        response = requests.get(url, headers=headers).json()
        # _LOGGER.debug(f"{DOMAIN} - Get Card Library: {response}")
        return response

        # {
        #   "cards": [
        #     {
        #       "cardId": "g5tcK",
        #       "reason": "physical-add",
        #       "shareType": "yoto",
        #       "familyId": "ksdlbksbdgklb",
        #       "card": {
        #         "cardId": "g5tcK",
        #         "content": {
        #           "activity": "yoto_Player",
        #           "editSettings": {
        #             "editKeys": false,
        #             "autoOverlayLabels": "disabled"
        #           },
        #           "config": {
        #             "disableAutoOverlayLabels": false
        #           },
        #           "availability": "",
        #           "cover": {
        #             "imageL": "https://card-content.yotoplay.com/yoto/pub/jbfaljsblajsfblj-wcAgqZMvA"
        #           },
        #           "version": "1"
        #         },
        #         "slug": "ladybird-audio-adventures-the-frozen-world",
        #         "userId": "yoto",
        #         "sortkey": "ladybird-audio-adventures-the-frozen-world",
        #         "title": "Ladybird Audio Adventures: The Frozen World",
        #         "updatedAt": "2022-07-21T14:30:22.231Z",
        #         "createdAt": "2020-09-03T17:30:17.911Z",
        #         "metadata": {
        #           "category": "stories",
        #           "author": "Ladybird",
        #           "previewAudio": "shopify-slug",
        #           "status": {
        #             "name": "live",
        #             "updatedAt": "2020-11-24T17:08:54.839Z"
        #           },
        #           "seriestitle": "Ladybird Audio Adventures - Volume 2",
        #           "media": {
        #             "fileSize": 35189015,
        #             "duration": 2883,
        #             "hasStreams": false
        #           },
        #           "description": "Join our intrepid adventurers Otto and Cassandra (and Missy, the smartest bird in the Universe) as they embark on a brand new Ladybird Audio Adventure!\n\nIn this adventure, Otto and Missy are off to explore the Frozen World. Setting course for the Arctic and Antarctica they discover penguins, orcas and seals, and a whole lot of snow! Now if they can just figure out how to get the heating going in Otto's teleporter they'll be able to get back home! \n\nThese audiobooks help children learn about their environment on journey of discovery with the narrators Ben Bailey Smith (aka Doc Brown, rapper, comedian and writer) and Sophie Aldred (best known for her role as Ace in Doctor Who).",
        #           "cover": {
        #             "imageL": "https://card-content.yotoplay.com/yoto/pub/lajsbfljabsfljabsfljbasfljbalsjf-wcAgqZMvA?width=250"
        #           },
        #           "seriesorder": "2",
        #           "languages": [
        #             "en"
        #           ]
        #         }
        #       },
        #       "provenanceId": "kasfblasbflbaslkfl",
        #       "inFamilyLibrary": true,
        #       "updatedAt": "2024-04-10T03:58:16.732Z",
        #       "createdAt": "2022-12-26T07:04:18.977Z",
        #       "lastPlayedAt": "2024-04-11T04:30:49.402Z",
        #       "masterUid": "asbkflbasflkblaksf"
        #     },
        #     {
        #       "cardId": "iYIMF",
        #       "reason": "physical-add",
        #       "shareType": "yoto",
        #       "familyId": "ksdlbksbdgklb",
        #       "card": {
        #         "cardId": "iYIMF",
        #         "content": {
        #           "activity": "yoto_Player",
        #           "editSettings": {
        #             "editKeys": false,
        #             "autoOverlayLabels": "chapters-offset-1"
        #           },
        #           "config": {
        #             "trackNumberOverlayTimeout": 0,
        #             "disableAutoOverlayLabels": false
        #           },
        #           "availability": "",
        #           "cover": {
        #             "imageL": "https://card-content.yotoplay.com/yoto/pub/kdsgblkjsbgjlslbj"
        #           },
        #           "version": "1"
        #         },
        #         "slug": "ladybird-audio-adventures-outer-space",
        #         "userId": "yoto",
        #         "sortkey": "ladybird-audio-adventures-outer-space",
        #         "title": "Ladybird Audio Adventures - Outer Space",
        #         "updatedAt": "2022-07-21T14:25:14.090Z",
        #         "createdAt": "2019-12-04T00:14:57.438Z",
        #         "metadata": {
        #           "category": "stories",
        #           "author": "Ladybird Audio Adventures",
        #           "previewAudio": "shopify-slug",
        #           "status": {
        #             "name": "live",
        #             "updatedAt": "2020-11-16T11:13:50.060Z"
        #           },
        #           "seriestitle": "Ladybird Audio Adventures Volume 1",
        #           "media": {
        #             "fileSize": 27225336,
        #             "duration": 3335,
        #             "hasStreams": false
        #           },
        #           "description": "The sky’s the limit for imaginations when it comes to this audio adventure! Wave goodbye to Earth and blast off into the skies above to explore 'nearby' planets, stars and galaxies, alongside inventor Otto and Missy – the cleverest raven in the universe. So, hop aboard Otto’s spacecraft and get ready for a story that’s nothing short of out of this world!\n\nLadybird Audio Adventures is an original series for 4-to 7-year-olds; a new, entertaining and engaging way for children to learn about the world around them. These are special stories written exclusively for audio with fun sound and musical effects, perfect for listening at home, before bed and on long journeys. ",
        #           "cover": {
        #             "imageL": "https://card-content.yotoplay.com/yoto/pub/ksdlfbksdbgklsbdlgk?width=250"
        #           },
        #           "seriesorder": "4",
        #           "languages": [
        #             "en"
        #           ]
        #         }
        #       },
        #       "provenanceId": "641352b283571a15872a37ca",
        #       "inFamilyLibrary": true,
        #       "updatedAt": "2024-04-05T04:03:55.198Z",
        #       "createdAt": "2023-03-16T17:32:34.249Z",
        #       "lastPlayedAt": "2024-04-05T06:15:11.308Z",
        #       "masterUid": "04dedd46720000"
        #     }
        # }

    def connect_mqtt(self, token: Token, deviceId: str):
        def on_message(client, userdata, message):
            # Process MQTT Message
            _LOGGER.debug(
                f"{DOMAIN} - MQTT Message: {str(message.payload.decode('utf-8'))}"
            )
            _LOGGER.debug(f"{DOMAIN} - MQTT Topic: {message.topic}")
            _LOGGER.debug(f"{DOMAIN} - MQTT QOS: {message.qos}")
            _LOGGER.debug(f"{DOMAIN} - MQTT Retain: {message.retain}")
            parts = message.topic.split("/")
            base, device, topic = parts
            if topic == "status":
                self._parse_status_message(
                    str(message.payload.decode("utf-8")),
                )

        #             mqtt.CallbackAPIVersion.VERSION1,
        client = mqtt.Client(
            client_id="DASH" + deviceId,
            transport="websockets",
        )
        client.username_pw_set(
            username=deviceId + "?x-amz-customauthorizer-name=" + self.MQTT_AUTH_NAME,
            password=token.access_token,
        )
        # client.on_connect = on_message
        client.on_message = on_message
        client.tls_set()
        client.connect(host=self.MQTT_URL, port=443)
        client.loop_start()
        client.subscribe("device/" + deviceId + "/events")
        client.subscribe("device/" + deviceId + "/status")
        client.subscribe("device/" + deviceId + "/response")
        # Command not needed but helps sniffing traffic
        client.subscribe("device/" + deviceId + "/command")

        # time.sleep(60)
        # client.loop_stop()
        return client

    def card_pause(self, client, deviceId):
        topic = "device/" + deviceId + "/command/card-pause"
        payload = ""
        self._publish_command(client, topic, payload)
        # MQTT Message: {"status":{"card-pause":"OK","req_body":""}}

    def card_play(self, client, deviceId):
        topic = "device/" + deviceId + "/command/card-play"
        self._publish_command(self, client, topic, "card-play")
        # MQTT Message: {"status":{"card-play":"OK","req_body":"{\"uri\":\"https://yoto.io/7JtVV\",\"secondsIn\":0,\"cutOff\":0,\"chapterKey\":\"01\",\"trackKey\":\"01\",\"requestId\":\"5385910e-f853-4f34-99a4-d2ed94f02f6d\"}"}}

    def _publish_command(self, client, topic, payload):
        client.publish(topic, payload)

    def _parse_status_message(self, message, player):
        pass

    def _get_card_detail(self, token: Token, cardid: str) -> dict:
        ############## Details below from snooping JSON requests of the app ######################

        url = self.BASE_URL + "/card/details/" + cardid
        headers = self._get_authenticated_headers(token)

        response = requests.post(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Card Detail: {response}")
        return response

        ############# ${BASE_URL}/card/details/abcABC #############
        # {
        #   "card": {
        #     "cardId": "abcABC", #string
        #     "content": {
        #       "activity": "yoto_Player",
        #       "version": "1",
        #       "availability": "",
        #       "editSettings": {
        #         "autoOverlayLabels": "chapters-offset-1",
        #         "editKeys": false
        #       },
        #       "config": {
        #         "trackNumberOverlayTimeout": 0,
        #         "disableAutoOverlayLabels": false
        #       },
        #       "cover": {
        #         "imageL": "https://card-content.yotoplay.com/yoto/pub/WgoJMZiFdH35UbDAR_4z2k1vL0MufKLHfR4ULd6I"
        #       },
        #       "chapters": [
        #         {
        #           "overlayLabel": "",
        #           "title": "Introduction",
        #           "key": "01-INT",
        #           "overlayLabelOverride": null,
        #           "ambient": null,
        #           "defaultTrackDisplay": null,
        #           "defaultTrackAmbient": null,
        #           "duration": 349, #int
        #           "fileSize": 2915405,
        #           "hasStreams": false,
        #           "display": {
        #             "icon16x16": "https://card-content.yotoplay.com/yoto/SwcetJ_c1xt9yN5jn2wdwMk4xupHLWONik-rzcBh"
        #           },
        #           "tracks": [
        #             {
        #               "overlayLabel": "",
        #               "format": "aac",
        #               "title": "Introduction",
        #               "type": "audio",
        #               "key": "01-INT",
        #               "overlayLabelOverride": null,
        #               "ambient": null,
        #               "fileSize": 2915405,
        #               "channels": "mono",
        #               "duration": 349,
        #               "transitions": {},
        #               "display": {
        #                 "icon16x16": "https://card-content.yotoplay.com/yoto/SwcetJ_c1xt9yN5jn2wdwMk4xupHLWONik-rzcBhkd4"
        #               },
        #               "trackUrl": "https://secure-media.yotoplay.com/yoto/mYZ6TgL7VRAViZ_RQL5daYEdCBCCXjes?Expires=1712889341&Policy=eyJTdGF0ZnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9zZWN1cmUtbWVkaWEueW90b3BsYXkulvdG8vbVlaNlRnTDdWSTBxUkFWaVpfUlFMNWRhdtWS1aVElsWGplcyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoSI6MTcxMjg4OTM0fV19&Signature=EiZwaoCrCG7y-LgEECIxwrkGNZYzUeMOubfcDL1uuqamskan3wG8WYTe8CGOlsG9kvanhUFojuR-bnG~YqT0wPUkn6UUtR8KY9EOVUp~Gr8X9~yGE1I-klUGgykSRIXu1za6sGsF4KwQH2QUNPyS9yS8T50d09zEgAZlGYSDqcz1u1Rb7GZRm69bwtWr1PjLZLrWkV1C9~yV~4wwR17xdgT2JU20ZJ99kBWaTG1efjH9qBaQTkL1EvewHfJkYXFQs~o3mi1bp6d4LYzXa59yzb-f3-cRK~IWgMIRiKNY~0Mgx8S-VA__&Key-Pair-Id=K11LSW6MJ7KP#sha256=mYZ6TgL7VI0qRAViZ_RQL5daYEdCBCCWmY-ZTIlX"
        #             }
        #           ]
        #         },
        #         {
        #           "overlayLabel": "1",
        #           "title": "Not the Moon",
        #           "key": "02-1",
        #           "overlayLabelOverride": null,
        #           "ambient": null,
        #           "defaultTrackDisplay": null,
        #           "defaultTrackAmbient": null,
        #           "duration": 140,
        #           "fileSize": 1111649,
        #           "hasStreams": false,
        #           "display": {
        #             "icon16x16": "https://card-content.yotoplay.com/yoto/XZOm4YE9ssAm_x2ykzasHyResnOWJzYIVe_hfc"
        #           },
        #           "tracks": [
        #             {
        #               "overlayLabel": "1",
        #               "format": "aac",
        #               "title": "Not the Moon",
        #               "type": "audio",
        #               "key": "02-1",
        #               "overlayLabelOverride": null,
        #               "ambient": null,
        #               "fileSize": 1111649,
        #               "channels": "mono",
        #               "duration": 140,
        #               "transitions": {},
        #               "display": {
        #                 "icon16x16": "https://card-content.yotoplay.com/yoto/XZOm4YE9ssAm_x2ykzasHyWJhf5RYzYIVe_hfc"
        #               },
        #               "trackUrl": "long url"
        #             }
        #           ]
        #         }
        #       ]
        #     },
        #     "createdAt": "2019-12-04T00:14:57.438Z",
        #     "metadata": {
        #       "description": "The sky’s the limit for imaginations when it comes to this audio adventure! Wave goodbye to Earth and blast off into the skies above to explore 'nearby' planets, stars and galaxies, alongside inventor Otto and Missy – the cleverest raven in the universe. So, hop aboard Otto’s spacecraft and get ready for a story that’s nothing short of out of this world!\n\nLadybird Audio Adventures is an original series for 4-to 7-year-olds; a new, entertaining and engaging way for children to learn about the world around them. These are special stories written exclusively for audio with fun sound and musical effects, perfect for listening at home, before bed and on long journeys. ",
        #       "category": "stories",
        #       "author": "Ladybird Audio Adventures",
        #       "previewAudio": "shopify-slug",
        #       "seriestitle": "Ladybird Audio Adventures Volume 1",
        #       "seriesorder": "4",
        #       "cover": {
        #         "imageL": "https://card-content.yotoplay.com/yoto/pub/WgoJMZiFdH35UbDAR_4z2k1vKLHfR4ULd6ItN4"
        #       },
        #       "languages": [
        #         "en"
        #       ],
        #       "status": {
        #         "name": "live",
        #         "updatedAt": "2020-11-16T11:13:50.060Z"
        #       },
        #       "media": {
        #         "duration": 3335,
        #         "fileSize": 27225336,
        #         "hasStreams": false
        #       }
        #     },
        #     "slug": "ladybird-audio-adventures-outer-space",
        #     "title": "Ladybird Audio Adventures - Outer Space",
        #     "updatedAt": "2022-07-21T14:25:14.090Z",
        #     "userId": "yoto",
        #     "sortkey": "ladybird-audio-adventures-outer-space"
        #   },
        #   "ownership": {
        #     "canAccess": true,
        #     "userHasRole": false,
        #     "cardIsFree": false,
        #     "cardIsMadeByUser": false,
        #     "cardIsInFamilyLibrary": true,
        #     "cardIsCreatedByFamily": false,
        #     "isAccessibleUsingSubscription": false
        #   }
        # }

    def _get_authenticated_headers(self, token: Token) -> dict:
        return {
            "User-Agent": "Yoto/2.73 (com.yotoplay.Yoto; build:10405; iOS 17.4.0) Alamofire/5.6.4",
            "Content-Type": "application/json",
            "Authorization": token.token_type + " " + token.access_token,
        }

    def get_child_value(self, data, key):
        value = data
        for x in key.split("."):
            try:
                value = value[x]
            except Exception:
                try:
                    value = value[int(x)]
                except Exception:
                    value = None
        return value

    def _parse_datetime(self, value, timezone) -> datetime.datetime:
        if value is None:
            return datetime.datetime(2000, 1, 1, tzinfo=timezone)

        value = (
            value.replace("-", "").replace("T", "").replace(":", "").replace("Z", "")
        )
        m = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", value)
        return datetime.datetime(
            year=int(m.group(1)),
            month=int(m.group(2)),
            day=int(m.group(3)),
            hour=int(m.group(4)),
            minute=int(m.group(5)),
            second=int(m.group(6)),
            tzinfo=timezone,
        )


######Endpoints:

# api.yotoplay.com/device-v2/devices/mine
# api.yotoplay.com/device-v2/$deviceid/status
# api.yotoplay.com/media/displayIcons/user/me
# api.yotoplay.com/user/details
# api.yotoplay.com/user/family/mine?allowStub=true
# api.yotoplay.com/card/mine
# api.yotoplay.com/card/mine/user/family/mine?allowStub=true
# api.yotoplay.com/card/family/library
# api.yotoplay.com/card/library/free
# api.yotoplay.com/card/library/club
# api.yotoplay.com/card/family/library
