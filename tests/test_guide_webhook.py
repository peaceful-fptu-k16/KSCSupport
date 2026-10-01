import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from community.guide_webhook import ServerGuideWebhook


class FakeChannel:
    def __init__(self, channel_id: int, name: str) -> None:
        self.id = channel_id
        self.name = name
        self.mention = f"<#{channel_id}>"


class FakeGuild:
    id = 10
    member_count = 79
    members = []
    icon = None
    text_channels = [
        FakeChannel(1, "📜・rules"),
        FakeChannel(2, "💭・gossip"),
        FakeChannel(3, "🎶・music"),
        FakeChannel(4, "🤖・bot"),
        FakeChannel(5, "📣・announcements"),
        FakeChannel(6, "👤・introductions"),
        FakeChannel(7, "🎉・events"),
        FakeChannel(8, "📰・weekly-recap"),
    ]


class ServerGuideWebhookTests(unittest.TestCase):
    def test_build_embeds_contains_server_map_commands_and_rules(self) -> None:
        embeds = ServerGuideWebhook.build_embeds(FakeGuild())
        self.assertEqual(len(embeds), 3)
        self.assertIn("WELCOME", embeds[0].title)
        self.assertIn("<#1>", embeds[0].description)
        self.assertIn("/phat", embeds[1].fields[1].value)
        self.assertIn("Tôn trọng", embeds[2].description)


class ServerGuideWebhookAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_force_repost_replaces_old_message(self) -> None:
        repository = SimpleNamespace(
            get_config=AsyncMock(return_value="10"),
            set_config=AsyncMock(),
        )
        webhook = SimpleNamespace(
            send=AsyncMock(return_value=SimpleNamespace(id=20)),
            edit_message=AsyncMock(),
            delete_message=AsyncMock(),
        )
        guide = ServerGuideWebhook(repository)
        guide._webhook = webhook

        await guide.publish(FakeGuild(), force_repost=True)

        webhook.edit_message.assert_not_awaited()
        webhook.send.assert_awaited_once()
        webhook.delete_message.assert_awaited_once_with(10)
        repository.set_config.assert_awaited_once_with(10, "server_guide_webhook_message_id", "20")


if __name__ == "__main__":
    unittest.main()
