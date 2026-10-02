import asyncio
import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv(".env.local" if os.path.exists(".env.local") else ".env")

from branding import sync_bot_avatar
from music.errors import MusicError


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ksc-music")


class MusicCommandTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, MusicError):
            message = original.message
        else:
            logger.error(
                "app_command_failed guild_id=%s user_id=%s command=%s error=%s",
                interaction.guild_id,
                interaction.user.id,
                interaction.command.name if interaction.command else None,
                original,
            )
            message = "Không thể thực hiện thao tác lúc này. Hãy thử lại sau nhé."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class MusicBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        super().__init__(
            command_prefix=os.getenv("BOT_PREFIX", "!"),
            intents=intents,
            help_command=None,
            case_insensitive=True,
            tree_cls=MusicCommandTree,
        )
        self._brand_avatar_synced = False

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.community")
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            guild_synced = await self.tree.sync(guild=guild)
            logger.info(
                "Synced %s guild slash commands guild_id=%s",
                len(guild_synced),
                guild_id,
            )
            self.tree.clear_commands(guild=None)
            global_synced = await self.tree.sync()
            logger.info(
                "Cleared global slash commands to prevent guild duplicates remaining=%s",
                len(global_synced),
            )
        else:
            synced = await self.tree.sync()
            logger.info("Synced %s global slash commands", len(synced))

    async def on_ready(self) -> None:
        if self.user and not self._brand_avatar_synced:
            changed = await sync_bot_avatar(self.user)
            self._brand_avatar_synced = True
            logger.info("Brand avatar ready changed=%s", changed)
        logger.info("Connected as %s in %s guild(s)", self.user, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{self.command_prefix}phat | YouTube & SoundCloud",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Thiếu nội dung. Dùng `{ctx.prefix}help` để xem cách dùng.")
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Vui lòng thử lại sau {error.retry_after:.1f} giây.")
            return

        original = getattr(error, "original", error)
        if isinstance(original, MusicError):
            await ctx.send(original.message)
            return
        logger.error(
            "prefix_command_failed guild_id=%s user_id=%s command=%s error=%s",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            ctx.command.qualified_name if ctx.command else None,
            original,
        )
        await ctx.send("Không thể thực hiện thao tác lúc này. Hãy thử lại sau nhé.")


async def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing from .env")

    async with MusicBot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
