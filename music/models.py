from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Optional

from .effects import AudioProfile


class TrackSource(str, Enum):
    YOUTUBE = "YouTube"
    SOUNDCLOUD = "SoundCloud"


class LoopMode(str, Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

    @classmethod
    def parse(cls, value: str) -> "LoopMode":
        aliases = {"song": "track", "bai": "track", "hangcho": "queue"}
        return cls(aliases.get(value.lower(), value.lower()))


@dataclass(frozen=True, slots=True)
class AudioAnalysisSummary:
    bpm: float
    key: str
    key_name: str
    key_confidence: float
    energy: float
    vocal_activity: float


@dataclass(frozen=True, slots=True)
class Track:
    title: str
    url: str
    source: TrackSource
    duration: Optional[int] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None
    requester_id: Optional[int] = None
    requester_name: Optional[str] = None
    view_count: Optional[int] = None
    upload_date: Optional[str] = None
    channel_id: Optional[str] = None
    channel_verified: bool = False
    is_official: bool = False
    view_growth_7d: Optional[int] = None
    discovery_text: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    current: Optional[Track]
    queue: tuple[Track, ...]
    volume: float
    loop_mode: LoopMode
    elapsed: int = 0
    audio_profile: AudioProfile = AudioProfile()
    fair_queue: bool = False
    autoplay: bool = False
    radio_label: Optional[str] = None
    dj_mix: bool = False
    analysis: Optional[AudioAnalysisSummary] = None
    analysis_pending: bool = False
    smart_reorder: bool = False


@dataclass
class PlaybackState:
    queue: deque[Track] = field(default_factory=deque)
    current: Optional[Track] = None
    volume: float = 0.5
    loop_mode: LoopMode = LoopMode.OFF
    generation: int = 0
    skip_requested: bool = False
    started_at: Optional[float] = None
    paused_at: Optional[float] = None
    paused_seconds: float = 0.0
    playback_offset: float = 0.0
    playback_speed: float = 1.0
    audio_profile: AudioProfile = field(default_factory=AudioProfile)
    fair_queue: bool = False
    autoplay: bool = False
    radio_label: Optional[str] = None
    dj_mix: bool = False
    smart_reorder: bool = False
    last_requester_id: Optional[int] = None
    priority_count: int = 0

    def enqueue(self, tracks: list[Track]) -> None:
        self.queue.extend(tracks)

    def enqueue_front(self, tracks: list[Track]) -> None:
        for track in reversed(tracks):
            self.queue.appendleft(track)
        self.priority_count += len(tracks)

    def claim_next(self) -> Optional[Track]:
        if self.current or not self.queue:
            return None
        if self.priority_count:
            self.current = self.queue.popleft()
            self.priority_count -= 1
        elif self.fair_queue and self.last_requester_id is not None:
            next_index = next(
                (
                    index
                    for index, track in enumerate(self.queue)
                    if track.requester_id != self.last_requester_id
                ),
                0,
            )
            self.queue.rotate(-next_index)
            self.current = self.queue.popleft()
        else:
            self.current = self.queue.popleft()
        self.last_requester_id = self.current.requester_id
        self.skip_requested = False
        self.started_at = None
        self.paused_at = None
        self.paused_seconds = 0.0
        self.generation += 1
        return self.current

    def peek_next(self) -> Optional[Track]:
        if not self.queue:
            return None
        if self.priority_count:
            return self.queue[0]
        if self.fair_queue and self.last_requester_id is not None:
            return next(
                (
                    track
                    for track in self.queue
                    if track.requester_id != self.last_requester_id
                ),
                self.queue[0],
            )
        return self.queue[0]

    def promote(self, track: Track, *, offset: float = 0.0, speed: float = 1.0) -> bool:
        try:
            index = self.queue.index(track)
            self.queue.remove(track)
        except ValueError:
            return False
        if index < self.priority_count:
            self.priority_count -= 1
        self.current = track
        self.last_requester_id = track.requester_id
        self.skip_requested = False
        self.mark_started(offset=offset, speed=speed)
        return True

    def mark_started(self, *, offset: float = 0.0, speed: float = 1.0) -> None:
        self.started_at = time.time()
        self.paused_at = None
        self.paused_seconds = 0.0
        self.playback_offset = max(0.0, offset)
        self.playback_speed = max(0.1, speed)

    def mark_paused(self) -> None:
        if self.current and self.started_at is not None and self.paused_at is None:
            self.paused_at = time.time()

    def mark_resumed(self) -> None:
        if self.paused_at is not None:
            self.paused_seconds += time.time() - self.paused_at
            self.paused_at = None

    def elapsed(self) -> int:
        if self.started_at is None:
            return 0
        reference = self.paused_at if self.paused_at is not None else time.time()
        played = (reference - self.started_at - self.paused_seconds) * self.playback_speed
        return max(0, int(self.playback_offset + played))

    def finish_current(self, *, skipped: bool = False, failed: bool = False) -> None:
        finished = self.current
        if finished and not skipped and not failed:
            if self.loop_mode is LoopMode.TRACK:
                self.queue.appendleft(finished)
                self.priority_count += 1
            elif self.loop_mode is LoopMode.QUEUE:
                self.queue.append(finished)
        self.current = None
        self.skip_requested = False
        self.started_at = None
        self.paused_at = None
        self.paused_seconds = 0.0
        self.playback_offset = 0.0
        self.playback_speed = 1.0

    def invalidate(self, *, clear_queue: bool, reset_loop: bool = False) -> None:
        self.generation += 1
        self.current = None
        self.skip_requested = False
        self.started_at = None
        self.paused_at = None
        self.paused_seconds = 0.0
        self.playback_offset = 0.0
        self.playback_speed = 1.0
        if clear_queue:
            self.queue.clear()
            self.priority_count = 0
        if reset_loop:
            self.loop_mode = LoopMode.OFF

    def snapshot(self) -> PlaybackSnapshot:
        return PlaybackSnapshot(
            current=self.current,
            queue=tuple(self.queue),
            volume=self.volume,
            loop_mode=self.loop_mode,
            elapsed=self.elapsed(),
            audio_profile=self.audio_profile,
            fair_queue=self.fair_queue,
            autoplay=self.autoplay,
            radio_label=self.radio_label,
            dj_mix=self.dj_mix,
            smart_reorder=self.smart_reorder,
        )


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "live/không rõ"
    minutes, second = divmod(int(seconds), 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours}:{minute:02d}:{second:02d}" if hours else f"{minute}:{second:02d}"


def shorten_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def format_listening_time(seconds: int) -> str:
    seconds = max(0, seconds)
    if seconds < 60:
        return f"{seconds} giây"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} giờ {minutes} phút" if hours else f"{minutes} phút"


def format_compact_number(value: Optional[int], *, unknown: str = "Chưa rõ") -> str:
    if value is None:
        return unknown
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)
