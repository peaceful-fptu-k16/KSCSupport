import asyncio
import hashlib
import logging
import math
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .audio import DEFAULT_USER_AGENT, get_ffmpeg_executable
from .models import Track


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrackAnalysis:
    bpm: float
    confidence: float
    loudness_db: float
    beat_offset: float = 0.0
    beat_interval: float = 0.0
    key_index: int = -1
    key_mode: str = "unknown"
    key_confidence: float = 0.0
    energy: float = 0.5
    vocal_activity: float = 0.5
    intro_end: float = 0.0
    drop_time: float = 0.0
    outro_start: float = 0.0
    downbeat_offset: float = 0.0
    structure_confidence: float = 0.0

    @property
    def key_label(self) -> str:
        if not 0 <= self.key_index < 12 or self.key_mode not in {"major", "minor"}:
            return "Unknown"
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        return f"{names[self.key_index]} {self.key_mode}"

    @property
    def camelot_key(self) -> str:
        if not 0 <= self.key_index < 12:
            return "--"
        major = ("8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B")
        minor = ("5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A")
        if self.key_mode == "major":
            return major[self.key_index]
        if self.key_mode == "minor":
            return minor[self.key_index]
        return "--"


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    mode: str
    crossfade_seconds: float
    tempo_ratio: float = 1.0
    start_at_seconds: Optional[float] = None
    phrase_bars: int = 0
    quality_score: int = 0
    harmonic_score: float = 0.0
    energy_delta: float = 0.0
    vocal_safe: bool = False
    mix_curve: str = "equal_power"

    @property
    def ffmpeg_filter(self) -> str:
        filters = ["dynaudnorm=f=150:g=15:p=0.95"]
        if abs(self.tempo_ratio - 1.0) >= 0.005:
            filters.append(f"atempo={self.tempo_ratio:.5f}")
        return ",".join(filters)


class TransitionPlanner:
    def __init__(self, default_crossfade: float = 6.0) -> None:
        self.default_crossfade = max(2.0, min(12.0, default_crossfade))
        self.phrase_bars = max(2, min(8, int(os.getenv("DJ_PHRASE_BARS", "4"))))
        self.vocal_threshold = max(
            0.5,
            min(0.95, float(os.getenv("DJ_VOCAL_THRESHOLD", "0.72"))),
        )
        self.energy_delta_threshold = max(
            0.2,
            min(0.8, float(os.getenv("DJ_ENERGY_DELTA_THRESHOLD", "0.42"))),
        )

    def plan(
        self,
        current: Track,
        incoming: Track,
        current_analysis: Optional[TrackAnalysis],
        incoming_analysis: Optional[TrackAnalysis],
    ) -> TransitionPlan:
        duration_cap = max(
            2.0,
            min(
                self.default_crossfade,
                (current.duration or 30) / 8,
                (incoming.duration or 30) / 8,
            ),
        )
        if not current_analysis or not incoming_analysis:
            return TransitionPlan("crossfade", duration_cap, quality_score=40)
        if min(current_analysis.confidence, incoming_analysis.confidence) < 0.35:
            return TransitionPlan("safe_fade", min(4.0, duration_cap), quality_score=35)

        current_bpm = self._normalized_bpm(current_analysis.bpm)
        incoming_bpm = self._normalized_bpm(incoming_analysis.bpm)
        ratio = current_bpm / max(1.0, incoming_bpm)
        tempo_score = max(0.0, 1.0 - abs(1.0 - ratio) / 0.12)
        harmonic_score = self.harmonic_compatibility(current_analysis, incoming_analysis)
        energy_delta = abs(current_analysis.energy - incoming_analysis.energy)
        energy_score = max(0.0, 1.0 - energy_delta / 0.6)
        vocal_peak = max(current_analysis.vocal_activity, incoming_analysis.vocal_activity)
        vocal_score = max(0.0, 1.0 - vocal_peak * 0.45)
        quality = round(
            100
            * (
                tempo_score * 0.35
                + harmonic_score * 0.30
                + energy_score * 0.20
                + vocal_score * 0.15
            )
        )

        if energy_delta >= self.energy_delta_threshold:
            return TransitionPlan(
                "energy_fade",
                min(3.0, duration_cap),
                quality_score=quality,
                harmonic_score=harmonic_score,
                energy_delta=energy_delta,
            )
        if harmonic_score < 0.45 and min(
            current_analysis.key_confidence,
            incoming_analysis.key_confidence,
        ) >= 0.2:
            return TransitionPlan(
                "harmonic_fade",
                min(3.5, duration_cap),
                quality_score=quality,
                harmonic_score=harmonic_score,
                energy_delta=energy_delta,
            )
        if vocal_peak >= self.vocal_threshold:
            return TransitionPlan(
                "vocal_safe",
                min(2.5, duration_cap),
                quality_score=quality,
                harmonic_score=harmonic_score,
                energy_delta=energy_delta,
                vocal_safe=True,
            )
        if 0.94 <= ratio <= 1.06:
            beat_interval = current_analysis.beat_interval or (60 / current_bpm)
            requested_beats = self.phrase_bars * 4
            available_seconds = min(
                12.0,
                (current.duration or 30) / 8,
                (incoming.duration or 30) / 8,
            )
            available_beats = max(8, int(available_seconds / beat_interval / 4) * 4)
            phrase_beats = min(requested_beats, available_beats)
            phrase_bars = max(2, phrase_beats // 4)
            target_start = max(0.0, (current.duration or 30) - phrase_beats * beat_interval)
            if current_analysis.structure_confidence >= 0.55 and current_analysis.outro_start > 0:
                target_start = max(target_start, current_analysis.outro_start)
            beat_offset = max(
                0.0,
                current_analysis.downbeat_offset
                if current_analysis.structure_confidence >= 0.55
                else current_analysis.beat_offset,
            )
            if target_start > beat_offset:
                beat_index = round((target_start - beat_offset) / beat_interval)
                start_at = beat_offset + beat_index * beat_interval
            else:
                start_at = target_start
            crossfade = max(2.0, (current.duration or 30) - start_at)
            return TransitionPlan(
                "beatmatch",
                min(12.0, crossfade),
                ratio,
                start_at_seconds=start_at,
                phrase_bars=phrase_bars,
                quality_score=quality,
                harmonic_score=harmonic_score,
                energy_delta=energy_delta,
            )
        return TransitionPlan(
            "safe_fade",
            min(4.0, duration_cap),
            quality_score=quality,
            harmonic_score=harmonic_score,
            energy_delta=energy_delta,
        )

    @staticmethod
    def harmonic_compatibility(current: TrackAnalysis, incoming: TrackAnalysis) -> float:
        if (
            current.key_index < 0
            or incoming.key_index < 0
            or current.key_mode not in {"major", "minor"}
            or incoming.key_mode not in {"major", "minor"}
        ):
            return 0.65
        if current.key_index == incoming.key_index and current.key_mode == incoming.key_mode:
            return 1.0

        # Relative major/minor pairs share the same pitch material.
        relative = (
            current.key_mode == "major"
            and incoming.key_mode == "minor"
            and incoming.key_index == (current.key_index + 9) % 12
        ) or (
            current.key_mode == "minor"
            and incoming.key_mode == "major"
            and incoming.key_index == (current.key_index + 3) % 12
        )
        if relative:
            return 0.92

        distance = (incoming.key_index - current.key_index) % 12
        if current.key_mode == incoming.key_mode and distance in {5, 7}:
            return 0.78
        if current.key_index == incoming.key_index:
            return 0.62
        return 0.2

    def smart_reorder_score(
        self,
        current: TrackAnalysis,
        incoming: TrackAnalysis,
        *,
        genre_match: float,
        popularity: float,
    ) -> float:
        current_bpm = self._normalized_bpm(current.bpm)
        incoming_bpm = self._normalized_bpm(incoming.bpm)
        ratio = current_bpm / max(1.0, incoming_bpm)
        bpm_score = max(0.0, 1.0 - abs(1.0 - ratio) / 0.15)
        key_score = self.harmonic_compatibility(current, incoming)
        energy_score = max(0.0, 1.0 - abs(current.energy - incoming.energy) / 0.7)
        return (
            0.30 * bpm_score
            + 0.25 * key_score
            + 0.20 * energy_score
            + 0.15 * max(0.0, min(1.0, genre_match))
            + 0.10 * max(0.0, min(1.0, popularity))
        )

    @staticmethod
    def _normalized_bpm(value: float) -> float:
        while value < 80:
            value *= 2
        while value > 180:
            value /= 2
        return value


class AutoDJAnalyzer:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or os.getenv("DJ_DATABASE_PATH", "data/autodj.db"))
        self.analysis_seconds = max(30, min(120, int(os.getenv("DJ_ANALYSIS_SECONDS", "75"))))
        self.structure_max_seconds = max(
            120,
            min(480, int(os.getenv("DJ_STRUCTURE_MAX_SECONDS", "360"))),
        )
        self.structure_enabled = os.getenv("DJ_STRUCTURE_ENABLED", "true").lower() not in {
            "0",
            "false",
            "off",
        }
        self.sample_rate = max(8000, min(22050, int(os.getenv("DJ_ANALYSIS_SAMPLE_RATE", "11025"))))
        self._analysis_slots = asyncio.Semaphore(
            max(1, min(3, int(os.getenv("DJ_ANALYSIS_CONCURRENCY", "2"))))
        )
        self.enabled = os.getenv("DJ_ANALYSIS_ENABLED", "true").lower() not in {"0", "false", "off"}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def analyze(self, track: Track) -> Optional[TrackAnalysis]:
        if not self.enabled:
            return None
        await self._initialize()
        key = hashlib.sha256(track.url.encode("utf-8")).hexdigest()
        cached = await asyncio.to_thread(self._load, key)
        if cached:
            return cached
        try:
            async with self._analysis_slots:
                analysis = await asyncio.to_thread(self._analyze_sync, track)
        except Exception:
            logger.exception("autodj_analysis_failed source=%s title=%r", track.source.value, track.title)
            return None
        if analysis:
            await asyncio.to_thread(self._save, key, track, analysis)
        return analysis

    async def _initialize(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._create_schema)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=15)

    def _create_schema(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS track_analysis (
                    track_key TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    bpm REAL NOT NULL,
                    confidence REAL NOT NULL,
                    loudness_db REAL NOT NULL,
                    beat_offset REAL NOT NULL DEFAULT 0,
                    beat_interval REAL NOT NULL DEFAULT 0,
                    key_index INTEGER NOT NULL DEFAULT -1,
                    key_mode TEXT NOT NULL DEFAULT 'unknown',
                    key_confidence REAL NOT NULL DEFAULT 0,
                    energy REAL NOT NULL DEFAULT 0.5,
                    vocal_activity REAL NOT NULL DEFAULT 0.5,
                    intro_end REAL NOT NULL DEFAULT 0,
                    drop_time REAL NOT NULL DEFAULT 0,
                    outro_start REAL NOT NULL DEFAULT 0,
                    downbeat_offset REAL NOT NULL DEFAULT 0,
                    structure_confidence REAL NOT NULL DEFAULT 0,
                    analysis_version INTEGER NOT NULL DEFAULT 5,
                    analyzed_at INTEGER NOT NULL DEFAULT (unixepoch())
                )
                """
            )
            columns = {
                str(row[1]) for row in db.execute("PRAGMA table_info(track_analysis)")
            }
            if "beat_offset" not in columns:
                db.execute(
                    "ALTER TABLE track_analysis ADD COLUMN beat_offset REAL NOT NULL DEFAULT 0"
                )
            if "beat_interval" not in columns:
                db.execute(
                    "ALTER TABLE track_analysis ADD COLUMN beat_interval REAL NOT NULL DEFAULT 0"
                )
            if "analysis_version" not in columns:
                db.execute(
                    "ALTER TABLE track_analysis ADD COLUMN analysis_version INTEGER NOT NULL DEFAULT 1"
                )
            migrations = {
                "key_index": "INTEGER NOT NULL DEFAULT -1",
                "key_mode": "TEXT NOT NULL DEFAULT 'unknown'",
                "key_confidence": "REAL NOT NULL DEFAULT 0",
                "energy": "REAL NOT NULL DEFAULT 0.5",
                "vocal_activity": "REAL NOT NULL DEFAULT 0.5",
                "intro_end": "REAL NOT NULL DEFAULT 0",
                "drop_time": "REAL NOT NULL DEFAULT 0",
                "outro_start": "REAL NOT NULL DEFAULT 0",
                "downbeat_offset": "REAL NOT NULL DEFAULT 0",
                "structure_confidence": "REAL NOT NULL DEFAULT 0",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    db.execute(
                        f"ALTER TABLE track_analysis ADD COLUMN {name} {definition}"
                    )

    def _load(self, key: str) -> Optional[TrackAnalysis]:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT bpm, confidence, loudness_db, beat_offset, beat_interval,
                       key_index, key_mode, key_confidence, energy, vocal_activity
                       , intro_end, drop_time, outro_start, downbeat_offset,
                       structure_confidence
                FROM track_analysis
                WHERE track_key = ? AND analysis_version >= 5
                """,
                (key,),
            ).fetchone()
        if not row:
            return None
        return TrackAnalysis(
            bpm=float(row[0]),
            confidence=float(row[1]),
            loudness_db=float(row[2]),
            beat_offset=float(row[3]),
            beat_interval=float(row[4]),
            key_index=int(row[5]),
            key_mode=str(row[6]),
            key_confidence=float(row[7]),
            energy=float(row[8]),
            vocal_activity=float(row[9]),
            intro_end=float(row[10]),
            drop_time=float(row[11]),
            outro_start=float(row[12]),
            downbeat_offset=float(row[13]),
            structure_confidence=float(row[14]),
        )

    def _save(self, key: str, track: Track, analysis: TrackAnalysis) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO track_analysis(
                    track_key, url, title, bpm, confidence, loudness_db,
                    beat_offset, beat_interval, key_index, key_mode,
                    key_confidence, energy, vocal_activity, analysis_version
                    , intro_end, drop_time, outro_start, downbeat_offset,
                    structure_confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 5, ?, ?, ?, ?, ?)
                ON CONFLICT(track_key) DO UPDATE SET
                    bpm=excluded.bpm,
                    confidence=excluded.confidence,
                    loudness_db=excluded.loudness_db,
                    beat_offset=excluded.beat_offset,
                    beat_interval=excluded.beat_interval,
                    key_index=excluded.key_index,
                    key_mode=excluded.key_mode,
                    key_confidence=excluded.key_confidence,
                    energy=excluded.energy,
                    vocal_activity=excluded.vocal_activity,
                    intro_end=excluded.intro_end,
                    drop_time=excluded.drop_time,
                    outro_start=excluded.outro_start,
                    downbeat_offset=excluded.downbeat_offset,
                    structure_confidence=excluded.structure_confidence,
                    analysis_version=5,
                    analyzed_at=unixepoch()
                """,
                (
                    key,
                    track.url,
                    track.title,
                    analysis.bpm,
                    analysis.confidence,
                    analysis.loudness_db,
                    analysis.beat_offset,
                    analysis.beat_interval,
                    analysis.key_index,
                    analysis.key_mode,
                    analysis.key_confidence,
                    analysis.energy,
                    analysis.vocal_activity,
                    analysis.intro_end,
                    analysis.drop_time,
                    analysis.outro_start,
                    analysis.downbeat_offset,
                    analysis.structure_confidence,
                ),
            )

    def _analyze_sync(self, track: Track) -> Optional[TrackAnalysis]:
        try:
            import librosa
            import numpy as np
        except ImportError:
            logger.warning("autodj_analysis_disabled missing=librosa")
            self.enabled = False
            return None

        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--quiet",
            "--no-warnings",
            "--no-playlist",
            "--no-check-certificates",
            "--socket-timeout",
            "20",
            "--user-agent",
            DEFAULT_USER_AGENT,
            "--format",
            "bestaudio/best",
            "--output",
            "-",
        ]
        cookie_file = os.getenv("YTDLP_COOKIE_FILE")
        if cookie_file:
            command.extend(("--cookies", cookie_file))
        command.extend(("--", track.url))

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        downloader = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if not downloader.stdout:
            downloader.terminate()
            return None
        analysis_duration = self.analysis_seconds
        if self.structure_enabled and track.duration:
            analysis_duration = min(track.duration, self.structure_max_seconds)
        ffmpeg = subprocess.Popen(
            [
                get_ffmpeg_executable(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-t",
                str(analysis_duration),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(self.sample_rate),
                "-f",
                "f32le",
                "pipe:1",
            ],
            stdin=downloader.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        downloader.stdout.close()
        try:
            raw, _ = ffmpeg.communicate(timeout=max(90, analysis_duration))
        except subprocess.TimeoutExpired:
            ffmpeg.kill()
            ffmpeg.communicate()
            logger.warning("autodj_decode_timeout title=%r", track.title)
            return None
        finally:
            if downloader.poll() is None:
                downloader.terminate()
            try:
                downloader.wait(timeout=3)
            except subprocess.TimeoutExpired:
                downloader.kill()
        if ffmpeg.returncode not in {0, None} or not raw:
            return None

        samples = np.frombuffer(raw, dtype=np.float32)
        if samples.size < self.sample_rate * 10:
            return None
        feature_samples = samples[: self.analysis_seconds * self.sample_rate]
        onset = librosa.onset.onset_strength(y=samples, sr=self.sample_rate)
        tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=self.sample_rate)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        expected = max(1.0, samples.size / self.sample_rate / 60 * max(1.0, bpm))
        confidence = min(1.0, len(beats) / expected)
        rms = librosa.feature.rms(y=feature_samples)[0]
        loudness = 20 * math.log10(max(1e-6, float(np.median(rms))))
        beat_times = librosa.frames_to_time(beats, sr=self.sample_rate)
        beat_offset = float(beat_times[0]) if len(beat_times) else 0.0
        beat_interval = (
            float(np.median(np.diff(beat_times)))
            if len(beat_times) > 1
            else 60 / max(1.0, bpm)
        )
        key_index, key_mode, key_confidence = self._estimate_key(
            librosa,
            np,
            feature_samples,
            self.sample_rate,
        )
        energy = float(np.clip((loudness + 36.0) / 24.0, 0.0, 1.0))
        harmonic, _percussive = librosa.effects.hpss(feature_samples)
        harmonic_rms = float(np.median(librosa.feature.rms(y=harmonic)[0]))
        total_rms = max(1e-6, float(np.median(rms)))
        vocal_activity = float(np.clip((harmonic_rms / total_rms - 0.35) / 0.65, 0.0, 1.0))
        (
            intro_end,
            drop_time,
            outro_start,
            downbeat_offset,
            structure_confidence,
        ) = self._detect_structure(
            librosa,
            np,
            samples,
            self.sample_rate,
            onset,
            beat_times,
            track.duration,
            beat_interval,
        )
        return TrackAnalysis(
            bpm=bpm,
            confidence=confidence,
            loudness_db=loudness,
            beat_offset=beat_offset,
            beat_interval=beat_interval,
            key_index=key_index,
            key_mode=key_mode,
            key_confidence=key_confidence,
            energy=energy,
            vocal_activity=vocal_activity,
            intro_end=intro_end,
            drop_time=drop_time,
            outro_start=outro_start,
            downbeat_offset=downbeat_offset,
            structure_confidence=structure_confidence,
        )

    @staticmethod
    def _estimate_key(librosa, np, samples, sample_rate: int) -> tuple[int, str, float]:
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate)
        profile = np.mean(chroma, axis=1)
        norm = float(np.linalg.norm(profile))
        if norm <= 1e-9:
            return -1, "unknown", 0.0
        profile = profile / norm
        major_template = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        )
        minor_template = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        )
        scores: list[tuple[float, int, str]] = []
        for root in range(12):
            for mode, template in (("major", major_template), ("minor", minor_template)):
                rotated = np.roll(template, root)
                rotated = rotated / np.linalg.norm(rotated)
                scores.append((float(np.dot(profile, rotated)), root, mode))
        scores.sort(reverse=True)
        best, second = scores[0], scores[1]
        confidence = float(np.clip((best[0] - second[0]) * 8.0, 0.0, 1.0))
        return best[1], best[2], confidence

    @staticmethod
    def _detect_structure(
        librosa,
        np,
        samples,
        sample_rate: int,
        onset,
        beat_times,
        track_duration: Optional[int],
        beat_interval: float,
    ) -> tuple[float, float, float, float, float]:
        hop_length = 512
        rms = librosa.feature.rms(y=samples, hop_length=hop_length)[0]
        times = librosa.frames_to_time(
            np.arange(len(rms)),
            sr=sample_rate,
            hop_length=hop_length,
        )
        if not len(rms) or not len(times):
            return 0.0, 0.0, 0.0, 0.0, 0.0

        window = max(1, round(sample_rate / hop_length * 2.0))
        smooth = np.convolve(rms, np.ones(window) / window, mode="same")
        median_energy = max(1e-7, float(np.median(smooth)))
        intro_limit = min(float(times[-1]) * 0.35, 45.0)
        intro_candidates = np.where(
            (times >= 3.0)
            & (times <= intro_limit)
            & (smooth >= median_energy * 0.82)
        )[0]
        intro_end = float(times[intro_candidates[0]]) if len(intro_candidates) else 8.0

        lookback = max(1, round(sample_rate / hop_length * 2.0))
        rises = smooth - np.roll(smooth, lookback)
        rises[:lookback] = 0
        drop_mask = (times >= intro_end + 3.0) & (times <= min(float(times[-1]) * 0.7, 120.0))
        drop_indices = np.where(drop_mask)[0]
        drop_time = (
            float(times[drop_indices[int(np.argmax(rises[drop_indices]))]])
            if len(drop_indices)
            else intro_end
        )

        detected_duration = float(times[-1])
        effective_duration = float(track_duration or detected_duration)
        outro_mask = (times >= detected_duration * 0.65) & (smooth <= median_energy * 0.72)
        outro_indices = np.where(outro_mask)[0]
        fallback_outro = max(drop_time + 8.0, effective_duration - max(8.0, beat_interval * 16))
        outro_start = float(times[outro_indices[0]]) if len(outro_indices) else fallback_outro
        outro_start = min(effective_duration, max(drop_time + 4.0, outro_start))

        downbeat_offset = float(beat_times[0]) if len(beat_times) else 0.0
        if len(beat_times) >= 8:
            beat_frames = librosa.time_to_frames(
                beat_times,
                sr=sample_rate,
                hop_length=hop_length,
            )
            beat_strengths = [
                float(onset[min(len(onset) - 1, max(0, int(frame)))])
                for frame in beat_frames
            ]
            phase_scores = [sum(beat_strengths[phase::4]) for phase in range(4)]
            phase = int(np.argmax(phase_scores))
            downbeat_offset = float(beat_times[phase])

        coverage = min(1.0, detected_duration / max(1.0, effective_duration))
        marker_score = sum((intro_end > 0, drop_time > intro_end, outro_start > drop_time)) / 3
        structure_confidence = float(np.clip(coverage * 0.65 + marker_score * 0.35, 0.0, 1.0))
        return intro_end, drop_time, outro_start, downbeat_offset, structure_confidence
