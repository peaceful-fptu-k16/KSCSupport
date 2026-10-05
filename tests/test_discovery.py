import unittest
from datetime import date

from music.discovery import (
    AI_PRESETS,
    RADIO_PRESETS,
    custom_ai_preset,
    discovery_score,
    discovery_queries,
    has_producer_credit,
    is_discovery_candidate,
    is_urban_candidate,
    rank_discovery_tracks,
)
from music.models import Track, TrackSource


def track(
    title: str,
    uploader: str,
    *,
    views: int = 1_000_000,
    uploaded: str = "2026-09-01",
) -> Track:
    return Track(
        title,
        f"https://youtube.com/watch?v={title}",
        TrackSource.YOUTUBE,
        duration=240,
        uploader=uploader,
        view_count=views,
        upload_date=uploaded,
        channel_verified=True,
    )


class DiscoveryPolicyTests(unittest.TestCase):
    def test_official_filter_rejects_unwanted_formats(self) -> None:
        self.assertTrue(is_discovery_candidate(track("Bài Hát | Official MV", "Artist Official")))
        for title in (
            "Bài Hát Lyrics Video",
            "Bài Hát Cover",
            "Bài Hát Sped Up",
            "Bài Hát Slowed + Reverb",
            "Bài Hát Fanmade",
            "Bài Hát Remix",
        ):
            self.assertFalse(is_discovery_candidate(track(title, "Artist Official")), title)

    def test_verified_chart_channel_is_not_treated_as_official_mv(self) -> None:
        chart = track(
            "Most Viewed Vietnamese Music Last Week | Top Vpop Songs",
            "Bảng Xếp Hạng Âm Nhạc",
        )

        self.assertFalse(is_discovery_candidate(chart))

    def test_foreign_official_mv_is_not_treated_as_vpop(self) -> None:
        foreign = track("Dynamite Official MV", "HYBE LABELS")

        self.assertFalse(is_discovery_candidate(foreign))

    def test_radio_ranking_keeps_artist_gap(self) -> None:
        tracks = [
            track("A1 Official MV", "Artist A", views=9_000_000),
            track("A2 Official MV", "Artist A", views=8_000_000),
            track("B Official MV", "Artist B", views=7_000_000),
            track("C Official MV", "Artist C", views=6_000_000),
            track("D Official MV", "Artist D", views=5_000_000),
            track("E Official MV", "Artist E", views=4_000_000),
        ]

        ranked = rank_discovery_tracks(tracks, RADIO_PRESETS["trending"], limit=5, artist_gap=3)

        artists = [item.uploader for item in ranked]
        self.assertNotIn("Artist A", artists[1:4])

    def test_new_music_scores_recent_release_higher(self) -> None:
        recent = track("New Official MV", "Artist A", views=500_000, uploaded="2026-09-28")
        old = track("Old Official MV", "Artist B", views=500_000, uploaded="2024-01-01")

        self.assertGreater(
            discovery_score(recent, RADIO_PRESETS["new"], today=date(2026, 10, 2)),
            discovery_score(old, RADIO_PRESETS["new"], today=date(2026, 10, 2)),
        )

    def test_custom_ai_preset_combines_user_preferences(self) -> None:
        preset = custom_ai_preset("Drill + Hoodtrap", "chạy đêm", "Cao", "Mới")

        self.assertIn("Drill + Hoodtrap", preset.query)
        self.assertIn("chạy đêm", preset.query)
        self.assertEqual(preset.freshness, "new")
        self.assertEqual(preset.trend, "popular")
        self.assertEqual(preset.source_policy, "urban")
        self.assertEqual(len(AI_PRESETS), 17)
        self.assertEqual(AI_PRESETS["jersey"].source_policy, "urban")

    def test_urban_policy_accepts_remix_without_official_mv(self) -> None:
        remix = track("Rap Việt Hoodtrap Remix", "Producer Việt Nam")

        self.assertTrue(is_urban_candidate(remix))
        ranked = rank_discovery_tracks([remix], AI_PRESETS["hoodtrap"], limit=1)
        self.assertEqual(ranked, [remix])
        self.assertFalse(ranked[0].is_official)

    def test_urban_ranking_prioritizes_low_view_producer_credit(self) -> None:
        producer_track = track(
            "SAIGON HOODTRAP (prod. Kewtiie)",
            "Underground Artist Việt Nam",
            views=20_000,
        )
        popular_track = track(
            "SAIGON HOODTRAP",
            "Popular Artist Việt Nam",
            views=10_000_000,
        )

        ranked = rank_discovery_tracks(
            [popular_track, producer_track],
            AI_PRESETS["hoodtrap"],
            limit=2,
            artist_gap=1,
        )

        self.assertTrue(has_producer_credit(producer_track))
        self.assertFalse(has_producer_credit(popular_track))
        self.assertEqual(ranked[0], producer_track)

    def test_urban_queries_search_for_producer_credits(self) -> None:
        queries = discovery_queries(AI_PRESETS["drill"])

        self.assertTrue(any('"prod."' in query for query in queries))
        self.assertTrue(any('"prod by"' in query for query in queries))

    def test_urban_policy_still_rejects_low_quality_formats(self) -> None:
        for title in (
            "Rap Việt Hoodtrap Cover",
            "Rap Việt Hoodtrap Reupload",
            "Rap Việt Hoodtrap Sped Up",
            "Rap Việt Hoodtrap Slowed + Reverb",
            "Rap Việt Hoodtrap Fanmade",
        ):
            self.assertFalse(is_urban_candidate(track(title, "Producer Việt Nam")), title)

    def test_non_urban_custom_preset_keeps_official_policy(self) -> None:
        preset = custom_ai_preset("V-Pop", "chill", "Cao", "Mới")

        self.assertEqual(preset.source_policy, "official")
        self.assertIn("Official MV", preset.query)
