import io
import re
from datetime import date
from typing import Callable, Optional

import discord

from branding import BRAND_NAME
from .achievements import ACHIEVEMENTS, BY_KEY, CATEGORIES
from .repository import (
    AnalyticsSnapshot,
    BirthdayEntry,
    CommunityProfile,
    CommunityRepository,
    WeeklySnapshot,
)
from .cards import CommunityCardRenderer


def find_text_channel(guild: discord.Guild, keyword: str) -> Optional[discord.TextChannel]:
    wanted = re.sub(r"[^a-z0-9]", "", keyword.casefold())
    for channel in guild.text_channels:
        normalized = re.sub(r"[^a-z0-9]", "", channel.name.casefold())
        if wanted in normalized:
            return channel
    return None


def community_profile_embed(member: discord.abc.User, profile: CommunityProfile) -> discord.Embed:
    today = date.today()
    days = 0
    if profile.joined_at:
        joined = date.fromtimestamp(profile.joined_at)
        days = max(0, (today - joined).days)
    hours, minutes = divmod(profile.voice_seconds // 60, 60)
    birthday = "Chưa thiết lập"
    if profile.birthday_day and profile.birthday_month:
        birthday = (
            "Đã ẩn"
            if profile.birthday_visibility == "hidden"
            else f"{profile.birthday_day:02d}/{profile.birthday_month:02d}"
        )
    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        description=(
            "🎂 **Hôm nay là sinh nhật!**\nHồ sơ đang khoác giao diện Birthday Celebration."
            if profile.birthday_day == today.day and profile.birthday_month == today.month
            else "Hồ sơ hoạt động cộng đồng của bạn."
        ),
        color=(
            0xF9A8D4
            if profile.birthday_day == today.day and profile.birthday_month == today.month
            else 0xC4B5FD
        ),
    )
    avatar = getattr(member, "display_avatar", None)
    if avatar:
        embed.set_thumbnail(url=avatar.url)
    embed.add_field(name="Thành viên", value=f"**{days} ngày**", inline=True)
    embed.add_field(name="Tin nhắn", value=f"**{profile.message_count:,}**", inline=True)
    embed.add_field(name="Voice", value=f"**{hours}h {minutes}m**", inline=True)
    embed.add_field(name="Sinh nhật", value=birthday, inline=True)
    embed.add_field(
        name="Giới thiệu",
        value="Đã hoàn tất" if profile.introduced else "Chưa hoàn tất",
        inline=True,
    )
    embed.set_footer(text="Số liệu được ghi nhận từ khi Community System hoạt động")
    return embed


async def render_profile_card(
    renderer: CommunityCardRenderer,
    member: discord.abc.User,
    profile: CommunityProfile,
    featured: tuple[str, ...] = (),
) -> bytes:
    days = 0
    if profile.joined_at:
        days = max(0, (date.today() - date.fromtimestamp(profile.joined_at)).days)
    birthday = "Not set"
    if profile.birthday_day and profile.birthday_month:
        birthday = (
            "Private"
            if profile.birthday_visibility == "hidden"
            else f"{profile.birthday_day:02d}/{profile.birthday_month:02d}"
        )
    birthday_today = bool(
        profile.birthday_day == date.today().day
        and profile.birthday_month == date.today().month
    )
    return await renderer.render_profile(
        avatar_url=member.display_avatar.url,
        display_name=member.display_name,
        days=days,
        messages=profile.message_count,
        voice_seconds=profile.voice_seconds,
        birthday=birthday,
        introduced=profile.introduced,
        featured=featured,
        birthday_today=birthday_today,
    )


def welcome_embed(member: discord.Member, *, has_media: bool = True) -> discord.Embed:
    count = member.guild.member_count or len(member.guild.members)
    embed = discord.Embed(
        title="✨ CHÀO MỪNG ✨",
        description=(
            f"## Xin chào {member.mention}\n"
            f"Chào mừng bạn đến với **{BRAND_NAME}**.\n\n"
            f"👥 Thành viên thứ **#{count:,}**\n"
            f"📅 Tham gia <t:{int(member.joined_at.timestamp()) if member.joined_at else 0}:R>"
        ),
        color=0xC4B5FD,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if has_media:
        embed.set_image(url="attachment://welcome.gif")
    embed.set_footer(text="Hãy dành một chút thời gian khám phá cộng đồng nhé!")
    return embed


class IntroductionModal(discord.ui.Modal, title="👋 Giới thiệu bản thân"):
    preferred_name = discord.ui.TextInput(
        label="Tên gọi",
        placeholder="Mọi người có thể gọi bạn là gì?",
        max_length=50,
    )
    about = discord.ui.TextInput(
        label="Một chút về bạn",
        style=discord.TextStyle.paragraph,
        placeholder="Xin chào mọi người...",
        max_length=500,
    )
    interests = discord.ui.TextInput(
        label="Sở thích",
        placeholder="Coding, gaming, thể thao...",
        required=False,
        max_length=200,
    )

    def __init__(
        self,
        repository: CommunityRepository,
        renderer: CommunityCardRenderer,
        guild_id: int,
        owner_id: int,
        channel_resolver: Callable[[discord.Guild, str], Optional[discord.TextChannel]],
    ) -> None:
        super().__init__(timeout=300)
        self.repository = repository
        self.renderer = renderer
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.channel_resolver = channel_resolver

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id or not interaction.guild:
            await interaction.response.send_message("Form này không thuộc về bạn.", ephemeral=True)
            return
        await self.repository.save_introduction(
            self.guild_id,
            interaction.user.id,
            interaction.user.display_name,
            str(self.preferred_name),
            str(self.about),
            str(self.interests),
        )
        channel = self.channel_resolver(interaction.guild, "introductions")
        if not channel:
            await interaction.response.send_message(
                "Đã lưu giới thiệu nhưng chưa tìm thấy kênh introductions.",
                ephemeral=True,
            )
            return
        try:
            card = await self.renderer.render_introduction(
                avatar_url=interaction.user.display_avatar.url,
                display_name=interaction.user.display_name,
                preferred_name=str(self.preferred_name),
                about=str(self.about),
                interests=str(self.interests),
            )
            await channel.send(file=discord.File(io.BytesIO(card), filename="introduction.png"))
        except Exception:
            embed = discord.Embed(
                title="👋 THÀNH VIÊN MỚI",
                description=f"## {self.preferred_name}\n{self.about}",
                color=0x7DD3FC,
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url,
            )
            if str(self.interests).strip():
                embed.add_field(name="✨ Sở thích", value=str(self.interests), inline=False)
            await channel.send(embed=embed)
        await interaction.response.send_message("Giới thiệu của bạn đã được đăng.", ephemeral=True)


class WelcomeView(discord.ui.View):
    def __init__(
        self,
        repository: CommunityRepository,
        renderer: CommunityCardRenderer,
        member: discord.Member,
    ) -> None:
        super().__init__(timeout=7 * 24 * 60 * 60)
        self.repository = repository
        self.renderer = renderer
        self.owner_id = member.id
        self.guild_id = member.guild.id
        rules = find_text_channel(member.guild, "rules")
        if rules:
            self.add_item(
                discord.ui.Button(
                    label="Xem luật",
                    emoji="📜",
                    style=discord.ButtonStyle.link,
                    url=rules.jump_url,
                    row=1,
                )
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng chào mừng này thuộc thành viên khác.", ephemeral=True)
        return False

    @discord.ui.button(label="Khám phá server", emoji="🧭", style=discord.ButtonStyle.primary)
    async def guide(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        guild = interaction.guild
        if not guild:
            return
        items = []
        for keyword, label in (
            ("rules", "Đọc quy định cộng đồng"),
            ("announcements", "Theo dõi thông báo"),
            ("gossip", "Trò chuyện cùng mọi người"),
            ("events", "Xem hoạt động sắp tới"),
            ("music", "Nghe nhạc trong server"),
        ):
            channel = find_text_channel(guild, keyword)
            if channel:
                items.append(f"{channel.mention} — {label}")
        embed = discord.Embed(
            title="🧭 BẮT ĐẦU TỪ ĐÂY",
            description="\n".join(items) or "Chưa cấu hình hướng dẫn server.",
            color=0x7DD3FC,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Hồ sơ", emoji="👤", style=discord.ButtonStyle.secondary)
    async def profile(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        profile = await self.repository.get_profile(
            self.guild_id,
            interaction.user.id,
            interaction.user.display_name,
        )
        records = await self.repository.list_achievements(self.guild_id, interaction.user.id)
        featured = tuple(
            record.key
            for record in records
            if record.pinned and record.key in BY_KEY
        )
        await interaction.response.send_message(
            file=discord.File(
                io.BytesIO(
                    await render_profile_card(self.renderer, interaction.user, profile, featured)
                ),
                filename="community-profile.png",
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Giới thiệu bản thân", emoji="💬", style=discord.ButtonStyle.success)
    async def introduce(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            IntroductionModal(
                self.repository,
                self.renderer,
                self.guild_id,
                self.owner_id,
                find_text_channel,
            )
        )


class BirthdayWishModal(discord.ui.Modal, title="💌 Gửi lời chúc"):
    wish = discord.ui.TextInput(
        label="Lời chúc",
        style=discord.TextStyle.paragraph,
        placeholder="Chúc bạn tuổi mới luôn vui vẻ...",
        max_length=500,
    )

    def __init__(self, view: "BirthdayView") -> None:
        super().__init__(timeout=300)
        self.birthday_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.birthday_view.repository.add_birthday_wish(
            self.birthday_view.guild_id,
            self.birthday_view.target_user_id,
            interaction.user.id,
            interaction.user.display_name,
            str(self.wish),
            self.birthday_view.birthday_date,
        )
        reactions, wishes = await self.birthday_view.repository.birthday_counts(
            self.birthday_view.guild_id,
            self.birthday_view.target_user_id,
            self.birthday_view.birthday_date,
        )
        await interaction.response.edit_message(
            embed=self.birthday_view.embed(reactions, wishes),
            view=self.birthday_view,
        )
        await interaction.followup.send(
            f"Lời chúc đã được gửi tới **{self.birthday_view.target_name}**.",
            ephemeral=True,
        )


class BirthdayWishesView(discord.ui.View):
    def __init__(self, target_name: str, wishes, *, page: int = 0) -> None:
        super().__init__(timeout=300)
        self.target_name = target_name
        self.wishes = wishes
        self.page = page
        self.page_size = 4
        self._sync()

    @property
    def pages(self) -> int:
        return max(1, (len(self.wishes) + self.page_size - 1) // self.page_size)

    def _sync(self) -> None:
        self.previous.disabled = self.page == 0
        self.position.label = f"{self.page + 1} / {self.pages}"
        self.next.disabled = self.page >= self.pages - 1

    def embed(self) -> discord.Embed:
        start = self.page * self.page_size
        entries = self.wishes[start:start + self.page_size]
        description = "\n\n".join(
            f"💜 **{wish.author_name}**\n{wish.message}"
            for wish in entries
        ) or "Chưa có lời chúc nào. Hãy là người đầu tiên gửi một lời thật đẹp."
        embed = discord.Embed(
            title=f"💌 LỜI CHÚC DÀNH CHO {self.target_name}",
            description=description,
            color=0xF9A8D4,
        )
        embed.set_footer(text=f"{len(self.wishes)} lời chúc · Trang {self.page + 1}/{self.pages}")
        return embed

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def position(self, _interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        return

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = min(self.pages - 1, self.page + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)


class BirthdayView(discord.ui.View):
    def __init__(
        self,
        repository: CommunityRepository,
        guild_id: int,
        target_user_id: int,
        target_name: str,
        avatar_url: str,
        birthday_date: str,
        *,
        has_media: bool = True,
    ) -> None:
        super().__init__(timeout=None)
        self.repository = repository
        self.guild_id = guild_id
        self.target_user_id = target_user_id
        self.target_name = target_name
        self.avatar_url = avatar_url
        self.birthday_date = birthday_date
        self.has_media = has_media

    def embed(self, reactions: int = 0, wishes: int = 0) -> discord.Embed:
        embed = discord.Embed(
            title="🎂✨ CHÚC MỪNG SINH NHẬT",
            description=(
                f"## <@{self.target_user_id}>\n"
                "Chúc bạn một tuổi mới thật nhiều niềm vui, may mắn và những điều tốt đẹp."
            ),
            color=0xF9A8D4,
        )
        embed.set_thumbnail(url=self.avatar_url)
        if self.has_media:
            embed.set_image(url="attachment://birthday.gif")
        embed.add_field(name="🎉 Chúc mừng", value=f"**{reactions} người**", inline=True)
        embed.add_field(name="💌 Lời nhắn", value=f"**{wishes} lời chúc**", inline=True)
        embed.set_footer(text="Cùng gửi một lời chúc thật đẹp nhé!")
        return embed

    @discord.ui.button(label="Chúc mừng", emoji="🎉", style=discord.ButtonStyle.primary, custom_id="birthday:congratulate")
    async def congratulate(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        added, reactions = await self.repository.add_birthday_reaction(
            self.guild_id,
            self.target_user_id,
            interaction.user.id,
            self.birthday_date,
        )
        _, wishes = await self.repository.birthday_counts(
            self.guild_id,
            self.target_user_id,
            self.birthday_date,
        )
        await interaction.response.edit_message(embed=self.embed(reactions, wishes), view=self)
        if not added:
            await interaction.followup.send("Bạn đã gửi lời chúc mừng rồi.", ephemeral=True)

    @discord.ui.button(label="Gửi lời chúc", emoji="💌", style=discord.ButtonStyle.secondary, custom_id="birthday:send_wish")
    async def send_wish(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(BirthdayWishModal(self))

    @discord.ui.button(label="Xem lời chúc", emoji="📖", style=discord.ButtonStyle.secondary, custom_id="birthday:view_wishes")
    async def view_wishes(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        wishes = await self.repository.list_birthday_wishes(
            self.guild_id,
            self.target_user_id,
            self.birthday_date,
        )
        view = BirthdayWishesView(self.target_name, wishes)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)


def birthday_calendar_embed(month: int, entries: list[BirthdayEntry]) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎂 SINH NHẬT THÁNG {month:02d}",
        color=0xFDBA8C,
    )
    if entries:
        embed.description = "\n".join(
            f"`{entry.day:02d}/{entry.month:02d}`  🎉 <@{entry.user_id}>"
            for entry in entries
        )
        embed.set_footer(text=f"{len(entries)} sinh nhật trong tháng")
    else:
        embed.description = "Chưa có sinh nhật công khai trong tháng này."
    return embed


def _achievement_value(profile: CommunityProfile, metric: str) -> int:
    if metric == "messages":
        return profile.message_count
    if metric == "voice_seconds":
        return profile.voice_seconds
    if metric == "days" and profile.joined_at:
        return max(0, (date.today() - date.fromtimestamp(profile.joined_at)).days)
    return 0


class AchievementCategorySelect(discord.ui.Select):
    def __init__(self, parent: "AchievementsView") -> None:
        super().__init__(
            placeholder="Chọn nhóm huy hiệu",
            options=[discord.SelectOption(label=label, value=key) for key, label in CATEGORIES.items()],
            row=0,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.category = self.values[0]
        await interaction.response.edit_message(embed=self.parent_view.embed(), view=self.parent_view)


class AchievementsView(discord.ui.View):
    def __init__(
        self,
        repository: CommunityRepository,
        profile: CommunityProfile,
        records,
        guild_id: int,
        owner_id: int,
        *,
        category: str = "all",
    ) -> None:
        super().__init__(timeout=300)
        self.repository = repository
        self.profile = profile
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.category = category
        self.unlocked = {record.key for record in records}
        self.pinned = {record.key for record in records if record.pinned}
        self.add_item(AchievementCategorySelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bộ huy hiệu này thuộc thành viên khác.", ephemeral=True)
        return False

    def embed(self) -> discord.Embed:
        items = [
            item
            for item in ACHIEVEMENTS
            if self.category == "all" or item.category == self.category
        ]
        lines = []
        for item in items:
            if item.key in self.unlocked:
                pin = " · 📌" if item.key in self.pinned else ""
                lines.append(f"{item.icon} **{item.title}**{pin}\n　{item.description} · Đã mở khóa")
                continue
            if item.manual:
                lines.append(f"🔒 **{item.title}**\n　{item.description} · Admin trao")
                continue
            value = _achievement_value(self.profile, item.metric)
            ratio = min(1.0, value / max(1, item.threshold))
            blocks = round(ratio * 10)
            unit_value = value // 3600 if item.metric == "voice_seconds" else value
            unit_threshold = item.threshold // 3600 if item.metric == "voice_seconds" else item.threshold
            lines.append(
                f"🔒 **{item.title}**\n　{'█' * blocks}{'░' * (10 - blocks)} "
                f"`{unit_value:,}/{unit_threshold:,}`"
            )
        embed = discord.Embed(
            title="🏅 HUY HIỆU KSC GAMING",
            description="\n\n".join(lines) or "Chưa có huy hiệu trong nhóm này.",
            color=0xC4B5FD,
        )
        embed.set_footer(
            text=f"Đã mở khóa {len(self.unlocked)} / {len(ACHIEVEMENTS)} · Nổi bật tự động {len(self.pinned)} / 5"
        )
        return embed


async def achievements_payload(
    repository: CommunityRepository,
    guild_id: int,
    user: discord.abc.User,
    *,
    category: str = "all",
) -> tuple[discord.Embed, AchievementsView]:
    profile = await repository.get_profile(guild_id, user.id, user.display_name)
    records = await repository.list_achievements(guild_id, user.id)
    view = AchievementsView(repository, profile, records, guild_id, user.id, category=category)
    return view.embed(), view


COMMUNITY_FEATURES = {
    "welcome": ("Welcome", "welcome"),
    "goodbye": ("Goodbye", "member-log"),
    "birthday": ("Birthday", "celebrations"),
    "analytics": ("Analytics", "community-analytics"),
    "weekly": ("Weekly Recap", "weekly-recap"),
}


def community_settings_embed(settings: dict[str, str], guild: discord.Guild) -> discord.Embed:
    lines = []
    for key, (label, fallback) in COMMUNITY_FEATURES.items():
        enabled = settings.get(f"feature_{key}", "on") == "on"
        channel_id = settings.get(f"channel_{key}")
        channel = guild.get_channel(int(channel_id)) if channel_id and channel_id.isdigit() else None
        if not channel:
            channel = find_text_channel(guild, fallback)
        privacy = {
            "public": "Công khai",
            "compact": "Tối giản",
            "admin": "Chỉ quản trị",
        }.get(settings.get(f"privacy_{key}", "public"), "Công khai")
        lines.append(
            f"{'🟢' if enabled else '⚫'} **{label}**\n"
            f"　{channel.mention if channel else '`Chưa chọn kênh`'} · {privacy}"
        )
    embed = discord.Embed(
        title="⚙️ KSC COMMUNITY CONTROL CENTER",
        description="\n\n".join(lines),
        color=0x6EE7B7,
    )
    embed.set_footer(text="Chọn tính năng bên dưới để thay đổi trạng thái, kênh và quyền riêng tư")
    return embed


class SettingsFeatureSelect(discord.ui.Select):
    def __init__(self, parent: "CommunitySettingsView") -> None:
        options = [
            discord.SelectOption(label=label, value=key, default=key == parent.feature)
            for key, (label, _fallback) in COMMUNITY_FEATURES.items()
        ]
        super().__init__(
            placeholder="Chọn tính năng cần cấu hình",
            options=options,
            custom_id="community_settings:feature",
            row=0,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.feature = self.values[0]
        await self.parent_view.update(interaction)


class SettingsToggle(discord.ui.Button):
    def __init__(self, parent: "CommunitySettingsView") -> None:
        enabled = parent.settings.get(f"feature_{parent.feature}", "on") == "on"
        super().__init__(
            label="Đang bật" if enabled else "Đang tắt",
            emoji="✅" if enabled else "⏸️",
            style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary,
            custom_id="community_settings:toggle",
            row=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        key = f"feature_{self.parent_view.feature}"
        enabled = self.parent_view.settings.get(key, "on") == "on"
        await self.parent_view.repository.set_config(
            self.parent_view.guild.id,
            key,
            "off" if enabled else "on",
        )
        await self.parent_view.update(interaction, reload=True)


class SettingsChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent: "CommunitySettingsView") -> None:
        label = COMMUNITY_FEATURES[parent.feature][0]
        super().__init__(
            placeholder=f"Chọn kênh cho {label}",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            custom_id="community_settings:channel",
            row=2,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.repository.set_config(
            self.parent_view.guild.id,
            f"channel_{self.parent_view.feature}",
            str(self.values[0].id),
        )
        await self.parent_view.update(interaction, reload=True)


class SettingsPrivacySelect(discord.ui.Select):
    def __init__(self, parent: "CommunitySettingsView") -> None:
        current = parent.settings.get(f"privacy_{parent.feature}", "public")
        options = [
            discord.SelectOption(label="Công khai", value="public", emoji="🌐"),
            discord.SelectOption(label="Tối giản", value="compact", emoji="🪶"),
            discord.SelectOption(label="Chỉ quản trị", value="admin", emoji="🔒"),
        ]
        for option in options:
            option.default = option.value == current
        super().__init__(
            placeholder="Chọn quyền riêng tư",
            options=options,
            custom_id="community_settings:privacy",
            row=3,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.repository.set_config(
            self.parent_view.guild.id,
            f"privacy_{self.parent_view.feature}",
            self.values[0],
        )
        await self.parent_view.update(interaction, reload=True)


class CommunitySettingsView(discord.ui.View):
    def __init__(
        self,
        repository: CommunityRepository,
        guild: discord.Guild,
        settings: dict[str, str],
        *,
        feature: str = "welcome",
    ) -> None:
        super().__init__(timeout=None)
        self.repository = repository
        self.guild = guild
        self.settings = settings
        self.feature = feature
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        self.clear_items()
        self.add_item(SettingsFeatureSelect(self))
        self.add_item(SettingsToggle(self))
        self.add_item(SettingsChannelSelect(self))
        self.add_item(SettingsPrivacySelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild:
            return True
        await interaction.response.send_message("Bạn cần quyền Manage Server để thay đổi cấu hình.", ephemeral=True)
        return False

    async def update(self, interaction: discord.Interaction, *, reload: bool = False) -> None:
        await interaction.response.defer()
        if reload:
            self.settings = await self.repository.community_settings(self.guild.id)
        self._refresh_controls()
        await interaction.edit_original_response(
            embed=community_settings_embed(self.settings, self.guild),
            view=self,
        )


async def community_settings_payload(
    repository: CommunityRepository,
    guild: discord.Guild,
) -> tuple[discord.Embed, CommunitySettingsView]:
    settings = await repository.community_settings(guild.id)
    return community_settings_embed(settings, guild), CommunitySettingsView(repository, guild, settings)


def _change(current: int, previous: int) -> str:
    if previous <= 0:
        return "Mới" if current else "0%"
    percent = (current - previous) / previous * 100
    return f"{'▲' if percent >= 0 else '▼'} {abs(percent):.1f}%"


def _sparkline(values: list[int]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return bars[0] * min(24, max(1, len(values)))
    if len(values) > 24:
        stride = (len(values) + 23) // 24
        values = [sum(values[index:index + stride]) for index in range(0, len(values), stride)]
    maximum = max(values)
    return "".join(bars[round(value / maximum * (len(bars) - 1))] for value in values)


def _heatmap(snapshot: AnalyticsSnapshot) -> str:
    cells = {(item.weekday, item.hour): item.messages + item.voice_seconds // 60 for item in snapshot.hourly}
    buckets = []
    for start_hour in (0, 6, 12, 18):
        buckets.append([
            sum(cells.get((weekday, hour), 0) for hour in range(start_hour, start_hour + 6))
            for weekday in (1, 2, 3, 4, 5, 6, 0)
        ])
    maximum = max((value for row in buckets for value in row), default=0) or 1
    shades = "░▒▓█"
    lines = ["      T2 T3 T4 T5 T6 T7 CN"]
    for label, row in zip(("00-05", "06-11", "12-17", "18-23"), buckets):
        lines.append(f"{label}  " + "  ".join(shades[round(value / maximum * 3)] for value in row))
    return "```text\n" + "\n".join(lines) + "\n```"


def analytics_embed(snapshot: AnalyticsSnapshot, guild: discord.Guild, page: str = "overview") -> discord.Embed:
    titles = {
        "overview": "📊 TỔNG QUAN CỘNG ĐỒNG",
        "members": "👥 THÀNH VIÊN",
        "chat": "💬 HOẠT ĐỘNG TRÒ CHUYỆN",
        "voice": "🔊 HOẠT ĐỘNG VOICE",
        "activity": "🔥 NHỊP ĐỘ CỘNG ĐỒNG",
        "retention": "🔄 GIỮ CHÂN THÀNH VIÊN",
        "growth": "📈 TĂNG TRƯỞNG THÀNH VIÊN",
        "events": "🎉 EVENT ANALYTICS",
    }
    embed = discord.Embed(
        title=titles.get(page, titles["overview"]),
        description=f"`{snapshot.start_day}` → `{snapshot.end_day}` · **{snapshot.days} ngày**",
        color=0x7DD3FC,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_image(url="attachment://analytics.png")
    if page == "overview":
        embed.add_field(name="👥 Thành viên", value=f"**{snapshot.total_members:,}**\n{snapshot.new_members:+,} mới", inline=True)
        embed.add_field(name="💬 Tin nhắn", value=f"**{snapshot.messages:,}**\n{_change(snapshot.messages, snapshot.previous_messages)}", inline=True)
        embed.add_field(name="🔊 Voice", value=f"**{snapshot.voice_seconds / 3600:,.1f} giờ**\n{_change(snapshot.voice_seconds, snapshot.previous_voice_seconds)}", inline=True)
        embed.add_field(name="🔥 Active", value=f"**{snapshot.active_members:,}**\n{_change(snapshot.active_members, snapshot.previous_active_members)}", inline=True)
        embed.add_field(name="🏅 Thành tựu", value=f"**{snapshot.achievements:,}** mở khóa", inline=True)
        embed.add_field(name="📈 Tăng trưởng ròng", value=f"**{snapshot.new_members - snapshot.left_members:+,}**", inline=True)
        today = snapshot.daily[-1] if snapshot.daily else None
        embed.add_field(
            name="🟢 Hôm nay",
            value=(
                f"**{today.messages:,}** tin nhắn · "
                f"**{today.voice_seconds / 3600:,.1f}h** voice · "
                f"**{today.active_members:,}** active"
                if today
                else "Chưa ghi nhận hoạt động."
            ),
            inline=False,
        )
    elif page == "members":
        embed.add_field(name="Tổng thành viên", value=f"**{snapshot.total_members:,}**", inline=True)
        embed.add_field(name="Tham gia", value=f"**+{snapshot.new_members:,}**", inline=True)
        embed.add_field(name="Rời server", value=f"**-{snapshot.left_members:,}**", inline=True)
        leaders = "\n".join(
            f"**{index}.** <@{member.user_id}> · {member.messages:,} tin · {member.voice_seconds / 3600:.1f}h"
            for index, member in enumerate(snapshot.top_members, 1)
        ) or "Chưa có hoạt động trong kỳ."
        embed.add_field(name="Thành viên nổi bật", value=leaders, inline=False)
        embed.add_field(name="Biểu đồ tăng trưởng", value=_sparkline([point.total for point in snapshot.growth]), inline=False)
    elif page == "chat":
        channels = "\n".join(
            f"**{index}.** <#{item.channel_id}> · {item.messages:,} tin nhắn"
            for index, item in enumerate(snapshot.top_chat_channels, 1)
        ) or "Dữ liệu theo kênh sẽ xuất hiện từ phiên bản này."
        embed.add_field(name=f"{snapshot.messages:,} tin nhắn", value=channels, inline=False)
        embed.add_field(name="Xu hướng", value=_sparkline([point.messages for point in snapshot.daily]), inline=False)
    elif page == "voice":
        channels = "\n".join(
            f"**{index}.** <#{item.channel_id}> · {item.voice_seconds / 3600:.1f} giờ"
            for index, item in enumerate(snapshot.top_voice_channels, 1)
        ) or "Dữ liệu theo kênh sẽ xuất hiện khi phiên voice kết thúc."
        embed.add_field(name=f"{snapshot.voice_seconds / 3600:,.1f} giờ voice", value=channels, inline=False)
        embed.add_field(name="Xu hướng", value=_sparkline([point.voice_seconds for point in snapshot.daily]), inline=False)
    elif page == "activity":
        embed.add_field(name="Hôm nay", value=f"**{snapshot.daily[-1].active_members if snapshot.daily else 0:,}** active", inline=True)
        embed.add_field(name=f"{snapshot.days} ngày", value=f"**{snapshot.active_members:,}** active", inline=True)
        ratio = snapshot.active_members / max(1, snapshot.total_members) * 100
        embed.add_field(name="Tỷ lệ hoạt động", value=f"**{ratio:.1f}%**", inline=True)
        embed.add_field(name="Nhịp hoạt động", value=_sparkline([point.active_members for point in snapshot.daily]), inline=False)
        weekday = ("CN", "T2", "T3", "T4", "T5", "T6", "T7")[snapshot.peak_weekday]
        embed.add_field(name="Peak time", value=f"**{weekday} · {snapshot.peak_hour:02d}:00–{(snapshot.peak_hour + 1) % 24:02d}:00**", inline=False)
        embed.add_field(name="Heatmap", value=_heatmap(snapshot), inline=False)
    elif page == "retention":
        embed.add_field(name="Sau 1 ngày", value=f"**{snapshot.retention_1d:.1f}%**", inline=True)
        embed.add_field(name="Sau 7 ngày", value=f"**{snapshot.retention_7d:.1f}%**", inline=True)
        embed.add_field(name="Sau 30 ngày", value=f"**{snapshot.retention_30d:.1f}%**", inline=True)
        embed.add_field(
            name="Cách tính",
            value="Tỷ lệ thành viên mới quay lại và có ít nhất một hoạt động sau mốc tương ứng.",
            inline=False,
        )
        joined = max(1, snapshot.funnel_joined)
        embed.add_field(
            name="Funnel thành viên mới",
            value=(
                f"**100%** Tham gia ({snapshot.funnel_joined})\n"
                f"**{snapshot.funnel_introduced / joined * 100:.0f}%** Hoàn tất giới thiệu ({snapshot.funnel_introduced})\n"
                f"**{snapshot.funnel_first_activity / joined * 100:.0f}%** Có hoạt động đầu tiên ({snapshot.funnel_first_activity})\n"
                f"**{snapshot.funnel_returned_7d / joined * 100:.0f}%** Quay lại sau 7 ngày ({snapshot.funnel_returned_7d})\n"
                f"**{snapshot.funnel_returned_30d / joined * 100:.0f}%** Quay lại sau 30 ngày ({snapshot.funnel_returned_30d})"
            ),
            inline=False,
        )
    elif page == "growth":
        embed.add_field(name="Tham gia", value=f"**+{snapshot.new_members:,}**", inline=True)
        embed.add_field(name="Rời server", value=f"**-{snapshot.left_members:,}**", inline=True)
        embed.add_field(name="Tăng ròng", value=f"**{snapshot.new_members - snapshot.left_members:+,}**", inline=True)
        embed.add_field(name="Thành viên theo ngày", value=_sparkline([point.total for point in snapshot.growth]), inline=False)
        embed.add_field(name="Lượt tham gia", value=_sparkline([point.joined for point in snapshot.growth]), inline=False)
    else:
        attendance = snapshot.events.attendees / max(1, snapshot.events.registrations) * 100
        embed.add_field(name="Sự kiện", value=f"**{snapshot.events.events:,}**", inline=True)
        embed.add_field(name="Đăng ký", value=f"**{snapshot.events.registrations:,}**", inline=True)
        embed.add_field(name="Tham dự", value=f"**{snapshot.events.attendees:,}** · {attendance:.0f}%", inline=True)
        embed.add_field(
            name="Sự kiện nổi bật",
            value=(
                f"**{snapshot.events.top_event_name}** · {snapshot.events.top_event_attendees} người tham dự"
                if snapshot.events.top_event_name
                else "Chưa có dữ liệu sự kiện trong kỳ."
            ),
            inline=False,
        )
    embed.set_footer(text=f"{BRAND_NAME} · Tự động cập nhật mỗi 15 phút · Asia/Saigon")
    return embed


class AnalyticsSectionSelect(discord.ui.Select):
    def __init__(self, parent: "AnalyticsView") -> None:
        options = [
            discord.SelectOption(label="Tổng quan", value="overview", emoji="📊"),
            discord.SelectOption(label="Thành viên", value="members", emoji="👥"),
            discord.SelectOption(label="Trò chuyện", value="chat", emoji="💬"),
            discord.SelectOption(label="Voice", value="voice", emoji="🔊"),
            discord.SelectOption(label="Hoạt động", value="activity", emoji="🔥"),
            discord.SelectOption(label="Retention", value="retention", emoji="🔄"),
            discord.SelectOption(label="Tăng trưởng", value="growth", emoji="📈"),
            discord.SelectOption(label="Sự kiện", value="events", emoji="🎉"),
        ]
        for option in options:
            option.default = option.value == parent.page
        super().__init__(placeholder="Chọn báo cáo", options=options, row=0)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.page = self.values[0]
        await self.parent_view.update(interaction)


class AnalyticsPeriodSelect(discord.ui.Select):
    def __init__(self, parent: "AnalyticsView") -> None:
        options = [
            discord.SelectOption(label="7 ngày", value="7"),
            discord.SelectOption(label="30 ngày", value="30"),
            discord.SelectOption(label="90 ngày", value="90"),
        ]
        for option in options:
            option.default = option.value == str(parent.days)
        super().__init__(placeholder="Khoảng thời gian", options=options, row=1)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.days = int(self.values[0])
        await self.parent_view.update(interaction, reload=True)


class AnalyticsView(discord.ui.View):
    def __init__(
        self,
        repository: CommunityRepository,
        renderer: CommunityCardRenderer,
        guild: discord.Guild,
        owner_id: int,
        snapshot: AnalyticsSnapshot,
    ) -> None:
        super().__init__(timeout=300)
        self.repository = repository
        self.renderer = renderer
        self.guild = guild
        self.owner_id = owner_id
        self.snapshot = snapshot
        self.days = snapshot.days
        self.page = "overview"
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        self.clear_items()
        self.add_item(AnalyticsSectionSelect(self))
        self.add_item(AnalyticsPeriodSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Dashboard này thuộc phiên quản trị khác.", ephemeral=True)
        return False

    async def update(self, interaction: discord.Interaction, *, reload: bool = False) -> None:
        await interaction.response.defer()
        if reload:
            self.snapshot = await self.repository.analytics_snapshot(self.guild.id, days=self.days)
        self._refresh_controls()
        card = await self.renderer.render_analytics(snapshot=self.snapshot, server_name=BRAND_NAME)
        await interaction.edit_original_response(
            embed=analytics_embed(self.snapshot, self.guild, self.page),
            attachments=[discord.File(io.BytesIO(card), filename="analytics.png")],
            view=self,
        )


async def analytics_payload(
    repository: CommunityRepository,
    renderer: CommunityCardRenderer,
    guild: discord.Guild,
    owner_id: int,
    *,
    days: int = 30,
) -> tuple[discord.Embed, AnalyticsView, discord.File]:
    snapshot = await repository.analytics_snapshot(guild.id, days=days)
    view = AnalyticsView(repository, renderer, guild, owner_id, snapshot)
    card = await renderer.render_analytics(snapshot=snapshot, server_name=BRAND_NAME)
    return (
        analytics_embed(snapshot, guild),
        view,
        discord.File(io.BytesIO(card), filename="analytics.png"),
    )


WEEKLY_PAGES = (
    "overview",
    "community",
    "activity",
    "achievements",
    "highlights",
    "events",
    "next",
)


def _scheduled_events(guild: discord.Guild) -> list[discord.ScheduledEvent]:
    return sorted(
        guild.scheduled_events,
        key=lambda event: event.start_time,
    )


def weekly_embed(snapshot: WeeklySnapshot, guild: discord.Guild, page: int = 0) -> discord.Embed:
    page = max(0, min(page, len(WEEKLY_PAGES) - 1))
    section = WEEKLY_PAGES[page]
    titles = {
        "overview": "✨ KSC GAMING WEEKLY",
        "community": "👥 CỘNG ĐỒNG TUẦN NÀY",
        "activity": "🔥 NHỊP ĐỘ HOẠT ĐỘNG",
        "achievements": "🏅 THÀNH TỰU TUẦN NÀY",
        "highlights": "⭐ THÀNH VIÊN NỔI BẬT",
        "events": "🎉 SỰ KIỆN CỘNG ĐỒNG",
        "next": "📅 TUẦN TIẾP THEO",
    }
    analytics = snapshot.analytics
    embed = discord.Embed(
        title=titles[section],
        description=f"`{snapshot.start_day}` → `{snapshot.end_day}`",
        color=0xF9A8D4,
    )
    embed.set_image(url="attachment://weekly-recap.png")
    if section == "overview":
        embed.add_field(name="👥 Thành viên mới", value=f"**+{analytics.new_members:,}**", inline=True)
        embed.add_field(name="💬 Tin nhắn", value=f"**{analytics.messages:,}**", inline=True)
        embed.add_field(name="🔊 Voice", value=f"**{analytics.voice_seconds / 3600:,.1f} giờ**", inline=True)
        embed.add_field(name="🔥 Active", value=f"**{analytics.active_members:,}**", inline=True)
        embed.add_field(name="🏅 Thành tựu", value=f"**{analytics.achievements:,}**", inline=True)
        embed.add_field(name="📈 Tăng trưởng", value=f"**{analytics.new_members - analytics.left_members:+,}**", inline=True)
        if snapshot.milestones:
            embed.add_field(name="🎉 Cột mốc mới", value="\n".join(f"**{item}**" for item in snapshot.milestones), inline=False)
    elif section == "community":
        embed.add_field(name="Tham gia", value=f"**+{analytics.new_members:,}**", inline=True)
        embed.add_field(name="Rời server", value=f"**-{analytics.left_members:,}**", inline=True)
        embed.add_field(name="Tổng thành viên", value=f"**{analytics.total_members:,}**", inline=True)
        newcomers = " ".join(f"<@{member.user_id}>" for member in snapshot.new_members)
        embed.add_field(
            name="Chào mừng thành viên mới",
            value=newcomers or "Tuần này chưa ghi nhận thành viên mới.",
            inline=False,
        )
    elif section == "activity":
        embed.add_field(name="Tin nhắn", value=f"**{analytics.messages:,}**\n{_change(analytics.messages, analytics.previous_messages)}", inline=True)
        embed.add_field(name="Voice", value=f"**{analytics.voice_seconds / 3600:,.1f}h**\n{_change(analytics.voice_seconds, analytics.previous_voice_seconds)}", inline=True)
        embed.add_field(name="Active", value=f"**{analytics.active_members:,}**\n{_change(analytics.active_members, analytics.previous_active_members)}", inline=True)
        embed.add_field(name="Nhịp trò chuyện", value=_sparkline([point.messages for point in analytics.daily]), inline=False)
        embed.add_field(name="Nhịp voice", value=_sparkline([point.voice_seconds for point in analytics.daily]), inline=False)
    elif section == "achievements":
        lines = []
        for badge in snapshot.badges:
            item = BY_KEY.get(badge.key)
            lines.append(f"{item.icon if item else '🏅'} **{item.title if item else badge.key}** · {badge.count} người")
        embed.description += "\n\n" + ("\n".join(lines) if lines else "Chưa có thành tựu mới trong tuần này.")
        embed.set_footer(text=f"{analytics.achievements:,} thành tựu đã được mở khóa")
    elif section == "highlights":
        lines = []
        for index, member in enumerate(analytics.top_members[:5], 1):
            lines.append(
                f"**{index}.** <@{member.user_id}>\n"
                f"　💬 {member.messages:,} tin nhắn · 🔊 {member.voice_seconds / 3600:.1f} giờ"
            )
        embed.description += "\n\n" + ("\n\n".join(lines) if lines else "Chưa có đủ dữ liệu hoạt động trong tuần.")
    elif section == "events":
        attendance = analytics.events.attendees / max(1, analytics.events.registrations) * 100
        embed.add_field(name="Sự kiện", value=f"**{analytics.events.events}**", inline=True)
        embed.add_field(name="Đăng ký", value=f"**{analytics.events.registrations}**", inline=True)
        embed.add_field(name="Tham dự", value=f"**{analytics.events.attendees}** · {attendance:.0f}%", inline=True)
        if analytics.events.top_event_name:
            embed.add_field(
                name="Sự kiện nổi bật",
                value=f"🏆 **{analytics.events.top_event_name}** · {analytics.events.top_event_attendees} người",
                inline=False,
            )
        events = _scheduled_events(guild)
        if events:
            embed.description += "\n\n" + "\n".join(
                f"🎉 **{event.name}**\n　<t:{int(event.start_time.timestamp())}:F>"
                for event in events[:6]
            )
        else:
            embed.description += "\n\nChưa có Discord Event nào được lên lịch."
        birthdays = "\n".join(
            f"🎂 <@{entry.user_id}> · {entry.reactions} lượt chúc · {entry.wishes} lời nhắn"
            for entry in snapshot.birthdays
        )
        if birthdays:
            embed.add_field(name="Sinh nhật trong tuần", value=birthdays, inline=False)
    else:
        events = _scheduled_events(guild)
        embed.description += "\n\n**Cùng chờ đón những hoạt động tiếp theo của cộng đồng.**"
        if events:
            embed.add_field(
                name="Lịch sắp tới",
                value="\n".join(
                    f"📌 **{event.name}** · <t:{int(event.start_time.timestamp())}:R>"
                    for event in events[:6]
                ),
                inline=False,
            )
        embed.add_field(
            name="Một tuần mới",
            value="Cảm ơn mọi người đã cùng tạo nên một tuần thật nhiều kết nối tại KSC Gaming.",
            inline=False,
        )
    if not embed.footer.text:
        embed.set_footer(text=f"{BRAND_NAME} · Trang {page + 1}/{len(WEEKLY_PAGES)}")
    return embed


class WeeklyRecapView(discord.ui.View):
    def __init__(self, snapshot: WeeklySnapshot, guild: discord.Guild, *, page: int = 0) -> None:
        super().__init__(timeout=None)
        self.snapshot = snapshot
        self.guild = guild
        self.page = page
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.previous.disabled = self.page == 0
        self.position.label = f"{self.page + 1} / {len(WEEKLY_PAGES)}"
        self.next.disabled = self.page == len(WEEKLY_PAGES) - 1

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="weekly_recap:previous")
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=weekly_embed(self.snapshot, self.guild, self.page), view=self)

    @discord.ui.button(label="1 / 7", style=discord.ButtonStyle.secondary, disabled=True, custom_id="weekly_recap:position")
    async def position(self, _interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        return

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="weekly_recap:next")
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.page = min(len(WEEKLY_PAGES) - 1, self.page + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=weekly_embed(self.snapshot, self.guild, self.page), view=self)


async def weekly_payload(
    repository: CommunityRepository,
    renderer: CommunityCardRenderer,
    guild: discord.Guild,
    start: date,
    end: date,
) -> tuple[discord.Embed, WeeklyRecapView, discord.File]:
    snapshot = await repository.weekly_snapshot(guild.id, start, end)
    view = WeeklyRecapView(snapshot, guild)
    card = await renderer.render_weekly(snapshot=snapshot, server_name=BRAND_NAME)
    return (
        weekly_embed(snapshot, guild),
        view,
        discord.File(io.BytesIO(card), filename="weekly-recap.png"),
    )
