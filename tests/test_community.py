import tempfile
import unittest
import io
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image

from community.cards import CommunityCardRenderer
from community.achievements import automatic_keys, featured_keys
from community.repository import CommunityRepository
from community.ui import AchievementsView, analytics_embed, birthday_calendar_embed, weekly_embed


class CommunityRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = CommunityRepository(str(Path(self.temp_dir.name) / "community.db"))
        await self.repository.initialize()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_activity_profile_tracks_messages_and_voice(self) -> None:
        await self.repository.record_member_join(10, 7, "Duy", joined_at=1_700_000_000)
        await self.repository.increment_message(10, 7, "Duy", day="2026-10-01")
        await self.repository.increment_message(10, 7, "Duy", day="2026-10-01")
        await self.repository.start_voice_session(10, 7, "Duy", 99, started_at=1_000)
        listened = await self.repository.end_voice_session(10, 7, ended_at=1_125)

        profile = await self.repository.get_profile(10, 7, "Duy")

        self.assertEqual(listened, 125)
        self.assertEqual(profile.message_count, 2)
        self.assertEqual(profile.voice_seconds, 125)

    async def test_birthday_privacy_controls_calendar_and_daily_notice(self) -> None:
        await self.repository.set_birthday(10, 1, "Public", 15, 10, "full")
        await self.repository.set_birthday(10, 2, "Day only", 15, 10, "day_only")
        await self.repository.set_birthday(10, 3, "Hidden", 15, 10, "hidden")

        calendar = await self.repository.list_birthdays(10, 10)
        daily = await self.repository.birthdays_on(10, 15, 10)

        self.assertEqual([entry.user_id for entry in calendar], [1])
        self.assertEqual({entry.user_id for entry in daily}, {1, 2})

    async def test_invalid_birthday_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.repository.set_birthday(10, 1, "Duy", 31, 2, "full")

    async def test_birthday_announcement_and_reaction_are_idempotent(self) -> None:
        self.assertTrue(await self.repository.claim_birthday_announcement(10, 7, "2026-10-01"))
        self.assertFalse(await self.repository.claim_birthday_announcement(10, 7, "2026-10-01"))

        first, count = await self.repository.add_birthday_reaction(10, 7, 8, "2026-10-01")
        second, repeated_count = await self.repository.add_birthday_reaction(10, 7, 8, "2026-10-01")
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual((count, repeated_count), (1, 1))

    async def test_introduction_updates_profile(self) -> None:
        await self.repository.save_introduction(
            10,
            7,
            "Duy",
            "Duy",
            "Xin chào mọi người",
            "Coding, gaming",
        )
        profile = await self.repository.get_profile(10, 7, "Duy")
        self.assertTrue(profile.introduced)

    async def test_achievements_unlock_and_limit_featured_badges(self) -> None:
        for index in range(6):
            key = f"badge_{index}"
            self.assertTrue(await self.repository.unlock_achievement(10, 7, key))
            if index < 5:
                self.assertTrue(await self.repository.set_achievement_pinned(10, 7, key, True))
            else:
                with self.assertRaises(ValueError):
                    await self.repository.set_achievement_pinned(10, 7, key, True)
        records = await self.repository.list_achievements(10, 7)
        self.assertEqual(sum(record.pinned for record in records), 5)

    async def test_automatic_achievement_thresholds(self) -> None:
        keys = automatic_keys(days=365, messages=5_000, voice_seconds=100 * 3600)
        self.assertIn("member_longtime", keys)
        self.assertIn("chat_active", keys)
        self.assertIn("voice_regular", keys)
        self.assertNotIn("special_founder", keys)

    async def test_featured_achievements_are_selected_and_saved_automatically(self) -> None:
        unlocked = [
            "member_new",
            "member_longtime",
            "chat_active",
            "chat_voice",
            "voice_legend",
            "special_helper",
        ]
        for key in unlocked:
            await self.repository.unlock_achievement(10, 7, key)
        selected = featured_keys(unlocked)
        await self.repository.set_featured_achievements(10, 7, selected)
        records = await self.repository.list_achievements(10, 7)
        pinned = {record.key for record in records if record.pinned}

        self.assertEqual(len(pinned), 5)
        self.assertIn("special_helper", pinned)
        self.assertIn("voice_legend", pinned)
        self.assertNotIn("member_new", pinned)

    async def test_analytics_aggregates_period_and_channel_activity(self) -> None:
        joined_at = int(datetime(2026, 9, 20, tzinfo=timezone.utc).timestamp())
        await self.repository.record_member_join(10, 7, "Duy", joined_at=joined_at)
        await self.repository.increment_message(10, 7, "Duy", day="2026-08-20", channel_id=101)
        await self.repository.increment_message(10, 7, "Duy", day="2026-10-01", channel_id=101, hour=21)
        await self.repository.increment_message(10, 7, "Duy", day="2026-10-01", channel_id=101, hour=21)
        voice_start = int(datetime(2026, 10, 1, 1, tzinfo=timezone.utc).timestamp())
        await self.repository.start_voice_session(10, 7, "Duy", 202, started_at=voice_start)
        await self.repository.end_voice_session(10, 7, ended_at=voice_start + 3_600)

        snapshot = await self.repository.analytics_snapshot(10, days=30, end=date(2026, 10, 1))

        self.assertEqual(snapshot.messages, 2)
        self.assertEqual(snapshot.previous_messages, 1)
        self.assertEqual(snapshot.active_members, 1)
        self.assertEqual(snapshot.top_chat_channels[0].channel_id, 101)
        self.assertEqual(snapshot.top_chat_channels[0].messages, 2)
        self.assertEqual(snapshot.top_voice_channels[0].channel_id, 202)
        self.assertEqual(snapshot.voice_seconds, 3_600)
        self.assertEqual(len(snapshot.daily), 30)
        self.assertEqual(snapshot.peak_hour, 9)
        self.assertTrue(snapshot.hourly)
        self.assertEqual(len(snapshot.growth), 30)

    async def test_event_analytics_tracks_registration_and_voice_attendance(self) -> None:
        start = int(datetime(2026, 10, 1, 12, tzinfo=timezone.utc).timestamp())
        await self.repository.upsert_event(10, 500, "KSC Community Night", 202, start, start + 7200, "active", 12)
        await self.repository.set_event_registration(10, 500, 7, True)
        marked = await self.repository.mark_event_attendance(10, 7, 202, start + 600)

        snapshot = await self.repository.analytics_snapshot(10, days=7, end=date(2026, 10, 1))
        self.assertEqual(marked, 1)
        self.assertEqual(snapshot.events.events, 1)
        self.assertEqual(snapshot.events.registrations, 12)
        self.assertEqual(snapshot.events.attendees, 1)
        self.assertEqual(snapshot.events.top_event_name, "KSC Community Night")

    async def test_birthday_wishes_can_be_counted_and_paginated(self) -> None:
        await self.repository.add_birthday_wish(10, 7, 8, "Nam", "Chúc mừng sinh nhật!", "2026-10-01")
        await self.repository.add_birthday_wish(10, 7, 9, "Linh", "Tuổi mới thật vui nhé!", "2026-10-01")
        await self.repository.add_birthday_reaction(10, 7, 8, "2026-10-01")

        reactions, wishes = await self.repository.birthday_counts(10, 7, "2026-10-01")
        entries = await self.repository.list_birthday_wishes(10, 7, "2026-10-01")
        self.assertEqual((reactions, wishes), (1, 2))
        self.assertEqual([entry.author_name for entry in entries], ["Nam", "Linh"])

    async def test_community_settings_have_defaults_and_persist_changes(self) -> None:
        settings = await self.repository.community_settings(10)
        self.assertEqual(settings["feature_birthday"], "on")
        self.assertEqual(settings["privacy_analytics"], "public")
        await self.repository.set_config(10, "feature_weekly", "off")
        await self.repository.set_config(10, "channel_weekly", "123")
        updated = await self.repository.community_settings(10)
        self.assertEqual(updated["feature_weekly"], "off")
        self.assertEqual(updated["channel_weekly"], "123")

    async def test_analytics_embed_exposes_admin_metrics(self) -> None:
        snapshot = await self.repository.analytics_snapshot(10, days=7, end=date(2026, 10, 1))
        embed = analytics_embed(snapshot, None)
        activity = analytics_embed(snapshot, None, "activity")
        growth = analytics_embed(snapshot, None, "growth")
        events = analytics_embed(snapshot, None, "events")
        self.assertIn("TỔNG QUAN", embed.title)
        self.assertEqual(embed.image.url, "attachment://analytics.png")
        self.assertIn("Peak time", [field.name for field in activity.fields])
        self.assertIn("TĂNG TRƯỞNG", growth.title)
        self.assertIn("EVENT", events.title)

    async def test_weekly_recap_collects_members_badges_and_birthdays(self) -> None:
        joined_at = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
        await self.repository.record_member_join(10, 7, "Duy", joined_at=joined_at)
        await self.repository.increment_message(10, 7, "Duy", day="2026-10-01", channel_id=101)
        await self.repository.unlock_achievement(10, 7, "member_new")
        await self.repository.claim_birthday_announcement(10, 7, "2026-10-01")
        await self.repository.add_birthday_reaction(10, 7, 8, "2026-10-01")

        snapshot = await self.repository.weekly_snapshot(
            10,
            date(2026, 9, 29),
            date(2026, 10, 5),
        )

        self.assertEqual(snapshot.period_key, "2026-09-29:2026-10-05")
        self.assertEqual(snapshot.analytics.messages, 1)
        self.assertEqual(snapshot.new_members[0].user_id, 7)
        self.assertEqual(snapshot.badges[0].key, "member_new")
        self.assertEqual(snapshot.birthdays[0].reactions, 1)

    async def test_weekly_embed_has_seven_page_navigation_content(self) -> None:
        from types import SimpleNamespace

        snapshot = await self.repository.weekly_snapshot(
            10,
            date(2026, 9, 29),
            date(2026, 10, 5),
        )
        guild = SimpleNamespace(scheduled_events=[])
        overview = weekly_embed(snapshot, guild, 0)
        final_page = weekly_embed(snapshot, guild, 6)
        self.assertIn("WEEKLY", overview.title)
        self.assertIn("TUẦN TIẾP THEO", final_page.title)
        self.assertEqual(overview.image.url, "attachment://weekly-recap.png")

    async def test_achievement_view_renders_progress_and_pins(self) -> None:
        await self.repository.record_member_join(10, 7, "Duy", joined_at=1_700_000_000)
        await self.repository.unlock_achievement(10, 7, "member_new")
        await self.repository.set_achievement_pinned(10, 7, "member_new", True)
        profile = await self.repository.get_profile(10, 7, "Duy")
        records = await self.repository.list_achievements(10, 7)
        view = AchievementsView(self.repository, profile, records, 10, 7)
        embed = view.embed()
        self.assertIn("Thành viên mới", embed.description)
        self.assertIn("📌", embed.description)
        self.assertEqual(len(view.children), 1)

    async def test_birthday_calendar_embed_is_compact(self) -> None:
        await self.repository.set_birthday(10, 7, "Duy", 15, 10, "full")
        entries = await self.repository.list_birthdays(10, 10)
        embed = birthday_calendar_embed(10, entries)
        self.assertIn("<@7>", embed.description)
        self.assertIn("1 sinh nhật", embed.footer.text)


class CommunityCardTests(unittest.TestCase):
    def test_animated_cards_have_stable_dimensions_and_reasonable_size(self) -> None:
        renderer = CommunityCardRenderer()
        welcome = renderer._draw_welcome(None, "Duy", "KSC", 1284)
        birthday = renderer._draw_birthday(None, "Duy")

        for data in (welcome, birthday):
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual(image.size, (1200, 675))
                self.assertEqual(image.format, "GIF")
                self.assertGreater(image.n_frames, 10)
            self.assertLess(len(data), 8 * 1024 * 1024)

    def test_profile_card_is_rendered_as_png(self) -> None:
        renderer = CommunityCardRenderer()
        featured = (
            "member_veteran",
            "chat_active",
            "voice_legend",
            "special_founder",
            "special_champion",
        )
        data = renderer._draw_profile(None, "Duy", 428, 12_482, 386 * 3600, "15/10", True, featured)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1200, 675))
            self.assertEqual(image.format, "PNG")

        birthday_data = renderer._draw_profile(
            None,
            "Duy",
            428,
            12_482,
            386 * 3600,
            "01/10",
            True,
            featured,
            True,
        )
        with Image.open(io.BytesIO(birthday_data)) as image:
            self.assertEqual(image.size, (1200, 675))

    def test_analytics_card_is_rendered_as_png(self) -> None:
        from types import SimpleNamespace

        daily = tuple(SimpleNamespace(messages=value) for value in (1, 3, 2, 7, 5, 9, 6))
        snapshot = SimpleNamespace(
            days=7,
            total_members=1284,
            messages=14820,
            voice_seconds=386 * 3600,
            active_members=684,
            new_members=28,
            left_members=7,
            achievements=42,
            retention_7d=58.0,
            start_day="2026-09-25",
            end_day="2026-10-01",
            daily=daily,
        )
        renderer = CommunityCardRenderer()
        data = renderer._draw_analytics(snapshot, "KSC Gaming")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1200, 675))
            self.assertEqual(image.format, "PNG")

    def test_weekly_card_is_rendered_as_png(self) -> None:
        from types import SimpleNamespace

        analytics = SimpleNamespace(
            new_members=12,
            left_members=3,
            messages=4280,
            voice_seconds=128 * 3600,
            achievements=24,
            active_members=86,
        )
        snapshot = SimpleNamespace(
            start_day="2026-09-21",
            end_day="2026-09-27",
            analytics=analytics,
        )
        renderer = CommunityCardRenderer()
        data = renderer._draw_weekly(snapshot, "KSC Gaming")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1200, 675))
            self.assertEqual(image.format, "PNG")


if __name__ == "__main__":
    unittest.main()
