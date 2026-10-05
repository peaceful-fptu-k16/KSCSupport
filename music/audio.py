import math
import os
import shlex
import shutil
import subprocess
import sys
import threading
from array import array
from collections.abc import Callable
from typing import Any, Optional

import discord

from .effects import EQUALIZER_BANDS, EqualizerPreset


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36"
)

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


class CrossfadeAudio(discord.AudioSource):
    """Mixes consecutive PCM sources without stopping Discord voice playback."""

    FRAME_SIZE = 3840
    FRAMES_PER_SECOND = 50

    def __init__(
        self,
        original: discord.AudioSource,
        *,
        duration: Optional[int],
        on_transition: Callable[[Any, float], None],
    ) -> None:
        self.original = original
        self.duration = duration
        self.on_transition = on_transition
        self._next: Optional[discord.AudioSource] = None
        self._next_payload: Any = None
        self._next_duration: Optional[int] = None
        self._frames_played = 0
        self._transition_start = 0
        self._transition_frames = 0
        self._next_frames_read = 0
        self._mix_curve = "equal_power"
        self._premature_end = False
        self._lock = threading.RLock()
        self._cleaned = False

    def set_next(
        self,
        source: discord.AudioSource,
        payload: Any,
        *,
        duration: Optional[int],
        crossfade_seconds: float,
        start_at_seconds: Optional[float] = None,
        mix_curve: str = "equal_power",
        minimum_start_ratio: float = 0.88,
    ) -> bool:
        with self._lock:
            if self._cleaned or self._next is not None or not self.duration:
                source.cleanup()
                return False
            requested = max(1, round(crossfade_seconds * self.FRAMES_PER_SECOND))
            end_frame = max(1, round(self.duration * self.FRAMES_PER_SECOND))
            planned_start = (
                round(start_at_seconds * self.FRAMES_PER_SECOND)
                if start_at_seconds is not None
                else end_frame - requested
            )
            guarded_start = round(
                end_frame * max(0.5, min(0.98, minimum_start_ratio))
            )
            self._transition_start = max(
                self._frames_played,
                min(end_frame - 1, max(guarded_start, planned_start)),
            )
            self._transition_frames = max(1, end_frame - self._transition_start)
            self._next = source
            self._next_payload = payload
            self._next_duration = duration
            self._next_frames_read = 0
            self._mix_curve = mix_curve
            self._premature_end = False
            return True

    @property
    def next_ready(self) -> bool:
        with self._lock:
            return self._next is not None

    @property
    def premature_end(self) -> bool:
        with self._lock:
            return self._premature_end

    def clear_next(self) -> None:
        with self._lock:
            source = self._next
            self._next = None
            self._next_payload = None
            self._next_duration = None
            self._transition_frames = 0
            self._next_frames_read = 0
            self._mix_curve = "equal_power"
        if source:
            source.cleanup()

    def set_volume(self, volume: float) -> None:
        with self._lock:
            for source in (self.original, self._next):
                if isinstance(source, discord.PCMVolumeTransformer):
                    source.volume = volume

    def read(self) -> bytes:
        callback: Optional[tuple[Any, float]] = None
        with self._lock:
            if self._cleaned:
                return b""

            current = self.original.read()
            if not current:
                if not self._next:
                    return b""
                if self._frames_played < self._transition_start:
                    self._premature_end = True
                    return b""
                promoted = self._promote_locked()
                callback = (promoted, self._next_frames_read / self.FRAMES_PER_SECOND)
                data = self.original.read()
                self._frames_played += bool(data)
            elif not self._next or self._frames_played < self._transition_start:
                data = current
                self._frames_played += 1
            else:
                incoming = self._next.read()
                if not incoming:
                    self._next.cleanup()
                    self._next = None
                    self._next_payload = None
                    self._next_duration = None
                    self._transition_frames = 0
                    data = current
                    self._frames_played += 1
                else:
                    self._next_frames_read += 1
                    position = self._frames_played - self._transition_start + 1
                    progress = min(1.0, position / self._transition_frames)
                    data = self._mix(current, incoming, progress, self._mix_curve)
                    self._frames_played += 1
                    if position >= self._transition_frames:
                        payload = self._promote_locked()
                        callback = (payload, self._frames_played / self.FRAMES_PER_SECOND)

        if callback:
            payload, overlap = callback
            self.on_transition(payload, overlap)
        return data

    def _promote_locked(self) -> Any:
        previous = self.original
        payload = self._next_payload
        overlap_frames = self._next_frames_read
        self.original = self._next
        self.duration = self._next_duration
        self._frames_played = overlap_frames
        self._next = None
        self._next_payload = None
        self._next_duration = None
        self._transition_start = 0
        self._transition_frames = 0
        self._next_frames_read = 0
        self._mix_curve = "equal_power"
        self._premature_end = False
        previous.cleanup()
        return payload

    @staticmethod
    def _mix(
        current: bytes,
        incoming: bytes,
        progress: float,
        curve: str = "equal_power",
    ) -> bytes:
        if len(current) != len(incoming):
            return incoming if progress >= 0.5 else current
        left = array("h")
        right = array("h")
        left.frombytes(current)
        right.frombytes(incoming)
        if sys.byteorder != "little":
            left.byteswap()
            right.byteswap()
        if curve == "equal_power":
            old_gain = math.cos(progress * math.pi / 2)
            new_gain = math.sin(progress * math.pi / 2)
        else:
            old_gain = 1.0 - progress
            new_gain = progress
        for index in range(min(len(left), len(right))):
            mixed = round(left[index] * old_gain + right[index] * new_gain)
            left[index] = max(-32768, min(32767, mixed))
        if sys.byteorder != "little":
            left.byteswap()
        return left.tobytes()

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        with self._lock:
            if self._cleaned:
                return
            self._cleaned = True
            current = self.original
            incoming = self._next
            self._next = None
        current.cleanup()
        if incoming:
            incoming.cleanup()


class PipedFFmpegAudio(discord.AudioSource):
    """Feeds yt-dlp output directly into FFmpeg without an intermediate URL."""

    FRAME_SIZE = 3840

    def __init__(
        self,
        downloader: subprocess.Popen,
        *,
        executable: str,
        before_options: str = "",
        options: str = "",
    ) -> None:
        if not downloader.stdout:
            raise RuntimeError("Downloader stdout is unavailable")
        args = [executable]
        if before_options:
            args.extend(shlex.split(before_options))
        args.extend(
            (
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-loglevel",
                "warning",
            )
        )
        if options:
            args.extend(shlex.split(options))
        args.append("pipe:1")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.downloader = downloader
        self.ffmpeg = subprocess.Popen(
            args,
            stdin=downloader.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        downloader.stdout.close()
        self._cleaned = False

    def read(self) -> bytes:
        if not self.ffmpeg.stdout:
            return b""
        data = self.ffmpeg.stdout.read(self.FRAME_SIZE)
        return data if len(data) == self.FRAME_SIZE else b""

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        stdout = self.ffmpeg.stdout
        if stdout:
            stdout.close()
        self._stop_process(self.ffmpeg)
        self._stop_process(self.downloader)

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def build_before_options(seek_seconds: int = 0) -> str:
    seek = f"-ss {max(0, int(seek_seconds))} " if seek_seconds else ""
    return f"{seek}{FFMPEG_BEFORE_OPTIONS}"


def build_ffmpeg_options(audio_filter: str = "") -> str:
    return f'{FFMPEG_OPTIONS} -af "{audio_filter}"' if audio_filter else FFMPEG_OPTIONS


class _PeakingFilter:
    def __init__(self, frequency: float, gain_db: float, *, sample_rate: int = 48000) -> None:
        amplitude = 10 ** (gain_db / 40)
        omega = 2 * math.pi * frequency / sample_rate
        alpha = math.sin(omega) / 2
        cosine = math.cos(omega)
        a0 = 1 + alpha / amplitude
        self.b0 = (1 + alpha * amplitude) / a0
        self.b1 = (-2 * cosine) / a0
        self.b2 = (1 - alpha * amplitude) / a0
        self.a1 = (-2 * cosine) / a0
        self.a2 = (1 - alpha / amplitude) / a0
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, sample: float) -> float:
        output = (
            self.b0 * sample
            + self.b1 * self.x1
            + self.b2 * self.x2
            - self.a1 * self.y1
            - self.a2 * self.y2
        )
        self.x2 = self.x1
        self.x1 = sample
        self.y2 = self.y1
        self.y1 = output
        return output


class DynamicEqualizerAudio(discord.AudioSource):
    """Applies stereo EQ to PCM frames without replacing the Discord audio source."""

    def __init__(self, original: discord.AudioSource, preset: EqualizerPreset) -> None:
        self.original = original
        self._lock = threading.Lock()
        self._preset = preset
        self._filters = self._build_filters(preset)

    @property
    def preset(self) -> EqualizerPreset:
        return self._preset

    def set_preset(self, preset: EqualizerPreset) -> None:
        with self._lock:
            self._preset = preset
            self._filters = self._build_filters(preset)

    def read(self) -> bytes:
        data = self.original.read()
        if not data or self._preset is EqualizerPreset.BALANCED:
            return data

        samples = array("h")
        samples.frombytes(data)
        if sys.byteorder != "little":
            samples.byteswap()

        with self._lock:
            left_filters, right_filters = self._filters
            for index in range(0, len(samples) - 1, 2):
                left = float(samples[index])
                right = float(samples[index + 1])
                for audio_filter in left_filters:
                    left = audio_filter.process(left)
                for audio_filter in right_filters:
                    right = audio_filter.process(right)
                samples[index] = max(-32768, min(32767, round(left)))
                samples[index + 1] = max(-32768, min(32767, round(right)))

        if sys.byteorder != "little":
            samples.byteswap()
        return samples.tobytes()

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        self.original.cleanup()

    @staticmethod
    def _build_filters(
        preset: EqualizerPreset,
    ) -> tuple[list[_PeakingFilter], list[_PeakingFilter]]:
        bands = EQUALIZER_BANDS[preset]
        return (
            [_PeakingFilter(frequency, gain) for frequency, gain in bands],
            [_PeakingFilter(frequency, gain) for frequency, gain in bands],
        )


def get_ffmpeg_executable() -> str:
    configured = os.getenv("FFMPEG_BINARY") or os.getenv("FFMPEG_PATH")
    if configured:
        if os.path.isfile(configured) or shutil.which(configured):
            return configured
        raise RuntimeError(f"Configured FFmpeg executable not found: {configured}")

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "FFmpeg executable not found. Install FFmpeg, set FFMPEG_BINARY, "
            "or install imageio-ffmpeg."
        ) from exc
