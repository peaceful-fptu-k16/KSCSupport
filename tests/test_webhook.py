import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from music.models import LoopMode, PlaybackSnapshot, Track, TrackSource
from music.webhook import NowPlayingWebhook


class FakeGuild:
    id = 1
    name = "KSC"


class NowPlayingWebhookTests(unittest.TestCase):
    def test_progress_bar_tracks_elapsed_position(self) -> None:
        bar = NowPlayingWebhook.progress_bar(50, 100, width=10)

        self.assertEqual(bar, "━━━━━●━━━━━")

    def test_embed_contains_artwork_and_playback_details(self) -> None:
        track = Track(
            title="APT.",
            url="https://youtube.com/watch?v=example",
            source=TrackSource.YOUTUBE,
            duration=169,
            uploader="Bruno Mars & ROSÉ",
            thumbnail="https://i.ytimg.com/vi/example/hqdefault.jpg",
            requester_name="Dora",
        )
        snapshot = PlaybackSnapshot(
            current=track,
            queue=(),
            volume=0.8,
            loop_mode=LoopMode.OFF,
            elapsed=84,
        )

        embed = NowPlayingWebhook.build_embed(FakeGuild(), snapshot, paused=False)

        self.assertEqual(embed.title, "🎵 NOW PLAYING")
        self.assertIn("APT", embed.description)
        self.assertIn("1:24", embed.description)
        self.assertEqual(embed.thumbnail.url, track.thumbnail)
        self.assertTrue(any(field.name == "🔊 Volume" and "80%" in field.value for field in embed.fields))
        self.assertIn("SERVER ONLINE", embed.footer.text)


class NowPlayingWebhookAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_force_repost_sends_new_message_before_deleting_old_one(self) -> None:
        repository = SimpleNamespace(
            get_state=AsyncMock(return_value="10"),
            set_state=AsyncMock(),
        )
        webhook = SimpleNamespace(
            send=AsyncMock(return_value=SimpleNamespace(id=20)),
            edit_message=AsyncMock(),
            delete_message=AsyncMock(),
        )
        notifier = NowPlayingWebhook(repository)
        notifier._webhook = webhook
        notifier.guild_id = None
        snapshot = PlaybackSnapshot(
            current=None,
            queue=(),
            volume=0.5,
            loop_mode=LoopMode.OFF,
        )

        await notifier.publish(FakeGuild(), snapshot, paused=False, force_repost=True)

        webhook.edit_message.assert_not_awaited()
        repository.set_state.assert_awaited_once_with(
            "now_playing_webhook_message:1",
            "20",
        )
        webhook.delete_message.assert_awaited_once_with(10)
