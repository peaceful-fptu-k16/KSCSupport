import asyncio
import io
import logging
from datetime import date, datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from community import CommunityRepository
from community.achievements import BY_KEY, automatic_keys, featured_keys
from community.cards import CommunityCardRenderer
from community.guide_webhook import ServerGuideWebhook
from branding import BRAND_NAME
from community.ui import (
    BirthdayView,
    CommunitySettingsView,
    IntroductionModal,
    WelcomeView,
    analytics_embed,
    analytics_payload,
    achievements_payload,
    birthday_calendar_embed,
    community_profile_embed,
    community_settings_payload,
    find_text_channel,
    render_profile_card,
    welcome_embed,
    weekly_payload,
    WeeklyRecapView,
)


logger = logging.getLogger(__name__)
LOCAL_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")
CHANNELS = (
    "welcome",
    "announcements",
    "introductions",
    "rules",
    "celebrations",
    "events",
    "weekly-recap",
    "community-analytics",
    "member-log",
    "bot-config",
)


class Community(commands.Cog):
    """Member lifecycle and community activity foundation."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.repository = CommunityRepository()
        self.cards = CommunityCardRenderer()
        self.server_guide_webhook = ServerGuideWebhook(self.repository)
        self._guide_bump_tasks: dict[int, asyncio.Task] = {}
        self._voice_seeded = False
        self._achievement_scan_day: str | None = None
        self._analytics_day: str | None = None
        self._weekly_checked_day: str | None = None

    async def cog_load(self) -> None:
        await self.repository.initialize()
        await self.server_guide_webhook.start()
        self.birthday_scheduler.start()
        self.achievement_scheduler.start()
        self.analytics_scheduler.start()
        self.weekly_scheduler.start()

    async def _sync_featured(self, guild_id: int, user_id: int) -> None:
        records = await self.repository.list_achievements(guild_id, user_id)
        selected = featured_keys(record.key for record in records)
        await self.repository.set_featured_achievements(guild_id, user_id, selected)

    async def _announce_unlocks(self, member: discord.Member, keys: list[str]) -> None:
        channel = find_text_channel(member.guild, "celebrations")
        if not channel:
            return
        for key in keys:
            item = BY_KEY.get(key)
            if not item or not item.public:
                continue
            embed = discord.Embed(
                title="🏅 THÀNH TỰU MỚI",
                description=f"## {item.icon} {item.title}\n{member.mention}\n\n{item.description}",
                color=0xFDE68A,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

    async def _unlock_keys(
        self,
        member: discord.Member,
        keys: list[str],
        *,
        announce: bool,
    ) -> list[str]:
        unlocked = []
        for key in keys:
            if await self.repository.unlock_achievement(member.guild.id, member.id, key):
                unlocked.append(key)
        if unlocked:
            await self._sync_featured(member.guild.id, member.id)
            if announce:
                await self._announce_unlocks(member, unlocked)
        return unlocked

    async def _feature_enabled(self, guild_id: int, feature: str) -> bool:
        return (await self.repository.get_config(guild_id, f"feature_{feature}") or "on") == "on"

    async def _privacy(self, guild_id: int, feature: str, default: str = "public") -> str:
        return await self.repository.get_config(guild_id, f"privacy_{feature}") or default

    async def _configured_channel(
        self,
        guild: discord.Guild,
        feature: str,
        fallback: str,
    ) -> discord.TextChannel | None:
        channel_id = await self.repository.get_config(guild.id, f"channel_{feature}")
        if channel_id and channel_id.isdigit():
            channel = guild.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                return channel
        return find_text_channel(guild, fallback)

    async def _evaluate_member(self, member: discord.Member, *, announce: bool = True) -> list[str]:
        profile = await self.repository.get_profile(
            member.guild.id,
            member.id,
            member.display_name,
        )
        days = 0
        if profile.joined_at:
            days = max(0, (datetime.now(LOCAL_TZ).date() - datetime.fromtimestamp(profile.joined_at, LOCAL_TZ).date()).days)
        unlocked = await self._unlock_keys(
            member,
            automatic_keys(
                days=days,
                messages=profile.message_count,
                voice_seconds=profile.voice_seconds,
            ),
            announce=announce,
        )
        if not unlocked:
            await self._sync_featured(member.guild.id, member.id)
        return unlocked

    def cog_unload(self) -> None:
        self.birthday_scheduler.cancel()
        self.achievement_scheduler.cancel()
        self.analytics_scheduler.cancel()
        self.weekly_scheduler.cancel()
        asyncio.create_task(self._shutdown())

    async def _shutdown(self) -> None:
        for task in self._guide_bump_tasks.values():
            task.cancel()
        if self._guide_bump_tasks:
            await asyncio.gather(*self._guide_bump_tasks.values(), return_exceptions=True)
        self._guide_bump_tasks.clear()
        await self.server_guide_webhook.close()
        await self.cards.close()

    @staticmethod
    async def _reply(ctx: commands.Context, content: str | None = None, **kwargs) -> None:
        if ctx.interaction:
            kwargs.setdefault("ephemeral", True)
        await ctx.send(content, **kwargs)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._voice_seeded:
            return
        self._voice_seeded = True
        self._achievement_scan_day = datetime.now(LOCAL_TZ).date().isoformat()
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                joined_at = int(member.joined_at.timestamp()) if member.joined_at else None
                await self.repository.record_member_join(
                    guild.id,
                    member.id,
                    member.display_name,
                    joined_at,
                )
                await self._evaluate_member(member, announce=False)
            for channel in guild.voice_channels:
                for member in channel.members:
                    if not member.bot:
                        await self.repository.start_voice_session(
                            guild.id,
                            member.id,
                            member.display_name,
                            channel.id,
                        )
            detected = {
                name: getattr(find_text_channel(guild, name), "id", None)
                for name in CHANNELS
            }
            logger.info("community_channels guild_id=%s channels=%s", guild.id, detected)
            for event in guild.scheduled_events:
                await self._sync_scheduled_event(event)
            await self._restore_weekly_view(guild)
            await self._restore_birthday_views(guild)
            await self._ensure_settings_panel(guild)
            identity_changed = await self.server_guide_webhook.sync_identity(guild)
            await self.server_guide_webhook.publish(guild, force_repost=identity_changed)
        logger.info("community_activity_tracking_ready guilds=%s", len(self.bot.guilds))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        joined_at = int(member.joined_at.timestamp()) if member.joined_at else None
        await self.repository.record_member_join(
            member.guild.id,
            member.id,
            member.display_name,
            joined_at,
        )
        await self._evaluate_member(member)
        if not await self._feature_enabled(member.guild.id, "welcome"):
            return
        channel = await self._configured_channel(member.guild, "welcome", "welcome")
        if not channel:
            logger.warning("community_channel_missing guild_id=%s channel=welcome", member.guild.id)
            return
        try:
            card = await self.cards.render_welcome(
                avatar_url=member.display_avatar.url,
                display_name=member.display_name,
                server_name=BRAND_NAME,
                member_count=member.guild.member_count or len(member.guild.members),
            )
            await channel.send(
                content=member.mention,
                embed=welcome_embed(member),
                file=discord.File(io.BytesIO(card), filename="welcome.gif"),
                view=WelcomeView(self.repository, self.cards, member),
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            logger.exception("welcome_send_failed guild_id=%s user_id=%s", member.guild.id, member.id)
        except Exception:
            logger.exception("welcome_card_failed guild_id=%s user_id=%s", member.guild.id, member.id)
            await channel.send(
                content=member.mention,
                embed=welcome_embed(member, has_media=False),
                view=WelcomeView(self.repository, self.cards, member),
                allowed_mentions=discord.AllowedMentions(users=True),
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        profile = await self.repository.get_profile(
            member.guild.id,
            member.id,
            member.display_name,
        )
        await self.repository.record_member_leave(member.guild.id, member.id)
        if not await self._feature_enabled(member.guild.id, "goodbye"):
            return
        channel = await self._configured_channel(member.guild, "goodbye", "member-log")
        if not channel:
            return
        joined = f"<t:{profile.joined_at}:D>" if profile.joined_at else "Không rõ"
        embed = discord.Embed(
            title="👋 Thành viên đã rời server",
            description=f"**{member}** (`{member.id}`)",
            color=0x7DD3FC,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Tham gia", value=joined, inline=True)
        if await self._privacy(member.guild.id, "goodbye", "compact") == "public":
            embed.add_field(name="Tin nhắn ghi nhận", value=f"{profile.message_count:,}", inline=True)
            embed.add_field(name="Voice ghi nhận", value=f"{profile.voice_seconds // 3600} giờ", inline=True)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        try:
            total_messages = await self.repository.increment_message(
                message.guild.id,
                message.author.id,
                message.author.display_name,
                day=datetime.now(LOCAL_TZ).date().isoformat(),
                channel_id=message.channel.id,
                hour=datetime.now(LOCAL_TZ).hour,
            )
            for item in BY_KEY.values():
                if not item.manual and item.metric == "messages" and total_messages == item.threshold:
                    await self._unlock_keys(message.author, [item.key], announce=True)
        except Exception:
            logger.exception(
                "community_message_record_failed guild_id=%s user_id=%s",
                message.guild.id,
                message.author.id,
            )
        if message.channel.id == self.server_guide_webhook.channel_id:
            self._schedule_guide_bump(message.guild.id)

    def _schedule_guide_bump(self, guild_id: int) -> None:
        previous = self._guide_bump_tasks.get(guild_id)
        if previous:
            previous.cancel()

        async def bump() -> None:
            try:
                await asyncio.sleep(self.server_guide_webhook.bump_delay)
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self.server_guide_webhook.publish(guild, force_repost=True)
            except asyncio.CancelledError:
                pass
            finally:
                if self._guide_bump_tasks.get(guild_id) is asyncio.current_task():
                    self._guide_bump_tasks.pop(guild_id, None)

        self._guide_bump_tasks[guild_id] = asyncio.create_task(bump())

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot or before.channel == after.channel:
            return
        now = int(datetime.now(LOCAL_TZ).timestamp())
        try:
            if before.channel:
                await self.repository.end_voice_session(member.guild.id, member.id, ended_at=now)
            if after.channel:
                await self.repository.start_voice_session(
                    member.guild.id,
                    member.id,
                    member.display_name,
                    after.channel.id,
                    started_at=now,
                )
                await self.repository.mark_event_attendance(
                    member.guild.id,
                    member.id,
                    after.channel.id,
                    now,
                )
            await self._evaluate_member(member)
        except Exception:
            logger.exception(
                "community_voice_record_failed guild_id=%s user_id=%s",
                member.guild.id,
                member.id,
            )

    async def _sync_scheduled_event(self, event: discord.ScheduledEvent) -> None:
        await self.repository.upsert_event(
            event.guild_id,
            event.id,
            event.name,
            event.channel_id,
            int(event.start_time.timestamp()),
            int(event.end_time.timestamp()) if event.end_time else None,
            getattr(event.status, "name", str(event.status)),
            event.user_count or 0,
        )

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent) -> None:
        await self._sync_scheduled_event(event)

    @commands.Cog.listener()
    async def on_scheduled_event_update(
        self,
        _before: discord.ScheduledEvent,
        after: discord.ScheduledEvent,
    ) -> None:
        await self._sync_scheduled_event(after)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent) -> None:
        await self._sync_scheduled_event(event)

    @commands.Cog.listener()
    async def on_scheduled_event_user_add(
        self,
        event: discord.ScheduledEvent,
        user: discord.User,
    ) -> None:
        await self._sync_scheduled_event(event)
        await self.repository.set_event_registration(event.guild_id, event.id, user.id, True)

    @commands.Cog.listener()
    async def on_scheduled_event_user_remove(
        self,
        event: discord.ScheduledEvent,
        user: discord.User,
    ) -> None:
        await self.repository.set_event_registration(event.guild_id, event.id, user.id, False)

    @commands.hybrid_command(
        name="hoso",
        aliases=["congdong", "profile"],
        description="Xem hồ sơ KSC Gaming",
    )
    async def community_profile(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        profile = await self.repository.get_profile(
            ctx.guild.id,
            ctx.author.id,
            ctx.author.display_name,
        )
        records = await self.repository.list_achievements(ctx.guild.id, ctx.author.id)
        featured = tuple(
            record.key
            for record in records
            if record.pinned and record.key in BY_KEY
        )
        try:
            card = await render_profile_card(self.cards, ctx.author, profile, featured)
            await self._reply(
                ctx,
                file=discord.File(io.BytesIO(card), filename="community-profile.png"),
            )
        except Exception:
            logger.exception("community_profile_card_failed user_id=%s", ctx.author.id)
            await self._reply(ctx, embed=community_profile_embed(ctx.author, profile))

    @commands.hybrid_command(name="huyhieu", description="Xem bộ sưu tập huy hiệu tự động")
    async def badges(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await achievements_payload(self.repository, ctx.guild.id, ctx.author)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="thanhtich", description="Xem tiến độ thành tựu")
    async def achievements(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await achievements_payload(self.repository, ctx.guild.id, ctx.author)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="traohuyhieu", description="Trao huy hiệu đặc biệt cho thành viên")
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(thanhvien="Thành viên nhận huy hiệu", mahuyhieu="Mã huy hiệu đặc biệt")
    @app_commands.choices(
        mahuyhieu=[
            app_commands.Choice(name=item.title, value=item.key)
            for item in BY_KEY.values()
            if item.manual
        ]
    )
    async def award_badge(
        self,
        ctx: commands.Context,
        thanhvien: discord.Member,
        mahuyhieu: str,
    ) -> None:
        if not ctx.guild or mahuyhieu not in BY_KEY or not BY_KEY[mahuyhieu].manual:
            return
        added = await self.repository.unlock_achievement(ctx.guild.id, thanhvien.id, mahuyhieu)
        if not added:
            await self._reply(ctx, "Thành viên đã có huy hiệu này.")
            return
        item = BY_KEY[mahuyhieu]
        await self._sync_featured(ctx.guild.id, thanhvien.id)
        await self._announce_unlocks(thanhvien, [mahuyhieu])
        await self._reply(ctx, f"Đã trao **{item.title}** cho {thanhvien.mention}.")

    @commands.hybrid_command(name="gioithieu", description="Giới thiệu bản thân với cộng đồng")
    async def introduce(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        if not ctx.interaction:
            await self._reply(ctx, "Hãy dùng lệnh slash `/gioithieu` để mở form giới thiệu.")
            return
        await ctx.interaction.response.send_modal(
            IntroductionModal(
                self.repository,
                self.cards,
                ctx.guild.id,
                ctx.author.id,
                find_text_channel,
            )
        )

    @commands.hybrid_command(name="sinhnhat", description="Xem hoặc thiết lập sinh nhật")
    @app_commands.describe(
        ngay="Ngày sinh (không cần năm)",
        thang="Tháng sinh",
        riengtu="Cách hiển thị sinh nhật",
    )
    @app_commands.choices(
        riengtu=[
            app_commands.Choice(name="Hiện ngày và tháng", value="full"),
            app_commands.Choice(name="Chỉ thông báo đúng ngày", value="day_only"),
            app_commands.Choice(name="Ẩn hoàn toàn", value="hidden"),
        ]
    )
    async def birthday(
        self,
        ctx: commands.Context,
        ngay: app_commands.Range[int, 1, 31] | None = None,
        thang: app_commands.Range[int, 1, 12] | None = None,
        riengtu: str = "full",
    ) -> None:
        if not ctx.guild:
            return
        if ngay is None and thang is None:
            profile = await self.repository.get_profile(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
            )
            if not profile.birthday_day or not profile.birthday_month:
                await self._reply(ctx, "Bạn chưa thiết lập sinh nhật. Dùng `/sinhnhat ngay thang`.")
                return
            mode = {
                "full": "Hiện trong lịch và thông báo",
                "day_only": "Chỉ thông báo đúng ngày",
                "hidden": "Ẩn hoàn toàn",
            }[profile.birthday_visibility]
            await self._reply(
                ctx,
                f"🎂 Sinh nhật: **{profile.birthday_day:02d}/{profile.birthday_month:02d}**\n🔐 {mode}",
            )
            return
        if ngay is None or thang is None:
            await self._reply(ctx, "Bạn cần nhập đủ cả ngày và tháng.")
            return
        try:
            await self.repository.set_birthday(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
                ngay,
                thang,
                riengtu,
            )
        except ValueError:
            await self._reply(ctx, "Ngày hoặc tháng không hợp lệ.")
            return
        await self._reply(ctx, f"Đã lưu sinh nhật **{ngay:02d}/{thang:02d}**.")

    @commands.hybrid_command(name="lichsinhnhat", description="Xem lịch sinh nhật trong tháng")
    @app_commands.describe(thang="Tháng cần xem; bỏ trống để xem tháng hiện tại")
    async def birthday_calendar(
        self,
        ctx: commands.Context,
        thang: app_commands.Range[int, 1, 12] | None = None,
    ) -> None:
        if not ctx.guild:
            return
        month = thang or datetime.now(LOCAL_TZ).month
        entries = await self.repository.list_birthdays(ctx.guild.id, month)
        await self._reply(ctx, embed=birthday_calendar_embed(month, entries))

    @commands.hybrid_command(name="communitysetup", description="Kiểm tra cấu hình Community System")
    @commands.has_guild_permissions(manage_guild=True)
    async def community_setup(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await community_settings_payload(self.repository, ctx.guild)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="communitysettings", description="Mở Community Control Center")
    @commands.has_guild_permissions(manage_guild=True)
    async def community_settings(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        embed, view = await community_settings_payload(self.repository, ctx.guild)
        await self._reply(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="analytics", description="Mở dashboard Community Analytics")
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(ngay="Khoảng thời gian phân tích")
    @app_commands.choices(
        ngay=[
            app_commands.Choice(name="7 ngày", value=7),
            app_commands.Choice(name="30 ngày", value=30),
            app_commands.Choice(name="90 ngày", value=90),
        ]
    )
    async def analytics(self, ctx: commands.Context, ngay: int = 30) -> None:
        if not ctx.guild:
            return
        if ngay not in {7, 30, 90}:
            await self._reply(ctx, "Khoảng thời gian hợp lệ: 7, 30 hoặc 90 ngày.")
            return
        embed, view, card = await analytics_payload(
            self.repository,
            self.cards,
            ctx.guild,
            ctx.author.id,
            days=ngay,
        )
        await self._reply(ctx, embed=embed, view=view, file=card)

    @commands.hybrid_command(name="weekly", description="Xem Weekly Recap mới nhất")
    async def weekly(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        start, end = self._completed_week(datetime.now(LOCAL_TZ).date())
        embed, view, card = await weekly_payload(
            self.repository,
            self.cards,
            ctx.guild,
            start,
            end,
        )
        await self._reply(ctx, embed=embed, view=view, file=card)

    @commands.hybrid_command(name="communitypreview", description="Xem thử giao diện Community")
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(loai="Giao diện cần xem thử")
    @app_commands.choices(
        loai=[
            app_commands.Choice(name="Welcome", value="welcome"),
            app_commands.Choice(name="Birthday", value="birthday"),
            app_commands.Choice(name="Profile", value="profile"),
            app_commands.Choice(name="Introduction", value="introduction"),
        ]
    )
    async def community_preview(self, ctx: commands.Context, loai: str = "welcome") -> None:
        if not ctx.guild:
            return
        avatar_url = ctx.author.display_avatar.url
        if loai == "welcome":
            data = await self.cards.render_welcome(
                avatar_url=avatar_url,
                display_name=ctx.author.display_name,
                server_name=BRAND_NAME,
                member_count=ctx.guild.member_count or len(ctx.guild.members),
            )
            filename = "welcome-preview.gif"
        elif loai == "birthday":
            data = await self.cards.render_birthday(
                avatar_url=avatar_url,
                display_name=ctx.author.display_name,
            )
            filename = "birthday-preview.gif"
        elif loai == "profile":
            profile = await self.repository.get_profile(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
            )
            records = await self.repository.list_achievements(ctx.guild.id, ctx.author.id)
            featured = tuple(
                record.key
                for record in records
                if record.pinned and record.key in BY_KEY
            )
            data = await render_profile_card(self.cards, ctx.author, profile, featured)
            filename = "profile-preview.png"
        else:
            data = await self.cards.render_introduction(
                avatar_url=avatar_url,
                display_name=ctx.author.display_name,
                preferred_name=ctx.author.display_name,
                about="Xin chào mọi người, mình rất vui được trở thành một phần của cộng đồng KSC.",
                interests="Âm nhạc, Gaming, Trò chuyện",
            )
            filename = "introduction-preview.png"
        await self._reply(
            ctx,
            file=discord.File(io.BytesIO(data), filename=filename),
        )

    async def _ensure_settings_panel(self, guild: discord.Guild) -> None:
        channel = find_text_channel(guild, "bot-config")
        if not channel:
            return
        embed, view = await community_settings_payload(self.repository, guild)
        message_id = await self.repository.get_config(guild.id, "settings_message_id")
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.Forbidden, ValueError):
                pass
        message = await channel.send(embed=embed, view=view)
        await self.repository.set_config(guild.id, "settings_message_id", str(message.id))

    async def _restore_birthday_views(self, guild: discord.Guild) -> None:
        birthday_date = datetime.now(LOCAL_TZ).date().isoformat()
        for user_id, message_id in await self.repository.birthday_announcements_on(guild.id, birthday_date):
            member = guild.get_member(user_id)
            if not member:
                continue
            self.bot.add_view(
                BirthdayView(
                    self.repository,
                    guild.id,
                    member.id,
                    member.display_name,
                    member.display_avatar.url,
                    birthday_date,
                ),
                message_id=message_id,
            )

    async def _publish_analytics(self, guild: discord.Guild) -> None:
        if not await self._feature_enabled(guild.id, "analytics"):
            return
        if await self._privacy(guild.id, "analytics", "admin") == "admin":
            return
        channel = await self._configured_channel(guild, "analytics", "community-analytics")
        if not channel:
            return
        snapshot = await self.repository.analytics_snapshot(guild.id, days=30)
        card = await self.cards.render_analytics(snapshot=snapshot, server_name=BRAND_NAME)
        embed = analytics_embed(snapshot, guild)
        file = discord.File(io.BytesIO(card), filename="analytics.png")
        message_id = await self.repository.get_config(guild.id, "analytics_message_id")
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed, attachments=[file])
                return
            except (discord.NotFound, discord.Forbidden, ValueError):
                pass
        message = await channel.send(embed=embed, file=file)
        await self.repository.set_config(guild.id, "analytics_message_id", str(message.id))

    @staticmethod
    def _completed_week(today: date) -> tuple[date, date]:
        current_week_start = today - timedelta(days=today.weekday())
        end = current_week_start - timedelta(days=1)
        return end - timedelta(days=6), end

    async def _restore_weekly_view(self, guild: discord.Guild) -> None:
        period = await self.repository.get_config(guild.id, "weekly_last_period")
        message_id = await self.repository.get_config(guild.id, "weekly_message_id")
        if not period or not message_id:
            return
        try:
            start_text, end_text = period.split(":", 1)
            snapshot = await self.repository.weekly_snapshot(
                guild.id,
                date.fromisoformat(start_text),
                date.fromisoformat(end_text),
            )
            self.bot.add_view(WeeklyRecapView(snapshot, guild), message_id=int(message_id))
        except (ValueError, TypeError):
            logger.warning("weekly_view_restore_invalid guild_id=%s period=%s", guild.id, period)

    async def _publish_weekly(self, guild: discord.Guild, start: date, end: date) -> None:
        period_key = f"{start.isoformat()}:{end.isoformat()}"
        if await self.repository.get_config(guild.id, "weekly_last_period") == period_key:
            return
        if not await self._feature_enabled(guild.id, "weekly"):
            return
        if await self._privacy(guild.id, "weekly", "public") == "admin":
            return
        channel = await self._configured_channel(guild, "weekly", "weekly-recap")
        if not channel:
            return
        embed, view, card = await weekly_payload(
            self.repository,
            self.cards,
            guild,
            start,
            end,
        )
        message = await channel.send(embed=embed, view=view, file=card)
        await self.repository.set_config(guild.id, "weekly_last_period", period_key)
        await self.repository.set_config(guild.id, "weekly_message_id", str(message.id))

    @tasks.loop(hours=1)
    async def analytics_scheduler(self) -> None:
        now = datetime.now(LOCAL_TZ)
        today = now.date().isoformat()
        if now.hour < 8 or self._analytics_day == today:
            return
        for guild in self.bot.guilds:
            try:
                await self._publish_analytics(guild)
            except Exception:
                logger.exception("analytics_publish_failed guild_id=%s", guild.id)
        self._analytics_day = today
        logger.info("analytics_publish_complete date=%s", today)

    @tasks.loop(hours=1)
    async def weekly_scheduler(self) -> None:
        now = datetime.now(LOCAL_TZ)
        today = now.date().isoformat()
        if now.hour < 9 or self._weekly_checked_day == today:
            return
        start, end = self._completed_week(now.date())
        for guild in self.bot.guilds:
            try:
                await self._publish_weekly(guild, start, end)
            except Exception:
                logger.exception("weekly_publish_failed guild_id=%s", guild.id)
        self._weekly_checked_day = today
        logger.info("weekly_publish_check_complete period=%s:%s", start, end)

    @tasks.loop(hours=1)
    async def achievement_scheduler(self) -> None:
        today = datetime.now(LOCAL_TZ).date().isoformat()
        if self._achievement_scan_day == today:
            return
        self._achievement_scan_day = today
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                try:
                    await self._evaluate_member(member, announce=True)
                except Exception:
                    logger.exception(
                        "daily_achievement_scan_failed guild_id=%s user_id=%s",
                        guild.id,
                        member.id,
                    )
        logger.info("daily_achievement_scan_complete date=%s", today)

    @tasks.loop(minutes=30)
    async def birthday_scheduler(self) -> None:
        now = datetime.now(LOCAL_TZ)
        if now.hour < 8:
            return
        birthday_date = now.date().isoformat()
        for guild in self.bot.guilds:
            if not await self._feature_enabled(guild.id, "birthday"):
                continue
            if await self._privacy(guild.id, "birthday", "public") == "admin":
                continue
            birthday_privacy = await self._privacy(guild.id, "birthday", "public")
            channel = await self._configured_channel(guild, "birthday", "celebrations")
            if not channel:
                continue
            entries = await self.repository.birthdays_on(guild.id, now.day, now.month)
            for entry in entries:
                member = guild.get_member(entry.user_id)
                if not member:
                    continue
                claimed = await self.repository.claim_birthday_announcement(
                    guild.id,
                    member.id,
                    birthday_date,
                )
                if not claimed:
                    continue
                view = BirthdayView(
                    self.repository,
                    guild.id,
                    member.id,
                    member.display_name,
                    member.display_avatar.url,
                    birthday_date,
                )
                if birthday_privacy == "compact":
                    view.has_media = False
                    message = await channel.send(
                        content=member.mention,
                        embed=view.embed(),
                        view=view,
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
                    await self.repository.set_birthday_message(
                        guild.id,
                        member.id,
                        birthday_date,
                        message.id,
                    )
                    continue
                try:
                    card = await self.cards.render_birthday(
                        avatar_url=member.display_avatar.url,
                        display_name=member.display_name,
                    )
                    message = await channel.send(
                        content=member.mention,
                        embed=view.embed(),
                        file=discord.File(io.BytesIO(card), filename="birthday.gif"),
                        view=view,
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
                except Exception:
                    logger.exception(
                        "birthday_card_failed guild_id=%s user_id=%s",
                        guild.id,
                        member.id,
                    )
                    view.has_media = False
                    message = await channel.send(
                        content=member.mention,
                        embed=view.embed(),
                        view=view,
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
                await self.repository.set_birthday_message(
                    guild.id,
                    member.id,
                    birthday_date,
                    message.id,
                )

    @birthday_scheduler.before_loop
    async def before_birthday_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)

    @achievement_scheduler.before_loop
    async def before_achievement_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    @analytics_scheduler.before_loop
    async def before_analytics_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(15)

    @weekly_scheduler.before_loop
    async def before_weekly_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(20)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Community(bot))
