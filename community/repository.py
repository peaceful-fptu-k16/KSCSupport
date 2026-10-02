import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite


@dataclass(frozen=True, slots=True)
class BirthdayEntry:
    user_id: int
    display_name: str
    day: int
    month: int
    visibility: str


@dataclass(frozen=True, slots=True)
class BirthdayWish:
    author_id: int
    author_name: str
    message: str
    created_at: int


@dataclass(frozen=True, slots=True)
class CommunityProfile:
    user_id: int
    display_name: str
    joined_at: Optional[int]
    message_count: int
    voice_seconds: int
    birthday_day: Optional[int]
    birthday_month: Optional[int]
    birthday_visibility: str
    introduced: bool


@dataclass(frozen=True, slots=True)
class AchievementRecord:
    key: str
    unlocked_at: int
    pinned: bool


@dataclass(frozen=True, slots=True)
class AnalyticsChannel:
    channel_id: int
    messages: int
    voice_seconds: int


@dataclass(frozen=True, slots=True)
class AnalyticsMember:
    user_id: int
    display_name: str
    messages: int
    voice_seconds: int


@dataclass(frozen=True, slots=True)
class AnalyticsDay:
    day: str
    messages: int
    voice_seconds: int
    active_members: int


@dataclass(frozen=True, slots=True)
class AnalyticsHour:
    weekday: int
    hour: int
    messages: int
    voice_seconds: int


@dataclass(frozen=True, slots=True)
class AnalyticsGrowth:
    day: str
    joined: int
    left: int
    total: int


@dataclass(frozen=True, slots=True)
class EventAnalytics:
    events: int
    registrations: int
    attendees: int
    top_event_name: Optional[str]
    top_event_attendees: int


@dataclass(frozen=True, slots=True)
class AnalyticsSnapshot:
    days: int
    start_day: str
    end_day: str
    total_members: int
    new_members: int
    left_members: int
    messages: int
    voice_seconds: int
    active_members: int
    achievements: int
    previous_messages: int
    previous_voice_seconds: int
    previous_active_members: int
    top_chat_channels: tuple[AnalyticsChannel, ...]
    top_voice_channels: tuple[AnalyticsChannel, ...]
    top_members: tuple[AnalyticsMember, ...]
    daily: tuple[AnalyticsDay, ...]
    hourly: tuple[AnalyticsHour, ...]
    growth: tuple[AnalyticsGrowth, ...]
    peak_weekday: int
    peak_hour: int
    funnel_joined: int
    funnel_introduced: int
    funnel_first_activity: int
    funnel_returned_7d: int
    funnel_returned_30d: int
    events: EventAnalytics
    retention_1d: float
    retention_7d: float
    retention_30d: float


@dataclass(frozen=True, slots=True)
class WeeklyBadge:
    key: str
    count: int


@dataclass(frozen=True, slots=True)
class WeeklyMember:
    user_id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class WeeklyBirthday:
    user_id: int
    display_name: str
    birthday_date: str
    reactions: int
    wishes: int


@dataclass(frozen=True, slots=True)
class WeeklySnapshot:
    period_key: str
    start_day: str
    end_day: str
    analytics: AnalyticsSnapshot
    badges: tuple[WeeklyBadge, ...]
    new_members: tuple[WeeklyMember, ...]
    birthdays: tuple[WeeklyBirthday, ...]
    milestones: tuple[str, ...]


class CommunityRepository:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or os.getenv("COMMUNITY_DATABASE_PATH", "data/community.db"))

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS members (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    joined_at INTEGER,
                    left_at INTEGER,
                    birthday_day INTEGER,
                    birthday_month INTEGER,
                    birthday_visibility TEXT NOT NULL DEFAULT 'full',
                    introduced_at INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS daily_activity (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    voice_seconds INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, day)
                );

                CREATE TABLE IF NOT EXISTS voice_sessions (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    started_at INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS channel_activity (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    voice_seconds INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, channel_id, day)
                );

                CREATE TABLE IF NOT EXISTS hourly_activity (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    voice_seconds INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, day, hour)
                );

                CREATE TABLE IF NOT EXISTS community_events (
                    guild_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    channel_id INTEGER,
                    scheduled_start INTEGER NOT NULL,
                    scheduled_end INTEGER,
                    status TEXT NOT NULL,
                    registered_count INTEGER NOT NULL DEFAULT 0,
                    attended_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    PRIMARY KEY (guild_id, event_id)
                );

                CREATE TABLE IF NOT EXISTS event_members (
                    guild_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    registered INTEGER NOT NULL DEFAULT 1,
                    attended INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, event_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS introductions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    preferred_name TEXT NOT NULL,
                    about TEXT NOT NULL,
                    interests TEXT,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS birthday_reactions (
                    guild_id INTEGER NOT NULL,
                    birthday_user_id INTEGER NOT NULL,
                    reacting_user_id INTEGER NOT NULL,
                    birthday_date TEXT NOT NULL,
                    PRIMARY KEY (guild_id, birthday_user_id, reacting_user_id, birthday_date)
                );

                CREATE TABLE IF NOT EXISTS birthday_wishes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    birthday_user_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    author_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    birthday_date TEXT NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS birthday_announcements (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    birthday_date TEXT NOT NULL,
                    message_id INTEGER,
                    PRIMARY KEY (guild_id, user_id, birthday_date)
                );

                CREATE TABLE IF NOT EXISTS community_config (
                    guild_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (guild_id, key)
                );

                CREATE TABLE IF NOT EXISTS achievements (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    badge_key TEXT NOT NULL,
                    unlocked_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    pinned INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, badge_key)
                );

                CREATE INDEX IF NOT EXISTS idx_achievements_user
                    ON achievements(guild_id, user_id, unlocked_at DESC);

                CREATE INDEX IF NOT EXISTS idx_members_birthday
                    ON members(guild_id, birthday_month, birthday_day);
                CREATE INDEX IF NOT EXISTS idx_activity_guild_day
                    ON daily_activity(guild_id, day);
                CREATE INDEX IF NOT EXISTS idx_channel_activity_guild_day
                    ON channel_activity(guild_id, day);
                CREATE INDEX IF NOT EXISTS idx_hourly_activity_guild_day
                    ON hourly_activity(guild_id, day, hour);
                CREATE INDEX IF NOT EXISTS idx_events_guild_start
                    ON community_events(guild_id, scheduled_start);
                """
            )
            await db.commit()

    async def record_member_join(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        joined_at: Optional[int] = None,
    ) -> None:
        joined_at = joined_at or int(time.time())
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO members(guild_id, user_id, display_name, joined_at, left_at)
                VALUES (?, ?, ?, ?, NULL)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    joined_at = COALESCE(members.joined_at, excluded.joined_at),
                    left_at = NULL
                """,
                (guild_id, user_id, display_name, joined_at),
            )
            await db.commit()

    async def record_member_leave(self, guild_id: int, user_id: int) -> None:
        await self.end_voice_session(guild_id, user_id)
        async with self._connect() as db:
            await db.execute(
                "UPDATE members SET left_at = unixepoch() WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await db.commit()

    async def increment_message(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        *,
        day: Optional[str] = None,
        channel_id: Optional[int] = None,
        hour: Optional[int] = None,
    ) -> int:
        day = day or date.today().isoformat()
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_member(db, guild_id, user_id, display_name)
            await db.execute(
                """
                INSERT INTO daily_activity(guild_id, user_id, day, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(guild_id, user_id, day) DO UPDATE SET
                    message_count = message_count + 1
                """,
                (guild_id, user_id, day),
            )
            if channel_id is not None:
                await db.execute(
                    """
                    INSERT INTO channel_activity(guild_id, channel_id, day, message_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(guild_id, channel_id, day) DO UPDATE SET
                        message_count = message_count + 1
                    """,
                    (guild_id, channel_id, day),
                )
            if hour is not None:
                await db.execute(
                    """
                    INSERT INTO hourly_activity(guild_id, user_id, day, hour, message_count)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(guild_id, user_id, day, hour) DO UPDATE SET
                        message_count = message_count + 1
                    """,
                    (guild_id, user_id, day, max(0, min(23, hour))),
                )
            row = await self._fetchone(
                db,
                "SELECT COALESCE(SUM(message_count), 0) FROM daily_activity WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await db.commit()
            return int(row[0])

    async def start_voice_session(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        channel_id: int,
        *,
        started_at: Optional[int] = None,
    ) -> None:
        started_at = started_at or int(time.time())
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_member(db, guild_id, user_id, display_name)
            await db.execute(
                """
                INSERT INTO voice_sessions(guild_id, user_id, channel_id, started_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    started_at = excluded.started_at
                """,
                (guild_id, user_id, channel_id, started_at),
            )
            await db.commit()

    async def end_voice_session(
        self,
        guild_id: int,
        user_id: int,
        *,
        ended_at: Optional[int] = None,
    ) -> int:
        ended_at = ended_at or int(time.time())
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await self._fetchone(
                db,
                "SELECT started_at, channel_id FROM voice_sessions WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            if not row:
                await db.rollback()
                return 0
            seconds = max(0, min(ended_at - int(row[0]), 24 * 60 * 60))
            day = date.fromtimestamp(ended_at).isoformat()
            await db.execute(
                """
                INSERT INTO daily_activity(guild_id, user_id, day, voice_seconds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, day) DO UPDATE SET
                    voice_seconds = voice_seconds + excluded.voice_seconds
                """,
                (guild_id, user_id, day, seconds),
            )
            await db.execute(
                """
                INSERT INTO channel_activity(guild_id, channel_id, day, voice_seconds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, channel_id, day) DO UPDATE SET
                    voice_seconds = voice_seconds + excluded.voice_seconds
                """,
                (guild_id, int(row[1]), day, seconds),
            )
            await db.execute(
                """
                INSERT INTO hourly_activity(guild_id, user_id, day, hour, voice_seconds)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, day, hour) DO UPDATE SET
                    voice_seconds = voice_seconds + excluded.voice_seconds
                """,
                (guild_id, user_id, day, time.localtime(ended_at).tm_hour, seconds),
            )
            await db.execute(
                "DELETE FROM voice_sessions WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await db.commit()
            return seconds

    async def save_introduction(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        preferred_name: str,
        about: str,
        interests: str,
    ) -> None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_member(db, guild_id, user_id, display_name)
            await db.execute(
                """
                INSERT INTO introductions(
                    guild_id, user_id, preferred_name, about, interests
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, preferred_name, about, interests),
            )
            await db.execute(
                "UPDATE members SET introduced_at = unixepoch() WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await db.commit()

    async def set_birthday(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        day: int,
        month: int,
        visibility: str,
    ) -> None:
        if visibility not in {"full", "day_only", "hidden"}:
            raise ValueError("invalid birthday visibility")
        date(2000, month, day)
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_member(db, guild_id, user_id, display_name)
            await db.execute(
                """
                UPDATE members
                SET birthday_day = ?, birthday_month = ?, birthday_visibility = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (day, month, visibility, guild_id, user_id),
            )
            await db.commit()

    async def list_birthdays(self, guild_id: int, month: int) -> list[BirthdayEntry]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT user_id, display_name, birthday_day, birthday_month, birthday_visibility
                FROM members
                WHERE guild_id = ? AND birthday_month = ?
                  AND birthday_day IS NOT NULL AND birthday_visibility = 'full'
                  AND left_at IS NULL
                ORDER BY birthday_day, display_name COLLATE NOCASE
                """,
                (guild_id, month),
            )
        return [BirthdayEntry(int(r[0]), str(r[1]), int(r[2]), int(r[3]), str(r[4])) for r in rows]

    async def birthdays_on(self, guild_id: int, day: int, month: int) -> list[BirthdayEntry]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT user_id, display_name, birthday_day, birthday_month, birthday_visibility
                FROM members
                WHERE guild_id = ? AND birthday_day = ? AND birthday_month = ?
                  AND birthday_visibility != 'hidden' AND left_at IS NULL
                ORDER BY display_name COLLATE NOCASE
                """,
                (guild_id, day, month),
            )
        return [BirthdayEntry(int(r[0]), str(r[1]), int(r[2]), int(r[3]), str(r[4])) for r in rows]

    async def claim_birthday_announcement(
        self,
        guild_id: int,
        user_id: int,
        birthday_date: str,
    ) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO birthday_announcements(guild_id, user_id, birthday_date)
                VALUES (?, ?, ?)
                """,
                (guild_id, user_id, birthday_date),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def set_birthday_message(
        self,
        guild_id: int,
        user_id: int,
        birthday_date: str,
        message_id: int,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE birthday_announcements SET message_id = ?
                WHERE guild_id = ? AND user_id = ? AND birthday_date = ?
                """,
                (message_id, guild_id, user_id, birthday_date),
            )
            await db.commit()

    async def add_birthday_reaction(
        self,
        guild_id: int,
        birthday_user_id: int,
        reacting_user_id: int,
        birthday_date: str,
    ) -> tuple[bool, int]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO birthday_reactions(
                    guild_id, birthday_user_id, reacting_user_id, birthday_date
                ) VALUES (?, ?, ?, ?)
                """,
                (guild_id, birthday_user_id, reacting_user_id, birthday_date),
            )
            row = await self._fetchone(
                db,
                """
                SELECT COUNT(*) FROM birthday_reactions
                WHERE guild_id = ? AND birthday_user_id = ? AND birthday_date = ?
                """,
                (guild_id, birthday_user_id, birthday_date),
            )
            await db.commit()
            return cursor.rowcount > 0, int(row[0])

    async def add_birthday_wish(
        self,
        guild_id: int,
        birthday_user_id: int,
        author_id: int,
        author_name: str,
        message: str,
        birthday_date: str,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO birthday_wishes(
                    guild_id, birthday_user_id, author_id, author_name, message, birthday_date
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (guild_id, birthday_user_id, author_id, author_name, message, birthday_date),
            )
            await db.commit()

    async def birthday_counts(
        self,
        guild_id: int,
        birthday_user_id: int,
        birthday_date: str,
    ) -> tuple[int, int]:
        async with self._connect() as db:
            reactions = await self._fetchone(
                db,
                """
                SELECT COUNT(*) FROM birthday_reactions
                WHERE guild_id = ? AND birthday_user_id = ? AND birthday_date = ?
                """,
                (guild_id, birthday_user_id, birthday_date),
            )
            wishes = await self._fetchone(
                db,
                """
                SELECT COUNT(*) FROM birthday_wishes
                WHERE guild_id = ? AND birthday_user_id = ? AND birthday_date = ?
                """,
                (guild_id, birthday_user_id, birthday_date),
            )
        return int(reactions[0]), int(wishes[0])

    async def list_birthday_wishes(
        self,
        guild_id: int,
        birthday_user_id: int,
        birthday_date: str,
    ) -> list[BirthdayWish]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT author_id, author_name, message, created_at
                FROM birthday_wishes
                WHERE guild_id = ? AND birthday_user_id = ? AND birthday_date = ?
                ORDER BY created_at, id
                """,
                (guild_id, birthday_user_id, birthday_date),
            )
        return [BirthdayWish(int(row[0]), str(row[1]), str(row[2]), int(row[3])) for row in rows]

    async def birthday_announcements_on(
        self,
        guild_id: int,
        birthday_date: str,
    ) -> list[tuple[int, int]]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT user_id, message_id FROM birthday_announcements
                WHERE guild_id = ? AND birthday_date = ? AND message_id IS NOT NULL
                """,
                (guild_id, birthday_date),
            )
        return [(int(row[0]), int(row[1])) for row in rows]

    async def get_profile(self, guild_id: int, user_id: int, display_name: str) -> CommunityProfile:
        async with self._connect() as db:
            await self._ensure_member(db, guild_id, user_id, display_name)
            await db.commit()
            row = await self._fetchone(
                db,
                """
                SELECT m.user_id, m.display_name, m.joined_at,
                       COALESCE(SUM(a.message_count), 0),
                       COALESCE(SUM(a.voice_seconds), 0),
                       m.birthday_day, m.birthday_month, m.birthday_visibility,
                       m.introduced_at IS NOT NULL
                FROM members m
                LEFT JOIN daily_activity a
                  ON a.guild_id = m.guild_id AND a.user_id = m.user_id
                WHERE m.guild_id = ? AND m.user_id = ?
                GROUP BY m.guild_id, m.user_id
                """,
                (guild_id, user_id),
            )
        return CommunityProfile(
            user_id=int(row[0]),
            display_name=str(row[1]),
            joined_at=row[2],
            message_count=int(row[3]),
            voice_seconds=int(row[4]),
            birthday_day=row[5],
            birthday_month=row[6],
            birthday_visibility=str(row[7]),
            introduced=bool(row[8]),
        )

    async def unlock_achievement(self, guild_id: int, user_id: int, key: str) -> bool:
        return bool(await self.unlock_achievements(guild_id, user_id, [key]))

    async def unlock_achievements(
        self,
        guild_id: int,
        user_id: int,
        keys: list[str],
    ) -> list[str]:
        unique = list(dict.fromkeys(keys))
        if not unique:
            return []
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            placeholders = ", ".join("?" for _ in unique)
            rows = await self._fetchall(
                db,
                f"""
                SELECT badge_key FROM achievements
                WHERE guild_id = ? AND user_id = ?
                  AND badge_key IN ({placeholders})
                """,
                (guild_id, user_id, *unique),
            )
            existing = {str(row[0]) for row in rows}
            unlocked = [key for key in unique if key not in existing]
            await db.executemany(
                """
                INSERT OR IGNORE INTO achievements(guild_id, user_id, badge_key)
                VALUES (?, ?, ?)
                """,
                [(guild_id, user_id, key) for key in unlocked],
            )
            await db.commit()
            return unlocked

    async def list_achievements(self, guild_id: int, user_id: int) -> list[AchievementRecord]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT badge_key, unlocked_at, pinned
                FROM achievements
                WHERE guild_id = ? AND user_id = ?
                ORDER BY pinned DESC, unlocked_at DESC
                """,
                (guild_id, user_id),
            )
        return [AchievementRecord(str(row[0]), int(row[1]), bool(row[2])) for row in rows]

    async def set_achievement_pinned(
        self,
        guild_id: int,
        user_id: int,
        key: str,
        pinned: bool,
    ) -> bool:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await self._fetchone(
                db,
                "SELECT pinned FROM achievements WHERE guild_id = ? AND user_id = ? AND badge_key = ?",
                (guild_id, user_id, key),
            )
            if not row:
                await db.rollback()
                return False
            if pinned and not bool(row[0]):
                count = await self._fetchone(
                    db,
                    "SELECT COUNT(*) FROM achievements WHERE guild_id = ? AND user_id = ? AND pinned = 1",
                    (guild_id, user_id),
                )
                if int(count[0]) >= 5:
                    await db.rollback()
                    raise ValueError("maximum pinned achievements reached")
            await db.execute(
                """
                UPDATE achievements SET pinned = ?
                WHERE guild_id = ? AND user_id = ? AND badge_key = ?
                """,
                (int(pinned), guild_id, user_id, key),
            )
            await db.commit()
            return True

    async def set_featured_achievements(
        self,
        guild_id: int,
        user_id: int,
        keys: list[str],
    ) -> None:
        selected = list(dict.fromkeys(keys))[:5]
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "UPDATE achievements SET pinned = 0 WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            if selected:
                placeholders = ", ".join("?" for _ in selected)
                await db.execute(
                    f"""
                    UPDATE achievements SET pinned = 1
                    WHERE guild_id = ? AND user_id = ?
                      AND badge_key IN ({placeholders})
                    """,
                    (guild_id, user_id, *selected),
                )
            await db.commit()

    async def get_config(self, guild_id: int, key: str) -> Optional[str]:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                "SELECT value FROM community_config WHERE guild_id = ? AND key = ?",
                (guild_id, key),
            )
        return str(row[0]) if row else None

    async def set_config(self, guild_id: int, key: str, value: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO community_config(guild_id, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value
                """,
                (guild_id, key, value),
            )
            await db.commit()

    async def community_settings(self, guild_id: int) -> dict[str, str]:
        defaults = {
            "feature_welcome": "on",
            "feature_goodbye": "on",
            "feature_birthday": "on",
            "feature_analytics": "on",
            "feature_weekly": "on",
            "privacy_welcome": "public",
            "privacy_goodbye": "compact",
            "privacy_birthday": "public",
            "privacy_analytics": "public",
            "privacy_weekly": "public",
        }
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                "SELECT key, value FROM community_config WHERE guild_id = ?",
                (guild_id,),
            )
        defaults.update({str(row[0]): str(row[1]) for row in rows})
        return defaults

    async def upsert_event(
        self,
        guild_id: int,
        event_id: int,
        name: str,
        channel_id: Optional[int],
        scheduled_start: int,
        scheduled_end: Optional[int],
        status: str,
        registered_count: int = 0,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO community_events(
                    guild_id, event_id, name, channel_id, scheduled_start,
                    scheduled_end, status, registered_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, event_id) DO UPDATE SET
                    name = excluded.name,
                    channel_id = excluded.channel_id,
                    scheduled_start = excluded.scheduled_start,
                    scheduled_end = excluded.scheduled_end,
                    status = excluded.status,
                    registered_count = excluded.registered_count,
                    updated_at = unixepoch()
                """,
                (
                    guild_id,
                    event_id,
                    name,
                    channel_id,
                    scheduled_start,
                    scheduled_end,
                    status,
                    max(0, registered_count),
                ),
            )
            await db.commit()

    async def set_event_registration(
        self,
        guild_id: int,
        event_id: int,
        user_id: int,
        registered: bool,
    ) -> None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                INSERT INTO event_members(guild_id, event_id, user_id, registered)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, event_id, user_id) DO UPDATE SET registered = excluded.registered
                """,
                (guild_id, event_id, user_id, int(registered)),
            )
            await db.commit()

    async def mark_event_attendance(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        occurred_at: int,
    ) -> int:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            events = await self._fetchall(
                db,
                """
                SELECT event_id FROM community_events
                WHERE guild_id = ? AND channel_id = ?
                  AND scheduled_start <= ?
                  AND COALESCE(scheduled_end, scheduled_start + 21600) >= ?
                """,
                (guild_id, channel_id, occurred_at, occurred_at),
            )
            marked = 0
            for row in events:
                event_id = int(row[0])
                cursor = await db.execute(
                    """
                    INSERT INTO event_members(guild_id, event_id, user_id, registered, attended)
                    VALUES (?, ?, ?, 0, 1)
                    ON CONFLICT(guild_id, event_id, user_id) DO UPDATE SET attended = 1
                    """,
                    (guild_id, event_id, user_id),
                )
                if cursor.rowcount > 0:
                    marked += 1
                await db.execute(
                    """
                    UPDATE community_events SET attended_count = (
                        SELECT COUNT(*) FROM event_members
                        WHERE guild_id = ? AND event_id = ? AND attended = 1
                    ), updated_at = unixepoch()
                    WHERE guild_id = ? AND event_id = ?
                    """,
                    (guild_id, event_id, guild_id, event_id),
                )
            await db.commit()
            return marked

    async def analytics_snapshot(
        self,
        guild_id: int,
        *,
        days: int = 30,
        end: Optional[date] = None,
    ) -> AnalyticsSnapshot:
        if days not in {7, 30, 90}:
            raise ValueError("analytics period must be 7, 30, or 90 days")
        end = end or date.today()
        start = end - timedelta(days=days - 1)
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)

        async with self._connect() as db:
            total_row = await self._fetchone(
                db,
                "SELECT COUNT(*) FROM members WHERE guild_id = ? AND left_at IS NULL",
                (guild_id,),
            )
            growth_row = await self._fetchone(
                db,
                """
                SELECT
                    SUM(CASE WHEN date(joined_at, 'unixepoch', '+7 hours') BETWEEN ? AND ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN date(left_at, 'unixepoch', '+7 hours') BETWEEN ? AND ? THEN 1 ELSE 0 END)
                FROM members WHERE guild_id = ?
                """,
                (start.isoformat(), end.isoformat(), start.isoformat(), end.isoformat(), guild_id),
            )
            current_row = await self._fetchone(
                db,
                """
                SELECT COALESCE(SUM(message_count), 0), COALESCE(SUM(voice_seconds), 0),
                       COUNT(DISTINCT CASE WHEN message_count > 0 OR voice_seconds > 0 THEN user_id END)
                FROM daily_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ?
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            previous_row = await self._fetchone(
                db,
                """
                SELECT COALESCE(SUM(message_count), 0), COALESCE(SUM(voice_seconds), 0),
                       COUNT(DISTINCT CASE WHEN message_count > 0 OR voice_seconds > 0 THEN user_id END)
                FROM daily_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ?
                """,
                (guild_id, previous_start.isoformat(), previous_end.isoformat()),
            )
            achievement_row = await self._fetchone(
                db,
                """
                SELECT COUNT(*) FROM achievements
                WHERE guild_id = ?
                  AND date(unlocked_at, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            chat_rows = await self._fetchall(
                db,
                """
                SELECT channel_id, SUM(message_count), SUM(voice_seconds)
                FROM channel_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ? AND message_count > 0
                GROUP BY channel_id ORDER BY SUM(message_count) DESC LIMIT 5
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            voice_rows = await self._fetchall(
                db,
                """
                SELECT channel_id, SUM(message_count), SUM(voice_seconds)
                FROM channel_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ? AND voice_seconds > 0
                GROUP BY channel_id ORDER BY SUM(voice_seconds) DESC LIMIT 5
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            member_rows = await self._fetchall(
                db,
                """
                SELECT a.user_id, COALESCE(m.display_name, CAST(a.user_id AS TEXT)),
                       SUM(a.message_count), SUM(a.voice_seconds)
                FROM daily_activity a
                LEFT JOIN members m ON m.guild_id = a.guild_id AND m.user_id = a.user_id
                WHERE a.guild_id = ? AND a.day BETWEEN ? AND ?
                GROUP BY a.user_id
                ORDER BY (SUM(a.message_count) + SUM(a.voice_seconds) / 60.0) DESC
                LIMIT 5
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            daily_rows = await self._fetchall(
                db,
                """
                SELECT day, SUM(message_count), SUM(voice_seconds),
                       COUNT(DISTINCT CASE WHEN message_count > 0 OR voice_seconds > 0 THEN user_id END)
                FROM daily_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ?
                GROUP BY day ORDER BY day
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            hourly_rows = await self._fetchall(
                db,
                """
                SELECT CAST(strftime('%w', day) AS INTEGER), hour,
                       SUM(message_count), SUM(voice_seconds)
                FROM hourly_activity
                WHERE guild_id = ? AND day BETWEEN ? AND ?
                GROUP BY strftime('%w', day), hour
                ORDER BY strftime('%w', day), hour
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            growth_rows = await self._fetchall(
                db,
                """
                WITH RECURSIVE dates(day) AS (
                    SELECT ? UNION ALL SELECT date(day, '+1 day') FROM dates WHERE day < ?
                )
                SELECT dates.day,
                       (SELECT COUNT(*) FROM members m WHERE m.guild_id = ?
                         AND date(m.joined_at, 'unixepoch', '+7 hours') = dates.day),
                       (SELECT COUNT(*) FROM members m WHERE m.guild_id = ?
                         AND date(m.left_at, 'unixepoch', '+7 hours') = dates.day),
                       (SELECT COUNT(*) FROM members m WHERE m.guild_id = ?
                         AND date(m.joined_at, 'unixepoch', '+7 hours') <= dates.day
                         AND (m.left_at IS NULL OR date(m.left_at, 'unixepoch', '+7 hours') > dates.day))
                FROM dates
                """,
                (start.isoformat(), end.isoformat(), guild_id, guild_id, guild_id),
            )
            funnel_row = await self._fetchone(
                db,
                """
                SELECT COUNT(*),
                       SUM(m.introduced_at IS NOT NULL),
                       SUM(EXISTS(SELECT 1 FROM daily_activity a WHERE a.guild_id=m.guild_id AND a.user_id=m.user_id
                           AND (a.message_count > 0 OR a.voice_seconds > 0))),
                       SUM(EXISTS(SELECT 1 FROM daily_activity a WHERE a.guild_id=m.guild_id AND a.user_id=m.user_id
                           AND a.day >= date(m.joined_at, 'unixepoch', '+7 hours', '+7 days')
                           AND (a.message_count > 0 OR a.voice_seconds > 0))),
                       SUM(EXISTS(SELECT 1 FROM daily_activity a WHERE a.guild_id=m.guild_id AND a.user_id=m.user_id
                           AND a.day >= date(m.joined_at, 'unixepoch', '+7 hours', '+30 days')
                           AND (a.message_count > 0 OR a.voice_seconds > 0)))
                FROM members m
                WHERE m.guild_id = ?
                  AND date(m.joined_at, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            event_row = await self._fetchone(
                db,
                """
                SELECT COUNT(*), COALESCE(SUM(registered_count), 0), COALESCE(SUM(attended_count), 0)
                FROM community_events
                WHERE guild_id = ?
                  AND date(scheduled_start, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            top_event_row = await self._fetchone(
                db,
                """
                SELECT name, attended_count FROM community_events
                WHERE guild_id = ?
                  AND date(scheduled_start, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                ORDER BY attended_count DESC, registered_count DESC LIMIT 1
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            retention = {
                threshold: await self._retention_rate(db, guild_id, start, end, threshold)
                for threshold in (1, 7, 30)
            }

        by_day = {
            str(row[0]): AnalyticsDay(str(row[0]), int(row[1]), int(row[2]), int(row[3]))
            for row in daily_rows
        }
        daily = tuple(
            by_day.get(
                (start + timedelta(days=offset)).isoformat(),
                AnalyticsDay((start + timedelta(days=offset)).isoformat(), 0, 0, 0),
            )
            for offset in range(days)
        )
        channel = lambda row: AnalyticsChannel(int(row[0]), int(row[1]), int(row[2]))
        hourly = tuple(
            AnalyticsHour(int(row[0]), int(row[1]), int(row[2]), int(row[3]))
            for row in hourly_rows
        )
        peak = max(hourly, key=lambda item: item.messages + item.voice_seconds / 60, default=None)
        return AnalyticsSnapshot(
            days=days,
            start_day=start.isoformat(),
            end_day=end.isoformat(),
            total_members=int(total_row[0]),
            new_members=int(growth_row[0] or 0),
            left_members=int(growth_row[1] or 0),
            messages=int(current_row[0]),
            voice_seconds=int(current_row[1]),
            active_members=int(current_row[2]),
            achievements=int(achievement_row[0]),
            previous_messages=int(previous_row[0]),
            previous_voice_seconds=int(previous_row[1]),
            previous_active_members=int(previous_row[2]),
            top_chat_channels=tuple(channel(row) for row in chat_rows),
            top_voice_channels=tuple(channel(row) for row in voice_rows),
            top_members=tuple(
                AnalyticsMember(int(row[0]), str(row[1]), int(row[2]), int(row[3]))
                for row in member_rows
            ),
            daily=daily,
            hourly=hourly,
            growth=tuple(
                AnalyticsGrowth(str(row[0]), int(row[1]), int(row[2]), int(row[3]))
                for row in growth_rows
            ),
            peak_weekday=peak.weekday if peak else 0,
            peak_hour=peak.hour if peak else 0,
            funnel_joined=int(funnel_row[0] or 0),
            funnel_introduced=int(funnel_row[1] or 0),
            funnel_first_activity=int(funnel_row[2] or 0),
            funnel_returned_7d=int(funnel_row[3] or 0),
            funnel_returned_30d=int(funnel_row[4] or 0),
            events=EventAnalytics(
                events=int(event_row[0] or 0),
                registrations=int(event_row[1] or 0),
                attendees=int(event_row[2] or 0),
                top_event_name=str(top_event_row[0]) if top_event_row else None,
                top_event_attendees=int(top_event_row[1]) if top_event_row else 0,
            ),
            retention_1d=retention[1],
            retention_7d=retention[7],
            retention_30d=retention[30],
        )

    async def weekly_snapshot(self, guild_id: int, start: date, end: date) -> WeeklySnapshot:
        if end < start or (end - start).days != 6:
            raise ValueError("weekly recap requires a seven-day period")
        analytics = await self.analytics_snapshot(guild_id, days=7, end=end)
        async with self._connect() as db:
            badge_rows = await self._fetchall(
                db,
                """
                SELECT badge_key, COUNT(*)
                FROM achievements
                WHERE guild_id = ?
                  AND date(unlocked_at, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                GROUP BY badge_key ORDER BY COUNT(*) DESC, badge_key LIMIT 8
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            member_rows = await self._fetchall(
                db,
                """
                SELECT user_id, display_name FROM members
                WHERE guild_id = ?
                  AND date(joined_at, 'unixepoch', '+7 hours') BETWEEN ? AND ?
                ORDER BY joined_at DESC LIMIT 8
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            birthday_rows = await self._fetchall(
                db,
                """
                SELECT b.user_id, COALESCE(m.display_name, CAST(b.user_id AS TEXT)), b.birthday_date,
                       (SELECT COUNT(*) FROM birthday_reactions r
                        WHERE r.guild_id = b.guild_id AND r.birthday_user_id = b.user_id
                          AND r.birthday_date = b.birthday_date),
                       (SELECT COUNT(*) FROM birthday_wishes w
                        WHERE w.guild_id = b.guild_id AND w.birthday_user_id = b.user_id
                          AND w.birthday_date = b.birthday_date)
                FROM birthday_announcements b
                LEFT JOIN members m ON m.guild_id = b.guild_id AND m.user_id = b.user_id
                WHERE b.guild_id = ? AND b.birthday_date BETWEEN ? AND ?
                ORDER BY b.birthday_date
                """,
                (guild_id, start.isoformat(), end.isoformat()),
            )
            totals_end = await self._community_totals(db, guild_id, end)
            totals_before = await self._community_totals(db, guild_id, start - timedelta(days=1))

        milestones = []
        milestone_specs = (
            ("members", "thành viên", (100, 250, 500, 1_000, 2_500, 5_000, 10_000)),
            ("messages", "tin nhắn", (1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000)),
            ("voice_hours", "giờ voice", (100, 500, 1_000, 5_000, 10_000, 50_000)),
            ("achievements", "thành tựu", (100, 500, 1_000, 2_500, 5_000, 10_000)),
        )
        for key, label, thresholds in milestone_specs:
            for threshold in thresholds:
                if totals_before[key] < threshold <= totals_end[key]:
                    milestones.append(f"{threshold:,} {label}")
        return WeeklySnapshot(
            period_key=f"{start.isoformat()}:{end.isoformat()}",
            start_day=start.isoformat(),
            end_day=end.isoformat(),
            analytics=analytics,
            badges=tuple(WeeklyBadge(str(row[0]), int(row[1])) for row in badge_rows),
            new_members=tuple(WeeklyMember(int(row[0]), str(row[1])) for row in member_rows),
            birthdays=tuple(
                WeeklyBirthday(int(row[0]), str(row[1]), str(row[2]), int(row[3]), int(row[4]))
                for row in birthday_rows
            ),
            milestones=tuple(milestones),
        )

    @staticmethod
    async def _community_totals(
        db: aiosqlite.Connection,
        guild_id: int,
        end: date,
    ) -> dict[str, int]:
        member_row = await CommunityRepository._fetchone(
            db,
            """
            SELECT COUNT(*) FROM members
            WHERE guild_id = ? AND date(joined_at, 'unixepoch', '+7 hours') <= ?
              AND (left_at IS NULL OR date(left_at, 'unixepoch', '+7 hours') > ?)
            """,
            (guild_id, end.isoformat(), end.isoformat()),
        )
        activity_row = await CommunityRepository._fetchone(
            db,
            """
            SELECT COALESCE(SUM(message_count), 0), COALESCE(SUM(voice_seconds), 0)
            FROM daily_activity WHERE guild_id = ? AND day <= ?
            """,
            (guild_id, end.isoformat()),
        )
        achievement_row = await CommunityRepository._fetchone(
            db,
            """
            SELECT COUNT(*) FROM achievements
            WHERE guild_id = ? AND date(unlocked_at, 'unixepoch', '+7 hours') <= ?
            """,
            (guild_id, end.isoformat()),
        )
        return {
            "members": int(member_row[0]),
            "messages": int(activity_row[0]),
            "voice_hours": int(activity_row[1]) // 3600,
            "achievements": int(achievement_row[0]),
        }

    @staticmethod
    async def _retention_rate(
        db: aiosqlite.Connection,
        guild_id: int,
        start: date,
        end: date,
        threshold: int,
    ) -> float:
        cohort_start = start - timedelta(days=max(30, threshold))
        cohort_end = end - timedelta(days=threshold)
        if cohort_end < cohort_start:
            return 0.0
        row = await CommunityRepository._fetchone(
            db,
            f"""
            SELECT COUNT(*), SUM(
                EXISTS(
                    SELECT 1 FROM daily_activity a
                    WHERE a.guild_id = m.guild_id AND a.user_id = m.user_id
                      AND a.day BETWEEN date(m.joined_at, 'unixepoch', '+7 hours', '+{threshold} days') AND ?
                      AND (a.message_count > 0 OR a.voice_seconds > 0)
                )
            )
            FROM members m
            WHERE m.guild_id = ?
              AND date(m.joined_at, 'unixepoch', '+7 hours') BETWEEN ? AND ?
            """,
            (end.isoformat(), guild_id, cohort_start.isoformat(), cohort_end.isoformat()),
        )
        eligible = int(row[0] or 0)
        return (int(row[1] or 0) / eligible * 100.0) if eligible else 0.0

    @staticmethod
    async def _ensure_member(
        db: aiosqlite.Connection,
        guild_id: int,
        user_id: int,
        display_name: str,
    ) -> None:
        await db.execute(
            """
            INSERT INTO members(guild_id, user_id, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET display_name = excluded.display_name
            """,
            (guild_id, user_id, display_name),
        )

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path, timeout=10)
        try:
            yield db
        finally:
            await db.close()

    @staticmethod
    async def _fetchone(db: aiosqlite.Connection, query: str, params: tuple = ()):
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()

    @staticmethod
    async def _fetchall(db: aiosqlite.Connection, query: str, params: tuple = ()):
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()
