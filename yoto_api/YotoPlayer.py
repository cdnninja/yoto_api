"""YotoPlayers class"""

from dataclasses import dataclass
import datetime


@dataclass
class YotoPlayer:
    id: str = None
    name: str = None
    device_type: str = None
    online: bool = None
    last_updated_at: datetime.datetime = None
    battery_level: int = None
    night_light_mode: str = None


# {'devices': [{'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'name': 'Yoto Player', 'description': 'nameless.limit', 'online': False, 'releaseChannel': 'general', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'hasUserGivenName': False}]}

# Mqtt response:

{
    "status": {
        "battery": 4174,
        "powerCaps": "0x02",
        "batteryLevel": 100,
        "batteryTemp": 0,
        "batteryData": "0:0:0",
        "batteryLevelRaw": 100,
        "free": 3875896,
        "freeDMA": 100298,
        "free32": 100638,
        "upTime": 130228,
        "utcTime": 1713713466,
        "aliveTime": 4103240,
        "qiOtp": 0,
        "nightlightMode": "0x194a55",
        "temp": "notSupported",
    }
}
