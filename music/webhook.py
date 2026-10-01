import logging
import os
from typing import Optional

import aiohttp
import discord

from branding import BRAND_NAME, brand_avatar_bytes, brand_avatar_fingerprint

from .models import PlaybackSnapshot, TrackSource, format_duration
from .repository import MusicRepository


logger = logging.getLogger(__name__)


class NowPlayingWebhook:
    def __init__(self, repository: MusicRepository) -> None:
        self.repository = repository
        self.url = os.getenv("DISCORD_NOW_PLAYING_WEBHOOK_URL", "").strip()
        self.display_name = os.getenv(
            "NOW_PLAYING_WEBHOOK_NAME",
            "KSC Music",
        ).strip() or "KSC Music"
        guild_id = os.getenv("NOW_PLAYING_WEBHOOK_GUILD_ID", "").strip()
        self.guild_id = int(guild_id) if guild_id.isdigit() else None
        self.refresh_seconds = max(
            15,
            int(os.getenv("NOW_PLAYING_WEBHOOK_REFRESH_SECONDS", "30")),
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._webhook: Optional[discord.Webhook] = None
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
            logger.error("now_playing_webhook_invalid_url")
            await self.close()
        except discord.HTTPException as error:
            logger.warning("now_playing_webhook_fetch_failed status=%s", error.status)

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
        state_key = f"now_playing_webhook_identity:{guild.id}"
        if await self.repository.get_state(state_key) == signature:
            return False
        try:
            self._webhook = await self._webhook.edit(
                name=self.display_name,
                avatar=brand_avatar_bytes(),
            )
            await self.repository.set_state(state_key, signature)
            return True
        except discord.HTTPException as error:
            logger.warning("now_playing_webhook_identity_failed status=%s", error.status)
            return False

    async def publish(
        self,
        guild: discord.Guild,
        snapshot: PlaybackSnapshot,
        *,
        paused: bool,
        force_repost: bool = False,
    ) -> None:
        if not self._webhook or (self.guild_id and guild.id != self.guild_id):
            return

        embed = self.build_embed(guild, snapshot, paused=paused)
        state_key = f"now_playing_webhook_message:{guild.id}"
        stored_id = await self.repository.get_state(state_key)
        message_id = int(stored_id) if stored_id and stored_id.isdigit() else None
        try:
            if message_id and not force_repost:
                await self._webhook.edit_message(
                    message_id,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
        except discord.NotFound:
            message_id = None
        except discord.HTTPException as error:
            logger.warning(
                "now_playing_webhook_edit_failed guild_id=%s status=%s",
                guild.id,
                error.status,
            )
            return

        try:
            message = await self._webhook.send(
                embed=embed,
                username=self.display_name,
                allowed_mentions=discord.AllowedMentions.none(),
                wait=True,
            )
            if message:
                await self.repository.set_state(state_key, str(message.id))
                if force_repost and message_id and message.id != message_id:
                    try:
                        await self._webhook.delete_message(message_id)
                    except discord.NotFound:
                        pass
                    except discord.HTTPException as error:
                        logger.warning(
                            "now_playing_webhook_delete_failed guild_id=%s status=%s",
                            guild.id,
                            error.status,
                        )
        except discord.HTTPException as error:
            logger.warning(
                "now_playing_webhook_send_failed guild_id=%s status=%s",
                guild.id,
                error.status,
            )

    @classmethod
    def build_embed(
        cls,
        guild: discord.Guild,
        snapshot: PlaybackSnapshot,
        *,
        paused: bool,
    ) -> discord.Embed:
        track = snapshot.current
        if not track:
            embed = discord.Embed(
                title="🎵 PLAYER READY",
                description="No track is playing right now.",
                color=0xC4B5FD,
            )
            embed.set_footer(text=f"● SERVER ONLINE · {BRAND_NAME}")
            return embed

        color = 0x6EE7B7 if track.source is TrackSource.SOUNDCLOUD else 0xF9A8D4
        state = "PAUSED" if paused else "NOW PLAYING"
        progress = cls.progress_bar(snapshot.elapsed, track.duration)
        title = discord.utils.escape_markdown(track.title)
        artist = discord.utils.escape_markdown(track.uploader or "Unknown artist")
        embed = discord.Embed(
            title=f"🎵 {state}",
            description=(
                f"### [{title}]({track.url})\n"
                f"**{artist}**\n\n"
                f"`{format_duration(snapshot.elapsed)}` {progress} "
                f"`{format_duration(track.duration)}`"
            ),
            color=color,
        )
        embed.add_field(
            name="🔊 Volume",
            value=f"**{round(snapshot.volume * 100)}%**",
            inline=True,
        )
        embed.add_field(
            name="📜 Up Next",
            value=f"**{len(snapshot.queue)} tracks**",
            inline=True,
        )
        embed.add_field(
            name="👤 Requested by",
            value=f"**{track.requester_name or 'Autoplay'}**",
            inline=True,
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.set_footer(text=f"● SERVER ONLINE · {BRAND_NAME} · {track.source.value}")
        return embed

    @staticmethod
    def progress_bar(elapsed: int, duration: Optional[int], *, width: int = 12) -> str:
        if not duration:
            return "━━━━━━━━━━━━"
        position = min(width, max(0, round(width * elapsed / duration)))
        return f"{'━' * position}●{'━' * (width - position)}"
