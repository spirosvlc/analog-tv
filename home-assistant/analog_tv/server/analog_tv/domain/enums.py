from enum import StrEnum

class ChannelSourceType(StrEnum):
    FOLDER = "folder"
    M3U = "m3u"
    STREAM = "stream"
    YOUTUBE = "youtube"
    WEATHER = "weather"
    PLUTO = "pluto"

class AlertLevel(StrEnum):
    MEDIUM = "medium"
    SERIOUS = "serious"
    CRITICAL = "critical"
