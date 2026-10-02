import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from music.errors import MusicError
from music.models import Track, TrackSource
from music.repository import MusicRepository
from music.ui.lyrics_view import split_lyrics


class MusicRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = MusicRepository(str(Path(self.temp_dir.name) / "music.db"))
        await self.repository.initialize()
        self.track = Track(
            title="Dream Love",
            url="https://soundcloud.com/example/dream-love",
            source=TrackSource.SOUNDCLOUD,
            duration=245,
            uploader="Artist",
        )

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_favorite_can_be_added_and_removed(self) -> None:
        self.assertTrue(await self.repository.toggle_favorite(1, self.track))
        self.assertTrue(await self.repository.is_favorite(1, self.track))
        self.assertEqual((await self.repository.list_favorites(1))[0].url, self.track.url)

        self.assertFalse(await self.repository.toggle_favorite(1, self.track))
        self.assertFalse(await self.repository.is_favorite(1, self.track))

    async def test_playlist_lifecycle_and_ownership(self) -> None:
        playlist_id = await self.repository.save_playlist(1, "Chill đêm", [self.track])
        second = Track(
            title="Second",
            url="https://youtube.com/watch?v=second",
            source=TrackSource.YOUTUBE,
        )
        await self.repository.add_track_to_playlist(1, "Chill đêm", second)

        playlist = await self.repository.get_playlist(1, playlist_id)
        self.assertIsNotNone(playlist)
        self.assertEqual([track.title for track in playlist.tracks], ["Dream Love", "Second"])
        self.assertIsNone(await self.repository.get_playlist(2, playlist_id))
        self.assertTrue(await self.repository.delete_playlist(1, playlist_id))

    async def test_duplicate_playlist_requires_explicit_overwrite(self) -> None:
        await self.repository.save_playlist(1, "Focus", [self.track])
        with self.assertRaises(MusicError):
            await self.repository.save_playlist(1, "focus", [self.track])

    async def test_bot_state_is_persisted_and_updated(self) -> None:
        self.assertIsNone(await self.repository.get_state("webhook"))
        await self.repository.set_state("webhook", "123")
        self.assertEqual(await self.repository.get_state("webhook"), "123")
        await self.repository.set_state("webhook", "456")
        self.assertEqual(await self.repository.get_state("webhook"), "456")

    async def test_discovery_metrics_attach_real_observed_growth(self) -> None:
        track = Track(
            "Official MV",
            "https://youtube.com/watch?v=metric",
            TrackSource.YOUTUBE,
            view_count=1_840_000,
        )
        async with self.repository._connect() as db:
            await db.execute(
                "INSERT INTO discovery_snapshots(track_url, observed_day, view_count) VALUES (?, ?, ?)",
                (track.url, (date.today() - timedelta(days=7)).isoformat(), 1_000_000),
            )
            await db.commit()

        enriched = await self.repository.enrich_discovery_metrics([track])

        self.assertEqual(enriched[0].view_growth_7d, 840_000)

    async def test_history_records_real_listening_time_and_stats(self) -> None:
        requested = replace(self.track, requester_id=7, requester_name="Duy")
        await self.repository.record_playback_start(100, requested)
        self.assertTrue(
            await self.repository.record_playback_end(
                100,
                requested,
                83,
                completed=False,
            )
        )
        await self.repository.toggle_favorite(7, requested)

        history = await self.repository.list_history(7, 100)
        personal = await self.repository.get_listening_stats(100, user_id=7)
        server = await self.repository.get_listening_stats(100)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].listened_seconds, 83)
        self.assertFalse(history[0].completed)
        self.assertEqual(personal.play_count, 1)
        self.assertEqual(personal.listened_seconds, 83)
        self.assertEqual(personal.favorite_count, 1)
        self.assertEqual(personal.top_artist, "Artist")
        self.assertEqual(server.play_count, 1)

    async def test_new_playback_closes_stale_open_session(self) -> None:
        first = replace(self.track, requester_id=1)
        second = Track(
            title="Second",
            url="https://youtube.com/watch?v=second",
            source=TrackSource.YOUTUBE,
            requester_id=1,
        )
        await self.repository.record_playback_start(100, first)
        await self.repository.record_playback_start(100, second)
        await self.repository.record_playback_end(100, second, 12, completed=True)

        history = await self.repository.list_history(1, 100)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].track.title, "Second")
        self.assertTrue(history[0].completed)
        self.assertEqual(history[1].listened_seconds, 0)

    async def test_music_profile_supports_yearly_wrapped_metrics(self) -> None:
        requested = replace(self.track, requester_id=7, requester_name="Duy")
        await self.repository.record_playback_start(100, requested)
        await self.repository.record_playback_end(100, requested, 125, completed=True)

        profile = await self.repository.get_music_profile(100, 7)

        self.assertEqual(profile.stats.play_count, 1)
        self.assertEqual(profile.stats.listened_seconds, 125)
        self.assertEqual(profile.top_tracks[0][0].title, "Dream Love")
        self.assertEqual(profile.top_tracks[0][1], 1)
        self.assertIsNotNone(profile.peak_hour)

        empty = await self.repository.get_music_profile(100, 7, year=1999)
        self.assertEqual(empty.stats.play_count, 0)
        self.assertEqual(empty.top_tracks, ())
        self.assertIsNone(empty.peak_hour)


class LyricsPaginationTests(unittest.TestCase):
    def test_split_lyrics_keeps_lines_within_limit(self) -> None:
        pages = split_lyrics("line one\nline two\nline three", limit=18)

        self.assertEqual(pages, ["line one\nline two", "line three"])
        self.assertTrue(all(len(page) <= 18 for page in pages))

    def test_split_lyrics_does_not_discard_a_long_line(self) -> None:
        text = "a" * 45
        pages = split_lyrics(text, limit=20)

        self.assertEqual("".join(pages), text)
        self.assertEqual([len(page) for page in pages], [20, 20, 5])


if __name__ == "__main__":
    unittest.main()
