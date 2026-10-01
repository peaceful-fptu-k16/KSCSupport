import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from music import (
    AudioEffect,
    EqualizerPreset,
    LoopMode,
    LyricsService,
    MusicError,
    MusicPlayerManager,
    MusicRepository,
    Track,
    TrackSource,
    format_duration,
)
from music.errors import VoiceStateError
from music.ui import PlayerUI
from music.ui.audio_settings import audio_payload
from music.ui.discovery import (
    PartyManager,
    PartyView,
    discovery_payload,
    profile_payload,
    wrapped_payload,
)
from music.ui.history import history_payload, stats_payload
from music.ui.library import favorites_payload, playlists_payload
from music.ui.lyrics_view import lyrics_view_for
from music.ui.queue import queue_payload
from music.ui.search import SearchModal
from music.webhook import NowPlayingWebhook


logger = logging.getLogger(__name__)


class Music(commands.Cog):
    """Discord commands for the shared YouTube and SoundCloud player."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.player_manager = MusicPlayerManager(
            bot,
            on_track_start=self._announce_now_playing,
            on_track_end=self._record_track_end,
            on_track_error=self._announce_track_error,
            on_state_change=self._refresh_player,
        )
        self.repository = MusicRepository()
        self.now_playing_webhook = NowPlayingWebhook(self.repository)
        self._webhook_task: asyncio.Task | None = None
        self._webhook_bump_tasks: dict[int, asyncio.Task] = {}
        self.lyrics_service = LyricsService()
        self.party_manager = PartyManager()
        self.ui = PlayerUI(
            bot,
            self.player_manager,
            self.repository,
            self.lyrics_service,
        )

    async def cog_load(self) -> None:
        await self.repository.initialize()
        await self.ui.start()
        await self.now_playing_webhook.start()
        if self.now_playing_webhook.enabled:
            self._webhook_task = asyncio.create_task(self._webhook_refresh_loop())

    def cog_unload(self) -> None:
        asyncio.create_task(self._shutdown())

    async def _shutdown(self) -> None:
        for task in self._webhook_bump_tasks.values():
            task.cancel()
        if self._webhook_bump_tasks:
            await asyncio.gather(*self._webhook_bump_tasks.values(), return_exceptions=True)
        self._webhook_bump_tasks.clear()
        if self._webhook_task:
            self._webhook_task.cancel()
            try:
                await self._webhook_task
            except asyncio.CancelledError:
                pass
        await self.now_playing_webhook.close()
        await self.ui.close()
        await self.lyrics_service.close()
        await self.player_manager.close()

    @staticmethod
    async def _reply(ctx: commands.Context, content: str | None = None, **kwargs) -> None:
        if ctx.interaction:
            kwargs.setdefault("ephemeral", True)
        await ctx.send(content, **kwargs)

    @staticmethod
    async def _delete_order_message(ctx: commands.Context) -> None:
        if ctx.interaction:
            return
        try:
            await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        except discord.HTTPException as error:
            logger.warning(
                "order_message_delete_failed guild_id=%s message_id=%s error=%s",
                getattr(ctx.guild, "id", None),
                ctx.message.id,
                error,
            )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if self.now_playing_webhook.guild_id and guild.id != self.now_playing_webhook.guild_id:
                continue
            identity_changed = await self.now_playing_webhook.sync_identity(guild)
            if identity_changed:
                await self._publish_now_playing(guild.id, force_repost=True)

    async def _enqueue(
        self,
        ctx: commands.Context,
        query: str,
        source_hint: TrackSource | None = None,
    ) -> None:
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        try:
            if not ctx.guild:
                raise VoiceStateError("Lệnh này chỉ dùng được trong máy chủ Discord.")
            voice_state = getattr(ctx.author, "voice", None)
            if not voice_state or not voice_state.channel:
                raise VoiceStateError("Bạn cần vào một kênh thoại trước.")

            tracks = await self.player_manager.session(ctx.guild.id).enqueue_request(
                ctx.guild,
                voice_state.channel,
                ctx.channel,
                query,
                requester_id=ctx.author.id,
                requester_name=ctx.author.display_name,
                source_hint=source_hint,
            )
        except MusicError as error:
            await self._reply(ctx, error.message)
            return
        except Exception:
            logger.exception(
                "enqueue_unexpected guild_id=%s user_id=%s",
                getattr(ctx.guild, "id", None),
                ctx.author.id,
            )
            await self._reply(ctx, "Không thể chuẩn bị bài hát lúc này. Hãy thử lại sau nhé.")
            return

        if not ctx.interaction:
            await self._delete_order_message(ctx)
            await self.ui.render(ctx.guild.id, force_repost=True)
        elif len(tracks) == 1:
            await self._reply(
                ctx,
                f"Đã thêm **{tracks[0].title}** ({tracks[0].source.value}) vào hàng đợi.",
            )
        else:
            await self._reply(ctx, f"Đã thêm **{len(tracks)} bài** vào hàng đợi.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if message.channel.id == self.now_playing_webhook.channel_id:
            self._schedule_webhook_bump(message.guild.id)
        session = self.player_manager.sessions.get(message.guild.id)
        if not session or not session.player_message or not session.text_channel:
            return
        if message.channel.id != getattr(session.text_channel, "id", None):
            return
        if message.id > session.player_message.id:
            self.ui.schedule_bump(message.guild.id)

    async def _same_voice(self, ctx: commands.Context) -> discord.VoiceClient:
        if not ctx.guild or not ctx.guild.voice_client:
            raise VoiceStateError("Bot chưa ở trong kênh thoại.")
        voice_state = getattr(ctx.author, "voice", None)
        if not voice_state or voice_state.channel != ctx.guild.voice_client.channel:
            raise VoiceStateError("Bạn cần ở cùng kênh thoại với bot.")
        return ctx.guild.voice_client

    async def _announce_now_playing(self, guild_id: int, track: Track) -> None:
        try:
            await self.repository.record_playback_start(guild_id, track)
        except Exception:
            logger.exception("history_start_failed guild_id=%s", guild_id)
        await self.ui.render(guild_id)
        await self._publish_now_playing(guild_id)

    async def _record_track_end(
        self,
        guild_id: int,
        track: Track,
        listened_seconds: int,
        completed: bool,
    ) -> None:
        try:
            await self.repository.record_playback_end(
                guild_id,
                track,
                listened_seconds,
                completed=completed,
            )
        except Exception:
            logger.exception("history_end_failed guild_id=%s", guild_id)

    async def _announce_track_error(
        self,
        guild_id: int,
        track: Track,
        _error: Exception,
    ) -> None:
        logger.warning(
            "player_track_skipped guild_id=%s source=%s title=%r",
            guild_id,
            track.source.value,
            track.title,
        )
        await self.ui.render(guild_id)

    async def _refresh_player(self, guild_id: int) -> None:
        await self.ui.render(guild_id)
        await self._publish_now_playing(guild_id)

    async def _publish_now_playing(
        self,
        guild_id: int,
        *,
        force_repost: bool = False,
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        snapshot = await self.player_manager.session(guild_id).snapshot()
        paused = bool(guild.voice_client and guild.voice_client.is_paused())
        await self.now_playing_webhook.publish(
            guild,
            snapshot,
            paused=paused,
            force_repost=force_repost,
        )

    def _schedule_webhook_bump(self, guild_id: int) -> None:
        previous = self._webhook_bump_tasks.get(guild_id)
        if previous and not previous.done():
            previous.cancel()

        async def bump() -> None:
            try:
                await asyncio.sleep(1.5)
                await self._publish_now_playing(guild_id, force_repost=True)
            except asyncio.CancelledError:
                pass
            finally:
                if self._webhook_bump_tasks.get(guild_id) is asyncio.current_task():
                    self._webhook_bump_tasks.pop(guild_id, None)

        self._webhook_bump_tasks[guild_id] = asyncio.create_task(bump())

    async def _webhook_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.now_playing_webhook.refresh_seconds)
            for guild_id, session in list(self.player_manager.sessions.items()):
                snapshot = await session.snapshot()
                if snapshot.current:
                    await self._publish_now_playing(guild_id)

    @commands.hybrid_command(
        name="phat",
        aliases=["play", "p", "nhac"],
        description="Phát nhạc YouTube hoặc SoundCloud",
    )
    @app_commands.describe(query="Tên bài, link YouTube hoặc link SoundCloud")
    async def play(self, ctx: commands.Context, *, query: str | None = None) -> None:
        if not query:
            if ctx.interaction:
                await ctx.interaction.response.send_modal(
                    SearchModal(self.ui, owner_id=ctx.author.id)
                )
            else:
                await self._reply(ctx, f"Dùng `{ctx.prefix}phat <tên bài hoặc URL>`.")
            return
        await self._enqueue(ctx, query)

    @commands.hybrid_command(
        name="soundcloud",
        aliases=["sc"],
        description="Tìm và phát nhạc SoundCloud",
    )
    @app_commands.describe(query="Tên bài hoặc link SoundCloud")
    async def soundcloud(self, ctx: commands.Context, *, query: str | None = None) -> None:
        if not query:
            if ctx.interaction:
                await ctx.interaction.response.send_modal(
                    SearchModal(
                        self.ui,
                        owner_id=ctx.author.id,
                        source_hint=TrackSource.SOUNDCLOUD,
                    )
                )
            else:
                await self._reply(ctx, f"Dùng `{ctx.prefix}soundcloud <tên bài hoặc URL>`.")
            return
        await self._enqueue(ctx, query, TrackSource.SOUNDCLOUD)

    @commands.hybrid_command(name="pause", description="Tạm dừng nhạc")
    async def pause(self, ctx: commands.Context) -> None:
        try:
            voice_client = await self._same_voice(ctx)
            await self.player_manager.session(ctx.guild.id).pause(voice_client)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, "⏸️ Đã tạm dừng.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="resume", description="Tiếp tục phát nhạc")
    async def resume(self, ctx: commands.Context) -> None:
        try:
            voice_client = await self._same_voice(ctx)
            await self.player_manager.session(ctx.guild.id).resume(voice_client)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, "▶️ Đã tiếp tục phát.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="skip", aliases=["next"], description="Bỏ qua bài hiện tại")
    async def skip(self, ctx: commands.Context) -> None:
        try:
            voice_client = await self._same_voice(ctx)
            await self.player_manager.session(ctx.guild.id).skip(voice_client)
            await self._reply(ctx, "⏭️ Đã bỏ qua bài hiện tại.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="stop",
        aliases=["leave"],
        description="Dừng nhạc và rời kênh thoại",
    )
    async def stop(self, ctx: commands.Context) -> None:
        try:
            voice_client = await self._same_voice(ctx)
            await self.player_manager.session(ctx.guild.id).stop(voice_client)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, "⏹️ Đã dừng nhạc và rời kênh thoại.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="queue", aliases=["q", "hangcho"], description="Xem hàng đợi")
    async def queue(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await queue_payload(
            self.ui,
            self.repository,
            ctx.guild.id,
            ctx.author.id,
        )
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="yeuthich", aliases=["favorites", "fav"], description="Mở nhạc yêu thích")
    async def favorites(self, ctx: commands.Context) -> None:
        embed, view = await favorites_payload(self.ui, self.repository, ctx.author.id)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="playlist", aliases=["playlists"], description="Mở thư viện playlist")
    async def playlists(self, ctx: commands.Context) -> None:
        embed, view = await playlists_payload(self.ui, self.repository, ctx.author.id)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="loibaihat", aliases=["lyrics"], description="Xem lời bài đang phát")
    async def lyrics(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        track = (await self.player_manager.session(ctx.guild.id).snapshot()).current
        if not track:
            await self._reply(ctx, "Không có bài nào đang phát.")
            return
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        try:
            view = await lyrics_view_for(self.lyrics_service, track, ctx.author.id)
            await self._reply(ctx, embed=view.embed(), view=view)
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="lichsu", aliases=["history"], description="Xem lịch sử nghe nhạc")
    async def history(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await history_payload(
            self.ui,
            self.repository,
            ctx.guild.id,
            ctx.author.id,
        )
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="thongke", aliases=["stats"], description="Xem thống kê nghe nhạc")
    async def stats(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await stats_payload(
            self.ui,
            self.repository,
            ctx.guild.id,
            ctx.author.id,
        )
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="aidj", description="Tạo phiên nghe theo mood và gu của bạn")
    async def ai_dj(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await discovery_payload(
            self.ui,
            self.repository,
            ctx.guild.id,
            ctx.author.id,
            mode="ai",
        )
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="radio", description="Phát radio liên tục theo mood")
    async def radio(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await discovery_payload(
            self.ui,
            self.repository,
            ctx.guild.id,
            ctx.author.id,
            mode="radio",
        )
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="hosonhac", aliases=["musicprofile"], description="Xem hồ sơ nghe nhạc")
    async def profile(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await profile_payload(self.repository, ctx.guild.id, ctx.author)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="wrapped", description="Xem tổng kết âm nhạc năm nay")
    async def wrapped(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await wrapped_payload(self.repository, ctx.guild.id, ctx.author)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="party", description="Mở phiên nghe nhạc chung")
    async def party(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        voice = getattr(ctx.author, "voice", None)
        if not voice or not voice.channel:
            await self._reply(ctx, "Bạn cần vào một kênh thoại trước.")
            return
        session = self.party_manager.start(ctx.guild.id, ctx.author)
        view = PartyView(self.ui, self.party_manager, session)
        embed = await view.embed(ctx.guild)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Xem bài đang phát")
    async def now_playing(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        track = (await self.player_manager.session(ctx.guild.id).snapshot()).current
        if not track:
            await self._reply(ctx, "Không có bài nào đang phát.")
            return
        await self._reply(
            ctx,
            f"Đang phát **[{track.title}]({track.url})** · "
            f"{track.source.value} · {format_duration(track.duration)}"
        )

    @commands.hybrid_command(name="volume", aliases=["vol"], description="Đặt âm lượng từ 0 đến 100")
    @app_commands.describe(level="Âm lượng từ 0 đến 100")
    async def volume(self, ctx: commands.Context, level: app_commands.Range[int, 0, 100]) -> None:
        if not ctx.guild:
            return
        try:
            voice_client = await self._same_voice(ctx)
            await self.player_manager.session(ctx.guild.id).set_volume(level, voice_client)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"🔊 Âm lượng: **{level}%**")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="hieuung",
        aliases=["effect", "fx"],
        description="Chọn hiệu ứng âm thanh",
    )
    @app_commands.describe(preset="Preset hiệu ứng; bỏ trống để mở bảng điều khiển")
    @app_commands.choices(
        preset=[
            app_commands.Choice(name="Tắt", value="off"),
            app_commands.Choice(name="Bass Boost", value="bass_boost"),
            app_commands.Choice(name="Slow + Reverb", value="slow_reverb"),
            app_commands.Choice(name="8D Audio", value="8d"),
            app_commands.Choice(name="Nightcore", value="nightcore"),
            app_commands.Choice(name="Vaporwave", value="vaporwave"),
            app_commands.Choice(name="Reverb", value="reverb"),
        ]
    )
    async def effect(self, ctx: commands.Context, preset: str | None = None) -> None:
        if not ctx.guild:
            return
        if preset is None:
            embed, view = await audio_payload(self.ui, ctx.guild.id, ctx.author.id)
            await self._reply(ctx, embed=embed, view=view)
            return
        try:
            voice = await self._same_voice(ctx)
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            effect = AudioEffect.parse(preset)
            profile = await self.player_manager.session(ctx.guild.id).set_effect(
                ctx.guild,
                voice,
                effect,
            )
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"✨ Hiệu ứng: **{profile.effect.label}**")
        except ValueError:
            await self._reply(ctx, "Preset hiệu ứng không hợp lệ.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="equalizer",
        aliases=["eq"],
        description="Chọn preset equalizer",
    )
    @app_commands.describe(preset="Preset equalizer; bỏ trống để mở bảng điều khiển")
    @app_commands.choices(
        preset=[
            app_commands.Choice(name="Cân bằng", value="balanced"),
            app_commands.Choice(name="Bass mạnh", value="bass"),
            app_commands.Choice(name="Chill", value="chill"),
            app_commands.Choice(name="Vocal", value="vocal"),
            app_commands.Choice(name="Gaming", value="gaming"),
            app_commands.Choice(name="Acoustic", value="acoustic"),
            app_commands.Choice(name="EDM", value="edm"),
        ]
    )
    async def equalizer(self, ctx: commands.Context, preset: str | None = None) -> None:
        if not ctx.guild:
            return
        if preset is None:
            embed, view = await audio_payload(self.ui, ctx.guild.id, ctx.author.id)
            await self._reply(ctx, embed=embed, view=view)
            return
        try:
            voice = await self._same_voice(ctx)
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            equalizer = EqualizerPreset.parse(preset)
            profile = await self.player_manager.session(ctx.guild.id).set_equalizer(
                ctx.guild,
                voice,
                equalizer,
            )
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"🎚️ Equalizer: **{profile.equalizer.label}**")
        except ValueError:
            await self._reply(ctx, "Preset equalizer không hợp lệ.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="loop", description="Lặp bài, lặp hàng đợi hoặc tắt")
    @app_commands.describe(mode="off, track hoặc queue")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Tắt", value="off"),
            app_commands.Choice(name="Lặp bài", value="track"),
            app_commands.Choice(name="Lặp hàng đợi", value="queue"),
        ]
    )
    async def loop(self, ctx: commands.Context, mode: str) -> None:
        if not ctx.guild:
            return
        try:
            await self._same_voice(ctx)
            parsed_mode = LoopMode.parse(mode)
            await self.player_manager.session(ctx.guild.id).set_loop_mode(parsed_mode)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"🔁 Chế độ lặp: **{parsed_mode.value}**")
        except ValueError:
            await self._reply(ctx, "Chế độ hợp lệ: `off`, `track`, `queue`.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="congbang",
        aliases=["fairqueue", "fair"],
        description="Luân phiên bài hát giữa những người yêu cầu",
    )
    @app_commands.describe(mode="Bật hoặc tắt; bỏ trống để chuyển trạng thái")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Bật", value="on"),
            app_commands.Choice(name="Tắt", value="off"),
        ]
    )
    async def fair_queue(self, ctx: commands.Context, mode: str | None = None) -> None:
        if not ctx.guild:
            return
        try:
            await self._same_voice(ctx)
            session = self.player_manager.session(ctx.guild.id)
            current = (await session.snapshot()).fair_queue
            enabled = (
                not current
                if mode is None
                else mode.lower() in {"on", "bat", "bật", "true", "1"}
            )
            await session.set_fair_queue(enabled)
            await self.ui.render(ctx.guild.id)
            await self._reply(
                ctx,
                f"⚖️ Hàng đợi công bằng: **{'Bật' if enabled else 'Tắt'}**",
            )
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="tuphat",
        aliases=["autoplay"],
        description="Tự tìm bài liên quan khi hàng đợi hết",
    )
    @app_commands.describe(mode="Bật hoặc tắt; bỏ trống để chuyển trạng thái")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Bật", value="on"),
            app_commands.Choice(name="Tắt", value="off"),
        ]
    )
    async def autoplay(self, ctx: commands.Context, mode: str | None = None) -> None:
        if not ctx.guild:
            return
        try:
            await self._same_voice(ctx)
            session = self.player_manager.session(ctx.guild.id)
            current = (await session.snapshot()).autoplay
            enabled = (
                not current
                if mode is None
                else mode.lower() in {"on", "bat", "bật", "true", "1"}
            )
            await session.set_autoplay(enabled)
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"✨ Tự phát: **{'Bật' if enabled else 'Tắt'}**")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="shuffle", description="Xáo trộn hàng đợi")
    async def shuffle(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        try:
            await self._same_voice(ctx)
            count = await self.player_manager.session(ctx.guild.id).shuffle()
            if count < 2:
                await self._reply(ctx, "Cần ít nhất hai bài trong hàng đợi.")
                return
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, "🔀 Đã xáo trộn hàng đợi.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(
        name="clearqueue",
        aliases=["clear"],
        description="Xóa các bài đang chờ",
    )
    async def clear_queue(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        try:
            await self._same_voice(ctx)
            count = await self.player_manager.session(ctx.guild.id).clear_queue()
            await self.ui.render(ctx.guild.id)
            await self._reply(ctx, f"Đã xóa **{count} bài** khỏi hàng đợi.")
        except MusicError as error:
            await self._reply(ctx, error.message)

    @commands.hybrid_command(name="help", aliases=["commands"], description="Xem các lệnh phát nhạc")
    async def help_command(self, ctx: commands.Context) -> None:
        prefix = ctx.prefix or "/"
        embed = discord.Embed(
            title="KSC Music",
            description="Phát YouTube và SoundCloud trong cùng một hàng đợi.",
            color=0x5865F2,
        )
        embed.add_field(
            name="Phát nhạc",
            value=(
                f"`{prefix}phat <tên/link>` YouTube hoặc SoundCloud\n"
                f"`{prefix}soundcloud <tên/link>` tìm riêng SoundCloud"
            ),
            inline=False,
        )
        embed.add_field(
            name="Điều khiển",
            value=(
                f"`{prefix}pause` · `{prefix}resume` · `{prefix}skip` · `{prefix}stop`\n"
                f"`{prefix}queue` · `{prefix}nowplaying` · `{prefix}volume 50`\n"
                f"`{prefix}loop off|track|queue` · `{prefix}shuffle` · `{prefix}clearqueue`\n"
                f"`{prefix}congbang on|off` · `{prefix}tuphat on|off`\n"
                f"`{prefix}yeuthich` · `{prefix}playlist` · `{prefix}loibaihat`\n"
                f"`{prefix}hieuung` · `{prefix}equalizer` · `{prefix}lichsu` · `{prefix}thongke`"
                f"\n`{prefix}aidj` · `{prefix}radio` · `{prefix}party` · `{prefix}hoso` · `{prefix}wrapped`"
            ),
            inline=False,
        )
        if ctx.interaction:
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self.bot.user or member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            session = self.player_manager.sessions.get(member.guild.id)
            if session:
                await session.handle_external_disconnect()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.player_manager.remove_guild(guild)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
