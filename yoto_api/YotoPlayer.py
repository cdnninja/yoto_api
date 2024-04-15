"""YotoPlayers class"""

from dataclasses import dataclass
import datetime


@dataclass
class YotoPlayer:
    id: str = None
    name: str = None
    deviceType: str = None
    online: bool = None
    last_updated_at: datetime.datetime = None

# {'devices': [{'deviceId': 'y23IBS76kCaOSrGlz29XhIFO', 'name': 'Yoto Player', 'description': 'nameless.limit', 'online': False, 'releaseChannel': 'general', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'hasUserGivenName': False}]}
