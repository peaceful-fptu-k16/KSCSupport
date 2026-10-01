"""Core services for the KSC music bot."""

from .errors import MusicError
from .effects import AudioEffect, AudioProfile, EqualizerPreset
from .extractor import MediaExtractor
from .lyrics import LyricsService
from .models import LoopMode, PlaybackSnapshot, Track, TrackSource, format_duration
from .player import MusicPlayerManager
from .repository import MusicRepository

__all__ = [
    "LoopMode",
    "AudioEffect",
    "AudioProfile",
    "EqualizerPreset",
    "MediaExtractor",
    "MusicError",
    "MusicPlayerManager",
    "MusicRepository",
    "LyricsService",
    "PlaybackSnapshot",
    "Track",
    "TrackSource",
    "format_duration",
]
