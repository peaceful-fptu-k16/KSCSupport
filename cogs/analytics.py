import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

class SimpleAnalyticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cache = {}  # Simple in-memory cache
        
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track messages"""
        if message.author.bot:
            return
            
        # Simple tracking
        guild_id = message.guild.id if message.guild else 0
        user_id = message.author.id
        today = datetime.now().strftime("%Y-%m-%d")
        
        key = f"{guild_id}_{user_id}_{today}"
        self.message_cache[key] = self.message_cache.get(key, 0) + 1
    
    @commands.command(name="serverstats")
    async def server_stats(self, ctx):
        """Hiển thị thống kê server đơn giản"""
        guild = ctx.guild
        
        embed = discord.Embed(title=f"📊 Thống kê Server: {guild.name}", color=discord.Color.blue())
        
        # Basic server info
        embed.add_field(name="👥 Thành viên", value=f"{guild.member_count}", inline=True)
        embed.add_field(name="📝 Kênh", value=f"{len(guild.channels)}", inline=True)
        embed.add_field(name="🎭 Roles", value=f"{len(guild.roles)}", inline=True)
        
        # Online members
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
        embed.add_field(name="🟢 Online", value=f"{online_members}", inline=True)
        
        # Bot count
        bots = sum(1 for member in guild.members if member.bot)
        embed.add_field(name="🤖 Bots", value=f"{bots}", inline=True)
        
        # Server creation date
        created_days = (datetime.now() - guild.created_at.replace(tzinfo=None)).days
        embed.add_field(name="🎂 Tuổi server", value=f"{created_days} ngày", inline=True)
        
        # Today's messages (from cache)
        today = datetime.now().strftime("%Y-%m-%d")
        today_messages = sum(count for key, count in self.message_cache.items() 
                           if key.startswith(f"{guild.id}_") and key.endswith(f"_{today}"))
        embed.add_field(name="💬 Tin nhắn hôm nay", value=f"{today_messages}", inline=True)
        
        # Most active user today
        today_users = {}
        for key, count in self.message_cache.items():
            if key.startswith(f"{guild.id}_") and key.endswith(f"_{today}"):
                user_id = int(key.split("_")[1])
                today_users[user_id] = today_users.get(user_id, 0) + count
        
        if today_users:
            most_active_id = max(today_users, key=today_users.get)
            most_active_user = guild.get_member(most_active_id)
            if most_active_user:
                embed.add_field(
                    name="🏆 Hoạt động nhất hôm nay", 
                    value=f"{most_active_user.mention} ({today_users[most_active_id]} tin nhắn)", 
                    inline=False
                )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"ID: {guild.id}")
        await ctx.send(embed=embed)
    
    @commands.command(name="userstats")
    async def user_stats(self, ctx, member: discord.Member = None):
        """Thống kê user"""
        if not member:
            member = ctx.author
        
        embed = discord.Embed(title=f"📊 Thống kê: {member.display_name}", color=member.color)
        
        # Basic info
        embed.add_field(name="👤 Username", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="🆔 ID", value=f"{member.id}", inline=True)
        embed.add_field(name="📅 Tham gia Discord", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="📅 Tham gia server", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="🎭 Roles", value=f"{len(member.roles)-1}", inline=True)  # -1 để loại bỏ @everyone
        embed.add_field(name="🔝 Highest role", value=member.top_role.mention, inline=True)
        
        # Messages today from cache
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{ctx.guild.id}_{member.id}_{today}"
        messages_today = self.message_cache.get(key, 0)
        embed.add_field(name="💬 Tin nhắn hôm nay", value=f"{messages_today}", inline=True)
        
        # Status
        status_emoji = {
            discord.Status.online: "🟢",
            discord.Status.idle: "🟡", 
            discord.Status.dnd: "🔴",
            discord.Status.offline: "⚫"
        }
        embed.add_field(name="📶 Status", value=f"{status_emoji.get(member.status, '❓')} {member.status}", inline=True)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="topmessages")
    async def top_messages(self, ctx):
        """Top users tin nhắn hôm nay"""
        today = datetime.now().strftime("%Y-%m-%d")
        guild_id = ctx.guild.id
        
        # Collect today's stats
        today_stats = {}
        for key, count in self.message_cache.items():
            if key.startswith(f"{guild_id}_") and key.endswith(f"_{today}"):
                user_id = int(key.split("_")[1])
                today_stats[user_id] = today_stats.get(user_id, 0) + count
        
        if not today_stats:
            await ctx.send("📭 Chưa có ai nhắn tin hôm nay!")
            return
        
        # Sort by message count
        sorted_stats = sorted(today_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        embed = discord.Embed(title="🏆 Top 10 tin nhắn hôm nay", color=discord.Color.gold())
        
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for i, (user_id, count) in enumerate(sorted_stats):
            user = ctx.guild.get_member(user_id)
            if user:
                embed.add_field(
                    name=f"{medals[i]} #{i+1}",
                    value=f"{user.mention}: {count} tin nhắn",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="clearcache")
    @commands.has_permissions(manage_guild=True)
    async def clear_cache(self, ctx):
        """Xóa cache thống kê (Admin only)"""
        self.message_cache.clear()
        await ctx.send("✅ Đã xóa cache thống kê!")

async def setup(bot):
    await bot.add_cog(SimpleAnalyticsCog(bot))
