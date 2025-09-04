import discord
from discord.ext import commands
import os
import psutil
import time
from datetime import datetime

class UtilsCommands(commands.Cog):
    """⚙️ Tiện ích - Các lệnh tiện ích và thông tin bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Kiểm tra độ trễ của bot"""
        start_time = time.time()
        message = await ctx.send("🏓 Đang ping...")
        
        end_time = time.time()
        api_latency = (end_time - start_time) * 1000
        websocket_latency = self.bot.latency * 1000
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=0x7289DA
        )
        embed.add_field(name="📡 API Latency", value=f"{api_latency:.2f}ms", inline=True)
        embed.add_field(name="💓 WebSocket Latency", value=f"{websocket_latency:.2f}ms", inline=True)
        
        # Color based on latency
        avg_latency = (api_latency + websocket_latency) / 2
        if avg_latency < 100:
            embed.color = 0x00FF00  # Green
        elif avg_latency < 300:
            embed.color = 0xFFFF00  # Yellow
        else:
            embed.color = 0xFF0000  # Red
        
        await message.edit(content="", embed=embed)
    
    @commands.command(name='uptime', aliases=['runtime'])
    async def uptime(self, ctx):
        """Xem thời gian bot đã chạy"""
        current_time = time.time()
        uptime_seconds = int(current_time - self.start_time)
        
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_string = ""
        if days > 0:
            uptime_string += f"{days} ngày, "
        if hours > 0:
            uptime_string += f"{hours} giờ, "
        if minutes > 0:
            uptime_string += f"{minutes} phút, "
        uptime_string += f"{seconds} giây"
        
        embed = discord.Embed(
            title="⏰ Thời gian hoạt động",
            description=f"Bot đã chạy được: **{uptime_string}**",
            color=0x7289DA
        )
        embed.add_field(name="🚀 Khởi động lúc", value=f"<t:{int(self.start_time)}:F>", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='stats', aliases=['botinfo'])
    async def stats_command(self, ctx):
        """Hiển thị thống kê bot"""
        # Get system info
        memory_usage = psutil.virtual_memory()
        cpu_usage = psutil.cpu_percent()
        
        embed = discord.Embed(
            title="📊 Thống kê GenZ Assistant",
            color=0x7289DA
        )
        
        # Bot info
        embed.add_field(name="🤖 Bot", value=f"{self.bot.user.name}#{self.bot.user.discriminator}", inline=True)
        embed.add_field(name="🆔 ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="📅 Tạo lúc", value=f"<t:{int(self.bot.user.created_at.timestamp())}:d>", inline=True)
        
        # Server stats
        embed.add_field(name="🏠 Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="👥 Users", value=len(self.bot.users), inline=True)
        embed.add_field(name="💬 Channels", value=len(list(self.bot.get_all_channels())), inline=True)
        
        # System stats
        embed.add_field(name="💾 RAM", value=f"{memory_usage.percent}%", inline=True)
        embed.add_field(name="🖥️ CPU", value=f"{cpu_usage}%", inline=True)
        embed.add_field(name="🐍 Python", value=f"{psutil.python_version()}", inline=True)
        
        # Uptime
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        uptime_str = f"{days}d {hours}h {minutes}m"
        embed.add_field(name="⏰ Uptime", value=uptime_str, inline=True)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="GenZ Assistant • Made with ❤️")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='invite', aliases=['link'])
    async def invite_link(self, ctx):
        """Lấy link mời bot"""
        permissions = discord.Permissions(
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            add_reactions=True,
            manage_messages=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            manage_channels=True,
            moderate_members=True
        )
        
        invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=permissions)
        
        embed = discord.Embed(
            title="🔗 Mời GenZ Assistant",
            description="Thêm bot vào server của bạn!",
            color=0x7289DA
        )
        embed.add_field(
            name="📎 Link mời",
            value=f"[Nhấn vào đây để mời bot]({invite_url})",
            inline=False
        )
        embed.add_field(
            name="⚠️ Quyền cần thiết",
            value="Bot cần các quyền cơ bản để hoạt động tốt nhất:\n"
                  "• Đọc/Gửi tin nhắn\n"
                  "• Nhúng liên kết\n"
                  "• Quản lý tin nhắn\n"
                  "• Kick/Ban thành viên (cho admin)\n"
                  "• Timeout thành viên",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='support', aliases=['help_server'])
    async def support_server(self, ctx):
        """Thông tin hỗ trợ"""
        embed = discord.Embed(
            title="🆘 Cần hỗ trợ?",
            description="Dưới đây là các cách để nhận hỗ trợ về GenZ Assistant",
            color=0x7289DA
        )
        
        embed.add_field(
            name="📖 Hướng dẫn",
            value=f"Sử dụng `{self.bot.config['prefix']}help` để xem tất cả lệnh",
            inline=False
        )
        
        embed.add_field(
            name="🐛 Báo lỗi",
            value="Liên hệ admin server hoặc developer",
            inline=False
        )
        
        embed.add_field(
            name="💡 Góp ý",
            value="Chúng tôi luôn chào đón ý kiến đóng góp!",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='version', aliases=['ver'])
    async def version_info(self, ctx):
        """Thông tin phiên bản bot"""
        embed = discord.Embed(
            title="📋 Thông tin phiên bản",
            color=0x7289DA
        )
        
        embed.add_field(name="🤖 Bot Version", value="1.0.0", inline=True)
        embed.add_field(name="📚 Discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="🐍 Python", value=f"{psutil.python_version()}", inline=True)
        
        embed.add_field(
            name="🆕 Tính năng mới",
            value="• Hệ thống XP và leveling\n"
                  "• Tích hợp AI ChatGPT\n"
                  "• Mini games tương tác\n"
                  "• Hệ thống nhắc nhở\n"
                  "• Quản lý todo list",
            inline=False
        )
        
        embed.set_footer(text="GenZ Assistant • Cập nhật thường xuyên")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='userinfo', aliases=['ui'])
    async def user_info(self, ctx, user: discord.Member = None):
        """Xem thông tin của một người dùng"""
        target_user = user or ctx.author
        
        embed = discord.Embed(
            title=f"👤 Thông tin: {target_user.display_name}",
            color=target_user.color if target_user.color != discord.Color.default() else 0x7289DA
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(name="📛 Tên", value=f"{target_user.name}#{target_user.discriminator}", inline=True)
        embed.add_field(name="🆔 ID", value=target_user.id, inline=True)
        embed.add_field(name="🤖 Bot", value="Có" if target_user.bot else "Không", inline=True)
        
        embed.add_field(name="📅 Tham gia Discord", value=f"<t:{int(target_user.created_at.timestamp())}:d>", inline=True)
        embed.add_field(name="📅 Tham gia server", value=f"<t:{int(target_user.joined_at.timestamp())}:d>", inline=True)
        
        # Roles
        roles = [role.mention for role in target_user.roles[1:]]  # Skip @everyone
        if roles:
            roles_text = ", ".join(roles) if len(roles) <= 10 else f"{', '.join(roles[:10])}... và {len(roles) - 10} role khác"
            embed.add_field(name="🎭 Roles", value=roles_text, inline=False)
        
        # Permissions
        if target_user.guild_permissions.administrator:
            embed.add_field(name="⚡ Quyền đặc biệt", value="Administrator", inline=True)
        elif target_user.guild_permissions.manage_guild:
            embed.add_field(name="⚡ Quyền đặc biệt", value="Manage Server", inline=True)
        elif target_user.guild_permissions.manage_messages:
            embed.add_field(name="⚡ Quyền đặc biệt", value="Moderator", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='avatar', aliases=['av'])
    async def avatar(self, ctx, user: discord.Member = None):
        """Xem avatar của người dùng"""
        target_user = user or ctx.author
        
        embed = discord.Embed(
            title=f"🖼️ Avatar của {target_user.display_name}",
            color=0x7289DA
        )
        
        embed.set_image(url=target_user.display_avatar.url)
        embed.add_field(
            name="🔗 Links",
            value=f"[PNG]({target_user.display_avatar.with_format('png').url}) | "
                  f"[JPG]({target_user.display_avatar.with_format('jpg').url}) | "
                  f"[WEBP]({target_user.display_avatar.with_format('webp').url})",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UtilsCommands(bot))
