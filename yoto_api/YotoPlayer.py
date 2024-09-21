"""YotoPlayers class"""

from dataclasses import dataclass
import datetime


@dataclass
class Alarm:
    # raw api example. ['0000001,0700,4OD25,,,1,0']
    days_enabled: int = None
    enabled: bool = None
    time: datetime.time = None
    volume: int = None
    sound_id: str = None


@dataclass
class YotoPlayerConfig:
    # Device Config
    day_mode_time: datetime.time = None
    # Auto, or value
    day_display_brightness: str = None
    # Values in HEX_COLORS in const
    day_ambient_colour: str = None
    day_max_volume_limit: int = None

    night_mode_time: datetime.time = None
    # Auto, or value
    night_display_brightness: str = None
    # Values in HEX_COLORS in const
    night_ambient_colour: str = None
    night_max_volume_limit: int = None
    alarms: list = None


@dataclass
class YotoPlayer:
    # Device API
    id: str = None
    name: str = None
    device_type: str = None
    online: bool = None
    last_updated_at: datetime.datetime = None

    # Status API
    active_card: str = None
    is_playing: bool = None
    playing_source: str = None
    ambient_light_sensor_reading: int = None
    battery_level_percentage: int = None
    day_mode_on: bool = None
    night_light_mode: str = None
    user_volume: int = None
    system_volume: int = None
    temperature_celcius: int = None
    bluetooth_audio_connected: bool = None
    charging: bool = None
    audio_device_connected: bool = None
    firmware_version: str = None
    wifi_strength: int = None
    power_source: str = None
    last_updated_api: datetime.datetime = None

    # Config
    config: YotoPlayerConfig = None
    last_update_config: datetime.datetime = None

    # MQTT
    card_id: str = None
    repeat_all: bool = None
    volume_max: int = None
    volume: int = None
    chapter_title: str = None
    chapter_key: str = None
    source: str = None
    track_title: str = None
    track_length: int = None
    track_position: int = None
    track_key: str = None
    playback_status: str = None
    sleep_timer_active: bool = False
    sleep_timer_seconds_remaining: int = 0


# {'devices': [{'deviceId': 'XXXX', 'name': 'Yoto Player', 'description': 'nameless.limit', 'online': False, 'releaseChannel': 'general', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'hasUserGivenName': False}]}
# Device Status API: {'activeCard': 'none', 'ambientLightSensorReading': 0, 'averageDownloadSpeedBytesSecond': 0, 'batteryLevelPercentage': 100, 'buzzErrors': 0, 'cardInsertionState': 2, 'dayMode': 0, 'deviceId': 'XXXX', 'errorsLogged': 210, 'firmwareVersion': 'v2.17.5', 'freeDiskSpaceBytes': 30250544, 'isAudioDeviceConnected': False, 'isBackgroundDownloadActive': False, 'isBluetoothAudioConnected': False, 'isCharging': False, 'isOnline': True, 'networkSsid': 'XXXX', 'nightlightMode': '0x000000', 'playingSource': 0, 'powerCapabilities': '0x02', 'powerSource': 2, 'systemVolumePercentage': 47, 'taskWatchdogTimeoutCount': 0, 'temperatureCelcius': '20', 'totalDiskSpaceBytes': 31385600, 'updatedAt': '2024-04-23T01:26:19.927Z', 'uptime': 252342, 'userVolumePercentage': 50, 'utcOffsetSeconds': -21600, 'utcTime': 1713835609, 'wifiStrength': -61}
# Mqtt response:
