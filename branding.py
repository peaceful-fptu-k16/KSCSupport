import hashlib
import logging
import os
from pathlib import Path

import discord


BRAND_NAME = os.getenv("BOT_BRAND_NAME", "KSC Gaming")
PROJECT_ROOT = Path(__file__).resolve().parent
BRAND_MASCOT_PATH = Path(
    os.getenv(
        "BOT_MASCOT_PATH",
        str(PROJECT_ROOT / "docs" / "assets" / "ksc-mascot.png"),
    )
)
BRAND_STATE_PATH = PROJECT_ROOT / "data" / "brand-avatar.sha256"
logger = logging.getLogger(__name__)


def brand_avatar_bytes() -> bytes:
    return BRAND_MASCOT_PATH.read_bytes()


def brand_avatar_fingerprint() -> str:
    return hashlib.sha256(brand_avatar_bytes()).hexdigest()[:16]


async def sync_bot_avatar(user: discord.ClientUser) -> bool:
    """Upload the project mascot once per asset revision."""
    if os.getenv("SYNC_BRAND_AVATARS", "true").strip().lower() in {"0", "false", "off", "no"}:
        return False
    avatar = brand_avatar_bytes()
    fingerprint = hashlib.sha256(avatar).hexdigest()
    try:
        if BRAND_STATE_PATH.exists() and BRAND_STATE_PATH.read_text(encoding="ascii").strip() == fingerprint:
            return False
        await user.edit(avatar=avatar)
        BRAND_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BRAND_STATE_PATH.write_text(fingerprint, encoding="ascii")
        return True
    except (OSError, ValueError, discord.HTTPException) as error:
        logger.warning("bot_avatar_sync_failed error=%s", error)
        return False
