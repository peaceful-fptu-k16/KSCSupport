import unittest
from array import array

import discord

from music.audio import build_before_options, build_ffmpeg_options
from music.audio import DynamicEqualizerAudio
from music.effects import AudioEffect, AudioProfile, EqualizerPreset
from music.models import Track, TrackSource
from music.player import GuildPlayerSession


class AudioProfileTests(unittest.TestCase):
    def test_combines_effect_and_equalizer_filters(self) -> None:
        profile = AudioProfile(AudioEffect.NIGHTCORE, EqualizerPreset.EDM)

        self.assertIn("asetrate=48000*1.15", profile.filter_chain)
        self.assertIn("equalizer=f=64", profile.filter_chain)
        self.assertEqual(profile.speed, 1.15)
        self.assertTrue(profile.active)

    def test_balanced_profile_has_no_filter(self) -> None:
        profile = AudioProfile()

        self.assertEqual(profile.filter_chain, "")
        self.assertEqual(build_ffmpeg_options(profile.filter_chain), "-vn")
        self.assertFalse(profile.active)

    def test_ffmpeg_options_include_seek_and_filter(self) -> None:
        self.assertTrue(build_before_options(42).startswith("-ss 42 "))
        self.assertIn('-af "bass=g=8', build_ffmpeg_options("bass=g=8:f=110"))

    def test_equalizer_is_not_baked_into_ffmpeg_chain(self) -> None:
        profile = AudioProfile(equalizer=EqualizerPreset.VOCAL)

        self.assertEqual(profile.ffmpeg_filter_chain, "")


class StaticPcmAudio(discord.AudioSource):
    def __init__(self) -> None:
        samples = array("h", [1000, -1000] * 960)
        self.frame = samples.tobytes()

    def read(self) -> bytes:
        return self.frame

    def is_opus(self) -> bool:
        return False


class FakeAudio:
    def __init__(self) -> None:
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class RecordingExtractor:
    def __init__(self) -> None:
        self.kwargs = None

    async def create_audio(self, _track, _volume, **kwargs):
        self.kwargs = kwargs
        return FakeAudio()


class FakeVoice:
    def __init__(self) -> None:
        self.playing = True
        self.paused = False
        self.stop_calls = 0
        self.play_calls = 0
        self.source = None

    def is_playing(self) -> bool:
        return self.playing

    def is_paused(self) -> bool:
        return self.paused

    def stop(self) -> None:
        self.stop_calls += 1
        self.playing = False

    def play(self, source, *, after) -> None:
        self.source = source
        self.after = after
        self.play_calls += 1
        self.playing = True

    def pause(self) -> None:
        self.paused = True
        self.playing = False


class FakeGuild:
    id = 777


class FakeBot:
    pass


class AudioRestartTests(unittest.IsolatedAsyncioTestCase):
    async def test_changing_effect_restarts_current_track_with_seek(self) -> None:
        extractor = RecordingExtractor()
        voice = FakeVoice()
        session = GuildPlayerSession(FakeBot(), FakeGuild.id, extractor)
        session.state.current = Track(
            title="Current",
            url="https://example.com/current",
            source=TrackSource.YOUTUBE,
        )
        session.state.generation = 4
        session.state.mark_started(offset=37)

        profile = await session.set_effect(FakeGuild(), voice, AudioEffect.BASS_BOOST)

        self.assertEqual(profile.effect, AudioEffect.BASS_BOOST)
        self.assertEqual(extractor.kwargs["profile"], profile)
        self.assertGreaterEqual(extractor.kwargs["seek_seconds"], 37)
        self.assertEqual(voice.stop_calls, 1)
        self.assertEqual(voice.play_calls, 1)
        self.assertEqual((await session.snapshot()).audio_profile, profile)

    async def test_changing_equalizer_keeps_the_same_audio_source(self) -> None:
        extractor = RecordingExtractor()
        voice = FakeVoice()
        processor = DynamicEqualizerAudio(StaticPcmAudio(), EqualizerPreset.BALANCED)
        source = discord.PCMVolumeTransformer(processor, volume=0.5)
        voice.source = source
        session = GuildPlayerSession(FakeBot(), FakeGuild.id, extractor)
        session.state.current = Track(
            title="Current",
            url="https://example.com/current",
            source=TrackSource.YOUTUBE,
        )
        session.state.mark_started(offset=12)

        profile = await session.set_equalizer(FakeGuild(), voice, EqualizerPreset.VOCAL)

        self.assertEqual(profile.equalizer, EqualizerPreset.VOCAL)
        self.assertIs(voice.source, source)
        self.assertEqual(processor.preset, EqualizerPreset.VOCAL)
        self.assertEqual(voice.stop_calls, 0)
        self.assertEqual(voice.play_calls, 0)
        self.assertIsNone(extractor.kwargs)


if __name__ == "__main__":
    unittest.main()
