"""API Methods"""

import requests
import logging
from auth0.authentication import GetToken
import paho.mqtt.client as mqtt 


_LOGGER = logging.getLogger(__name__)


class YotoAPI(self):
    def __init__(self) -> None:
        self.AUDIENCE: str = "https://api.yotoplay.com"
        self.BASE_URL: str = "https://api.yotoplay.com"
        self.CLIENT_ID: str = "cIQ241O2gouOOAwFFvxuGVkHGT3LL6rn"
        self.LOGIN_URL: str = "login.yotoplay.com"
        self.SCOPE: str = "YOUR_SCOPE"
        self.MQTT_AUTH_NAME: str = "JwtAuthorizer_mGDDmvLsocFY"
        self.MQTT_URL: str  = "wss://aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"

    def login(self, username: str, password: str) -> Token:
        token = GetToken(self.LOGIN_URL, self.CLIENT_ID, client_secret=self.CLIENT_ID)
        token.login(username=username, password=password, realm="Username-Password-Authentication")
        return token
    
    def get_devices(self, token) -> None:
        url = self.BASE_URL + "/device-v2/devices/mine"
        
        response = requests.get(
            url
        ).json()
        _LOGGER.debug(f"{DOMAIN} - Get Devices Response: {response}")
        return response

    def get_cards(self, token) -> dict:
        ############## Details below from snooping JSON requests of the app ######################
        
        ############## ${BASE_URL}/auth/token #############
        # Request POST contents:
        # audience=https%3A//api.yotoplay.com&client_id=i42noid4b2oiboi4bo&grant_type=password&password=sndoinoinscoif&scope=openid%20email%20profile%20offline_access&username=anonymous%40gmail.com
        
        ############## ${BASE_URL}/card/family/library #############
        url = self.BASE_URL + "/card/family/library"
        
        response = requests.post(
            url
        ).json()
        _LOGGER.debug(f"{DOMAIN} - Get Card Library: {response}")
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

    def get_card_detail(self, token, cardid) -> dict:
        ############## Details below from snooping JSON requests of the app ######################
        
        url = self.BASE_URL + "/card/details/" + cardid
        
        response = requests.post(
            url
        ).json()
        _LOGGER.debug(f"{DOMAIN} - Get Card Library: {response}")
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

