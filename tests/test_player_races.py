import asyncio
import unittest

from music.audio import CrossfadeAudio
from music.autodj import TrackAnalysis
from music.models import Track, TrackSource
from music.player import GuildPlayerSession


class FakeAudio:
    def __init__(self) -> None:
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class BlockingExtractor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.audio = FakeAudio()

    async def create_audio(self, _track, _volume, **_kwargs):
        self.started.set()
        await self.release.wait()
        return self.audio


class FakeVoiceClient:
    def __init__(self, channel=None, *, playing: bool = False) -> None:
        self.play_calls = 0
        self.source = None
        self.channel = channel
        self.playing = playing

    def is_playing(self) -> bool:
        return self.playing

    def is_paused(self) -> bool:
        return False

    def play(self, source, *, after) -> None:
        self.play_calls += 1
        self.source = source
        self.after = after
        self.playing = True


class FakeGuild:
    id = 123

    def __init__(self, voice_client) -> None:
        self.voice_client = voice_client


class FakeBot:
    def get_guild(self, _guild_id):
        return None


class GuildBot:
    def __init__(self, guild):
        self.guild = guild

    def get_guild(self, _guild_id):
        return self.guild


class PrematureSource:
    premature_end = True

    def __init__(self):
        self.cleared = False

    def clear_next(self):
        self.cleared = True


class FakeChannel:
    id = 456


class OrderedExtractor:
    def __init__(self) -> None:
        self.calls = []
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def extract_tracks(
        self,
        query,
        *,
        requester_id,
        requester_name,
        source_hint,
    ):
        self.calls.append(query)
        if query == "first":
            self.first_started.set()
            await self.release_first.wait()
        return [Track(title=query, url=f"https://example.com/{query}", source=TrackSource.YOUTUBE)]


class ReplacingExtractor:
    def __init__(self) -> None:
        self.calls = 0
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()
        self.audios = []

    async def create_audio(self, _track, _volume, **_kwargs):
        self.calls += 1
        audio = FakeAudio()
        self.audios.append(audio)
        if self.calls == 1:
            self.first_started.set()
            await self.release_first.wait()
        return audio


class AutoplayExtractor:
    def __init__(self) -> None:
        self.queries = []

    async def search_tracks(self, query, **kwargs):
        self.queries.append((query, kwargs))
        return [
            Track(
                title="Seed",
                url="https://example.com/seed",
                source=TrackSource.YOUTUBE,
                requester_name="Tự phát",
            ),
            Track(
                title="Related",
                url="https://example.com/related",
                source=TrackSource.YOUTUBE,
                requester_name="Tự phát",
            ),
        ]


class StaticAnalyzer:
    async def analyze(self, _track):
        return TrackAnalysis(120, 0.9, -16)


class MappingAnalyzer:
    def __init__(self, analyses):
        self.analyses = analyses

    async def analyze(self, track):
        return self.analyses[track.title]


class PrefetchExtractor:
    def __init__(self) -> None:
        self.kwargs = None
        self.audio = None

    async def create_audio(self, _track, _volume, **kwargs):
        self.kwargs = kwargs
        self.audio = FakeAudio()
        return self.audio


class PlayerRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_early_eof_recovers_same_track_at_current_position(self) -> None:
        voice = FakeVoiceClient()
        guild = FakeGuild(voice)
        extractor = PrefetchExtractor()
        session = GuildPlayerSession(GuildBot(guild), 123, extractor)
        current = Track(
            "Current",
            "https://example.com/current",
            TrackSource.YOUTUBE,
            duration=240,
        )
        session.state.current = current
        session.state.generation = 7
        session.state.dj_mix = True
        session.state.mark_started(offset=100)
        premature = PrematureSource()
        session._dj_source = premature

        await session._track_finished(123, 7, None)

        self.assertEqual(session.state.current, current)
        self.assertEqual(session._early_eof_retries, 1)
        self.assertTrue(premature.cleared)
        self.assertEqual(voice.play_calls, 1)
        self.assertIsInstance(voice.source, CrossfadeAudio)
        self.assertAlmostEqual(voice.source.duration, 140, delta=1)
    async def test_smart_reorder_selects_better_transition_from_window(self) -> None:
        current_analysis = TrackAnalysis(
            120, 0.9, -14, key_index=0, key_mode="major", energy=0.55
        )
        difficult_analysis = TrackAnalysis(
            150, 0.9, -9, key_index=1, key_mode="major", energy=0.95
        )
        compatible_analysis = TrackAnalysis(
            123, 0.9, -14, key_index=9, key_mode="minor", energy=0.6
        )
        analyzer = MappingAnalyzer(
            {
                "Current": current_analysis,
                "Difficult": difficult_analysis,
                "Compatible": compatible_analysis,
            }
        )
        extractor = PrefetchExtractor()
        session = GuildPlayerSession(
            FakeBot(),
            123,
            extractor,
            autodj_analyzer=analyzer,
        )
        current = Track(
            "Current", "https://example.com/current", TrackSource.YOUTUBE, duration=240
        )
        difficult = Track(
            "Difficult", "https://example.com/difficult", TrackSource.YOUTUBE, duration=220
        )
        compatible = Track(
            "Compatible", "https://example.com/compatible", TrackSource.YOUTUBE, duration=225
        )
        session.state.current = current
        session.state.enqueue([difficult, compatible])
        session.state.dj_mix = True
        session.state.smart_reorder = True
        session.state.generation = 5
        session._current_analysis = current_analysis
        session._dj_source = CrossfadeAudio(
            FakeAudio(),
            duration=240,
            on_transition=lambda _payload, _overlap: None,
        )

        await session._prepare_dj_next(FakeGuild(None), 5)

        self.assertEqual(session.state.peek_next(), compatible)
        self.assertTrue(session._dj_source.next_ready)

    async def test_snapshot_exposes_current_audio_telemetry(self) -> None:
        session = GuildPlayerSession(FakeBot(), 123, PrefetchExtractor())
        session.state.current = Track(
            title="Analyzed",
            url="https://example.com/analyzed",
            source=TrackSource.YOUTUBE,
        )
        session._current_analysis = TrackAnalysis(
            128,
            0.9,
            -14,
            key_index=9,
            key_mode="minor",
            key_confidence=0.8,
            energy=0.76,
            vocal_activity=0.38,
        )

        snapshot = await session.snapshot()

        self.assertEqual(snapshot.analysis.key, "8A")
        self.assertEqual(snapshot.analysis.key_name, "A minor")
        self.assertEqual(snapshot.analysis.bpm, 128)

    async def test_autoplay_adds_unheard_related_track_only_when_queue_is_empty(self) -> None:
        extractor = AutoplayExtractor()
        session = GuildPlayerSession(FakeBot(), 123, extractor)
        session.state.autoplay = True
        seed = Track(
            title="Seed",
            url="https://example.com/seed",
            source=TrackSource.YOUTUBE,
            uploader="Artist",
        )

        await session._fill_autoplay(seed)
        snapshot = await session.snapshot()

        self.assertEqual([item.title for item in snapshot.queue], ["Related"])
        self.assertEqual(snapshot.queue[0].requester_name, "Tự phát")
        self.assertIn("Artist Seed mix", extractor.queries[0][0])

    async def test_autoplay_does_not_override_a_user_queue(self) -> None:
        extractor = AutoplayExtractor()
        session = GuildPlayerSession(FakeBot(), 123, extractor)
        session.state.autoplay = True
        session.state.enqueue(
            [Track(title="Queued", url="https://example.com/q", source=TrackSource.YOUTUBE)]
        )

        await session._fill_autoplay(
            Track(title="Seed", url="https://example.com/seed", source=TrackSource.YOUTUBE)
        )

        self.assertEqual(extractor.queries, [])

    async def test_autoplay_can_prime_queue_during_continuous_dj_playback(self) -> None:
        extractor = AutoplayExtractor()
        session = GuildPlayerSession(FakeBot(), 123, extractor)
        session.state.autoplay = True
        seed = Track(
            title="Seed",
            url="https://example.com/seed",
            source=TrackSource.YOUTUBE,
        )
        session.state.current = seed

        await session._fill_autoplay(seed, allow_current=True)

        self.assertEqual([item.title for item in session.state.queue], ["Related"])

    async def test_dj_prefetch_attaches_normalized_next_source(self) -> None:
        extractor = PrefetchExtractor()
        session = GuildPlayerSession(
            FakeBot(),
            123,
            extractor,
            autodj_analyzer=StaticAnalyzer(),
        )
        current = Track(
            title="Current",
            url="https://example.com/current",
            source=TrackSource.YOUTUBE,
            duration=240,
        )
        incoming = Track(
            title="Incoming",
            url="https://example.com/incoming",
            source=TrackSource.YOUTUBE,
            duration=220,
        )
        session.state.current = current
        session.state.queue.append(incoming)
        session.state.dj_mix = True
        session.state.generation = 4
        session._dj_source = CrossfadeAudio(
            FakeAudio(),
            duration=240,
            on_transition=lambda _payload, _overlap: None,
        )

        await session._prepare_dj_next(FakeGuild(None), 4)

        self.assertTrue(session._dj_source.next_ready)
        self.assertIn("dynaudnorm", extractor.kwargs["extra_filter"])
    async def test_stop_reports_partial_listening_session(self) -> None:
        events = []

        async def on_track_end(guild_id, track, listened_seconds, completed):
            events.append((guild_id, track.title, listened_seconds, completed))

        session = GuildPlayerSession(
            FakeBot(),
            123,
            ReplacingExtractor(),
            on_track_end=on_track_end,
        )
        session.state.current = Track(
            title="Partial",
            url="https://example.com/partial",
            source=TrackSource.YOUTUBE,
        )
        session.state.mark_started(offset=25)

        await session.stop(None)

        self.assertEqual(events, [(123, "Partial", 25, False)])

    async def test_stop_invalidates_audio_that_finishes_preparing_late(self) -> None:
        extractor = BlockingExtractor()
        voice = FakeVoiceClient()
        guild = FakeGuild(voice)
        session = GuildPlayerSession(FakeBot(), guild.id, extractor)
        session.state.enqueue(
            [Track(title="Slow", url="https://example.com/slow", source=TrackSource.YOUTUBE)]
        )

        start_task = asyncio.create_task(session.start_next(guild))
        await extractor.started.wait()
        await session.stop(None)
        extractor.release.set()
        await start_task

        self.assertEqual(voice.play_calls, 0)
        self.assertTrue(extractor.audio.cleaned)
        self.assertIsNone(session.state.current)

    async def test_concurrent_requests_keep_arrival_order(self) -> None:
        extractor = OrderedExtractor()
        channel = FakeChannel()
        voice = FakeVoiceClient(channel, playing=True)
        guild = FakeGuild(voice)
        session = GuildPlayerSession(FakeBot(), guild.id, extractor)

        first = asyncio.create_task(
            session.enqueue_request(
                guild,
                channel,
                channel,
                "first",
                requester_id=1,
                requester_name="First",
            )
        )
        await extractor.first_started.wait()
        second = asyncio.create_task(
            session.enqueue_request(
                guild,
                channel,
                channel,
                "second",
                requester_id=2,
                requester_name="Second",
            )
        )
        await asyncio.sleep(0)

        self.assertEqual(extractor.calls, ["first"])
        extractor.release_first.set()
        await asyncio.gather(first, second)
        snapshot = await session.snapshot()

        self.assertEqual([item.title for item in snapshot.queue], ["first", "second"])

    async def test_play_now_invalidates_track_still_being_prepared(self) -> None:
        extractor = ReplacingExtractor()
        channel = FakeChannel()
        voice = FakeVoiceClient(channel)
        guild = FakeGuild(voice)
        session = GuildPlayerSession(FakeBot(), guild.id, extractor)
        old_track = Track(
            title="Old",
            url="https://example.com/old",
            source=TrackSource.YOUTUBE,
        )
        new_track = Track(
            title="New",
            url="https://example.com/new",
            source=TrackSource.YOUTUBE,
        )
        session.state.enqueue([old_track])

        old_start = asyncio.create_task(session.start_next(guild))
        await extractor.first_started.wait()
        replace = asyncio.create_task(
            session.enqueue_tracks(guild, channel, channel, [new_track], position="now")
        )
        await asyncio.sleep(0)
        extractor.release_first.set()
        await asyncio.gather(old_start, replace)
        snapshot = await session.snapshot()

        self.assertTrue(extractor.audios[0].cleaned)
        self.assertEqual(voice.play_calls, 1)
        self.assertEqual(snapshot.current, new_track)


if __name__ == "__main__":
    unittest.main()
