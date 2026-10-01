import asyncio
import logging
import os
import re
from typing import Optional

import aiohttp
import discord

from branding import BRAND_NAME, brand_avatar_bytes, brand_avatar_fingerprint

from .repository import CommunityRepository


logger = logging.getLogger(__name__)


class ServerGuideWebhook:
    def __init__(self, repository: CommunityRepository) -> None:
        self.repository = repository
        self.url = os.getenv("DISCORD_SERVER_GUIDE_WEBHOOK_URL", "").strip()
        self.display_name = os.getenv("SERVER_GUIDE_WEBHOOK_NAME", BRAND_NAME).strip() or BRAND_NAME
        guild_id = os.getenv("SERVER_GUIDE_WEBHOOK_GUILD_ID", "").strip()
        self.guild_id = int(guild_id) if guild_id.isdigit() else None
        self.bump_delay = max(3, int(os.getenv("SERVER_GUIDE_BUMP_DELAY_SECONDS", "8")))
        self._session: Optional[aiohttp.ClientSession] = None
        self._webhook: Optional[discord.Webhook] = None
        self._lock = asyncio.Lock()
        self.channel_id: Optional[int] = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    async def start(self) -> None:
        if not self.enabled:
            return
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        try:
            self._webhook = discord.Webhook.from_url(self.url, session=self._session)
            webhook = await self._webhook.fetch()
            self.channel_id = webhook.channel_id
        except ValueError:
            logger.error("server_guide_webhook_invalid_url")
            await self.close()
        except discord.HTTPException as error:
            logger.warning("server_guide_webhook_fetch_failed status=%s", error.status)

    async def close(self) -> None:
        self._webhook = None
        self.channel_id = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def sync_identity(self, guild: discord.Guild) -> bool:
        if not self._webhook:
            return False
        signature = f"{self.display_name}:mascot:{brand_avatar_fingerprint()}"
        state_key = "server_guide_webhook_identity"
        if await self.repository.get_config(guild.id, state_key) == signature:
            return False
        try:
            self._webhook = await self._webhook.edit(
                name=self.display_name,
                avatar=brand_avatar_bytes(),
            )
            await self.repository.set_config(guild.id, state_key, signature)
            return True
        except discord.HTTPException as error:
            logger.warning("server_guide_webhook_identity_failed status=%s", error.status)
            return False

    async def publish(self, guild: discord.Guild, *, force_repost: bool = False) -> None:
        if not self._webhook or (self.guild_id and guild.id != self.guild_id):
            return
        async with self._lock:
            embeds = self.build_embeds(guild)
            state_key = "server_guide_webhook_message_id"
            stored_id = await self.repository.get_config(guild.id, state_key)
            message_id = int(stored_id) if stored_id and stored_id.isdigit() else None
            try:
                if message_id and not force_repost:
                    await self._webhook.edit_message(
                        message_id,
                        embeds=embeds,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    return
            except discord.NotFound:
                message_id = None
            except discord.HTTPException as error:
                logger.warning("server_guide_webhook_edit_failed status=%s", error.status)
                return

            try:
                message = await self._webhook.send(
                    embeds=embeds,
                    username=self.display_name,
                    allowed_mentions=discord.AllowedMentions.none(),
                    wait=True,
                )
                if not message:
                    return
                await self.repository.set_config(guild.id, state_key, str(message.id))
                if force_repost and message_id and message.id != message_id:
                    try:
                        await self._webhook.delete_message(message_id)
                    except discord.NotFound:
                        pass
                    except discord.HTTPException as error:
                        logger.warning("server_guide_webhook_delete_failed status=%s", error.status)
            except discord.HTTPException as error:
                logger.warning("server_guide_webhook_send_failed status=%s", error.status)

    @staticmethod
    def _channel(guild: discord.Guild, keyword: str) -> str:
        wanted = re.sub(r"[^a-z0-9]", "", keyword.casefold())
        for channel in guild.text_channels:
            normalized = re.sub(r"[^a-z0-9]", "", channel.name.casefold())
            if wanted in normalized:
                return channel.mention
        return f"`#{keyword}`"

    @classmethod
    def build_embeds(cls, guild: discord.Guild) -> list[discord.Embed]:
        rules = cls._channel(guild, "rules")
        announcements = cls._channel(guild, "announcements")
        introductions = cls._channel(guild, "introductions")
        gossip = cls._channel(guild, "gossip")
        music = cls._channel(guild, "music")
        events = cls._channel(guild, "events")
        weekly = cls._channel(guild, "weekly-recap")
        bot_channel = cls._channel(guild, "bot")

        overview = discord.Embed(
            title=f"✨ WELCOME TO {BRAND_NAME.upper()}",
            description=(
                "Một cộng đồng dành cho những cuộc trò chuyện thoải mái, âm nhạc, gaming "
                "và những khoảnh khắc đáng nhớ cùng nhau.\n\n"
                "**Bắt đầu nhanh**\n"
                f"1. Đọc nội quy tại {rules}\n"
                f"2. Giới thiệu bản thân tại {introductions}\n"
                f"3. Tham gia trò chuyện tại {gossip}"
            ),
            color=0xC4B5FD,
        )
        bot_avatar = getattr(getattr(guild, "me", None), "display_avatar", None)
        if bot_avatar:
            overview.set_thumbnail(url=bot_avatar.url)
        elif guild.icon:
            overview.set_thumbnail(url=guild.icon.url)
        overview.add_field(name="👥 Thành viên", value=f"**{guild.member_count or len(guild.members):,}**", inline=True)
        overview.add_field(name="📡 Trạng thái", value="**Online**", inline=True)
        overview.add_field(name="💜 Không gian", value="**Community First**", inline=True)

        guide = discord.Embed(
            title="🧭 SERVER GUIDE & BOT COMMANDS",
            color=0x7DD3FC,
        )
        guide.add_field(
            name="Kênh quan trọng",
            value=(
                f"📢 {announcements} · Thông báo chính thức\n"
                f"💬 {gossip} · Trò chuyện cộng đồng\n"
                f"🎉 {events} · Sự kiện sắp tới\n"
                f"📰 {weekly} · Tổng kết mỗi tuần"
            ),
            inline=False,
        )
        guide.add_field(
            name="Music",
            value=(
                f"Dùng tại {music}\n"
                "`/phat` phát YouTube hoặc SoundCloud · `/queue` xem hàng đợi\n"
                "`/aidj` V-Pop tự động · `/radio` nghe liên tục · `/help` xem toàn bộ lệnh"
            ),
            inline=False,
        )
        guide.add_field(
            name="Community",
            value=(
                f"Dùng tại {bot_channel}\n"
                "`/hoso` hồ sơ · `/huyhieu` thành tựu · `/sinhnhat` thiết lập sinh nhật\n"
                "`/lichsinhnhat` xem lịch · `/weekly` xem tổng kết cộng đồng"
            ),
            inline=False,
        )

        rules_embed = discord.Embed(
            title="📜 COMMUNITY RULES",
            description=(
                "**01 · Tôn trọng lẫn nhau**\n"
                "Không công kích, quấy rối, phân biệt đối xử hoặc cố tình gây căng thẳng.\n\n"
                "**02 · Giữ nội dung đúng kênh**\n"
                "Không spam, flood, quảng cáo trái phép hoặc lạm dụng mention.\n\n"
                "**03 · Nội dung an toàn**\n"
                "Không chia sẻ nội dung NSFW, độc hại, lừa đảo hoặc vi phạm pháp luật.\n\n"
                "**04 · Tôn trọng quyền riêng tư**\n"
                "Không công khai thông tin, hình ảnh hoặc hội thoại riêng khi chưa được đồng ý.\n\n"
                f"Nội quy đầy đủ và cập nhật mới nhất luôn nằm tại {rules}."
            ),
            color=0xF9A8D4,
        )
        rules_embed.set_footer(text=f"{BRAND_NAME} · Friendly · Safe · Connected")
        return [overview, guide, rules_embed]
