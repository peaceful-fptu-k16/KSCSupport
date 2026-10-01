import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from .errors import MusicError
from .models import Track


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LyricsResult:
    track_name: str
    artist_name: str
    lyrics: str
    instrumental: bool = False


class LyricsService:
    BASE_URL = "https://lrclib.net/api"

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_lock = asyncio.Lock()
        self._last_request = 0.0
        self._cache: dict[str, LyricsResult] = {}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_lyrics(self, track: Track) -> LyricsResult:
        if track.url in self._cache:
            return self._cache[track.url]

        title = self._clean_title(track.title)
        artist = track.uploader or ""
        params = {"track_name": title, "artist_name": artist}
        if track.duration:
            params["duration"] = str(track.duration)

        data = await self._request("/get", params=params, allow_not_found=True)
        if not data:
            results = await self._request(
                "/search",
                params={"track_name": title, "artist_name": artist},
                allow_not_found=True,
            )
            if not results:
                raise MusicError("Chưa tìm thấy lời cho bài hát này.", code="lyrics_not_found")
            data = self._best_match(results, track)

        plain = str(data.get("plainLyrics") or "").strip()
        instrumental = bool(data.get("instrumental"))
        if not plain and instrumental:
            result = LyricsResult(
                track_name=str(data.get("trackName") or title),
                artist_name=str(data.get("artistName") or artist),
                lyrics="Bản nhạc không lời.",
                instrumental=True,
            )
        elif not plain:
            raise MusicError("Nguồn lời hiện không có bản văn bản đầy đủ.", code="lyrics_not_found")
        else:
            result = LyricsResult(
                track_name=str(data.get("trackName") or title),
                artist_name=str(data.get("artistName") or artist),
                lyrics=plain,
            )
        self._cache[track.url] = result
        return result

    async def _request(self, path: str, *, params: dict, allow_not_found: bool):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "KSCMusicBot/1.0 (Discord music bot)"},
            )

        async with self._request_lock:
            wait = 0.3 - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            for attempt in range(2):
                try:
                    async with self._session.get(f"{self.BASE_URL}{path}", params=params) as response:
                        self._last_request = time.monotonic()
                        if response.status == 404 and allow_not_found:
                            return None
                        if response.status == 429 and attempt == 0:
                            retry_after = min(float(response.headers.get("Retry-After", "1")), 5.0)
                            await asyncio.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        return await response.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                    logger.info("lyrics_request_failed path=%s error=%s", path, error)
                    if attempt == 1:
                        raise MusicError(
                            "Dịch vụ lời bài hát đang bận. Hãy thử lại sau.",
                            code="lyrics_service_error",
                        ) from error
            return None

    @staticmethod
    def _best_match(results: list[dict], track: Track) -> dict:
        if not track.duration:
            return results[0]
        return min(results, key=lambda item: abs(int(item.get("duration") or 0) - track.duration))

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = re.sub(
            r"\s*[\[(](official|lyrics?|audio|video|mv|m/v).*?[\])]",
            "",
            title,
            flags=re.IGNORECASE,
        )
        return " ".join(cleaned.split())
