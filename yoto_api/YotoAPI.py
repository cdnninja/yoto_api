"""API Methods"""

import requests
import logging
import datetime

from datetime import timedelta
import pytz
from .const import DOMAIN, POWER_SOURCE, HEX_COLORS
from .Token import Token
from .Card import Card
from .YotoPlayer import YotoPlayer
from .utils import get_child_value, parse_datetime

_LOGGER = logging.getLogger(__name__)


class YotoAPI:
    def __init__(self) -> None:
        self.BASE_URL: str = "https://api.yotoplay.com"
        self.CLIENT_ID: str = "4P2do5RhHDXvCDZDZ6oti27Ft2XdRrzr"
        self.LOGIN_URL: str = "login.yotoplay.com"

    # https://api.yoto.dev/#75c77d23-397f-47f9-b76c-ce3c647b11d5
    def login(self, username: str, password: str) -> Token:
        url = f"{self.BASE_URL}/auth/token"
        data = {
            "audience": self.BASE_URL,
            "client_id": self.CLIENT_ID,
            "grant_type": "password",
            "password": password,
            "username": username,
            "scope": "openid email profile offline_access",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response}")

        valid_until = datetime.datetime.now(pytz.utc) + datetime.timedelta(
            seconds=response["expires_in"]
        )

        return Token(
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            token_type=response["token_type"],
            scope=response["scope"],
            valid_until=valid_until,
        )

    # https://api.yoto.dev/#644d0b20-0b27-4b34-bbfa-bdffb96ec672
    def refresh_token(self, token: Token) -> Token:
        url = f"{self.BASE_URL}/auth/token"
        data = {
            "client_id": self.CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Refresh TokenResponse {response}")

        valid_until = datetime.datetime.now(pytz.utc) + timedelta(
            seconds=response["expires_in"]
        )

        return Token(
            access_token=response["access_token"],
            refresh_token=token.refresh_token,
            token_type=response["token_type"],
            scope=token.scope,
            valid_until=valid_until,
        )

    def update_players(self, token: Token, players: list[YotoPlayer]) -> None:
        response = self._get_devices(token)
        for item in response["devices"]:
            if get_child_value(item, "deviceId") not in players:
                player: YotoPlayer = YotoPlayer(
                    id=get_child_value(item, "deviceId"),
                )
                players[player.id] = player
            deviceId = get_child_value(item, "deviceId")
            players[deviceId].name = get_child_value(item, "name")
            players[deviceId].device_type = get_child_value(item, "deviceType")
            players[deviceId].online = get_child_value(item, "online")

            # Should we call here or make this a separate call from YM?  This could help us reduce API calls.
            player_status_response = self._get_device_status(token, deviceId)
            players[deviceId].last_updated_at = parse_datetime(
                get_child_value(player_status_response, "updatedAt"), pytz.utc
            )
            if get_child_value(player_status_response, "activeCard") != "none":
                players[deviceId].is_playing = True
            else:
                players[deviceId].is_playing = False
            players[deviceId].active_card = get_child_value(
                player_status_response, "activeCard"
            )
            players[deviceId].ambient_light_sensor_reading = get_child_value(
                player_status_response, "ambientLightSensorReading"
            )
            players[deviceId].battery_level_percentage = get_child_value(
                player_status_response, "batteryLevelPercentage"
            )
            players[deviceId].day_mode_on = get_child_value(
                player_status_response, "dayMode"
            )
            players[deviceId].user_volume = get_child_value(
                player_status_response, "userVolumePercentage"
            )
            players[deviceId].system_volume = get_child_value(
                player_status_response, "systemVolumePercentage"
            )
            players[deviceId].temperature_celcius = get_child_value(
                player_status_response, "temperatureCelcius"
            )
            players[deviceId].bluetooth_audio_connected = get_child_value(
                player_status_response, "isBluetoothAudioConnected"
            )
            players[deviceId].charging = get_child_value(
                player_status_response, "isCharging"
            )
            players[deviceId].audio_device_connected = get_child_value(
                player_status_response, "isAudioDeviceConnected"
            )
            players[deviceId].firmware_version = get_child_value(
                player_status_response, "firmwareVersion"
            )
            players[deviceId].wifi_strength = get_child_value(
                player_status_response, "wifiStrength"
            )
            players[deviceId].playing_source = get_child_value(
                player_status_response, "playingSource"
            )
            players[deviceId].night_light_mode = get_child_value(
                player_status_response, "nightlightMode"
            )

            players[deviceId].power_source = POWER_SOURCE[
                get_child_value(player_status_response, "powerSource")
            ]
            player_config = self._get_device_config(token, deviceId)

            time = get_child_value(player_config, "device.config.dayTime")
            players[deviceId].day_mode_time = datetime.datetime.strptime(
                time, "%H:%M"
            ).time()
            players[deviceId].day_display_brightness = get_child_value(
                player_config, "device.config.playingSource"
            )
            players[deviceId].day_ambient_colour = HEX_COLORS[
                get_child_value(player_config, "device.config.ambientColour")
            ]
            players[deviceId].day_max_volume_limit = get_child_value(
                player_config, "device.config.maxVolumeLimit"
            )
            time = get_child_value(player_config, "device.config.nightTime")
            players[deviceId].night_mode_time = datetime.datetime.strptime(
                time, "%H:%M"
            ).time()
            players[deviceId].night_ambient_colour = HEX_COLORS[
                get_child_value(player_config, "device.config.nightAmbientColour")
            ]
            players[deviceId].night_max_volume_limit = get_child_value(
                player_config, "device.config.nightMaxVolumeLimit"
            )
            players[deviceId].night_display_brightness = get_child_value(
                player_config, "device.config.nightDisplayBrightness"
            )

    def update_library(self, token: Token, library: dict[Card]) -> list[Card]:
        response = self._get_cards(token)
        for item in response["cards"]:
            if get_child_value(item, "cardId") not in library:
                card: Card = Card(
                    id=get_child_value(item, "cardId"),
                )
                library[card.id] = card
            cardId = get_child_value(item, "cardId")
            library[cardId].title = get_child_value(item, "card.title")
            library[cardId].description = get_child_value(
                item, "card.metadata.description"
            )
            library[get_child_value(item, "cardId")].author = get_child_value(
                item, "card.metadata.author"
            )
            library[cardId].category = get_child_value(item, "card.metadata.stories")
            library[cardId].cover_image_large = get_child_value(
                item, "card.metadata.cover.imageL"
            )
            library[cardId].series_order = get_child_value(
                item, "card.metadata.cover.seriesorder"
            )
            library[cardId].series_title = get_child_value(
                item, "card.metadata.cover.seriestitle"
            )

    def set_player_config(self, player, settings):
        pass

    def set_player_config(self, player, settings):
        pass

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

    def _get_device_config(self, token: Token, player_id: str) -> None:
        url = self.BASE_URL + "/device-v2/" + player_id + "/config"

        headers = self._get_authenticated_headers(token)

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Device Config Response: {response}")
        return response
        #  2024-05-15 17:25:48,604 yoto_api.YotoAPI DEBUG:yoto_api - Get Device Config Response: {'device': {'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'name': '', 'errorCode': None, 'fwVersion': 'v2.17.5-5', 'popCode': 'FAJKEH', 'releaseChannelId': 'prerelease', 'releaseChannelVersion': 'v2.17.5-5', 'activationPopCode': 'IBSKCAAA', 'registrationCode': 'IBSKCAAA', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'mac': 'b4:8a:0a:92:7a:f4', 'online': True, 'geoTimezone': 'America/Edmonton', 'getPosix': 'MST7MDT,M3.2.0,M11.1.0', 'status': {'activeCard': 'none', 'aliveTime': None, 'als': 0, 'battery': None, 'batteryLevel': 100, 'batteryRemaining': None, 'bgDownload': 0, 'bluetoothHp': 0, 'buzzErrors': 0, 'bytesPS': 0, 'cardInserted': 0, 'chgStatLevel': None, 'charging': 0, 'day': 1, 'dayBright': None, 'dbatTimeout': None, 'dnowBrightness': None, 'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'errorsLogged': 164, 'failData': None, 'failReason': None, 'free': None, 'free32': None, 'freeDisk': 30219824, 'freeDMA': None, 'fwVersion': 'v2.17.5-5', 'headphones': 0, 'lastSeenAt': None, 'missedLogs': None, 'nfcErrs': 'n/a', 'nightBright': None, 'nightlightMode': '0x194a55', 'playingStatus': 0, 'powerCaps': '0x02', 'powerSrc': 2, 'qiOtp': None, 'sd_info': None, 'shutDown': None, 'shutdownTimeout': None, 'ssid': 'speed', 'statusVersion': None, 'temp': '0:24', 'timeFormat': None, 'totalDisk': 31385600, 'twdt': 0, 'updatedAt': '2024-05-15T23:23:45.284Z', 'upTime': 159925, 'userVolume': 31, 'utcOffset': -21600, 'utcTime': 1715815424, 'volume': 34, 'wifiRestarts': None, 'wifiStrength': -54}, 'config': {'locale': 'en', 'bluetoothEnabled': '1', 'repeatAll': True, 'showDiagnostics': True, 'btHeadphonesEnabled': True, 'pauseVolumeDown': False, 'pausePowerButton': True, 'displayDimTimeout': '60', 'shutdownTimeout': '3600', 'headphonesVolumeLimited': False, 'dayTime': '06:30', 'maxVolumeLimit': '16', 'ambientColour': '#40bfd9', 'dayDisplayBrightness': 'auto', 'dayYotoDaily': '3nC80/daily/<yyyymmdd>', 'dayYotoRadio': '3nC80/radio-day/01', 'daySoundsOff': '0', 'nightTime': '18:20', 'nightMaxVolumeLimit': '8', 'nightAmbientColour': '#f57399', 'nightDisplayBrightness': '100', 'nightYotoDaily': '0', 'nightYotoRadio': '0', 'nightSoundsOff': '1', 'hourFormat': '12', 'timezone': '', 'displayDimBrightness': '0', 'systemVolume': '87', 'volumeLevel': 'safe', 'clockFace': 'digital-sun', 'logLevel': 'none', 'alarms': []}, 'shortcuts': {'versionId': '36645a9463e038d6cb9923257b38d9d9df7a6509', 'modes': {'day': {'content': [{'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'daily', 'track': '<yyyymmdd>'}}, {'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'radio-day', 'track': '01'}}]}, 'night': {'content': [{'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'daily', 'track': '<yyyymmdd>'}}, {'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'radio-night', 'track': '01'}}]}}}}}

    def _set_device_config(self, token: Token, player_id: str) -> None:
        url = self.BASE_URL + "/device-v2/" + player_id + "/config"

        headers = self._get_authenticated_headers(token)

        response = requests.post(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Set Device Config Response: {response}")
        return response

    def _get_device_config(self, token: Token, player_id: str) -> None:
        url = self.BASE_URL + "/device-v2/" + player_id + "/config"

        headers = self._get_authenticated_headers(token)

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Device Config Response: {response}")
        return response
        #  2024-05-15 17:25:48,604 yoto_api.YotoAPI DEBUG:yoto_api - Get Device Config Response: {'device': {'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'name': '', 'errorCode': None, 'fwVersion': 'v2.17.5-5', 'popCode': 'FAJKEH', 'releaseChannelId': 'prerelease', 'releaseChannelVersion': 'v2.17.5-5', 'activationPopCode': 'IBSKCAAA', 'registrationCode': 'IBSKCAAA', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'mac': 'b4:8a:0a:92:7a:f4', 'online': True, 'geoTimezone': 'America/Edmonton', 'getPosix': 'MST7MDT,M3.2.0,M11.1.0', 'status': {'activeCard': 'none', 'aliveTime': None, 'als': 0, 'battery': None, 'batteryLevel': 100, 'batteryRemaining': None, 'bgDownload': 0, 'bluetoothHp': 0, 'buzzErrors': 0, 'bytesPS': 0, 'cardInserted': 0, 'chgStatLevel': None, 'charging': 0, 'day': 1, 'dayBright': None, 'dbatTimeout': None, 'dnowBrightness': None, 'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'errorsLogged': 164, 'failData': None, 'failReason': None, 'free': None, 'free32': None, 'freeDisk': 30219824, 'freeDMA': None, 'fwVersion': 'v2.17.5-5', 'headphones': 0, 'lastSeenAt': None, 'missedLogs': None, 'nfcErrs': 'n/a', 'nightBright': None, 'nightlightMode': '0x194a55', 'playingStatus': 0, 'powerCaps': '0x02', 'powerSrc': 2, 'qiOtp': None, 'sd_info': None, 'shutDown': None, 'shutdownTimeout': None, 'ssid': 'speed', 'statusVersion': None, 'temp': '0:24', 'timeFormat': None, 'totalDisk': 31385600, 'twdt': 0, 'updatedAt': '2024-05-15T23:23:45.284Z', 'upTime': 159925, 'userVolume': 31, 'utcOffset': -21600, 'utcTime': 1715815424, 'volume': 34, 'wifiRestarts': None, 'wifiStrength': -54}, 'config': {'locale': 'en', 'bluetoothEnabled': '1', 'repeatAll': True, 'showDiagnostics': True, 'btHeadphonesEnabled': True, 'pauseVolumeDown': False, 'pausePowerButton': True, 'displayDimTimeout': '60', 'shutdownTimeout': '3600', 'headphonesVolumeLimited': False, 'dayTime': '06:30', 'maxVolumeLimit': '16', 'ambientColour': '#40bfd9', 'dayDisplayBrightness': 'auto', 'dayYotoDaily': '3nC80/daily/<yyyymmdd>', 'dayYotoRadio': '3nC80/radio-day/01', 'daySoundsOff': '0', 'nightTime': '18:20', 'nightMaxVolumeLimit': '8', 'nightAmbientColour': '#f57399', 'nightDisplayBrightness': '100', 'nightYotoDaily': '0', 'nightYotoRadio': '0', 'nightSoundsOff': '1', 'hourFormat': '12', 'timezone': '', 'displayDimBrightness': '0', 'systemVolume': '87', 'volumeLevel': 'safe', 'clockFace': 'digital-sun', 'logLevel': 'none', 'alarms': []}, 'shortcuts': {'versionId': '36645a9463e038d6cb9923257b38d9d9df7a6509', 'modes': {'day': {'content': [{'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'daily', 'track': '<yyyymmdd>'}}, {'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'radio-day', 'track': '01'}}]}, 'night': {'content': [{'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'daily', 'track': '<yyyymmdd>'}}, {'cmd': 'track-play', 'params': {'card': '3nC80', 'chapter': 'radio-night', 'track': '01'}}]}}}}}

    def _set_device_config(self, token: Token, player_id: str) -> None:
        url = self.BASE_URL + "/device-v2/" + player_id + "/config"

        headers = self._get_authenticated_headers(token)

        response = requests.post(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Set Device Config Response: {response}")
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
