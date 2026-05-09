"""YotoPlayers class"""

from dataclasses import dataclass
import datetime
from typing import Optional, List


@dataclass
class Alarm:
    # raw api example. ['0000001,0700,4OD25,,,1,0']
    days_enabled: Optional[int] = None
    enabled: Optional[bool] = None
    time: Optional[datetime.time] = None
    volume: Optional[int] = None
    sound_id: Optional[str] = None


@dataclass
class YotoPlayerConfig:
    # Device Config
    day_mode_time: Optional[datetime.time] = None
    # Auto, or value
    day_display_brightness: Optional[str] = None
    # Values in HEX_COLORS in const
    day_ambient_colour: Optional[str] = None
    day_max_volume_limit: Optional[int] = None

    night_mode_time: Optional[datetime.time] = None
    # Auto, or value
    night_display_brightness: Optional[str] = None
    # Values in HEX_COLORS in const
    night_ambient_colour: Optional[str] = None
    night_max_volume_limit: Optional[int] = None
    alarms: Optional[List[Alarm]] = None


@dataclass
class YotoPlayer:
    # Device API
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    device_type: Optional[str] = None
    device_family: Optional[str] = None
    device_group: Optional[str] = None
    generation: Optional[str] = None
    form_factor: Optional[str] = None
    release_channel: Optional[str] = None
    online: Optional[bool] = None
    last_updated_at: Optional[datetime.datetime] = None

    # Status API
    active_card: Optional[str] = None
    is_playing: Optional[bool] = None
    playing_source: Optional[str] = None
    ambient_light_sensor_reading: Optional[int] = None
    day_mode_on: Optional[bool] = None
    night_light_mode: Optional[str] = None
    user_volume: Optional[int] = None
    system_volume: Optional[int] = None
    temperature_celcius: Optional[int] = None
    bluetooth_audio_connected: Optional[bool] = None
    charging: Optional[bool] = None
    audio_device_connected: Optional[bool] = None
    firmware_version: Optional[str] = None
    wifi_strength: Optional[int] = None
    power_source: Optional[str] = None
    last_updated_api: Optional[datetime.datetime] = None

    # Config
    config: Optional[YotoPlayerConfig] = None
    last_update_config: Optional[datetime.datetime] = None

    # MQTT
    card_id: Optional[str] = None
    repeat_all: Optional[bool] = None
    volume_max: Optional[int] = None
    volume: Optional[int] = None
    chapter_title: Optional[str] = None
    chapter_key: Optional[str] = None
    source: Optional[str] = None
    track_title: Optional[str] = None
    track_length: Optional[int] = None
    track_position: Optional[int] = None
    track_key: Optional[str] = None
    playback_status: Optional[str] = None
    sleep_timer_active: Optional[bool] = False
    sleep_timer_seconds_remaining: Optional[int] = 0
    battery_level_percentage: Optional[int] = None
    battery_temperature: Optional[int] = None


# {'devices': [{'deviceId': 'XXXX', 'name': 'Yoto Player', 'description': 'nameless.limit', 'online': False, 'releaseChannel': 'general', 'deviceType': 'v3', 'deviceFamily': 'v3', 'deviceGroup': '', 'hasUserGivenName': False}]}
# Device Status API: {'activeCard': 'none', 'ambientLightSensorReading': 0, 'averageDownloadSpeedBytesSecond': 0, 'batteryLevelPercentage': 100, 'buzzErrors': 0, 'cardInsertionState': 2, 'dayMode': 0, 'deviceId': 'XXXX', 'errorsLogged': 210, 'firmwareVersion': 'v2.17.5', 'freeDiskSpaceBytes': 30250544, 'isAudioDeviceConnected': False, 'isBackgroundDownloadActive': False, 'isBluetoothAudioConnected': False, 'isCharging': False, 'isOnline': True, 'networkSsid': 'XXXX', 'nightlightMode': '0x000000', 'playingSource': 0, 'powerCapabilities': '0x02', 'powerSource': 2, 'systemVolumePercentage': 47, 'taskWatchdogTimeoutCount': 0, 'temperatureCelcius': '20', 'totalDiskSpaceBytes': 31385600, 'updatedAt': '2024-04-23T01:26:19.927Z', 'uptime': 252342, 'userVolumePercentage': 50, 'utcOffsetSeconds': -21600, 'utcTime': 1713835609, 'wifiStrength': -61}
# Mqtt response:
