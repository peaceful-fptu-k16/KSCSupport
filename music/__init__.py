"""Core services for the KSC music bot."""

from .errors import MusicError
from .effects import AudioEffect, EqualizerPreset
from .lyrics import LyricsService
from .models import LoopMode, Track, TrackSource, format_duration
from .player import MusicPlayerManager
from .repository import MusicRepository

__all__ = [
    "LoopMode",
    "AudioEffect",
    "EqualizerPreset",
    "MusicError",
    "MusicPlayerManager",
    "MusicRepository",
    "LyricsService",
    "Track",
    "TrackSource",
    "format_duration",
]
