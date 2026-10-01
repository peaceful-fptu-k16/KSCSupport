import discord

from ..lyrics import LyricsResult, LyricsService
from ..models import Track


def split_lyrics(text: str, *, limit: int = 3400) -> list[str]:
    pages: list[str] = []
    current: list[str] = []
    current_length = 0
    source_lines = text.splitlines() or [text]
    lines = [chunk for line in source_lines for chunk in (line[index : index + limit] for index in range(0, max(1, len(line)), limit))]
    for line in lines:
        added = len(line) + 1
        if current and current_length + added > limit:
            pages.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += added
    if current:
        pages.append("\n".join(current))
    return pages or ["Không có nội dung lời."]


class LyricsView(discord.ui.View):
    def __init__(self, result: LyricsResult, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.result = result
        self.owner_id = owner_id
        self.pages = split_lyrics(result.lyrics)
        self.page = 0
        self._update_buttons()

    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎤 {self.result.track_name}",
            description=self.pages[self.page],
            color=0xC4B5FD,
        )
        embed.set_author(name=self.result.artist_name or "Không rõ nghệ sĩ")
        embed.set_footer(text=f"Trang {self.page + 1}/{len(self.pages)} · Nguồn: LRCLIB")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng lời này thuộc người dùng khác.", ephemeral=True)
        return False

    def _update_buttons(self) -> None:
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.pages) - 1

    @discord.ui.button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = min(len(self.pages) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)


async def lyrics_view_for(
    service: LyricsService,
    track: Track,
    owner_id: int,
) -> LyricsView:
    return LyricsView(await service.get_lyrics(track), owner_id)
