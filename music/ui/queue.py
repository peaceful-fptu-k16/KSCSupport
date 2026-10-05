import math

import discord

from ..errors import MusicError
from ..models import format_duration
from ..player import MusicPlayerManager
from ..repository import MusicRepository
from .player import PlayerUI, require_control_voice


PAGE_SIZE = 8


class QueueView(discord.ui.View):
    def __init__(
        self,
        ui: PlayerUI,
        repository: MusicRepository,
        guild_id: int,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.manager: MusicPlayerManager = ui.manager
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.page = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Hàng đợi này thuộc người dùng khác.", ephemeral=True)
        return False

    async def payload(self) -> tuple[discord.Embed, "QueueView"]:
        snapshot = await self.manager.session(self.guild_id).snapshot()
        page_count = max(1, math.ceil(len(snapshot.queue) / PAGE_SIZE))
        self.page = min(self.page, page_count - 1)
        start = self.page * PAGE_SIZE
        tracks = snapshot.queue[start : start + PAGE_SIZE]

        embed = discord.Embed(title="📜 HÀNG ĐỢI", color=0x7DD3FC)
        if snapshot.current:
            embed.description = (
                f"**Đang phát**\n[{snapshot.current.title}]({snapshot.current.url})\n"
                f"{snapshot.current.uploader or 'Không rõ nghệ sĩ'} · "
                f"{format_duration(snapshot.elapsed)} / {format_duration(snapshot.current.duration)}"
            )
        else:
            embed.description = "📭 Chưa có bài hát nào đang phát."

        for offset, track in enumerate(tracks, start=start + 1):
            requester = f" · 🙋 {track.requester_name}" if track.requester_name else ""
            embed.add_field(
                name=f"{offset:02d}. {track.title}",
                value=f"{track.uploader or 'Không rõ nghệ sĩ'}{requester} · {format_duration(track.duration)}",
                inline=False,
            )
        total_seconds = sum(track.duration or 0 for track in snapshot.queue)
        embed.set_footer(
            text=(
                f"{len(snapshot.queue)} bài · {format_duration(total_seconds)} · "
                f"Công bằng {'Bật' if snapshot.fair_queue else 'Tắt'} · "
                f"Tự phát {'Bật' if snapshot.autoplay else 'Tắt'} · "
                f"DJ Mix V5 {'Bật' if snapshot.dj_mix else 'Tắt'} · "
                f"Smart Order {'Bật' if snapshot.smart_reorder else 'Tắt'} · "
                f"Trang {self.page + 1}/{page_count}"
            )
        )
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= page_count - 1
        self.shuffle.disabled = len(snapshot.queue) < 2
        self.fair_queue.label = f"Fair Queue: {'On' if snapshot.fair_queue else 'Off'}"
        self.fair_queue.style = (
            discord.ButtonStyle.success if snapshot.fair_queue else discord.ButtonStyle.secondary
        )
        self.autoplay.label = f"Autoplay: {'On' if snapshot.autoplay else 'Off'}"
        self.autoplay.style = (
            discord.ButtonStyle.success if snapshot.autoplay else discord.ButtonStyle.secondary
        )
        self.dj_mix.label = f"DJ Mix V5: {'On' if snapshot.dj_mix else 'Off'}"
        self.dj_mix.style = (
            discord.ButtonStyle.success if snapshot.dj_mix else discord.ButtonStyle.secondary
        )
        self.smart_reorder.label = f"Smart Order: {'On' if snapshot.smart_reorder else 'Off'}"
        self.smart_reorder.style = (
            discord.ButtonStyle.success
            if snapshot.smart_reorder
            else discord.ButtonStyle.secondary
        )
        self.clear.disabled = not snapshot.queue
        self.save.disabled = not snapshot.current and not snapshot.queue
        return embed, self

    @discord.ui.button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        embed, view = await self.payload()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page += 1
        embed, view = await self.payload()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.primary, row=1)
    async def shuffle(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            await self.manager.session(self.guild_id).shuffle()
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="Fair Queue: Off",
        emoji="⚖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def fair_queue(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            session = self.manager.session(self.guild_id)
            snapshot = await session.snapshot()
            await session.set_fair_queue(not snapshot.fair_queue)
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="Autoplay: Off",
        emoji="✨",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def autoplay(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            session = self.manager.session(self.guild_id)
            snapshot = await session.snapshot()
            await session.set_autoplay(not snapshot.autoplay)
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="DJ Mix V5: Off",
        emoji="🎛️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def dj_mix(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            session = self.manager.session(self.guild_id)
            snapshot = await session.snapshot()
            await session.set_dj_mix(not snapshot.dj_mix)
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(
        label="Smart Order: Off",
        emoji="🧠",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def smart_reorder(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            session = self.manager.session(self.guild_id)
            snapshot = await session.snapshot()
            await session.set_smart_reorder(not snapshot.smart_reorder)
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)

    @discord.ui.button(label="Save", emoji="💾", style=discord.ButtonStyle.primary, row=2)
    async def save(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            SaveQueueModal(self.ui, self.repository, self.guild_id, self.owner_id)
        )

    @discord.ui.button(label="Clear", emoji="🗑️", style=discord.ButtonStyle.danger, row=2)
    async def clear(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            await require_control_voice(interaction)
            await interaction.response.defer()
            await self.manager.session(self.guild_id).clear_queue()
            await self.ui.render(self.guild_id)
            embed, view = await self.payload()
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)


class SaveQueueModal(discord.ui.Modal, title="💿 Lưu thành playlist"):
    name = discord.ui.TextInput(
        label="Tên playlist",
        placeholder="Chill đêm",
        min_length=1,
        max_length=50,
    )

    def __init__(
        self,
        ui: PlayerUI,
        repository: MusicRepository,
        guild_id: int,
        owner_id: int,
    ) -> None:
        super().__init__()
        self.ui = ui
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Thao tác này thuộc người dùng khác.", ephemeral=True)
            return
        snapshot = await self.ui.manager.session(self.guild_id).snapshot()
        tracks = ([snapshot.current] if snapshot.current else []) + list(snapshot.queue)
        try:
            await self.repository.save_playlist(interaction.user.id, self.name.value, tracks)
            await interaction.response.send_message(
                f"💿 Đã lưu playlist **{self.name.value}** với {len(tracks)} bài.",
                ephemeral=True,
            )
        except MusicError as error:
            await interaction.response.send_message(error.message, ephemeral=True)


async def queue_payload(
    ui: PlayerUI,
    repository: MusicRepository,
    guild_id: int,
    owner_id: int,
) -> tuple[discord.Embed, QueueView]:
    view = QueueView(ui, repository, guild_id, owner_id)
    embed, _ = await view.payload()
    return embed, view
