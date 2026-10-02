import hashlib
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite

from .errors import MusicError
from .models import Track, TrackSource


@dataclass(frozen=True, slots=True)
class PlaylistSummary:
    playlist_id: int
    name: str
    track_count: int


@dataclass(frozen=True, slots=True)
class Playlist:
    playlist_id: int
    name: str
    tracks: tuple[Track, ...]


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    history_id: int
    guild_id: int
    requester_id: Optional[int]
    requester_name: Optional[str]
    track: Track
    started_at: int
    listened_seconds: int
    completed: bool


@dataclass(frozen=True, slots=True)
class ListeningStats:
    play_count: int
    listened_seconds: int
    unique_tracks: int
    favorite_count: int
    top_artist: Optional[str]
    top_track: Optional[str]
    youtube_plays: int
    soundcloud_plays: int


@dataclass(frozen=True, slots=True)
class MusicProfile:
    stats: ListeningStats
    top_tracks: tuple[tuple[Track, int], ...]
    peak_hour: Optional[int]
    year: Optional[int] = None


class MusicRepository:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or os.getenv("MUSIC_DATABASE_PATH", "data/music.db"))

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS tracks (
                    track_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    duration INTEGER,
                    uploader TEXT,
                    thumbnail TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    track_key TEXT NOT NULL REFERENCES tracks(track_key) ON DELETE CASCADE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, track_key)
                );

                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL COLLATE NOCASE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, name)
                );

                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    track_key TEXT NOT NULL REFERENCES tracks(track_key) ON DELETE CASCADE,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (playlist_id, position)
                );

                CREATE INDEX IF NOT EXISTS idx_favorites_user
                    ON favorites(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_playlists_user
                    ON playlists(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS playback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    requester_id INTEGER,
                    requester_name TEXT,
                    track_key TEXT NOT NULL REFERENCES tracks(track_key) ON DELETE CASCADE,
                    started_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    ended_at INTEGER,
                    listened_seconds INTEGER NOT NULL DEFAULT 0,
                    completed INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_history_user
                    ON playback_history(requester_id, guild_id, started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_history_guild_open
                    ON playback_history(guild_id, ended_at, id DESC);

                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS discovery_snapshots (
                    track_url TEXT NOT NULL,
                    observed_day TEXT NOT NULL,
                    view_count INTEGER NOT NULL,
                    PRIMARY KEY (track_url, observed_day)
                );

                CREATE INDEX IF NOT EXISTS idx_discovery_snapshots_lookup
                    ON discovery_snapshots(track_url, observed_day DESC);
                """
            )
            await db.commit()

    async def get_state(self, key: str) -> Optional[str]:
        async with self._connect() as db:
            cursor = await db.execute("SELECT value FROM bot_state WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def set_state(self, key: str, value: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO bot_state(key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
            await db.commit()

    async def enrich_discovery_metrics(self, tracks: list[Track]) -> list[Track]:
        """Persist daily view snapshots and attach an observed seven-day delta."""
        today = date.today()
        earliest = (today - timedelta(days=7)).isoformat()
        result: list[Track] = []
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            for track in tracks:
                if track.view_count is None:
                    result.append(track)
                    continue
                row = await self._fetchone(
                    db,
                    """
                    SELECT view_count FROM discovery_snapshots
                    WHERE track_url = ? AND observed_day >= ? AND observed_day < ?
                    ORDER BY observed_day ASC LIMIT 1
                    """,
                    (track.url, earliest, today.isoformat()),
                )
                growth = max(0, track.view_count - int(row[0])) if row else None
                await db.execute(
                    """
                    INSERT INTO discovery_snapshots(track_url, observed_day, view_count)
                    VALUES (?, ?, ?)
                    ON CONFLICT(track_url, observed_day) DO UPDATE SET
                        view_count = MAX(view_count, excluded.view_count)
                    """,
                    (track.url, today.isoformat(), track.view_count),
                )
                result.append(replace(track, view_growth_7d=growth))
            await db.execute(
                "DELETE FROM discovery_snapshots WHERE observed_day < ?",
                ((today - timedelta(days=45)).isoformat(),),
            )
            await db.commit()
        return result

    async def record_playback_start(self, guild_id: int, track: Track) -> int:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._upsert_track(db, track)
            await db.execute(
                """
                UPDATE playback_history
                SET ended_at = unixepoch()
                WHERE guild_id = ? AND ended_at IS NULL
                """,
                (guild_id,),
            )
            cursor = await db.execute(
                """
                INSERT INTO playback_history(
                    guild_id, requester_id, requester_name, track_key
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    track.requester_id,
                    track.requester_name,
                    self.track_key(track),
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def record_playback_end(
        self,
        guild_id: int,
        track: Track,
        listened_seconds: int,
        *,
        completed: bool,
    ) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE playback_history
                SET ended_at = unixepoch(), listened_seconds = ?, completed = ?
                WHERE id = (
                    SELECT id FROM playback_history
                    WHERE guild_id = ? AND track_key = ? AND ended_at IS NULL
                    ORDER BY id DESC LIMIT 1
                )
                """,
                (
                    max(0, int(listened_seconds)),
                    int(completed),
                    guild_id,
                    self.track_key(track),
                ),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def list_history(
        self,
        user_id: int,
        guild_id: int,
        *,
        limit: int = 100,
    ) -> list[HistoryEntry]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT h.id, h.guild_id, h.requester_id, h.requester_name,
                       t.title, t.url, t.source, t.duration, t.uploader, t.thumbnail,
                       h.started_at, h.listened_seconds, h.completed
                FROM playback_history h
                JOIN tracks t ON t.track_key = h.track_key
                WHERE h.requester_id = ? AND h.guild_id = ?
                ORDER BY h.started_at DESC, h.id DESC
                LIMIT ?
                """,
                (user_id, guild_id, max(1, min(limit, 500))),
            )
            return [self._history_from_row(row) for row in rows]

    async def get_listening_stats(
        self,
        guild_id: int,
        *,
        user_id: Optional[int] = None,
    ) -> ListeningStats:
        where = "WHERE h.guild_id = ?"
        params: list[int] = [guild_id]
        if user_id is not None:
            where += " AND h.requester_id = ?"
            params.append(user_id)

        async with self._connect() as db:
            totals = await self._fetchone(
                db,
                f"""
                SELECT COUNT(*), COALESCE(SUM(h.listened_seconds), 0),
                       COUNT(DISTINCT h.track_key),
                       SUM(CASE WHEN t.source = 'YouTube' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN t.source = 'SoundCloud' THEN 1 ELSE 0 END)
                FROM playback_history h
                JOIN tracks t ON t.track_key = h.track_key
                {where}
                """,
                tuple(params),
            )
            top_artist = await self._top_history_value(
                db,
                "t.uploader",
                where,
                tuple(params),
                extra="AND t.uploader IS NOT NULL AND t.uploader != ''",
            )
            top_track = await self._top_history_value(
                db,
                "t.title",
                where,
                tuple(params),
            )
            favorite_count = 0
            if user_id is not None:
                favorite_row = await self._fetchone(
                    db,
                    "SELECT COUNT(*) FROM favorites WHERE user_id = ?",
                    (user_id,),
                )
                favorite_count = int(favorite_row[0])
            return ListeningStats(
                play_count=int(totals[0] or 0),
                listened_seconds=int(totals[1] or 0),
                unique_tracks=int(totals[2] or 0),
                favorite_count=favorite_count,
                top_artist=top_artist,
                top_track=top_track,
                youtube_plays=int(totals[3] or 0),
                soundcloud_plays=int(totals[4] or 0),
            )

    async def get_music_profile(
        self,
        guild_id: int,
        user_id: int,
        *,
        year: Optional[int] = None,
    ) -> MusicProfile:
        where = "WHERE h.guild_id = ? AND h.requester_id = ?"
        params: list[int] = [guild_id, user_id]
        if year is not None:
            where += " AND CAST(strftime('%Y', h.started_at, 'unixepoch') AS INTEGER) = ?"
            params.append(year)

        async with self._connect() as db:
            totals = await self._fetchone(
                db,
                f"""
                SELECT COUNT(*), COALESCE(SUM(h.listened_seconds), 0),
                       COUNT(DISTINCT h.track_key),
                       SUM(CASE WHEN t.source = 'YouTube' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN t.source = 'SoundCloud' THEN 1 ELSE 0 END)
                FROM playback_history h
                JOIN tracks t ON t.track_key = h.track_key
                {where}
                """,
                tuple(params),
            )
            top_artist = await self._top_history_value(
                db,
                "t.uploader",
                where,
                tuple(params),
                extra="AND t.uploader IS NOT NULL AND t.uploader != ''",
            )
            top_track = await self._top_history_value(
                db,
                "t.title",
                where,
                tuple(params),
            )
            favorite_row = await self._fetchone(
                db,
                "SELECT COUNT(*) FROM favorites WHERE user_id = ?",
                (user_id,),
            )
            rows = await self._fetchall(
                db,
                f"""
                SELECT t.title, t.url, t.source, t.duration, t.uploader, t.thumbnail,
                       COUNT(*) AS plays
                FROM playback_history h
                JOIN tracks t ON t.track_key = h.track_key
                {where}
                GROUP BY h.track_key
                ORDER BY plays DESC, MAX(h.started_at) DESC
                LIMIT 5
                """,
                tuple(params),
            )
            peak = await self._fetchone(
                db,
                f"""
                SELECT CAST(strftime('%H', h.started_at, 'unixepoch', 'localtime') AS INTEGER),
                       COUNT(*) AS plays
                FROM playback_history h
                {where}
                GROUP BY 1
                ORDER BY plays DESC, 1 DESC
                LIMIT 1
                """,
                tuple(params),
            )

        stats = ListeningStats(
            play_count=int(totals[0] or 0),
            listened_seconds=int(totals[1] or 0),
            unique_tracks=int(totals[2] or 0),
            favorite_count=int(favorite_row[0] or 0),
            top_artist=top_artist,
            top_track=top_track,
            youtube_plays=int(totals[3] or 0),
            soundcloud_plays=int(totals[4] or 0),
        )
        top_tracks = tuple((self._track_from_row(row), int(row[6])) for row in rows)
        return MusicProfile(
            stats=stats,
            top_tracks=top_tracks,
            peak_hour=int(peak[0]) if peak else None,
            year=year,
        )

    async def toggle_favorite(self, user_id: int, track: Track) -> bool:
        key = self.track_key(track)
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._upsert_track(db, track)
            row = await self._fetchone(
                db,
                "SELECT 1 FROM favorites WHERE user_id = ? AND track_key = ?",
                (user_id, key),
            )
            if row:
                await db.execute(
                    "DELETE FROM favorites WHERE user_id = ? AND track_key = ?",
                    (user_id, key),
                )
                added = False
            else:
                await db.execute(
                    "INSERT INTO favorites(user_id, track_key) VALUES (?, ?)",
                    (user_id, key),
                )
                added = True
            await db.commit()
            return added

    async def remove_favorite(self, user_id: int, track: Track) -> None:
        async with self._connect() as db:
            await db.execute(
                "DELETE FROM favorites WHERE user_id = ? AND track_key = ?",
                (user_id, self.track_key(track)),
            )
            await db.commit()

    async def is_favorite(self, user_id: int, track: Track) -> bool:
        async with self._connect() as db:
            row = await self._fetchone(
                db,
                "SELECT 1 FROM favorites WHERE user_id = ? AND track_key = ?",
                (user_id, self.track_key(track)),
            )
            return row is not None

    async def list_favorites(self, user_id: int, *, limit: int = 100) -> list[Track]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT t.title, t.url, t.source, t.duration, t.uploader, t.thumbnail
                FROM favorites f
                JOIN tracks t ON t.track_key = f.track_key
                WHERE f.user_id = ?
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            return [self._track_from_row(row) for row in rows]

    async def save_playlist(
        self,
        user_id: int,
        name: str,
        tracks: list[Track],
        *,
        overwrite: bool = False,
    ) -> int:
        name = self.validate_playlist_name(name)
        if not tracks:
            raise MusicError("Không có bài nào để lưu.", code="empty_playlist")
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await self._fetchone(
                db,
                "SELECT id FROM playlists WHERE user_id = ? AND name = ?",
                (user_id, name),
            )
            if row and not overwrite:
                raise MusicError("Playlist này đã tồn tại.", code="playlist_exists")
            if row:
                playlist_id = int(row[0])
                await db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
                await db.execute(
                    "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (playlist_id,),
                )
            else:
                cursor = await db.execute(
                    "INSERT INTO playlists(user_id, name) VALUES (?, ?)",
                    (user_id, name),
                )
                playlist_id = int(cursor.lastrowid)

            for position, track in enumerate(tracks):
                await self._upsert_track(db, track)
                await db.execute(
                    "INSERT INTO playlist_tracks(playlist_id, position, track_key) VALUES (?, ?, ?)",
                    (playlist_id, position, self.track_key(track)),
                )
            await db.commit()
            return playlist_id

    async def add_track_to_playlist(self, user_id: int, name: str, track: Track) -> int:
        name = self.validate_playlist_name(name)
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await self._fetchone(
                db,
                "SELECT id FROM playlists WHERE user_id = ? AND name = ?",
                (user_id, name),
            )
            if row:
                playlist_id = int(row[0])
            else:
                cursor = await db.execute(
                    "INSERT INTO playlists(user_id, name) VALUES (?, ?)",
                    (user_id, name),
                )
                playlist_id = int(cursor.lastrowid)
            await self._upsert_track(db, track)
            position_row = await self._fetchone(
                db,
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            )
            await db.execute(
                "INSERT INTO playlist_tracks(playlist_id, position, track_key) VALUES (?, ?, ?)",
                (playlist_id, int(position_row[0]), self.track_key(track)),
            )
            await db.execute(
                "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (playlist_id,),
            )
            await db.commit()
            return playlist_id

    async def list_playlists(self, user_id: int) -> list[PlaylistSummary]:
        async with self._connect() as db:
            rows = await self._fetchall(
                db,
                """
                SELECT p.id, p.name, COUNT(pt.track_key)
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
                WHERE p.user_id = ?
                GROUP BY p.id, p.name
                ORDER BY p.updated_at DESC
                """,
                (user_id,),
            )
            return [PlaylistSummary(int(row[0]), str(row[1]), int(row[2])) for row in rows]

    async def get_playlist(self, user_id: int, playlist_id: int) -> Optional[Playlist]:
        async with self._connect() as db:
            header = await self._fetchone(
                db,
                "SELECT id, name FROM playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            )
            if not header:
                return None
            rows = await self._fetchall(
                db,
                """
                SELECT t.title, t.url, t.source, t.duration, t.uploader, t.thumbnail
                FROM playlist_tracks pt
                JOIN tracks t ON t.track_key = pt.track_key
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
                """,
                (playlist_id,),
            )
            return Playlist(int(header[0]), str(header[1]), tuple(self._track_from_row(row) for row in rows))

    async def delete_playlist(self, user_id: int, playlist_id: int) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                "DELETE FROM playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    def track_key(track: Track) -> str:
        value = f"{track.source.value}\0{track.url}".encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def validate_playlist_name(name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise MusicError("Tên playlist không được để trống.", code="invalid_playlist_name")
        if len(normalized) > 50:
            raise MusicError("Tên playlist tối đa 50 ký tự.", code="invalid_playlist_name")
        return normalized

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path, timeout=10)
        try:
            await db.execute("PRAGMA foreign_keys=ON")
            yield db
        finally:
            await db.close()

    async def _upsert_track(self, db: aiosqlite.Connection, track: Track) -> None:
        await db.execute(
            """
            INSERT INTO tracks(track_key, title, url, source, duration, uploader, thumbnail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_key) DO UPDATE SET
                title = excluded.title,
                duration = excluded.duration,
                uploader = excluded.uploader,
                thumbnail = excluded.thumbnail
            """,
            (
                self.track_key(track),
                track.title,
                track.url,
                track.source.value,
                track.duration,
                track.uploader,
                track.thumbnail,
            ),
        )

    @classmethod
    async def _top_history_value(
        cls,
        db: aiosqlite.Connection,
        column: str,
        where: str,
        params: tuple,
        *,
        extra: str = "",
    ) -> Optional[str]:
        row = await cls._fetchone(
            db,
            f"""
            SELECT {column}, COUNT(*) AS plays
            FROM playback_history h
            JOIN tracks t ON t.track_key = h.track_key
            {where} {extra}
            GROUP BY {column}
            ORDER BY plays DESC, MAX(h.started_at) DESC
            LIMIT 1
            """,
            params,
        )
        return str(row[0]) if row and row[0] else None

    @staticmethod
    async def _fetchone(db: aiosqlite.Connection, query: str, params: tuple = ()):
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()

    @staticmethod
    async def _fetchall(db: aiosqlite.Connection, query: str, params: tuple = ()):
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

    @staticmethod
    def _track_from_row(row) -> Track:
        return Track(
            title=str(row[0]),
            url=str(row[1]),
            source=TrackSource(str(row[2])),
            duration=row[3],
            uploader=row[4],
            thumbnail=row[5],
        )

    @staticmethod
    def _history_from_row(row) -> HistoryEntry:
        track = Track(
            title=str(row[4]),
            url=str(row[5]),
            source=TrackSource(str(row[6])),
            duration=row[7],
            uploader=row[8],
            thumbnail=row[9],
            requester_id=row[2],
            requester_name=row[3],
        )
        return HistoryEntry(
            history_id=int(row[0]),
            guild_id=int(row[1]),
            requester_id=row[2],
            requester_name=row[3],
            track=track,
            started_at=int(row[10]),
            listened_seconds=int(row[11] or 0),
            completed=bool(row[12]),
        )
