import unittest

from music.extractor import MediaExtractor
from music.models import TrackSource


class ExtractorMetadataTests(unittest.TestCase):
    def test_youtube_flat_entry_gets_stable_watch_url(self) -> None:
        result = MediaExtractor.track_from_info(
            {
                "id": "abc123",
                "url": "abc123",
                "title": "Example",
                "extractor_key": "Youtube",
                "view_count": 12_800_000,
                "upload_date": "20260915",
                "channel_id": "UC123",
                "channel_is_verified": True,
            },
            requester_id=1,
            requester_name="Tester",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.url, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(result.source, TrackSource.YOUTUBE)
        self.assertEqual(result.thumbnail, "https://i.ytimg.com/vi/abc123/hqdefault.jpg")
        self.assertEqual(result.view_count, 12_800_000)
        self.assertEqual(result.upload_date, "2026-09-15")
        self.assertEqual(result.channel_id, "UC123")
        self.assertTrue(result.channel_verified)

    def test_thumbnail_list_is_used_when_primary_thumbnail_is_missing(self) -> None:
        result = MediaExtractor.track_from_info(
            {
                "id": "abc123",
                "url": "abc123",
                "title": "Example",
                "extractor_key": "Youtube",
                "thumbnails": [
                    {"url": "https://img.example/small.jpg"},
                    {"url": "https://img.example/large.jpg"},
                ],
            },
            requester_id=1,
            requester_name="Tester",
        )

        self.assertEqual(result.thumbnail, "https://img.example/large.jpg")

    def test_soundcloud_entry_keeps_page_url(self) -> None:
        page_url = "https://soundcloud.com/example/song"
        result = MediaExtractor.track_from_info(
            {
                "id": "42",
                "webpage_url": page_url,
                "url": "https://cdn.example/temporary-stream",
                "title": "Example",
                "duration": 245.8,
                "extractor_key": "Soundcloud",
            },
            requester_id=None,
            requester_name=None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.url, page_url)
        self.assertEqual(result.source, TrackSource.SOUNDCLOUD)
        self.assertEqual(result.duration, 245)


if __name__ == "__main__":
    unittest.main()
