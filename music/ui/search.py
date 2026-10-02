import logging
from typing import Optional

import discord

from ..errors import MusicError
from ..models import Track, TrackSource, format_duration, shorten_text


logger = logging.getLogger(__name__)


class SearchModal(discord.ui.Modal):
    query = discord.ui.TextInput(
        label="Tên bài hát, nghệ sĩ hoặc URL",
        placeholder="G-DRAGON Crooked",
        min_length=1,
        max_length=200,
    )

    def __init__(
        self,
        ui,
        *,
        owner_id: int,
        source_hint: Optional[TrackSource] = None,
    ) -> None:
        title = "🔎 Tìm nhạc SoundCloud" if source_hint is TrackSource.SOUNDCLOUD else "🔎 Tìm bài hát"
        super().__init__(title=title, timeout=180)
        self.ui = ui
        self.owner_id = owner_id
        self.source_hint = source_hint

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            tracks = await self.ui.manager.extractor.search_tracks(
                self.query.value,
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                source_hint=self.source_hint,
                limit=5,
            )
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)
            return
        except Exception:
            logger.exception(
                "search_unexpected guild_id=%s user_id=%s",
                interaction.guild_id,
                interaction.user.id,
            )
            await interaction.followup.send(
                "Không thể tìm nhạc lúc này. Hãy thử lại sau nhé.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🔎 KẾT QUẢ TÌM KIẾM",
            description=f'Kết quả cho **"{shorten_text(self.query.value, 80)}"**',
            color=0xC4B5FD,
        )
        for index, track in enumerate(tracks, start=1):
            embed.add_field(
                name=f"{index:02d}. {track.title}",
                value=f"{track.uploader or 'Không rõ nghệ sĩ'} · {format_duration(track.duration)}",
                inline=False,
            )
        await interaction.followup.send(
            embed=embed,
            view=SearchResultsView(self.ui, tracks, self.owner_id),
            ephemeral=True,
        )


class SearchResultSelect(discord.ui.Select):
    def __init__(self, ui, tracks: list[Track], owner_id: int) -> None:
        options = [
            discord.SelectOption(
                label=shorten_text(track.title, 100),
                value=str(index),
                description=shorten_text(
                    f"{track.uploader or track.source.value} · {format_duration(track.duration)}",
                    100,
                ),
                emoji="🩵" if track.source is TrackSource.SOUNDCLOUD else "🌸",
            )
            for index, track in enumerate(tracks)
        ]
        super().__init__(placeholder="🎵 Chọn bài hát", min_values=1, max_values=1, options=options)
        self.ui = ui
        self.tracks = tracks
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Kết quả tìm kiếm này thuộc người dùng khác.", ephemeral=True)
            return
        track = self.tracks[int(self.values[0])]
        embed = discord.Embed(
            title=track.title,
            description=(
                f"**{track.uploader or 'Không rõ nghệ sĩ'}**\n"
                f"⏱️ {format_duration(track.duration)} · {track.source.value}"
            ),
            color=0x7DD3FC,
            url=track.url,
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await interaction.response.edit_message(
            embed=embed,
            view=TrackActionsView(self.ui, track, self.owner_id),
        )


class SearchResultsView(discord.ui.View):
    def __init__(self, ui, tracks: list[Track], owner_id: int) -> None:
        super().__init__(timeout=180)
        self.add_item(SearchResultSelect(ui, tracks, owner_id))


class TrackActionsView(discord.ui.View):
    def __init__(self, ui, track: Track, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.ui = ui
        self.track = track
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Thao tác này thuộc người dùng khác.", ephemeral=True)
        return False

    async def _enqueue(self, interaction: discord.Interaction, position: str) -> None:
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("Thao tác này chỉ dùng được trong server.", ephemeral=True)
            return
        voice_state = getattr(interaction.user, "voice", None)
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message("Bạn cần vào một kênh thoại trước.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            session = self.ui.manager.session(interaction.guild.id)
            await session.enqueue_tracks(
                interaction.guild,
                voice_state.channel,
                interaction.channel,
                [self.track],
                position=position,
            )
            await self.ui.render(interaction.guild.id)
        except MusicError as error:
            await interaction.edit_original_response(content=error.message, embed=None, view=None)
            return
        except Exception:
            logger.exception(
                "search_enqueue_unexpected guild_id=%s user_id=%s",
                interaction.guild_id,
                interaction.user.id,
            )
            await interaction.edit_original_response(
                content="Không thể thêm bài hát lúc này.",
                embed=None,
                view=None,
            )
            return

        labels = {
            "now": "▶️ Đang phát ngay",
            "next": "⏭️ Đã đặt làm bài tiếp theo",
            "end": "➕ Đã thêm vào hàng đợi",
        }
        await interaction.edit_original_response(
            content=f"{labels[position]}: **{self.track.title}**",
            embed=None,
            view=None,
        )

    @discord.ui.button(label="Play Now", emoji="▶️", style=discord.ButtonStyle.primary)
    async def play_now(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._enqueue(interaction, "now")

    @discord.ui.button(label="Add to Queue", emoji="➕", style=discord.ButtonStyle.success)
    async def add_queue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._enqueue(interaction, "end")

    @discord.ui.button(label="Play Next", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def play_next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._enqueue(interaction, "next")

    @discord.ui.button(label="Favorite", emoji="💗", style=discord.ButtonStyle.secondary)
    async def favorite(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        added = await self.ui.repository.toggle_favorite(interaction.user.id, self.track)
        message = "Đã thêm vào nhạc yêu thích." if added else "Đã bỏ khỏi nhạc yêu thích."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Playlist", emoji="💿", style=discord.ButtonStyle.secondary)
    async def playlist(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from .library import AddTrackToPlaylistModal

        await interaction.response.send_modal(
            AddTrackToPlaylistModal(self.ui.repository, self.track, self.owner_id)
        )
