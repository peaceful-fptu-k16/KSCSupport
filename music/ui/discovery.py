import asyncio
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord

from ..errors import MusicError, VoiceStateError
from ..models import Track, TrackSource, format_duration
from ..repository import MusicProfile, MusicRepository

if TYPE_CHECKING:
    from .player import PlayerUI


MOODS = {
    "chill": ("Chill Night", "chill night mix", "🌙", 0xC4B5FD),
    "party": ("Party", "party hits mix", "🎉", 0xF9A8D4),
    "gaming": ("Gaming", "gaming music mix", "🎮", 0x6EE7B7),
    "love": ("Love", "love songs mix", "💕", 0xF9A8D4),
    "rainy": ("Rainy", "rainy day lofi mix", "🌧️", 0x7DD3FC),
    "energy": ("Energy", "high energy music mix", "⚡", 0xFDE68A),
    "sad": ("Sad", "sad songs mix", "💔", 0xA78BFA),
    "morning": ("Morning", "morning acoustic mix", "☀️", 0xFDBA8C),
}

VPOP_QUERIES = {
    "chill": "VPop Việt Nam chill Official MV",
    "party": "VPop Việt Nam sôi động Official MV",
    "gaming": "VPop Việt Nam năng lượng Official MV",
    "love": "VPop Việt Nam tình yêu Official MV",
    "rainy": "VPop Việt Nam ngày mưa Official MV",
    "energy": "VPop Việt Nam tích cực Official MV",
    "sad": "VPop Việt Nam buồn tâm trạng Official MV",
    "morning": "VPop Việt Nam nhẹ nhàng Official MV",
}

MIN_SONG_SECONDS = 60
MAX_SONG_SECONDS = 12 * 60


def _is_song_length(track: Track) -> bool:
    return (
        track.duration is not None
        and MIN_SONG_SECONDS <= track.duration <= MAX_SONG_SECONDS
    )


def _listening_time(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes = remainder // 60
    return f"{hours} giờ {minutes} phút" if hours else f"{minutes} phút"


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
    mood: str,
    *,
    limit: int = 8,
    vietnamese_only: bool = False,
) -> list[Track]:
    label, query, _emoji, _color = MOODS[mood]
    if vietnamese_only:
        queries = [VPOP_QUERIES[mood], f"nhạc Việt {label} Official Music Video"]
    else:
        profile = await repository.get_music_profile(guild_id, user.id)
        queries = [query]
        if profile.stats.top_artist:
            queries.insert(0, f"{profile.stats.top_artist} {label} mix")

    groups = await asyncio.gather(
        *(
            ui.manager.extractor.search_tracks(
                item,
                requester_id=user.id,
                requester_name=user.display_name,
                limit=5,
            )
            for item in queries
        ),
        return_exceptions=True,
    )
    tracks: list[Track] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, Exception):
            continue
        for track in group:
            if vietnamese_only and not _is_song_length(track):
                continue
            if track.url not in seen:
                seen.add(track.url)
                tracks.append(track)
    if not tracks:
        raise MusicError("Không tìm được bài phù hợp với mood này.", code="discovery_empty")
    random.shuffle(tracks)
    return tracks[:limit]


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


class MoodSelect(discord.ui.Select):
    def __init__(self, parent: "DiscoveryView") -> None:
        options = [
            discord.SelectOption(label=label, value=value, emoji=emoji)
            for value, (label, _query, emoji, _color) in MOODS.items()
        ]
        super().__init__(placeholder="Choose a mood", options=options)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.mood = self.values[0]
        self.parent_view.refresh()
        await interaction.response.edit_message(
            embed=self.parent_view.embed(),
            view=self.parent_view,
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
        mood: str = "chill",
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.repository = repository
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.mode = mode
        self.mood = mood
        self.mood_select = MoodSelect(self)
        self.add_item(self.mood_select)
        self.refresh()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng này thuộc người dùng khác.", ephemeral=True)
        return False

    def refresh(self) -> None:
        label, _query, emoji, _color = MOODS[self.mood]
        self.start.label = "Start Radio" if self.mode == "radio" else "Generate Mix"
        self.start.emoji = "📻" if self.mode == "radio" else "✨"
        self.mood_select.placeholder = f"{emoji} {label}"

    def embed(self) -> discord.Embed:
        label, _query, emoji, color = MOODS[self.mood]
        title = "📻 RADIO" if self.mode == "radio" else "🤖✨ AI DJ"
        description = (
            "Radio sẽ tiếp tục chọn bài cùng mood khi hàng đợi trống."
            if self.mode == "radio"
            else "V-Pop Official MV theo mood, chỉ chọn video có thời lượng một bài hát."
        )
        embed = discord.Embed(title=title, description=description, color=color)
        embed.add_field(name="Mood", value=f"{emoji} **{label}**", inline=True)
        embed.add_field(
            name="Mode",
            value="Continuous" if self.mode == "radio" else "Personalized mix",
            inline=True,
        )
        return embed

    @discord.ui.button(label="Generate Mix", emoji="✨", style=discord.ButtonStyle.primary, row=1)
    async def start(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            tracks = await _discover_tracks(
                self.ui,
                self.repository,
                self.guild_id,
                interaction.user,
                self.mood,
                vietnamese_only=self.mode == "ai",
            )
            await _enqueue_for_interaction(self.ui, interaction, tracks)
            if self.mode == "radio":
                await self.ui.manager.session(self.guild_id).set_autoplay(True)
            await self.ui.render(self.guild_id)
        except MusicError as error:
            await interaction.followup.send(error.message, ephemeral=True)
            return
        label = MOODS[self.mood][0]
        suffix = "Radio đã bật" if self.mode == "radio" else "AI DJ đã tạo phiên nghe"
        await interaction.followup.send(
            f"{suffix} **{label}** với **{len(tracks)} bài**.",
            ephemeral=True,
        )

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
    embed.add_field(name="Listening", value=_listening_time(stats.listened_seconds), inline=True)
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
            description = f"## {_listening_time(stats.listened_seconds)}\n@{self.user.display_name}"
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
