import asyncio
import math
from dataclasses import replace
from typing import TYPE_CHECKING

import discord

from ..errors import MusicError
from ..models import Track, format_duration
from ..repository import HistoryEntry, ListeningStats, MusicRepository

if TYPE_CHECKING:
    from .player import PlayerUI


PAGE_SIZE = 8


def _shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _listening_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} giây"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} giờ {minutes} phút" if hours else f"{minutes} phút"


def _played_duration(seconds: int) -> str:
    return "0:00" if seconds <= 0 else format_duration(seconds)


async def _enqueue(
    ui: "PlayerUI",
    interaction: discord.Interaction,
    track: Track,
    position: str,
) -> None:
    if not interaction.guild or not interaction.channel:
        raise MusicError("Thao tác này chỉ dùng được trong máy chủ.")
    voice_state = getattr(interaction.user, "voice", None)
    if not voice_state or not voice_state.channel:
        raise MusicError("Bạn cần vào một kênh thoại trước.")
    requested_track = replace(
        track,
        requester_id=interaction.user.id,
        requester_name=interaction.user.display_name,
    )
    await ui.manager.session(interaction.guild.id).enqueue_tracks(
        interaction.guild,
        voice_state.channel,
        interaction.channel,
        [requested_track],
        position=position,
    )
    await ui.render(interaction.guild.id)


class HistorySelect(discord.ui.Select):
    def __init__(self, parent: "HistoryView") -> None:
        super().__init__(placeholder="Chọn bài để phát lại", row=0)
        self.parent_view = parent
        self.refresh_options()

    def refresh_options(self) -> None:
        start = self.parent_view.page * PAGE_SIZE
        entries = self.parent_view.entries[start : start + PAGE_SIZE]
        self.options = [
            discord.SelectOption(
                label=_shorten(entry.track.title, 100),
                description=_shorten(
                    f"{entry.track.uploader or entry.track.source.value} · "
                    f"đã nghe {_played_duration(entry.listened_seconds)}",
                    100,
                ),
                value=str(start + index),
            )
            for index, entry in enumerate(entries)
        ] or [discord.SelectOption(label="Chưa có lịch sử", value="empty")]
        self.disabled = not entries

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "empty":
            return
        entry = self.parent_view.entries[int(self.values[0])]
        embed = discord.Embed(
            title="🕒 PHÁT LẠI",
            description=(
                f"**[{entry.track.title}]({entry.track.url})**\n"
                f"{entry.track.uploader or 'Không rõ nghệ sĩ'}"
            ),
            color=0xC4B5FD,
        )
        embed.add_field(name="Đã nghe", value=_played_duration(entry.listened_seconds))
        embed.add_field(name="Lần gần nhất", value=f"<t:{entry.started_at}:R>")
        await interaction.response.edit_message(
            embed=embed,
            view=HistoryTrackView(
                self.parent_view.ui,
                self.parent_view.repository,
                entry.track,
                self.parent_view.guild_id,
                self.parent_view.owner_id,
            ),
        )


class HistoryView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        entries: list[HistoryEntry],
        guild_id: int,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.entries = entries
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.page = 0
        self.history_select = HistorySelect(self)
        self.add_item(self.history_select)
        self._update_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Lịch sử này thuộc người dùng khác.", ephemeral=True)
        return False

    def embed(self) -> discord.Embed:
        page_count = max(1, math.ceil(len(self.entries) / PAGE_SIZE))
        start = self.page * PAGE_SIZE
        embed = discord.Embed(title="🕒 LỊCH SỬ NGHE", color=0x7DD3FC)
        if not self.entries:
            embed.description = "Chưa có bài nào trong lịch sử. Hãy phát một bài để bắt đầu."
        else:
            lines = []
            for index, entry in enumerate(self.entries[start : start + PAGE_SIZE], start=start + 1):
                status = "✓" if entry.completed else "◷"
                lines.append(
                    f"`{index:02d}.` {status} [{entry.track.title}]({entry.track.url})\n"
                    f"　{entry.track.uploader or 'Không rõ nghệ sĩ'} · "
                    f"<t:{entry.started_at}:t> · {_played_duration(entry.listened_seconds)}"
                )
            embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(self.entries)} lượt phát · Trang {self.page + 1}/{page_count}")
        return embed

    def _update_controls(self) -> None:
        page_count = max(1, math.ceil(len(self.entries) / PAGE_SIZE))
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= page_count - 1
        self.history_select.refresh_options()

    @discord.ui.button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._update_controls()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page += 1
        self._update_controls()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stats", emoji="📊", style=discord.ButtonStyle.primary, row=1)
    async def stats(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed, view = await stats_payload(
            self.ui,
            self.repository,
            self.guild_id,
            self.owner_id,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class HistoryTrackView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        track: Track,
        guild_id: int,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.track = track
        self.guild_id = guild_id
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Lịch sử này thuộc người dùng khác.", ephemeral=True)
        return False

    async def _play(self, interaction: discord.Interaction, position: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await _enqueue(self.ui, interaction, self.track, position)
            await interaction.followup.send(f"Đã thêm **{self.track.title}**.", ephemeral=True)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)

    @discord.ui.button(label="Play Now", emoji="▶️", style=discord.ButtonStyle.primary)
    async def play_now(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "now")

    @discord.ui.button(label="Add to Queue", emoji="➕", style=discord.ButtonStyle.success)
    async def add_queue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "end")

    @discord.ui.button(label="Favorite", emoji="💗", style=discord.ButtonStyle.secondary)
    async def favorite(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        added = await self.repository.toggle_favorite(self.owner_id, self.track)
        message = "Đã thêm vào nhạc yêu thích." if added else "Đã bỏ khỏi nhạc yêu thích."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed, view = await history_payload(
            self.ui,
            self.repository,
            self.guild_id,
            self.owner_id,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class StatsView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        guild_id: int,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng thống kê này thuộc người dùng khác.", ephemeral=True)
        return False

    @discord.ui.button(label="History", emoji="🕒", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed, view = await history_payload(
            self.ui,
            self.repository,
            self.guild_id,
            self.owner_id,
        )
        await interaction.response.edit_message(embed=embed, view=view)


def stats_embed(personal: ListeningStats, server: ListeningStats) -> discord.Embed:
    embed = discord.Embed(
        title="📊 THỐNG KÊ ÂM NHẠC",
        description="Hoạt động nghe nhạc được tính từ các phiên phát thực tế.",
        color=0xF9A8D4,
    )
    embed.add_field(name="Lượt phát của bạn", value=f"**{personal.play_count}**", inline=True)
    embed.add_field(name="Đã nghe", value=f"**{_listening_time(personal.listened_seconds)}**", inline=True)
    embed.add_field(name="Bài khác nhau", value=f"**{personal.unique_tracks}**", inline=True)
    embed.add_field(name="Yêu thích", value=f"**{personal.favorite_count}**", inline=True)
    embed.add_field(name="Top nghệ sĩ", value=personal.top_artist or "Chưa có", inline=True)
    embed.add_field(name="Top bài hát", value=personal.top_track or "Chưa có", inline=True)
    embed.add_field(
        name="Nguồn của bạn",
        value=f"YouTube **{personal.youtube_plays}** · SoundCloud **{personal.soundcloud_plays}**",
        inline=False,
    )
    embed.add_field(
        name="Toàn server",
        value=(
            f"**{server.play_count}** lượt phát · {_listening_time(server.listened_seconds)}\n"
            f"Top nghệ sĩ: **{server.top_artist or 'Chưa có'}**\n"
            f"Top bài: **{server.top_track or 'Chưa có'}**"
        ),
        inline=False,
    )
    return embed


async def history_payload(
    ui: "PlayerUI",
    repository: MusicRepository,
    guild_id: int,
    owner_id: int,
) -> tuple[discord.Embed, HistoryView]:
    entries = await repository.list_history(owner_id, guild_id)
    view = HistoryView(ui, repository, entries, guild_id, owner_id)
    return view.embed(), view


async def stats_payload(
    ui: "PlayerUI",
    repository: MusicRepository,
    guild_id: int,
    owner_id: int,
) -> tuple[discord.Embed, StatsView]:
    personal, server = await asyncio.gather(
        repository.get_listening_stats(guild_id, user_id=owner_id),
        repository.get_listening_stats(guild_id),
    )
    return (
        stats_embed(personal, server),
        StatsView(ui, repository, guild_id, owner_id),
    )
