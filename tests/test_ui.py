import io
import unittest

import discord
from PIL import Image

from music.effects import AudioEffect, EqualizerPreset
from music.models import AudioAnalysisSummary, LoopMode, PlaybackSnapshot, Track, TrackSource
from music.repository import HistoryEntry, ListeningStats, MusicProfile
from music.ui.audio_settings import AudioSettingsView
from music.ui.card import PlayerCardRenderer
from music.ui.discovery import DiscoveryView, PartyManager, WrappedView
from music.ui.history import HistoryView, stats_embed
from music.ui.player import PlayerActionButton, PlayerLayoutView
from music.ui.queue import QueueView
from music.ui.search import SearchResultsView, TrackActionsView


class FakeUser:
    id = 7
    display_name = "Duy"


class PlayerUITests(unittest.IsolatedAsyncioTestCase):
    async def test_player_controls_are_persistent_and_unique(self) -> None:
        view = PlayerLayoutView(None)
        buttons = [
            item for item in view.walk_children() if isinstance(item, PlayerActionButton)
        ]
        custom_ids = [item.custom_id for item in buttons]

        self.assertTrue(view.is_persistent())
        self.assertEqual(len(custom_ids), 9)
        self.assertEqual(len(custom_ids), len(set(custom_ids)))
        self.assertEqual(
            [item.label for item in buttons],
            [
                "Pause",
                "Skip",
                "Shuffle",
                "Stop",
                "Search",
                "Queue",
                "Favorite",
                "Lyrics",
                "More",
            ],
        )

    async def test_player_layout_uses_v2_container_and_media_gallery(self) -> None:
        snapshot = PlaybackSnapshot(
            current=Track(
                title="Dream Love",
                url="https://example.com/dream-love",
                source=TrackSource.YOUTUBE,
            ),
            queue=(),
            volume=0.5,
            loop_mode=LoopMode.OFF,
        )
        view = PlayerLayoutView(
            None,
            snapshot=snapshot,
            media_url="attachment://player.png",
        )

        self.assertIsInstance(view.children[0], discord.ui.Container)
        self.assertTrue(
            any(isinstance(item, discord.ui.MediaGallery) for item in view.walk_children())
        )

    async def test_player_status_contains_track_state(self) -> None:
        track = Track(
            title="Dream Love",
            url="https://youtube.com/watch?v=dream-love",
            source=TrackSource.YOUTUBE,
            duration=245,
            uploader="Artist",
            requester_name="Duy",
            view_count=1_200_000,
            is_official=True,
        )
        snapshot = PlaybackSnapshot(
            current=track,
            queue=(),
            volume=0.75,
            loop_mode=LoopMode.TRACK,
            analysis=AudioAnalysisSummary(
                bpm=96.2,
                key="3A",
                key_name="A# minor",
                key_confidence=0.72,
                energy=0.82,
                vocal_activity=0.44,
            ),
        )

        status = PlayerLayoutView._status_text(snapshot, paused=False)

        self.assertIn("NOW PLAYING", status)
        self.assertIn("Dream Love", status)
        self.assertIn("VOL 75%", status)
        self.assertIn("OFFICIAL MV", status)
        self.assertIn("1.2M VIEWS", status)
        self.assertIn("96 BPM", status)
        self.assertIn("KEY 3A", status)
        self.assertIn("ENERGY 82%", status)
        self.assertIn("VOCAL 44%", status)

    async def test_search_results_and_track_actions_match_result_count(self) -> None:
        tracks = [
            Track(
                title=f"Track {index}",
                url=f"https://example.com/{index}",
                source=TrackSource.YOUTUBE,
            )
            for index in range(5)
        ]

        results = SearchResultsView(None, tracks, owner_id=1)
        actions = TrackActionsView(None, tracks[0], owner_id=1)

        self.assertEqual(len(results.children[0].options), 5)
        self.assertEqual(
            [button.label for button in actions.children],
            ["Play Now", "Add to Queue", "Play Next", "Favorite", "Playlist"],
        )

    async def test_queue_view_exposes_fair_queue_and_autoplay_controls(self) -> None:
        class FakeUI:
            manager = None

        view = QueueView(FakeUI(), None, guild_id=1, owner_id=1)

        self.assertEqual(
            [(item.row, item.label) for item in view.children],
            [
                (0, "Previous"),
                (0, "Next"),
                (1, "Shuffle"),
                (1, "Fair Queue: Off"),
                (1, "Autoplay: Off"),
                (1, "DJ Mix V5: Off"),
                (1, "Smart Order: Off"),
                (2, "Save"),
                (2, "Clear"),
            ],
        )

    async def test_rendered_player_card_has_stable_dimensions(self) -> None:
        renderer = PlayerCardRenderer()
        snapshot = PlaybackSnapshot(
            current=Track(
                title="A very long title that still needs to fit inside the player card",
                url="https://example.com/track",
                source=TrackSource.YOUTUBE,
                duration=240,
                uploader="Artist",
            ),
            queue=(),
            volume=0.5,
            loop_mode=LoopMode.OFF,
            elapsed=60,
            analysis=AudioAnalysisSummary(
                bpm=128,
                key="8A",
                key_name="A minor",
                key_confidence=0.8,
                energy=0.76,
                vocal_activity=0.38,
            ),
        )
        try:
            data = await renderer.render(snapshot, paused=False)
        finally:
            await renderer.close()

        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1200, 675))
            self.assertEqual(image.format, "PNG")

    async def test_advanced_audio_view_exposes_all_presets(self) -> None:
        view = AudioSettingsView(
            None,
            guild_id=1,
            owner_id=1,
            effect=AudioEffect.OFF,
            equalizer=EqualizerPreset.BALANCED,
        )

        selects = [item for item in view.children if isinstance(item, discord.ui.Select)]
        buttons = [item for item in view.children if isinstance(item, discord.ui.Button)]
        self.assertEqual([len(select.options) for select in selects], [7, 7])
        self.assertEqual(buttons[0].label, "Reset")

    async def test_history_and_stats_views_render_real_metrics(self) -> None:
        track = Track(
            title="Dream Love",
            url="https://soundcloud.com/example/dream-love",
            source=TrackSource.SOUNDCLOUD,
            uploader="Artist",
        )
        history = HistoryView(
            None,
            None,
            [HistoryEntry(1, 10, 7, "Duy", track, 1_700_000_000, 83, False)],
            guild_id=10,
            owner_id=7,
        )
        stats = ListeningStats(3, 180, 2, 1, "Artist", "Dream Love", 1, 2)
        embed = stats_embed(stats, stats)

        self.assertIn("Dream Love", history.embed().description)
        self.assertIn("1:23", history.embed().description)
        self.assertTrue(any(field.name == "Đã nghe" and "3 phút" in field.value for field in embed.fields))

    async def test_discovery_views_expose_v3_controls(self) -> None:
        ai = DiscoveryView(None, None, guild_id=10, owner_id=7, mode="ai")
        radio = DiscoveryView(None, None, guild_id=10, owner_id=7, mode="radio")
        profile = MusicProfile(
            ListeningStats(3, 180, 2, 1, "Artist", "Dream Love", 1, 2),
            (),
            23,
            2026,
        )
        wrapped = WrappedView(FakeUser(), profile)
        parties = PartyManager()
        party = parties.start(10, FakeUser())
        replacement = parties.start(10, FakeUser())
        parties.end(party)

        mood_select = next(item for item in ai.children if isinstance(item, discord.ui.Select))
        radio_select = next(item for item in radio.children if isinstance(item, discord.ui.Select))
        self.assertEqual(len(mood_select.options), 17)
        self.assertEqual(len(radio_select.options), 5)
        self.assertEqual(ai.start.label, "Generate Mix")
        self.assertEqual(radio.start.label, "Start Radio")
        self.assertFalse(ai.refine.disabled)
        self.assertTrue(radio.refine.disabled)
        self.assertIn("MUSIC WRAPPED 2026", wrapped.embed().title)
        self.assertEqual(party.host_id, 7)
        self.assertTrue(parties.is_active(replacement))


if __name__ == "__main__":
    unittest.main()
