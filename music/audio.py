import math
import os
import shlex
import shutil
import subprocess
import sys
import threading
from array import array

import discord

from .effects import EQUALIZER_BANDS, EqualizerPreset


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36"
)

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


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
