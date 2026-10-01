import math
from typing import TYPE_CHECKING, Optional

import discord

from ..errors import MusicError
from ..models import Track, format_duration
from ..repository import MusicRepository, Playlist, PlaylistSummary

if TYPE_CHECKING:
    from .player import PlayerUI


PAGE_SIZE = 10


def _shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


async def _enqueue_tracks(
    ui: "PlayerUI",
    interaction: discord.Interaction,
    tracks: list[Track],
    *,
    position: str,
) -> None:
    if not interaction.guild or not interaction.channel:
        raise MusicError("Thao tác này chỉ dùng được trong máy chủ.")
    voice_state = getattr(interaction.user, "voice", None)
    if not voice_state or not voice_state.channel:
        raise MusicError("Bạn cần vào một kênh thoại trước.")
    await ui.manager.session(interaction.guild.id).enqueue_tracks(
        interaction.guild,
        voice_state.channel,
        interaction.channel,
        tracks,
        position=position,
    )
    await ui.render(interaction.guild.id)


class FavoriteSelect(discord.ui.Select):
    def __init__(self, parent: "FavoritesView") -> None:
        super().__init__(placeholder="Chọn một bài yêu thích", row=0)
        self.parent_view = parent
        self.refresh_options()

    def refresh_options(self) -> None:
        start = self.parent_view.page * PAGE_SIZE
        tracks = self.parent_view.tracks[start : start + PAGE_SIZE]
        self.options = [
            discord.SelectOption(
                label=_shorten(track.title, 100),
                description=_shorten(track.uploader or track.source.value, 100),
                value=str(start + index),
            )
            for index, track in enumerate(tracks)
        ] or [discord.SelectOption(label="Chưa có bài yêu thích", value="empty")]
        self.disabled = not tracks

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "empty":
            return
        track = self.parent_view.tracks[int(self.values[0])]
        await interaction.response.edit_message(
            embed=track_embed(track, "BÀI YÊU THÍCH"),
            view=FavoriteTrackView(
                self.parent_view.ui,
                self.parent_view.repository,
                track,
                self.parent_view.owner_id,
            ),
        )


class FavoritesView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        tracks: list[Track],
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.tracks = tracks
        self.owner_id = owner_id
        self.page = 0
        self.track_select = FavoriteSelect(self)
        self.add_item(self.track_select)
        self._update_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Thư viện này thuộc người dùng khác.", ephemeral=True)
        return False

    def embed(self) -> discord.Embed:
        page_count = max(1, math.ceil(len(self.tracks) / PAGE_SIZE))
        start = self.page * PAGE_SIZE
        embed = discord.Embed(title="💗 NHẠC YÊU THÍCH", color=0xF9A8D4)
        if not self.tracks:
            embed.description = "Chưa có bài yêu thích. Dùng nút trái tim trên trình phát hoặc kết quả tìm kiếm."
        else:
            lines = []
            for index, track in enumerate(self.tracks[start : start + PAGE_SIZE], start=start + 1):
                lines.append(
                    f"`{index:02d}.` [{track.title}]({track.url})\n"
                    f"　{track.uploader or 'Không rõ nghệ sĩ'} · {format_duration(track.duration)}"
                )
            embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(self.tracks)} bài · Trang {self.page + 1}/{page_count}")
        return embed

    def _update_controls(self) -> None:
        page_count = max(1, math.ceil(len(self.tracks) / PAGE_SIZE))
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= page_count - 1
        self.play_all.disabled = not self.tracks
        self.add_all.disabled = not self.tracks
        self.track_select.refresh_options()

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

    @discord.ui.button(label="Play All", emoji="▶️", style=discord.ButtonStyle.primary, row=1)
    async def play_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "now")

    @discord.ui.button(label="Queue All", emoji="➕", style=discord.ButtonStyle.success, row=1)
    async def add_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "end")

    async def _play(self, interaction: discord.Interaction, position: str) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
            await _enqueue_tracks(self.ui, interaction, self.tracks, position=position)
            await interaction.followup.send(f"Đã thêm **{len(self.tracks)} bài**.", ephemeral=True)
        except MusicError as error:
            if interaction.response.is_done():
                await interaction.followup.send(error.message, ephemeral=True)
            else:
                await interaction.response.send_message(error.message, ephemeral=True)


class FavoriteTrackView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        track: Track,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.track = track
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Thư viện này thuộc người dùng khác.", ephemeral=True)
        return False

    async def _play(self, interaction: discord.Interaction, position: str) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
            await _enqueue_tracks(self.ui, interaction, [self.track], position=position)
            await interaction.followup.send(f"Đã thêm **{self.track.title}**.", ephemeral=True)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)

    @discord.ui.button(label="Play Now", emoji="▶️", style=discord.ButtonStyle.primary)
    async def play_now(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "now")

    @discord.ui.button(label="Add to Queue", emoji="➕", style=discord.ButtonStyle.success)
    async def add_queue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "end")

    @discord.ui.button(label="Remove Favorite", emoji="💔", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.repository.remove_favorite(self.owner_id, self.track)
        embed, view = await favorites_payload(self.ui, self.repository, self.owner_id)
        await interaction.response.edit_message(embed=embed, view=view)


class PlaylistSelect(discord.ui.Select):
    def __init__(self, parent: "PlaylistsView") -> None:
        super().__init__(placeholder="Chọn playlist", row=0)
        self.parent_view = parent
        self.refresh_options()

    def refresh_options(self) -> None:
        start = self.parent_view.page * PAGE_SIZE
        playlists = self.parent_view.playlists[start : start + PAGE_SIZE]
        self.options = [
            discord.SelectOption(
                label=_shorten(playlist.name, 100),
                description=f"{playlist.track_count} bài",
                value=str(playlist.playlist_id),
            )
            for playlist in playlists
        ] or [discord.SelectOption(label="Chưa có playlist", value="empty")]
        self.disabled = not playlists

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "empty":
            return
        playlist = await self.parent_view.repository.get_playlist(
            self.parent_view.owner_id,
            int(self.values[0]),
        )
        if not playlist:
            await interaction.response.send_message("Playlist không còn tồn tại.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=playlist_embed(playlist),
            view=PlaylistDetailView(
                self.parent_view.ui,
                self.parent_view.repository,
                playlist,
                self.parent_view.owner_id,
            ),
        )


class PlaylistsView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        playlists: list[PlaylistSummary],
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.playlists = playlists
        self.owner_id = owner_id
        self.page = 0
        self.playlist_select = PlaylistSelect(self)
        self.add_item(self.playlist_select)
        self._update_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Thư viện này thuộc người dùng khác.", ephemeral=True)
        return False

    def embed(self) -> discord.Embed:
        page_count = max(1, math.ceil(len(self.playlists) / PAGE_SIZE))
        embed = discord.Embed(title="💿 PLAYLIST CỦA BẠN", color=0x6EE7B7)
        if not self.playlists:
            embed.description = "Chưa có playlist. Mở Hàng đợi rồi chọn Lưu để tạo playlist đầu tiên."
        else:
            start = self.page * PAGE_SIZE
            embed.description = "\n".join(
                f"`{index:02d}.` **{item.name}** · {item.track_count} bài"
                for index, item in enumerate(
                    self.playlists[start : start + PAGE_SIZE],
                    start=start + 1,
                )
            )
        embed.set_footer(text=f"{len(self.playlists)} playlist · Trang {self.page + 1}/{page_count}")
        return embed

    def _update_controls(self) -> None:
        page_count = max(1, math.ceil(len(self.playlists) / PAGE_SIZE))
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= page_count - 1
        self.playlist_select.refresh_options()

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


class PlaylistDetailView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        playlist: Playlist,
        owner_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.playlist = playlist
        self.owner_id = owner_id
        self.play.disabled = not playlist.tracks
        self.add_queue.disabled = not playlist.tracks

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Playlist này thuộc người dùng khác.", ephemeral=True)
        return False

    async def _play(self, interaction: discord.Interaction, position: str) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
            await _enqueue_tracks(self.ui, interaction, list(self.playlist.tracks), position=position)
            await interaction.followup.send(
                f"Đã thêm **{len(self.playlist.tracks)} bài** từ **{self.playlist.name}**.",
                ephemeral=True,
            )
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)

    @discord.ui.button(label="Play", emoji="▶️", style=discord.ButtonStyle.primary)
    async def play(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "now")

    @discord.ui.button(label="Add to Queue", emoji="➕", style=discord.ButtonStyle.success)
    async def add_queue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._play(interaction, "end")

    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.repository.delete_playlist(self.owner_id, self.playlist.playlist_id)
        embed, view = await playlists_payload(self.ui, self.repository, self.owner_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Back",
        emoji="↩️",
        style=discord.ButtonStyle.secondary,
        custom_id="library:back",
    )
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed, view = await playlists_payload(self.ui, self.repository, self.owner_id)
        await interaction.response.edit_message(embed=embed, view=view)


class AddTrackToPlaylistModal(discord.ui.Modal, title="💿 Thêm vào playlist"):
    name = discord.ui.TextInput(
        label="Tên playlist",
        placeholder="Chill đêm",
        min_length=1,
        max_length=50,
    )

    def __init__(self, repository: MusicRepository, track: Track, owner_id: int) -> None:
        super().__init__()
        self.repository = repository
        self.track = track
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Thao tác này thuộc người dùng khác.", ephemeral=True)
            return
        try:
            await self.repository.add_track_to_playlist(self.owner_id, self.name.value, self.track)
            await interaction.response.send_message(
                f"Đã thêm **{self.track.title}** vào **{self.name.value}**.",
                ephemeral=True,
            )
        except MusicError as error:
            await interaction.response.send_message(error.message, ephemeral=True)


def track_embed(track: Track, heading: str) -> discord.Embed:
    embed = discord.Embed(
        title=heading,
        description=f"**[{track.title}]({track.url})**\n{track.uploader or 'Không rõ nghệ sĩ'}",
        color=0xF9A8D4,
    )
    embed.add_field(name="Thời lượng", value=format_duration(track.duration))
    embed.add_field(name="Nguồn", value=track.source.value)
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    return embed


def playlist_embed(playlist: Playlist) -> discord.Embed:
    embed = discord.Embed(title=f"💿 {playlist.name}", color=0x6EE7B7)
    if not playlist.tracks:
        embed.description = "Playlist đang trống."
    else:
        visible = playlist.tracks[:15]
        embed.description = "\n".join(
            f"`{index:02d}.` [{track.title}]({track.url}) · {format_duration(track.duration)}"
            for index, track in enumerate(visible, start=1)
        )
        if len(playlist.tracks) > len(visible):
            embed.description += f"\n… và {len(playlist.tracks) - len(visible)} bài khác"
    embed.set_footer(text=f"{len(playlist.tracks)} bài")
    return embed


async def favorites_payload(
    ui: "PlayerUI",
    repository: MusicRepository,
    owner_id: int,
) -> tuple[discord.Embed, FavoritesView]:
    view = FavoritesView(ui, repository, await repository.list_favorites(owner_id), owner_id)
    return view.embed(), view


async def playlists_payload(
    ui: "PlayerUI",
    repository: MusicRepository,
    owner_id: int,
) -> tuple[discord.Embed, PlaylistsView]:
    view = PlaylistsView(ui, repository, await repository.list_playlists(owner_id), owner_id)
    return view.embed(), view
