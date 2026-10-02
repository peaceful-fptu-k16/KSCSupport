import asyncio
import logging
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional

import discord
import yt_dlp

from .audio import (
    DEFAULT_USER_AGENT,
    DynamicEqualizerAudio,
    PipedFFmpegAudio,
    build_before_options,
    build_ffmpeg_options,
    get_ffmpeg_executable,
)
from .effects import AudioProfile
from .errors import MusicError, MusicUnavailableError
from .models import Track, TrackSource


logger = logging.getLogger(__name__)
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


class MediaExtractor:
    def __init__(self, *, max_playlist_tracks: int = 50, concurrency: int = 2) -> None:
        self.max_playlist_tracks = max_playlist_tracks
        self._semaphore = asyncio.Semaphore(concurrency)

    def _options(self, **overrides: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "nocheckcertificate": True,
            "source_address": "0.0.0.0",
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
            "http_headers": {"User-Agent": DEFAULT_USER_AGENT},
            **overrides,
        }
        cookie_file = os.getenv("YTDLP_COOKIE_FILE")
        if cookie_file:
            options["cookiefile"] = cookie_file
        return options

    async def extract_tracks(
        self,
        query: str,
        *,
        requester_id: Optional[int],
        requester_name: Optional[str],
        source_hint: Optional[TrackSource] = None,
    ) -> list[Track]:
        return await self._extract_track_list(
            query,
            requester_id=requester_id,
            requester_name=requester_name,
            source_hint=source_hint,
            search_limit=1,
            result_limit=self.max_playlist_tracks,
        )

    async def search_tracks(
        self,
        query: str,
        *,
        requester_id: Optional[int],
        requester_name: Optional[str],
        source_hint: Optional[TrackSource] = None,
        limit: int = 5,
    ) -> list[Track]:
        return await self._extract_track_list(
            query,
            requester_id=requester_id,
            requester_name=requester_name,
            source_hint=source_hint,
            search_limit=max(1, min(limit, 10)),
            result_limit=max(1, min(limit, 10)),
        )

    async def _extract_track_list(
        self,
        query: str,
        *,
        requester_id: Optional[int],
        requester_name: Optional[str],
        source_hint: Optional[TrackSource],
        search_limit: int,
        result_limit: int,
    ) -> list[Track]:
        query = query.strip()
        if not query:
            raise MusicError("Hãy nhập tên bài hát hoặc URL.", code="empty_query")
        if not URL_PATTERN.match(query):
            prefix = (
                f"scsearch{search_limit}"
                if source_hint is TrackSource.SOUNDCLOUD
                else f"ytsearch{search_limit}"
            )
            query = f"{prefix}:{query}"

        options = self._options(
            format="bestaudio/best",
            extract_flat="in_playlist",
            noplaylist=False,
            playlistend=result_limit,
        )
        data = await self._run_extract(query, options)
        tracks = [
            track
            for info in self._valid_entries(data)[:result_limit]
            if (
                track := self.track_from_info(
                    info,
                    requester_id=requester_id,
                    requester_name=requester_name,
                )
            )
            is not None
        ]
        if not tracks:
            raise MusicUnavailableError("Không tìm thấy bài nhạc có thể phát.")
        return tracks

    async def create_audio(
        self,
        track: Track,
        volume: float,
        *,
        profile: AudioProfile = AudioProfile(),
        seek_seconds: int = 0,
    ) -> discord.AudioSource:
        if track.source is TrackSource.YOUTUBE:
            ffmpeg = self._youtube_pipe(track, profile, seek_seconds)
            equalized = DynamicEqualizerAudio(ffmpeg, profile.equalizer)
            return discord.PCMVolumeTransformer(equalized, volume=volume)

        options = self._options(format="bestaudio/best", noplaylist=True)
        data = self._first_valid_entry(await self._run_extract(track.url, options))
        if not data:
            raise MusicUnavailableError()
        stream_url = self._stream_url(data)
        if not stream_url:
            raise MusicUnavailableError("Không lấy được luồng âm thanh.")

        ffmpeg = discord.FFmpegPCMAudio(
            stream_url,
            executable=get_ffmpeg_executable(),
            before_options=build_before_options(seek_seconds),
            options=build_ffmpeg_options(profile.ffmpeg_filter_chain),
        )
        equalized = DynamicEqualizerAudio(ffmpeg, profile.equalizer)
        return discord.PCMVolumeTransformer(equalized, volume=volume)

    def _youtube_pipe(
        self,
        track: Track,
        profile: AudioProfile,
        seek_seconds: int,
    ) -> PipedFFmpegAudio:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--quiet",
            "--no-warnings",
            "--no-playlist",
            "--no-check-certificates",
            "--socket-timeout",
            "20",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            "--user-agent",
            DEFAULT_USER_AGENT,
            "--format",
            "bestaudio/best",
            "--output",
            "-",
        ]
        cookie_file = os.getenv("YTDLP_COOKIE_FILE")
        if cookie_file:
            command.extend(("--cookies", cookie_file))
        command.extend(("--", track.url))

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        downloader = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if not downloader.stdout:
            downloader.terminate()
            raise MusicUnavailableError("Không mở được luồng tải YouTube.")

        before_options = f"-ss {max(0, int(seek_seconds))}" if seek_seconds else None
        try:
            ffmpeg = PipedFFmpegAudio(
                downloader,
                executable=get_ffmpeg_executable(),
                before_options=before_options,
                options=build_ffmpeg_options(profile.ffmpeg_filter_chain),
            )
        except Exception:
            if downloader.stdout:
                downloader.stdout.close()
            downloader.terminate()
            raise
        return ffmpeg

    async def _run_extract(self, query: str, options: dict[str, Any]) -> Any:
        def extract() -> Any:
            with yt_dlp.YoutubeDL(options) as ytdl:
                return ytdl.extract_info(query, download=False)

        try:
            async with self._semaphore:
                return await asyncio.to_thread(extract)
        except yt_dlp.utils.DownloadError as exc:
            logger.info("media_extract_failed query_type=%s error=%s", self._query_type(query), exc)
            raise MusicUnavailableError() from exc
        except Exception as exc:
            logger.exception("media_extract_unexpected query_type=%s", self._query_type(query))
            raise MusicUnavailableError("Không thể đọc nguồn nhạc lúc này.") from exc

    @classmethod
    def track_from_info(
        cls,
        info: Mapping[str, Any],
        *,
        requester_id: Optional[int],
        requester_name: Optional[str],
    ) -> Optional[Track]:
        url = cls._stable_url(info)
        if not url:
            return None
        raw_duration = info.get("duration")
        try:
            duration = max(0, int(float(raw_duration))) if raw_duration is not None else None
        except (TypeError, ValueError):
            duration = None
        return Track(
            title=str(info.get("title") or "Không rõ tên"),
            url=url,
            source=cls._source(info),
            duration=duration,
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=cls._thumbnail(info),
            requester_id=requester_id,
            requester_name=requester_name,
            view_count=cls._optional_int(info.get("view_count")),
            upload_date=cls._upload_date(info),
            channel_id=str(info.get("channel_id") or info.get("uploader_id") or "") or None,
            channel_verified=bool(
                info.get("channel_is_verified")
                or info.get("uploader_is_verified")
                or info.get("is_verified")
            ),
            discovery_text=str(info.get("description") or "")[:2000] or None,
        )

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _upload_date(info: Mapping[str, Any]) -> Optional[str]:
        raw = str(info.get("upload_date") or info.get("release_date") or "")
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        timestamp = info.get("release_timestamp") or info.get("timestamp")
        try:
            return datetime.fromtimestamp(float(timestamp), timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            return None

    @classmethod
    def _thumbnail(cls, info: Mapping[str, Any]) -> Optional[str]:
        thumbnail = info.get("thumbnail")
        if thumbnail and URL_PATTERN.match(str(thumbnail)):
            return str(thumbnail)

        thumbnails = info.get("thumbnails") or []
        for item in reversed(thumbnails):
            if isinstance(item, Mapping):
                candidate = item.get("url")
                if candidate and URL_PATTERN.match(str(candidate)):
                    return str(candidate)

        extractor = str(info.get("extractor_key") or info.get("extractor") or "").lower()
        video_id = info.get("id")
        if "youtube" in extractor and video_id:
            return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        return None

    @staticmethod
    def _source(info: Mapping[str, Any]) -> TrackSource:
        extractor = str(info.get("extractor_key") or info.get("extractor") or "").lower()
        return TrackSource.SOUNDCLOUD if "soundcloud" in extractor else TrackSource.YOUTUBE

    @classmethod
    def _stable_url(cls, info: Mapping[str, Any]) -> str:
        url = str(info.get("webpage_url") or info.get("original_url") or info.get("url") or "")
        extractor = str(info.get("extractor_key") or info.get("extractor") or "").lower()
        video_id = info.get("id")
        if "youtube" in extractor and not URL_PATTERN.match(url) and video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url

    @staticmethod
    def _first_valid_entry(data: Any) -> Optional[Mapping[str, Any]]:
        if not data:
            return None
        if isinstance(data, Mapping) and "entries" in data:
            return next((entry for entry in data.get("entries") or [] if entry), None)
        return data if isinstance(data, Mapping) else None

    @classmethod
    def _valid_entries(cls, data: Any) -> list[Mapping[str, Any]]:
        if isinstance(data, Mapping) and "entries" in data:
            return [entry for entry in data.get("entries") or [] if entry]
        first = cls._first_valid_entry(data)
        return [first] if first else []

    @staticmethod
    def _stream_url(data: Mapping[str, Any]) -> str:
        if data.get("url"):
            return str(data["url"])
        formats = data.get("formats") or []
        audio_formats = [
            item for item in formats if item.get("url") and item.get("acodec") != "none"
        ]
        return str(audio_formats[-1]["url"]) if audio_formats else ""

    @staticmethod
    def _query_type(query: str) -> str:
        if query.startswith("ytsearch"):
            return "youtube_search"
        if query.startswith("scsearch"):
            return "soundcloud_search"
        if "soundcloud.com" in query:
            return "soundcloud_url"
        return "url"
