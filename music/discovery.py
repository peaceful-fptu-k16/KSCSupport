import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from .models import Track, TrackSource


@dataclass(frozen=True, slots=True)
class DiscoveryPreset:
    key: str
    label: str
    emoji: str
    query: str
    color: int
    freshness: str = "balanced"
    trend: str = "high"
    min_views: int = 0


RADIO_PRESETS = {
    "trending": DiscoveryPreset(
        "trending", "V-Pop Trending", "🔥", "V-Pop trending Official MV", 0xF97316, "recent", "high"
    ),
    "new": DiscoveryPreset(
        "new", "Nhạc Việt Mới", "🆕", "nhạc Việt mới phát hành Official MV", 0x6EE7B7, "new", "medium"
    ),
    "rising": DiscoveryPreset(
        "rising", "Đang Tăng Nhanh", "🚀", "V-Pop đang thịnh hành Official MV", 0x7DD3FC, "recent", "rising"
    ),
    "million": DiscoveryPreset(
        "million", "Triệu View", "👀", "V-Pop triệu view Official MV", 0xC4B5FD, "balanced", "popular", 1_000_000
    ),
    "hits": DiscoveryPreset(
        "hits", "V-Pop Hits", "💎", "V-Pop hits Official MV", 0xF9A8D4, "any", "popular"
    ),
}


AI_PRESETS = {
    "trending": DiscoveryPreset("trending", "V-Pop Trending", "🔥", "V-Pop trending Official MV", 0xF97316, "recent", "high"),
    "new": DiscoveryPreset("new", "Nhạc mới", "🆕", "nhạc Việt mới phát hành Official MV", 0x6EE7B7, "new", "medium"),
    "hits": DiscoveryPreset("hits", "Hit lớn", "👑", "V-Pop hit triệu view Official MV", 0xFDE68A, "any", "popular"),
    "chill": DiscoveryPreset("chill", "Chill", "🌙", "V-Pop chill Official MV", 0xC4B5FD),
    "love": DiscoveryPreset("love", "Love", "💕", "V-Pop tình yêu Official MV", 0xF9A8D4),
    "sad": DiscoveryPreset("sad", "Tâm trạng", "💔", "V-Pop buồn tâm trạng Official MV", 0xA78BFA),
    "energy": DiscoveryPreset("energy", "Năng lượng", "⚡", "V-Pop năng lượng Official MV", 0xFDE68A),
    "rap": DiscoveryPreset("rap", "Rap Việt", "🔥", "Rap Việt hot Official MV", 0xF97316),
    "drill": DiscoveryPreset("drill", "Drill", "🖤", "Rap Việt drill Official MV", 0x94A3B8),
    "hoodtrap": DiscoveryPreset("hoodtrap", "Hoodtrap", "🏙️", "Rap Việt hoodtrap Official MV", 0x7DD3FC),
    "jerk_drill": DiscoveryPreset("jerk_drill", "Jerk Drill", "⚡", "Rap Việt jerk drill Official MV", 0xFDE68A),
    "sexy_drill": DiscoveryPreset("sexy_drill", "Sexy Drill", "💜", "Rap Việt sexy drill Official MV", 0xC4B5FD),
    "trap": DiscoveryPreset("trap", "Trap", "🔊", "Rap Việt trap Official MV", 0xF97316),
    "rage": DiscoveryPreset("rage", "Rage", "🧨", "Rap Việt rage Official MV", 0xEF4444),
    "melodic_rap": DiscoveryPreset("melodic_rap", "Melodic Rap", "🌃", "Rap Việt melodic rap Official MV", 0x7DD3FC),
    "rnb": DiscoveryPreset("rnb", "Hip-Hop / R&B", "🎧", "Việt Nam hip hop R&B Official MV", 0x6EE7B7),
}


MIN_SONG_SECONDS = 90
MAX_SONG_SECONDS = 8 * 60
REJECT_PATTERN = re.compile(
    r"\b(lyrics?|lyric video|lời bài hát|karaoke|cover|re-?upload|fan\s?made|"
    r"sped\s?up|speed\s?up|slowed(?:\s*\+\s*reverb)?|nightcore|vietsub|"
    r"unofficial|official audio|audio official|visualizer|dance practice|live performance)\b",
    re.IGNORECASE,
)
OFFICIAL_MV_PATTERN = re.compile(
    r"\b(official\s+(?:music\s+)?video|official\s+mv|mv\s+official|music\s+video)\b",
    re.IGNORECASE,
)
UNOFFICIAL_REMIX_PATTERN = re.compile(r"\b(remix|bootleg|mashup)\b", re.IGNORECASE)
TRUSTED_CHANNEL_PATTERN = re.compile(
    r"(official|vevo|m-?tp entertainment|1989s entertainment|space\s?speakers|"
    r"st\.319|universal music|warner music|sony music|def jam|dao music|"
    r"dreams entertainment|yin yang media|t?ouliver|rap việt)",
    re.IGNORECASE,
)
VIETNAMESE_DIACRITICS_PATTERN = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
VIETNAMESE_SIGNAL_PATTERN = re.compile(
    r"\b(v-?pop|nhạc\s+việt|viet(?:nam|\s+nam|mese)|\.vn\b|rap\s+việt)\b",
    re.IGNORECASE,
)


def is_vietnamese_track(track: Track) -> bool:
    text = " ".join(
        part for part in (track.title, track.uploader or "", track.discovery_text or "") if part
    )
    return bool(
        VIETNAMESE_DIACRITICS_PATTERN.search(text)
        or VIETNAMESE_SIGNAL_PATTERN.search(text)
    )


def is_official_vpop(track: Track) -> bool:
    if track.source is not TrackSource.YOUTUBE:
        return False
    text = f"{track.title} {track.uploader or ''}"
    if REJECT_PATTERN.search(text) or UNOFFICIAL_REMIX_PATTERN.search(track.title):
        return False
    title_is_mv = bool(OFFICIAL_MV_PATTERN.search(track.title))
    channel_is_official = bool(TRUSTED_CHANNEL_PATTERN.search(track.uploader or ""))
    # Verified chart and compilation channels are not artist sources. The
    # upload must identify as an MV or come from an explicitly official channel.
    return bool(
        is_vietnamese_track(track)
        and (channel_is_official or (title_is_mv and track.channel_verified))
    )


def is_discovery_candidate(track: Track) -> bool:
    return bool(
        is_official_vpop(track)
        and track.duration is not None
        and MIN_SONG_SECONDS <= track.duration <= MAX_SONG_SECONDS
    )


def _age_days(track: Track, *, today: Optional[date] = None) -> Optional[int]:
    if not track.upload_date:
        return None
    try:
        uploaded = date.fromisoformat(track.upload_date)
    except ValueError:
        return None
    return max(0, ((today or datetime.now(timezone.utc).date()) - uploaded).days)


def discovery_score(track: Track, preset: DiscoveryPreset, *, today: Optional[date] = None) -> float:
    views = max(0, track.view_count or 0)
    growth = max(0, track.view_growth_7d or 0)
    age = _age_days(track, today=today)
    popularity = math.log10(views + 10)
    freshness = 0.0 if age is None else max(0.0, 8.0 - math.log2(age + 2))
    growth_score = math.log10(growth + 10)

    if preset.freshness == "new":
        return freshness * 5.0 + popularity * 1.8 + growth_score * 2.0
    if preset.trend == "rising":
        return growth_score * 7.0 + freshness * 3.0 + popularity
    if preset.trend == "popular":
        return popularity * 6.0 + freshness
    if preset.freshness == "recent":
        return popularity * 3.5 + freshness * 3.0 + growth_score * 3.0
    return popularity * 4.0 + freshness * 1.5 + growth_score * 2.0


def artist_key(track: Track) -> str:
    value = track.uploader or re.split(r"[-|–—]", track.title, maxsplit=1)[0]
    value = re.sub(r"\b(official|vevo|music|entertainment|channel)\b", "", value, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", value.casefold()) or track.url


def rank_discovery_tracks(
    tracks: Iterable[Track],
    preset: DiscoveryPreset,
    *,
    limit: int,
    artist_gap: int = 4,
) -> list[Track]:
    unique: dict[str, Track] = {}
    for track in tracks:
        if not is_discovery_candidate(track):
            continue
        if preset.min_views and (track.view_count or 0) < preset.min_views:
            continue
        unique.setdefault(track.url, replace(track, is_official=True))

    candidates = list(unique.values())
    ranked_with_positions = sorted(
        enumerate(candidates),
        key=lambda pair: (
            discovery_score(pair[1], preset)
            + (max(0.0, 12.0 - pair[0] * 0.6) if preset.freshness == "new" else 0.0)
        ),
        reverse=True,
    )
    ranked = [track for _index, track in ranked_with_positions]
    selected: list[Track] = []
    deferred: list[Track] = []
    for track in ranked:
        recent_artists = {artist_key(item) for item in selected[-artist_gap:]}
        if artist_key(track) in recent_artists:
            deferred.append(track)
            continue
        selected.append(track)
        if len(selected) >= limit:
            return selected

    for track in deferred:
        if track.url not in {item.url for item in selected}:
            selected.append(track)
        if len(selected) >= limit:
            break
    return selected


def discovery_queries(preset: DiscoveryPreset) -> list[str]:
    year = datetime.now(timezone.utc).year
    return [
        f"{preset.query} {year}",
        f"{preset.query} Việt Nam",
        f"{preset.query} MV chính thức nghệ sĩ Việt",
    ]


def custom_ai_preset(genre: str, vibe: str, trend: str, freshness: str) -> DiscoveryPreset:
    clean = lambda value: " ".join(value.strip().split())
    genre = clean(genre) or "V-Pop"
    vibe = clean(vibe)
    trend_value = clean(trend).casefold()
    freshness_value = clean(freshness).casefold()
    trend_mode = "rising" if "tăng" in trend_value else ("popular" if "cao" in trend_value else "medium")
    fresh_mode = "new" if "mới" in freshness_value else ("any" if "kinh" in freshness_value else "balanced")
    query = f"nhạc Việt {genre} {vibe} đang hot Official MV"
    label = " / ".join(part for part in (genre, vibe) if part)[:80]
    return DiscoveryPreset("custom", label, "✨", query, 0xC4B5FD, fresh_mode, trend_mode)
