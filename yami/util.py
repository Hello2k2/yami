from enum import Enum

SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".mp4", ".avi", ".mkv")
BUTTON_WIDTH = 10
GEOMETRY = "847x681"
TITLE = "Music Player"
EVENT_INTERVAL = 50


class PlayerState(Enum):
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3
