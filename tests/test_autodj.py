import unittest
import sqlite3
import tempfile
from array import array
from contextlib import closing
from pathlib import Path

import discord

from music.audio import CrossfadeAudio
from music.autodj import AutoDJAnalyzer, TrackAnalysis, TransitionPlanner
from music.models import Track, TrackSource


class FrameSource(discord.AudioSource):
    def __init__(self, value: int, frames: int) -> None:
        self.frame = array("h", [value] * 1920).tobytes()
        self.frames = frames
        self.cleaned = False

    def read(self) -> bytes:
        if self.frames <= 0:
            return b""
        self.frames -= 1
        return self.frame

    def is_opus(self) -> bool:
        return False

    def cleanup(self) -> None:
        self.cleaned = True


def track(title: str, duration: int = 240) -> Track:
    return Track(title, f"https://example.com/{title}", TrackSource.YOUTUBE, duration=duration)


class CrossfadeAudioTests(unittest.TestCase):
    def test_crossfade_mixes_frames_and_promotes_without_ending_stream(self) -> None:
        transitions = []
        current = FrameSource(1000, 4)
        incoming = FrameSource(3000, 5)
        source = CrossfadeAudio(
            current,
            duration=0.08,
            on_transition=lambda payload, overlap: transitions.append((payload, overlap)),
        )

        self.assertTrue(
            source.set_next(
                incoming,
                "next",
                duration=0.1,
                crossfade_seconds=0.04,
                minimum_start_ratio=0.5,
            )
        )
        samples = []
        for _ in range(5):
            frame = source.read()
            values = array("h")
            values.frombytes(frame)
            samples.append(values[0])

        self.assertEqual(samples, [1000, 1000, 2828, 3000, 3000])
        self.assertEqual(transitions[0][0], "next")
        self.assertAlmostEqual(transitions[0][1], 0.04, places=2)
        self.assertTrue(current.cleaned)
        self.assertFalse(incoming.cleaned)

    def test_clear_next_cleans_prefetched_source(self) -> None:
        source = CrossfadeAudio(
            FrameSource(1000, 5),
            duration=10,
            on_transition=lambda _payload, _overlap: None,
        )
        incoming = FrameSource(2000, 5)
        source.set_next(incoming, "next", duration=10, crossfade_seconds=4)

        source.clear_next()

        self.assertTrue(incoming.cleaned)

    def test_explicit_start_time_controls_crossfade_boundary(self) -> None:
        source = CrossfadeAudio(
            FrameSource(1000, 6),
            duration=0.12,
            on_transition=lambda _payload, _overlap: None,
        )
        source.set_next(
            FrameSource(3000, 6),
            "next",
            duration=0.12,
            crossfade_seconds=0.08,
            start_at_seconds=0.06,
            minimum_start_ratio=0.5,
        )

        samples = []
        for _ in range(4):
            values = array("h")
            values.frombytes(source.read())
            samples.append(values[0])

        self.assertEqual(samples[:3], [1000, 1000, 1000])
        self.assertGreater(samples[3], 1000)

    def test_premature_source_end_never_promotes_prefetched_track(self) -> None:
        transitions = []
        source = CrossfadeAudio(
            FrameSource(1000, 2),
            duration=10,
            on_transition=lambda payload, overlap: transitions.append((payload, overlap)),
        )
        incoming = FrameSource(3000, 10)
        source.set_next(
            incoming,
            "next",
            duration=10,
            crossfade_seconds=2,
            minimum_start_ratio=0.9,
        )

        self.assertTrue(source.read())
        self.assertTrue(source.read())
        self.assertEqual(source.read(), b"")

        self.assertTrue(source.premature_end)
        self.assertEqual(transitions, [])
        self.assertFalse(incoming.cleaned)

    def test_minimum_playback_ratio_guards_transition_start(self) -> None:
        source = CrossfadeAudio(
            FrameSource(1000, 500),
            duration=10,
            on_transition=lambda _payload, _overlap: None,
        )
        source.set_next(
            FrameSource(3000, 500),
            "next",
            duration=10,
            crossfade_seconds=8,
            start_at_seconds=1,
            minimum_start_ratio=0.9,
        )

        self.assertEqual(source._transition_start, 450)


class TransitionPlannerTests(unittest.TestCase):
    def test_close_confident_bpms_enable_beatmatch(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        plan = planner.plan(
            track("a"),
            track("b"),
            TrackAnalysis(120, 0.8, -14),
            TrackAnalysis(124, 0.8, -16),
        )

        self.assertEqual(plan.mode, "beatmatch")
        self.assertAlmostEqual(plan.tempo_ratio, 120 / 124, places=3)
        self.assertIn("atempo=", plan.ffmpeg_filter)

    def test_beatmatch_starts_on_phrase_aligned_beat(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        analysis = TrackAnalysis(
            120,
            0.9,
            -14,
            beat_offset=0.25,
            beat_interval=0.5,
        )

        plan = planner.plan(track("a"), track("b"), analysis, analysis)

        self.assertEqual(plan.mode, "beatmatch")
        self.assertEqual(plan.phrase_bars, 4)
        self.assertIsNotNone(plan.start_at_seconds)
        beat_position = (plan.start_at_seconds - analysis.beat_offset) / analysis.beat_interval
        self.assertAlmostEqual(beat_position, round(beat_position), places=6)
        self.assertLessEqual(plan.crossfade_seconds, 12)

    def test_uncertain_or_distant_bpm_uses_safe_fade(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        uncertain = planner.plan(
            track("a"),
            track("b"),
            TrackAnalysis(120, 0.2, -14),
            TrackAnalysis(122, 0.8, -16),
        )
        distant = planner.plan(
            track("a"),
            track("b"),
            TrackAnalysis(100, 0.8, -14),
            TrackAnalysis(140, 0.8, -16),
        )

        self.assertEqual(uncertain.mode, "safe_fade")
        self.assertEqual(distant.mode, "safe_fade")
        self.assertNotIn("atempo=", distant.ffmpeg_filter)

    def test_relative_keys_keep_harmonic_beatmatch(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        c_major = TrackAnalysis(120, 0.9, -14, key_index=0, key_mode="major", key_confidence=0.8)
        a_minor = TrackAnalysis(122, 0.9, -14, key_index=9, key_mode="minor", key_confidence=0.8)

        plan = planner.plan(track("c-major"), track("a-minor"), c_major, a_minor)

        self.assertEqual(plan.mode, "beatmatch")
        self.assertGreaterEqual(plan.harmonic_score, 0.9)
        self.assertGreater(plan.quality_score, 70)

    def test_incompatible_confident_keys_use_short_harmonic_fade(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        current = TrackAnalysis(120, 0.9, -14, key_index=0, key_mode="major", key_confidence=0.8)
        incoming = TrackAnalysis(121, 0.9, -14, key_index=1, key_mode="major", key_confidence=0.8)

        plan = planner.plan(track("c-major"), track("c-sharp"), current, incoming)

        self.assertEqual(plan.mode, "harmonic_fade")
        self.assertLessEqual(plan.crossfade_seconds, 3.5)

    def test_vocal_heavy_tracks_avoid_long_overlap(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        current = TrackAnalysis(120, 0.9, -14, vocal_activity=0.85)
        incoming = TrackAnalysis(121, 0.9, -14, vocal_activity=0.8)

        plan = planner.plan(track("vocal-a"), track("vocal-b"), current, incoming)

        self.assertEqual(plan.mode, "vocal_safe")
        self.assertTrue(plan.vocal_safe)
        self.assertLessEqual(plan.crossfade_seconds, 2.5)

    def test_smart_reorder_score_prefers_compatible_track(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        current = TrackAnalysis(120, 0.9, -14, key_index=0, key_mode="major", energy=0.55)
        compatible = TrackAnalysis(123, 0.9, -14, key_index=9, key_mode="minor", energy=0.6)
        difficult = TrackAnalysis(150, 0.9, -9, key_index=1, key_mode="major", energy=0.95)

        good_score = planner.smart_reorder_score(
            current,
            compatible,
            genre_match=1,
            popularity=0.8,
        )
        difficult_score = planner.smart_reorder_score(
            current,
            difficult,
            genre_match=1,
            popularity=0.8,
        )

        self.assertGreater(good_score, difficult_score)
        self.assertGreater(good_score, 0.8)

    def test_large_energy_jump_uses_energy_fade(self) -> None:
        planner = TransitionPlanner(default_crossfade=8)
        current = TrackAnalysis(120, 0.9, -24, energy=0.2)
        incoming = TrackAnalysis(121, 0.9, -8, energy=0.85)

        plan = planner.plan(track("quiet"), track("loud"), current, incoming)

        self.assertEqual(plan.mode, "energy_fade")
        self.assertGreater(plan.energy_delta, 0.4)


class AutoDJCacheTests(unittest.TestCase):
    def test_structure_detector_finds_intro_drop_outro_and_downbeat(self) -> None:
        import librosa
        import numpy as np

        sample_rate = 8000
        seconds = 60
        times = np.arange(sample_rate * seconds) / sample_rate
        envelope = np.select(
            [times < 8, times < 30, times < 50],
            [0.01, 0.08, 0.30],
            default=0.01,
        )
        samples = (np.sin(2 * np.pi * 220 * times) * envelope).astype(np.float32)
        onset = librosa.onset.onset_strength(y=samples, sr=sample_rate)
        beat_times = np.arange(0.5, seconds, 0.5)

        intro, drop, outro, downbeat, confidence = AutoDJAnalyzer._detect_structure(
            librosa,
            np,
            samples,
            sample_rate,
            onset,
            beat_times,
            seconds,
            0.5,
        )

        self.assertGreaterEqual(intro, 3)
        self.assertLess(intro, 15)
        self.assertGreater(drop, intro)
        self.assertGreater(outro, drop)
        self.assertGreaterEqual(downbeat, 0.5)
        self.assertGreater(confidence, 0.8)

    def test_v2_schema_migrates_to_v5_without_dropping_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "autodj.db"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute(
                    """
                    CREATE TABLE track_analysis (
                        track_key TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        bpm REAL NOT NULL,
                        confidence REAL NOT NULL,
                        loudness_db REAL NOT NULL,
                        beat_offset REAL NOT NULL DEFAULT 0,
                        beat_interval REAL NOT NULL DEFAULT 0,
                        analysis_version INTEGER NOT NULL DEFAULT 2,
                        analyzed_at INTEGER NOT NULL DEFAULT (unixepoch())
                    )
                    """
                )
                db.execute(
                    """
                    INSERT INTO track_analysis(
                        track_key, url, title, bpm, confidence, loudness_db,
                        beat_offset, beat_interval
                    ) VALUES ('legacy', 'https://example.com', 'Legacy', 120, 0.8, -14, 0.2, 0.5)
                    """
                )

            analyzer = AutoDJAnalyzer(str(path))
            analyzer._create_schema()

            with closing(sqlite3.connect(path)) as db:
                columns = {row[1] for row in db.execute("PRAGMA table_info(track_analysis)")}
                row_count = db.execute("SELECT COUNT(*) FROM track_analysis").fetchone()[0]
            self.assertTrue(
                {
                    "key_index",
                    "key_mode",
                    "key_confidence",
                    "energy",
                    "vocal_activity",
                    "intro_end",
                    "drop_time",
                    "outro_start",
                    "downbeat_offset",
                    "structure_confidence",
                }
                <= columns
            )
            self.assertEqual(row_count, 1)

    def test_v5_analysis_round_trips_through_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            analyzer = AutoDJAnalyzer(str(Path(directory) / "autodj.db"))
            analyzer._create_schema()
            item = track("cache")
            analysis = TrackAnalysis(
                123,
                0.88,
                -13,
                0.25,
                60 / 123,
                9,
                "minor",
                0.72,
                0.63,
                0.41,
                11.5,
                42.0,
                178.0,
                0.25,
                0.86,
            )
            key = "cache-key"

            analyzer._save(key, item, analysis)

            self.assertEqual(analyzer._load(key), analysis)


if __name__ == "__main__":
    unittest.main()
