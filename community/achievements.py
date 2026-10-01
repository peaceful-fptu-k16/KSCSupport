from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class Achievement:
    key: str
    title: str
    description: str
    category: str
    metric: str
    threshold: int
    icon: str
    public: bool = False
    manual: bool = False


ACHIEVEMENTS = (
    Achievement("member_new", "Thành viên mới", "Gia nhập KSC Gaming", "tenure", "days", 0, "🌱"),
    Achievement("member_familiar", "Thành viên quen thuộc", "Đồng hành 100 ngày", "tenure", "days", 100, "🌿"),
    Achievement("member_longtime", "Thành viên lâu năm", "Đồng hành 365 ngày", "tenure", "days", 365, "🌳", True),
    Achievement("member_veteran", "Server Veteran", "Đồng hành 2 năm", "tenure", "days", 730, "🏛️", True),
    Achievement("chat_start", "Khởi đầu câu chuyện", "Gửi 100 tin nhắn", "chat", "messages", 100, "💬"),
    Achievement("chat_regular", "Người trò chuyện", "Gửi 1.000 tin nhắn", "chat", "messages", 1_000, "🗣️"),
    Achievement("chat_active", "Thành viên tích cực", "Gửi 5.000 tin nhắn", "chat", "messages", 5_000, "🔥"),
    Achievement("chat_voice", "Community Voice", "Gửi 10.000 tin nhắn", "chat", "messages", 10_000, "✨", True),
    Achievement("voice_start", "Bắt đầu trò chuyện", "Tham gia voice 10 giờ", "voice", "voice_seconds", 10 * 3600, "🎙️"),
    Achievement("voice_regular", "Thành viên thường xuyên", "Tham gia voice 100 giờ", "voice", "voice_seconds", 100 * 3600, "🎧"),
    Achievement("voice_veteran", "Voice Veteran", "Tham gia voice 500 giờ", "voice", "voice_seconds", 500 * 3600, "🔥"),
    Achievement("voice_legend", "Voice Legend", "Tham gia voice 1.000 giờ", "voice", "voice_seconds", 1_000 * 3600, "👑", True),
    Achievement("special_founder", "Founding Member", "Thành viên sáng lập", "special", "manual", 0, "💎", True, True),
    Achievement("special_contributor", "Community Contributor", "Đóng góp nổi bật cho cộng đồng", "special", "manual", 0, "🌟", True, True),
    Achievement("special_helper", "Community Helper", "Giúp đỡ cộng đồng", "special", "manual", 0, "🤝", True, True),
    Achievement("special_champion", "Event Champion", "Thành tích đặc biệt tại sự kiện", "special", "manual", 0, "🏆", True, True),
)

BY_KEY = {achievement.key: achievement for achievement in ACHIEVEMENTS}
CATEGORIES = {
    "all": "Tất cả",
    "tenure": "Gắn bó",
    "chat": "Trò chuyện",
    "voice": "Voice",
    "special": "Đặc biệt",
}


def automatic_keys(*, days: int, messages: int, voice_seconds: int) -> list[str]:
    values = {"days": days, "messages": messages, "voice_seconds": voice_seconds}
    return [
        item.key
        for item in ACHIEVEMENTS
        if not item.manual and values[item.metric] >= item.threshold
    ]


def featured_keys(unlocked: Iterable[str], limit: int = 5) -> list[str]:
    """Choose the most meaningful unlocked badges for the profile card."""
    order = {item.key: index for index, item in enumerate(ACHIEVEMENTS)}
    available = (BY_KEY[key] for key in set(unlocked) if key in BY_KEY)
    ranked = sorted(
        available,
        key=lambda item: (item.manual, item.public, order[item.key]),
        reverse=True,
    )
    return [item.key for item in ranked[:limit]]
