import discord
from discord.ext import commands
import asyncio
import os
from typing import Optional, Union
from utils.channel_manager import ChannelManager

class Admin(commands.Cog):
    """🛠️ Quản trị viên & Server Tools"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def is_admin():
        """Check if user has admin permissions"""
        def predicate(ctx):
            return ctx.author.guild_permissions.administrator or ctx.author.id == int(os.getenv('DISCORD_OWNER_ID', 0))
        return commands.check(predicate)
    
    def is_mod():
        """Check if user has moderator permissions"""
        def predicate(ctx):
            return (ctx.author.guild_permissions.manage_messages or 
                   ctx.author.guild_permissions.administrator or 
                   ctx.author.id == int(os.getenv('DISCORD_OWNER_ID', 0)))
        return commands.check(predicate)
    
    @ChannelManager.bot_only()
    @commands.command(name='clear', aliases=['purge', 'xoa'])
    @is_mod()
    async def clear_messages(self, ctx, amount: int = 10):
        """Xóa số lượng tin nhắn nhất định"""
        if amount < 1 or amount > 100:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Số lượng tin nhắn phải từ 1 đến 100!",
                color=0xFF0000
            )
            await ctx.send(embed=embed, delete_after=5)
            return
        
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 để xóa cả lệnh
            
            embed = discord.Embed(
                title="🗑️ Đã xóa tin nhắn",
                description=f"Đã xóa {len(deleted) - 1} tin nhắn",
                color=0x00FF00
            )
            embed.set_footer(text=f"Thực hiện bởi {ctx.author.display_name}")
            
            await ctx.send(embed=embed, delete_after=5)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền xóa tin nhắn trong kênh này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed, delete_after=5)
    
    @commands.command(name='ban', aliases=['cam'])
    @is_admin()
    async def ban_user(self, ctx, user: discord.Member = None, *, reason: str = "Không có lý do"):
        """Cấm thành viên"""
        if not user:
            embed = discord.Embed(
                title="❌ Thiếu thông tin",
                description=f"Sử dụng: `{self.bot.config['prefix']}ban @user [lý do]`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bạn không thể ban người có quyền cao hơn hoặc bằng bạn!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if user == ctx.author:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Bạn không thể ban chính mình!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Send DM to user before banning
            try:
                dm_embed = discord.Embed(
                    title="🔨 Bạn đã bị ban",
                    description=f"Bạn đã bị ban khỏi server **{ctx.guild.name}**",
                    color=0xFF0000
                )
                dm_embed.add_field(name="Lý do", value=reason, inline=False)
                dm_embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            
            await ctx.guild.ban(user, reason=reason)
            
            embed = discord.Embed(
                title="🔨 Đã ban thành viên",
                description=f"{user.mention} đã bị ban",
                color=0xFF0000
            )
            embed.add_field(name="Lý do", value=reason, inline=False)
            embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền ban thành viên này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='unban', aliases=['unbancam'])
    @is_admin()
    async def unban_user(self, ctx, *, user_info: str = None):
        """Bỏ ban thành viên"""
        if not user_info:
            embed = discord.Embed(
                title="❌ Thiếu thông tin",
                description=f"Sử dụng: `{self.bot.config['prefix']}unban <UserID hoặc Username#1234>`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        banned_users = [entry.user async for entry in ctx.guild.bans()]
        
        # Try to find user by ID first
        if user_info.isdigit():
            user = discord.utils.get(banned_users, id=int(user_info))
        else:
            # Try to find by username#discriminator
            user = discord.utils.get(banned_users, name=user_info.split('#')[0])
        
        if not user:
            embed = discord.Embed(
                title="❌ Không tìm thấy",
                description="Không tìm thấy người dùng bị ban với thông tin này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await ctx.guild.unban(user)
            
            embed = discord.Embed(
                title="✅ Đã bỏ ban",
                description=f"{user.mention} ({user.name}) đã được bỏ ban",
                color=0x00FF00
            )
            embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền bỏ ban!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='mute', aliases=['im'])
    @is_mod()
    async def mute_user(self, ctx, user: discord.Member = None, duration: str = "10m", *, reason: str = "Không có lý do"):
        """Im lặng thành viên trong thời gian nhất định"""
        if not user:
            embed = discord.Embed(
                title="❌ Thiếu thông tin",
                description=f"Sử dụng: `{self.bot.config['prefix']}mute @user [thời gian] [lý do]`\n"
                           f"Ví dụ: `{self.bot.config['prefix']}mute @user 10m spam`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse duration
        try:
            if duration.endswith('s'):
                seconds = int(duration[:-1])
            elif duration.endswith('m'):
                seconds = int(duration[:-1]) * 60
            elif duration.endswith('h'):
                seconds = int(duration[:-1]) * 3600
            elif duration.endswith('d'):
                seconds = int(duration[:-1]) * 86400
            else:
                seconds = int(duration) * 60  # Default to minutes
        except ValueError:
            embed = discord.Embed(
                title="❌ Lỗi định dạng",
                description="Định dạng thời gian không hợp lệ! Sử dụng: 10s, 5m, 2h, 1d",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if seconds > 2419200:  # Max 28 days
            embed = discord.Embed(
                title="❌ Thời gian quá dài",
                description="Thời gian mute tối đa là 28 ngày!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            timeout_until = discord.utils.utcnow() + discord.utils.timedelta(seconds=seconds)
            await user.timeout(timeout_until, reason=reason)
            
            embed = discord.Embed(
                title="🔇 Đã mute thành viên",
                description=f"{user.mention} đã bị mute {duration}",
                color=0xFF0000
            )
            embed.add_field(name="Lý do", value=reason, inline=False)
            embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền mute thành viên này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='unmute', aliases=['unmuteuser'])
    @is_mod()
    async def unmute_user(self, ctx, user: discord.Member = None):
        """Bỏ mute thành viên"""
        if not user:
            embed = discord.Embed(
                title="❌ Thiếu thông tin",
                description=f"Sử dụng: `{self.bot.config['prefix']}unmute @user`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await user.timeout(None)
            
            embed = discord.Embed(
                title="🔊 Đã unmute thành viên",
                description=f"{user.mention} đã được unmute",
                color=0x00FF00
            )
            embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền unmute thành viên này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='slowmode', aliases=['slow'])
    @is_mod()
    async def set_slowmode(self, ctx, seconds: int = 0):
        """Bật/tắt chế độ chậm tin nhắn"""
        if seconds < 0 or seconds > 21600:  # Max 6 hours
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Thời gian slowmode phải từ 0 đến 21600 giây (6 giờ)!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await ctx.channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                embed = discord.Embed(
                    title="✅ Đã tắt slowmode",
                    description="Chế độ chậm tin nhắn đã được tắt",
                    color=0x00FF00
                )
            else:
                embed = discord.Embed(
                    title="⏰ Đã bật slowmode",
                    description=f"Chế độ chậm tin nhắn: {seconds} giây",
                    color=0x7289DA
                )
            
            embed.add_field(name="Bởi", value=ctx.author.mention, inline=False)
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bot không có quyền chỉnh sửa kênh này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='serverinfo', aliases=['server'])
    async def server_info(self, ctx):
        """Hiển thị thông tin server"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"📊 Thông tin server: {guild.name}",
            color=0x7289DA
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="📅 Ngày tạo", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="👥 Thành viên", value=guild.member_count, inline=True)
        embed.add_field(name="💬 Kênh văn bản", value=len(guild.text_channels), inline=True)
        embed.add_field(name="🔊 Kênh voice", value=len(guild.voice_channels), inline=True)
        embed.add_field(name="📁 Danh mục", value=len(guild.categories), inline=True)
        embed.add_field(name="😀 Emoji", value=len(guild.emojis), inline=True)
        embed.add_field(name="🎭 Role", value=len(guild.roles), inline=True)
        embed.add_field(name="🚀 Boost Level", value=guild.premium_tier, inline=True)
        
        if guild.description:
            embed.add_field(name="📝 Mô tả", value=guild.description, inline=False)
        
        embed.set_footer(text=f"Server ID: {guild.id}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
