import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord

from ..discovery import (
    AI_PRESETS,
    RADIO_PRESETS,
    DiscoveryPreset,
    custom_ai_preset,
    discovery_queries,
    rank_discovery_tracks,
)
from ..errors import MusicError, VoiceStateError
from ..models import Track, format_compact_number, format_listening_time
from ..repository import MusicProfile, MusicRepository

if TYPE_CHECKING:
    from .player import PlayerUI


def _personality(hour: Optional[int]) -> tuple[str, str]:
    if hour is None:
        return "NEW LISTENER", "Hãy nghe thêm vài bài để mở khóa gu âm nhạc."
    if hour >= 22 or hour < 4:
        return "NIGHT OWL", "Bạn thường bật nhạc khi thành phố đã yên."
    if hour < 10:
        return "MORNING STARTER", "Âm nhạc là cách bạn khởi động ngày mới."
    if hour < 17:
        return "DAYDREAMER", "Playlist của bạn hoạt động mạnh nhất ban ngày."
    return "SUNSET LISTENER", "Bạn thích nghe nhạc vào khoảng chuyển giao cuối ngày."


async def _discover_tracks(
    ui: "PlayerUI",
    repository: MusicRepository,
    guild_id: int,
    user: discord.abc.User,
    preset: DiscoveryPreset,
    *,
    limit: int = 8,
) -> list[Track]:
    groups = await asyncio.gather(
        *(
            ui.manager.extractor.search_tracks(
                query,
                requester_id=user.id,
                requester_name=user.display_name,
                limit=10,
            )
            for query in discovery_queries(preset)
        ),
        return_exceptions=True,
    )
    tracks: list[Track] = []
    for group in groups:
        if isinstance(group, Exception):
            continue
        tracks.extend(group)
    tracks = await repository.enrich_discovery_metrics(tracks)
    ranked = rank_discovery_tracks(tracks, preset, limit=limit, artist_gap=4)
    if not ranked:
        source_label = "nhạc Urban Việt phù hợp" if preset.source_policy == "urban" else "Official MV phù hợp"
        raise MusicError(
            f"Không tìm thấy đủ {source_label}. Hãy thử preset khác.",
            code="discovery_empty",
        )
    return ranked


async def _enqueue_for_interaction(
    ui: "PlayerUI",
    interaction: discord.Interaction,
    tracks: list[Track],
) -> None:
    if not interaction.guild or not interaction.channel:
        raise VoiceStateError("Tính năng này chỉ dùng được trong server.")
    voice = getattr(interaction.user, "voice", None)
    if not voice or not voice.channel:
        raise VoiceStateError("Bạn cần vào một kênh thoại trước.")
    await ui.manager.session(interaction.guild.id).enqueue_tracks(
        interaction.guild,
        voice.channel,
        interaction.channel,
        tracks,
        position="end",
    )


class PresetSelect(discord.ui.Select):
    def __init__(self, parent: "DiscoveryView") -> None:
        presets = RADIO_PRESETS if parent.mode == "radio" else AI_PRESETS
        options = [
            discord.SelectOption(
                label=preset.label,
                value=key,
                emoji=preset.emoji,
                description=(
                    "Radio V-Pop"
                    if parent.mode == "radio"
                    else (
                        "Artist / Producer · Trend / Popular"
                        if preset.source_policy == "urban"
                        else "Official MV · Trend / Popular"
                    )
                ),
            )
            for key, preset in presets.items()
        ]
        super().__init__(placeholder="Chọn Radio" if parent.mode == "radio" else "Chọn genre / vibe", options=options)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.preset_key = self.values[0]
        self.parent_view.custom_preset = None
        self.parent_view.preview_tracks = []
        self.parent_view.refresh()
        await interaction.response.edit_message(
            embed=self.parent_view.embed(),
            view=self.parent_view,
        )


class AIDJRefineModal(discord.ui.Modal, title="Tinh chỉnh AI DJ"):
    genre = discord.ui.TextInput(label="Genre", placeholder="Drill + Hoodtrap", max_length=80)
    vibe = discord.ui.TextInput(label="Vibe", placeholder="Tối, mạnh, chạy đêm", max_length=80, required=False)
    trend = discord.ui.TextInput(label="Độ trend", placeholder="Cao / Vừa", default="Cao", max_length=20)
    freshness = discord.ui.TextInput(label="Độ mới", placeholder="Mới / Hỗn hợp / Kinh điển", default="Hỗn hợp", max_length=30)

    def __init__(self, view: "DiscoveryView") -> None:
        super().__init__()
        self.discovery_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.discovery_view.custom_preset = custom_ai_preset(
            self.genre.value,
            self.vibe.value,
            self.trend.value,
            self.freshness.value,
        )
        self.discovery_view.preview_tracks = []
        self.discovery_view.refresh()
        await interaction.response.edit_message(
            embed=self.discovery_view.embed(),
            view=self.discovery_view,
        )


class DiscoveryView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        repository: MusicRepository,
        guild_id: int,
        owner_id: int,
        *,
        mode: str = "ai",
        preset_key: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.mode = mode
        self.preset_key = preset_key or ("trending" if mode == "radio" else "chill")
        self.custom_preset: Optional[DiscoveryPreset] = None
        self.preview_tracks: list[Track] = []
        self.preset_select = PresetSelect(self)
        self.add_item(self.preset_select)
        self.refresh()

    @property
    def preset(self) -> DiscoveryPreset:
        if self.custom_preset:
            return self.custom_preset
        presets = RADIO_PRESETS if self.mode == "radio" else AI_PRESETS
        return presets[self.preset_key]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng này thuộc người dùng khác.", ephemeral=True)
        return False

    def refresh(self) -> None:
        self.start.label = "Start Radio" if self.mode == "radio" else "Generate Mix"
        self.start.emoji = "📻" if self.mode == "radio" else "✨"
        self.preset_select.placeholder = f"{self.preset.emoji} {self.preset.label}"
        self.refine.disabled = self.mode == "radio"

    def embed(self) -> discord.Embed:
        preset = self.preset
        title = "📻 RADIO" if self.mode == "radio" else "🤖✨ AI DJ"
        description = (
            "Xu hướng V-Pop chung · Official MV · tự chống lặp nghệ sĩ."
            if self.mode == "radio"
            else "Trong kho nhạc Việt đang hot, chọn đúng genre và vibe của bạn. Urban không bị ép Official MV."
        )
        embed = discord.Embed(title=title, description=description, color=preset.color)
        embed.add_field(name="Preset", value=f"{preset.emoji} **{preset.label}**", inline=True)
        embed.add_field(
            name="Nguồn",
            value=(
                "🇻🇳 Việt Nam · 🎤 Artist / Producer / Label"
                if preset.source_policy == "urban"
                else "🇻🇳 Việt Nam · 🎬 Official MV"
            ),
            inline=True,
        )
        filter_text = (
            "Không cover · reupload · fanmade · sped-up/slowed · bản kéo dài"
            if preset.source_policy == "urban"
            else "Không lyrics · cover · reupload · unofficial remix"
        )
        embed.add_field(name="Bộ lọc", value=filter_text, inline=False)
        if self.preview_tracks:
            lines = []
            for index, track in enumerate(self.preview_tracks[:10], 1):
                growth = f" · +{format_compact_number(track.view_growth_7d)}/7d" if track.view_growth_7d else ""
                lines.append(
                    f"`{index:02d}` **{track.title[:55]}**\n"
                    f"　{track.uploader or 'Nghệ sĩ'} · 👀 {format_compact_number(track.view_count)}{growth}"
                )
            embed.add_field(name=f"Xem trước · {len(self.preview_tracks)} bài", value="\n".join(lines), inline=False)
        return embed

    async def _generate(self, interaction: discord.Interaction) -> list[Track]:
        return await _discover_tracks(
            self.ui,
            self.repository,
            self.guild_id,
            interaction.user,
            self.preset,
            limit=12 if self.mode == "radio" else 18,
        )

    @discord.ui.button(label="Generate Mix", emoji="✨", style=discord.ButtonStyle.primary, row=1)
    async def start(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            tracks = self.preview_tracks or await self._generate(interaction)
            await _enqueue_for_interaction(self.ui, interaction, tracks)
            if self.mode == "radio":
                session = self.ui.manager.session(self.guild_id)
                await session.set_radio_policy(self.preset)
                await session.set_autoplay(True)
            await self.ui.render(self.guild_id)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)
            return
        suffix = "Radio đã bật" if self.mode == "radio" else "AI DJ đã tạo phiên nghe"
        await interaction.followup.send(
            f"{suffix} **{self.preset.label}** với **{len(tracks)} bài**.",
            ephemeral=True,
        )

    @discord.ui.button(label="Preview", emoji="👀", style=discord.ButtonStyle.secondary, row=1)
    async def preview(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            self.preview_tracks = await self._generate(interaction)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)
            return
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="Refine", emoji="✨", style=discord.ButtonStyle.secondary, row=1)
    async def refine(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(AIDJRefineModal(self))

    @discord.ui.button(label="Profile", emoji="👤", style=discord.ButtonStyle.secondary, row=1)
    async def profile(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        profile = await self.repository.get_music_profile(self.guild_id, self.owner_id)
        await interaction.response.edit_message(
            embed=profile_embed(interaction.user, profile),
            view=ProfileView(self.repository, self.guild_id, self.owner_id),
        )


class ProfileView(discord.ui.View):
    def __init__(self, repository: MusicRepository, guild_id: int, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Hồ sơ này thuộc người dùng khác.", ephemeral=True)
        return False

    @discord.ui.button(label="Wrapped", emoji="✨", style=discord.ButtonStyle.primary)
    async def wrapped(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        year = datetime.now().year
        profile = await self.repository.get_music_profile(self.guild_id, self.owner_id, year=year)
        view = WrappedView(interaction.user, profile)
        await interaction.response.edit_message(embed=view.embed(), view=view)


def profile_embed(user: discord.abc.User, profile: MusicProfile) -> discord.Embed:
    personality, caption = _personality(profile.peak_hour)
    stats = profile.stats
    embed = discord.Embed(
        title=f"👤 {user.display_name}",
        description=f"### {personality}\n{caption}",
        color=0x7DD3FC,
    )
    if getattr(user, "display_avatar", None):
        embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="Listening", value=format_listening_time(stats.listened_seconds), inline=True)
    embed.add_field(name="Tracks", value=f"{stats.play_count} plays", inline=True)
    embed.add_field(name="Favorites", value=str(stats.favorite_count), inline=True)
    embed.add_field(name="Top Artist", value=stats.top_artist or "Chưa có", inline=True)
    embed.add_field(name="Top Track", value=stats.top_track or "Chưa có", inline=True)
    peak = f"{profile.peak_hour:02d}:00" if profile.peak_hour is not None else "Chưa có"
    embed.add_field(name="Peak Time", value=peak, inline=True)
    return embed


class WrappedView(discord.ui.View):
    def __init__(self, user: discord.abc.User, profile: MusicProfile) -> None:
        super().__init__(timeout=300)
        self.user = user
        self.profile = profile
        self.page = 0
        self.pages = 4
        self._sync()

    def _sync(self) -> None:
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page == self.pages - 1

    def embed(self) -> discord.Embed:
        stats = self.profile.stats
        year = self.profile.year or datetime.now().year
        personality, caption = _personality(self.profile.peak_hour)
        if self.page == 0:
            title = f"✨ MUSIC WRAPPED {year}"
            description = f"## {format_listening_time(stats.listened_seconds)}\n@{self.user.display_name}"
        elif self.page == 1:
            title = "👑 ARTIST OF THE YEAR"
            description = f"## {stats.top_artist or 'Chưa có dữ liệu'}"
        elif self.page == 2:
            title = "🔥 TRACK OF THE YEAR"
            top_plays = self.profile.top_tracks[0][1] if self.profile.top_tracks else 0
            description = f"## {stats.top_track or 'Chưa có dữ liệu'}\n{top_plays} lượt phát trong năm"
        else:
            title = "🌙 LISTENING PERSONALITY"
            description = f"## {personality}\n{caption}"
        embed = discord.Embed(title=title, description=description, color=0xF9A8D4)
        embed.set_footer(text=f"{self.page + 1} / {self.pages}")
        return embed

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = min(self.pages - 1, self.page + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)


@dataclass
class PartySession:
    guild_id: int
    host_id: int
    host_name: str
    participants: set[int] = field(default_factory=set)
    votes: set[int] = field(default_factory=set)
    track_url: Optional[str] = None

    def sync_track(self, track: Optional[Track]) -> None:
        url = track.url if track else None
        if url != self.track_url:
            self.track_url = url
            self.votes.clear()


class PartyManager:
    def __init__(self) -> None:
        self.sessions: dict[int, PartySession] = {}

    def start(self, guild_id: int, host: discord.abc.User) -> PartySession:
        session = PartySession(guild_id, host.id, host.display_name, {host.id})
        self.sessions[guild_id] = session
        return session

    def is_active(self, session: PartySession) -> bool:
        return self.sessions.get(session.guild_id) is session

    def end(self, session: PartySession) -> None:
        if self.is_active(session):
            self.sessions.pop(session.guild_id, None)


class SuggestModal(discord.ui.Modal, title="Suggest a track"):
    query = discord.ui.TextInput(
        label="Song, artist or URL",
        placeholder="G-DRAGON Crooked",
        max_length=200,
    )

    def __init__(self, view: "PartyView") -> None:
        super().__init__()
        self.party_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            tracks = await self.party_view.ui.manager.extractor.search_tracks(
                self.query.value,
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                limit=1,
            )
            await _enqueue_for_interaction(self.party_view.ui, interaction, tracks[:1])
            await self.party_view.ui.render(self.party_view.session.guild_id)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)
            return
        self.party_view.session.participants.add(interaction.user.id)
        await interaction.followup.send(f"Đã đề xuất **{tracks[0].title}**.", ephemeral=True)


class PartyView(discord.ui.View):
    def __init__(self, ui: "PlayerUI", manager: PartyManager, session: PartySession) -> None:
        super().__init__(timeout=3600)
        self.ui = ui
        self.manager = manager
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.manager.is_active(self.session):
            return True
        await interaction.response.send_message("Listening Party này đã kết thúc.", ephemeral=True)
        return False

    async def embed(self, guild: discord.Guild) -> discord.Embed:
        snapshot = await self.ui.manager.session(guild.id).snapshot()
        self.session.sync_track(snapshot.current)
        current = snapshot.current
        listeners = self._listeners(guild)
        threshold = max(1, math.ceil(max(1, len(listeners)) / 2))
        embed = discord.Embed(
            title="🎉 LISTENING PARTY",
            description=(
                f"**{current.title}**\n{current.uploader or current.source.value}"
                if current
                else "Chưa có bài nào đang phát."
            ),
            color=0xF9A8D4,
        )
        embed.add_field(name="Host", value=self.session.host_name, inline=True)
        embed.add_field(name="Listeners", value=str(len(listeners)), inline=True)
        embed.add_field(name="Vote Skip", value=f"{len(self.session.votes)} / {threshold}", inline=True)
        if current and current.thumbnail:
            embed.set_thumbnail(url=current.thumbnail)
        return embed

    @staticmethod
    def _listeners(guild: discord.Guild) -> list[discord.Member]:
        voice = guild.voice_client
        if not voice or not voice.channel:
            return []
        return [member for member in voice.channel.members if not member.bot]

    async def _same_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("Bot chưa ở trong voice channel.", ephemeral=True)
            return False
        voice = getattr(interaction.user, "voice", None)
        if not voice or voice.channel != interaction.guild.voice_client.channel:
            await interaction.response.send_message("Bạn cần ở cùng voice channel với bot.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Join", emoji="➕", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._same_voice(interaction):
            return
        self.session.participants.add(interaction.user.id)
        await interaction.response.edit_message(embed=await self.embed(interaction.guild), view=self)

    @discord.ui.button(label="Suggest", emoji="🎵", style=discord.ButtonStyle.primary)
    async def suggest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._same_voice(interaction):
            return
        await interaction.response.send_modal(SuggestModal(self))

    @discord.ui.button(label="Vote Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def vote_skip(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not await self._same_voice(interaction):
            return
        guild = interaction.guild
        snapshot = await self.ui.manager.session(guild.id).snapshot()
        self.session.sync_track(snapshot.current)
        self.session.votes.add(interaction.user.id)
        listeners = self._listeners(guild)
        threshold = max(1, math.ceil(max(1, len(listeners)) / 2))
        if len(self.session.votes) >= threshold:
            try:
                await self.ui.manager.session(guild.id).skip(guild.voice_client)
            except MusicError as error:
                await interaction.response.send_message(error.message, ephemeral=True)
                return
            self.session.votes.clear()
            await interaction.response.send_message("Đủ phiếu, đang chuyển bài.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=await self.embed(guild), view=self)

    @discord.ui.button(label="End", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.user.id != self.session.host_id:
            await interaction.response.send_message("Chỉ host mới có thể kết thúc party.", ephemeral=True)
            return
        self.manager.end(self.session)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Listening Party đã kết thúc.", embed=None, view=self)


async def discovery_payload(
    ui: "PlayerUI",
    repository: MusicRepository,
    guild_id: int,
    owner_id: int,
    *,
    mode: str,
) -> tuple[discord.Embed, DiscoveryView]:
    view = DiscoveryView(ui, repository, guild_id, owner_id, mode=mode)
    return view.embed(), view


async def profile_payload(
    repository: MusicRepository,
    guild_id: int,
    user: discord.abc.User,
) -> tuple[discord.Embed, ProfileView]:
    profile = await repository.get_music_profile(guild_id, user.id)
    return profile_embed(user, profile), ProfileView(repository, guild_id, user.id)


async def wrapped_payload(
    repository: MusicRepository,
    guild_id: int,
    user: discord.abc.User,
) -> tuple[discord.Embed, WrappedView]:
    profile = await repository.get_music_profile(
        guild_id,
        user.id,
        year=datetime.now().year,
    )
    view = WrappedView(user, profile)
    return view.embed(), view
