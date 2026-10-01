import asyncio
import io
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from ..errors import MusicError, VoiceStateError
from ..lyrics import LyricsService
from ..models import LoopMode, PlaybackSnapshot, Track, TrackSource, format_duration
from ..player import GuildPlayerSession, MusicPlayerManager
from ..repository import MusicRepository
from .card import PlayerCardRenderer


logger = logging.getLogger(__name__)


async def require_control_voice(interaction: discord.Interaction) -> discord.VoiceClient:
    if not interaction.guild or not interaction.guild.voice_client:
        raise VoiceStateError("Bot chưa ở trong kênh thoại.")
    voice_state = getattr(interaction.user, "voice", None)
    if not voice_state or voice_state.channel != interaction.guild.voice_client.channel:
        raise VoiceStateError("Bạn cần ở cùng kênh thoại với bot.")
    return interaction.guild.voice_client


class PlayerUI:
    def __init__(
        self,
        bot: commands.Bot,
        manager: MusicPlayerManager,
        repository: MusicRepository,
        lyrics_service: LyricsService,
    ) -> None:
        self.bot = bot
        self.manager = manager
        self.repository = repository
        self.lyrics_service = lyrics_service
        self.card_renderer = PlayerCardRenderer()
        self.refresh_seconds = max(15, int(os.getenv("PLAYER_REFRESH_SECONDS", "30")))
        self._refresh_task: Optional[asyncio.Task] = None
        self._bump_tasks: dict[int, asyncio.Task] = {}

    def register_persistent_view(self) -> None:
        self.bot.add_view(PlayerLayoutView(self))

    async def start(self) -> None:
        self.register_persistent_view()
        if not self._refresh_task or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def close(self) -> None:
        for task in self._bump_tasks.values():
            task.cancel()
        if self._bump_tasks:
            await asyncio.gather(*self._bump_tasks.values(), return_exceptions=True)
        self._bump_tasks.clear()
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        await self.card_renderer.close()

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.refresh_seconds)
            for guild_id, session in list(self.manager.sessions.items()):
                snapshot = await session.snapshot()
                guild = self.bot.get_guild(guild_id)
                if (
                    snapshot.current
                    and session.player_message
                    and guild
                    and guild.voice_client
                    and not guild.voice_client.is_paused()
                ):
                    await self.render(guild_id)

    async def bind_interaction(self, interaction: discord.Interaction) -> GuildPlayerSession:
        if not interaction.guild:
            raise VoiceStateError("Thao tác này chỉ dùng được trong máy chủ Discord.")
        session = self.manager.session(interaction.guild.id)
        if interaction.channel:
            session.text_channel = interaction.channel
        custom_id = str((interaction.data or {}).get("custom_id", ""))
        if (
            isinstance(interaction.message, discord.Message)
            and custom_id.startswith("ksc:player:")
        ):
            session.player_message = interaction.message
        return session

    def schedule_bump(self, guild_id: int, *, delay: float = 1.0) -> None:
        previous = self._bump_tasks.get(guild_id)
        if previous and not previous.done():
            previous.cancel()

        async def bump() -> None:
            try:
                await asyncio.sleep(delay)
                await self.render(guild_id, force_repost=True)
            except asyncio.CancelledError:
                pass
            finally:
                if self._bump_tasks.get(guild_id) is asyncio.current_task():
                    self._bump_tasks.pop(guild_id, None)

        self._bump_tasks[guild_id] = asyncio.create_task(bump())

    def _cancel_scheduled_bump(self, guild_id: int) -> None:
        task = self._bump_tasks.get(guild_id)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()

    async def render(
        self,
        guild_id: int,
        *,
        force_repost: bool = False,
    ) -> Optional[discord.Message]:
        if force_repost:
            self._cancel_scheduled_bump(guild_id)
        session = self.manager.session(guild_id)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None

        async with session.ui_lock:
            snapshot = await session.snapshot()
            paused = bool(guild.voice_client and guild.voice_client.is_paused())
            card = None
            filename = f"ksc-player-{guild_id}.png"
            try:
                card = await self.card_renderer.render(snapshot, paused=paused)
            except Exception:
                logger.exception("player_card_render_failed guild_id=%s", guild_id)
            view = PlayerLayoutView(
                self,
                snapshot=snapshot,
                paused=paused,
                media_url=f"attachment://{filename}" if card else None,
            )

            if session.player_message and not force_repost:
                try:
                    attachments = (
                        [discord.File(io.BytesIO(card), filename=filename)] if card else []
                    )
                    await session.player_message.edit(
                        content=None,
                        embed=None,
                        attachments=attachments,
                        view=view,
                    )
                    return session.player_message
                except discord.NotFound:
                    session.player_message = None
                except discord.HTTPException as error:
                    logger.warning("player_message_edit_failed guild_id=%s error=%s", guild_id, error)

            if not session.text_channel:
                return None
            previous_message = session.player_message
            if card:
                file = discord.File(io.BytesIO(card), filename=filename)
                session.player_message = await session.text_channel.send(file=file, view=view)
            else:
                session.player_message = await session.text_channel.send(view=view)
            if force_repost and previous_message and previous_message.id != session.player_message.id:
                try:
                    await previous_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                except discord.HTTPException as error:
                    logger.warning(
                        "player_message_delete_failed guild_id=%s error=%s",
                        guild_id,
                        error,
                    )
            return session.player_message

    @staticmethod
    def _build_embed(
        guild: discord.Guild,
        snapshot: PlaybackSnapshot,
        paused: bool,
    ) -> discord.Embed:
        track = snapshot.current
        if not track:
            voice = guild.voice_client
            embed = discord.Embed(
                title="🎧 TRÌNH PHÁT NHẠC",
                description="🎵\n\n**Chưa có bài hát nào đang được phát**",
                color=0xC4B5FD,
            )
            if voice and voice.channel:
                listeners = sum(1 for member in voice.channel.members if not member.bot)
                embed.add_field(name="Phòng", value=voice.channel.name, inline=True)
                embed.add_field(name="Người nghe", value=str(listeners), inline=True)
            embed.set_footer(text="Dùng nút Tìm nhạc hoặc /phat để bắt đầu")
            return embed

        color = 0x6EE7B7 if track.source is TrackSource.SOUNDCLOUD else 0xF9A8D4
        state_label = "⏸️ ĐANG TẠM DỪNG" if paused else "🎧 ĐANG PHÁT"
        embed = discord.Embed(
            title=state_label,
            description=f"### [{track.title}]({track.url})\n{track.uploader or 'Không rõ nghệ sĩ'}",
            color=color,
        )
        embed.add_field(name="Thời lượng", value=format_duration(track.duration), inline=True)
        embed.add_field(name="Âm lượng", value=f"{round(snapshot.volume * 100)}%", inline=True)
        embed.add_field(name="Lặp", value=snapshot.loop_mode.value, inline=True)
        embed.add_field(
            name="Hiệu ứng",
            value=snapshot.audio_profile.effect.label,
            inline=True,
        )
        embed.add_field(
            name="Equalizer",
            value=snapshot.audio_profile.equalizer.label,
            inline=True,
        )
        embed.add_field(name="Tiếp theo", value=f"{len(snapshot.queue)} bài", inline=True)
        embed.add_field(name="Nguồn", value=track.source.value, inline=True)
        embed.add_field(
            name="Chế độ",
            value=(
                f"⚖️ {'Bật' if snapshot.fair_queue else 'Tắt'} · "
                f"✨ {'Bật' if snapshot.autoplay else 'Tắt'}"
            ),
            inline=True,
        )
        if track.requester_name:
            embed.add_field(name="Yêu cầu bởi", value=track.requester_name, inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.set_footer(text="KSC Music · YouTube & SoundCloud")
        return embed

    @staticmethod
    def queue_text(snapshot: PlaybackSnapshot) -> str:
        lines = []
        if snapshot.current:
            lines.append(f"**Đang phát:** [{snapshot.current.title}]({snapshot.current.url})")
        for index, track in enumerate(snapshot.queue[:10], start=1):
            lines.append(f"`{index}.` [{track.title}]({track.url}) · {track.source.value}")
        if len(snapshot.queue) > 10:
            lines.append(f"... và {len(snapshot.queue) - 10} bài khác")
        return "\n".join(lines) if lines else "📭 Hàng đợi đang trống."


class PlayerActionButton(discord.ui.Button):
    def __init__(
        self,
        ui: PlayerUI,
        action: str,
        *,
        label: str,
        emoji: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ) -> None:
        super().__init__(
            label=label,
            emoji=emoji,
            style=style,
            custom_id=f"ksc:player:{action}",
        )
        self.ui = ui
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        handlers = PlayerControlsView(self.ui)
        button = getattr(handlers, self.action)
        await button.callback(interaction)


class PlayerLayoutView(discord.ui.LayoutView):
    def __init__(
        self,
        ui: PlayerUI,
        *,
        snapshot: Optional[PlaybackSnapshot] = None,
        paused: bool = False,
        media_url: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=None)
        self.ui = ui
        if snapshot is None:
            snapshot = PlaybackSnapshot(
                current=None,
                queue=(),
                volume=0.5,
                loop_mode=LoopMode.OFF,
            )

        accent = (
            0x6EE7B7
            if snapshot.current and snapshot.current.source is TrackSource.SOUNDCLOUD
            else 0xC4B5FD
        )
        container = discord.ui.Container(accent_color=accent)
        if media_url:
            container.add_item(
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(
                        media_url,
                        description="KSC Music player",
                    )
                )
            )
        container.add_item(discord.ui.TextDisplay(self._status_text(snapshot, paused)))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(
            discord.ui.ActionRow(
                PlayerActionButton(
                    ui,
                    "pause_resume",
                    label="Resume" if paused else "Pause",
                    emoji="▶️" if paused else "⏸️",
                    style=discord.ButtonStyle.primary,
                ),
                PlayerActionButton(ui, "skip", label="Skip", emoji="⏭️"),
                PlayerActionButton(ui, "shuffle", label="Shuffle", emoji="🔀"),
                PlayerActionButton(
                    ui,
                    "stop",
                    label="Stop",
                    emoji="⏹️",
                    style=discord.ButtonStyle.danger,
                ),
            )
        )
        container.add_item(
            discord.ui.ActionRow(
                PlayerActionButton(
                    ui,
                    "search",
                    label="Search",
                    emoji="🔎",
                    style=discord.ButtonStyle.success,
                ),
                PlayerActionButton(
                    ui,
                    "queue",
                    label="Queue",
                    emoji="📜",
                    style=discord.ButtonStyle.primary,
                ),
                PlayerActionButton(ui, "favorite", label="Favorite", emoji="💗"),
                PlayerActionButton(ui, "lyrics", label="Lyrics", emoji="🎤"),
                PlayerActionButton(ui, "more", label="More", emoji="⚙️"),
            )
        )
        self.add_item(container)

    @staticmethod
    def _status_text(snapshot: PlaybackSnapshot, paused: bool) -> str:
        if not snapshot.current:
            return "### Ready to play\n-# Use Search or `/phat` to start listening."
        state = "PAUSED" if paused else "NOW PLAYING"
        modes = [
            f"VOL {round(snapshot.volume * 100)}%",
            f"LOOP {snapshot.loop_mode.value.upper()}",
        ]
        if snapshot.fair_queue:
            modes.append("FAIR QUEUE")
        if snapshot.autoplay:
            modes.append("AUTOPLAY")
        return (
            f"### {state} · [{snapshot.current.title}]({snapshot.current.url})\n"
            f"-# {' · '.join(modes)} · {len(snapshot.queue)} UP NEXT"
        )


class PlayerControlsView(discord.ui.View):
    def __init__(self, ui: PlayerUI, *, paused: bool = False) -> None:
        super().__init__(timeout=None)
        self.ui = ui
        self.pause_resume.label = "Resume" if paused else "Pause"
        self.pause_resume.emoji = "▶️" if paused else "⏸️"

    async def _session_and_voice(
        self,
        interaction: discord.Interaction,
    ) -> tuple[GuildPlayerSession, discord.VoiceClient]:
        session = await self.ui.bind_interaction(interaction)
        return session, await require_control_voice(interaction)

    async def _error(self, interaction: discord.Interaction, error: MusicError) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(error.message, ephemeral=True)
        else:
            await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="Pause",
        emoji="⏸️",
        style=discord.ButtonStyle.primary,
        custom_id="ksc:player:pause_resume",
        row=0,
    )
    async def pause_resume(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        try:
            session, voice = await self._session_and_voice(interaction)
            await interaction.response.defer(ephemeral=True)
            if voice.is_paused():
                await session.resume(voice)
                message = "▶️ Đã tiếp tục phát."
            else:
                await session.pause(voice)
                message = "⏸️ Đã tạm dừng."
            await self.ui.render(interaction.guild_id)
            await interaction.followup.send(message, ephemeral=True)
        except MusicError as error:
            await self._error(interaction, error)

    @discord.ui.button(
        label="Skip",
        emoji="⏭️",
        style=discord.ButtonStyle.secondary,
        custom_id="ksc:player:skip",
        row=0,
    )
    async def skip(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session, voice = await self._session_and_voice(interaction)
            await interaction.response.defer(ephemeral=True)
            await session.skip(voice)
            await interaction.followup.send("⏭️ Đã bỏ qua bài hiện tại.", ephemeral=True)
        except MusicError as error:
            await self._error(interaction, error)

    @discord.ui.button(
        label="Shuffle",
        emoji="🔀",
        style=discord.ButtonStyle.secondary,
        custom_id="ksc:player:shuffle",
        row=0,
    )
    async def shuffle(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session, _voice = await self._session_and_voice(interaction)
            count = await session.shuffle()
            if count < 2:
                raise MusicError("Cần ít nhất hai bài trong hàng đợi.", code="short_queue")
            await interaction.response.defer(ephemeral=True)
            await self.ui.render(interaction.guild_id)
            await interaction.followup.send("🔀 Đã trộn hàng đợi.", ephemeral=True)
        except MusicError as error:
            await self._error(interaction, error)

    @discord.ui.button(
        label="Stop",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="ksc:player:stop",
        row=0,
    )
    async def stop(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session, voice = await self._session_and_voice(interaction)
            await interaction.response.defer(ephemeral=True)
            await session.stop(voice)
            await self.ui.render(interaction.guild_id)
            await interaction.followup.send("⏹️ Đã dừng nhạc.", ephemeral=True)
        except MusicError as error:
            await self._error(interaction, error)

    @discord.ui.button(
        label="Search",
        emoji="🔎",
        style=discord.ButtonStyle.success,
        custom_id="ksc:player:search",
        row=1,
    )
    async def search(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.ui.bind_interaction(interaction)
        from .search import SearchModal

        await interaction.response.send_modal(SearchModal(self.ui, owner_id=interaction.user.id))

    @discord.ui.button(
        label="Queue",
        emoji="📜",
        style=discord.ButtonStyle.primary,
        custom_id="ksc:player:queue",
        row=1,
    )
    async def queue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        session = await self.ui.bind_interaction(interaction)
        from .queue import queue_payload

        embed, view = await queue_payload(
            self.ui,
            self.ui.repository,
            session.guild_id,
            interaction.user.id,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Favorite",
        emoji="💗",
        style=discord.ButtonStyle.secondary,
        custom_id="ksc:player:favorite",
        row=1,
    )
    async def favorite(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        session = await self.ui.bind_interaction(interaction)
        track = (await session.snapshot()).current
        if not track:
            await interaction.response.send_message("Không có bài nào đang phát.", ephemeral=True)
            return
        added = await self.ui.repository.toggle_favorite(interaction.user.id, track)
        message = "Đã thêm vào nhạc yêu thích." if added else "Đã bỏ khỏi nhạc yêu thích."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(
        label="Lyrics",
        emoji="🎤",
        style=discord.ButtonStyle.secondary,
        custom_id="ksc:player:lyrics",
        row=1,
    )
    async def lyrics(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        session = await self.ui.bind_interaction(interaction)
        track = (await session.snapshot()).current
        if not track:
            await interaction.response.send_message("Không có bài nào đang phát.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        from .lyrics_view import lyrics_view_for

        try:
            view = await lyrics_view_for(self.ui.lyrics_service, track, interaction.user.id)
            await interaction.followup.send(embed=view.embed(), view=view, ephemeral=True)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)

    @discord.ui.button(
        label="More",
        emoji="⚙️",
        style=discord.ButtonStyle.secondary,
        custom_id="ksc:player:more",
        row=1,
    )
    async def more(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            await self.ui.bind_interaction(interaction)
            await interaction.response.send_message(
                "Tùy chọn phát nhạc",
                view=MoreOptionsView(self.ui, interaction.user.id),
                ephemeral=True,
            )
        except MusicError as error:
            await self._error(interaction, error)


class MoreOptionsView(discord.ui.View):
    def __init__(self, ui: PlayerUI, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.ui = ui
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng điều khiển này thuộc người dùng khác.", ephemeral=True)
        return False

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = await self.ui.bind_interaction(interaction)
            await require_control_voice(interaction)
            await interaction.response.defer(ephemeral=True)
            snapshot = await session.snapshot()
            modes = [LoopMode.OFF, LoopMode.TRACK, LoopMode.QUEUE]
            mode = modes[(modes.index(snapshot.loop_mode) + 1) % len(modes)]
            await session.set_loop_mode(mode)
            await self.ui.render(interaction.guild_id)
            await interaction.edit_original_response(
                content=f"Chế độ lặp: **{mode.value}**",
                view=self,
            )
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="Volume",
        emoji="🔊",
        style=discord.ButtonStyle.secondary,
    )
    async def volume(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            await self.ui.bind_interaction(interaction)
            await require_control_voice(interaction)
            await interaction.response.send_modal(VolumeModal(self.ui))
        except MusicError as error:
            await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(label="Playlist", emoji="💿", style=discord.ButtonStyle.secondary)
    async def playlists(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from .library import playlists_payload

        embed, view = await playlists_payload(
            self.ui,
            self.ui.repository,
            interaction.user.id,
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    @discord.ui.button(label="Audio", emoji="🎚️", style=discord.ButtonStyle.primary)
    async def audio(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from .audio_settings import audio_payload

        if not interaction.guild_id:
            return
        embed, view = await audio_payload(self.ui, interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    @discord.ui.button(label="History", emoji="🕒", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from .history import history_payload

        if not interaction.guild_id:
            return
        embed, view = await history_payload(
            self.ui,
            self.ui.repository,
            interaction.guild_id,
            interaction.user.id,
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class VolumeModal(discord.ui.Modal, title="🔊 Âm lượng"):
    level = discord.ui.TextInput(
        label="Mức âm lượng từ 0 đến 100",
        placeholder="75",
        min_length=1,
        max_length=3,
    )

    def __init__(self, ui: PlayerUI) -> None:
        super().__init__()
        self.ui = ui

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            value = int(self.level.value)
            if not 0 <= value <= 100:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Âm lượng phải là số từ 0 đến 100.",
                ephemeral=True,
            )
            return

        try:
            session = await self.ui.bind_interaction(interaction)
            voice = await require_control_voice(interaction)
            await session.set_volume(value, voice)
            await interaction.response.defer(ephemeral=True)
            await self.ui.render(interaction.guild_id)
            await interaction.followup.send(f"🔊 Âm lượng: **{value}%**", ephemeral=True)
        except MusicError as error:
            await interaction.response.send_message(error.message, ephemeral=True)
