import discord # type: ignore
from discord.ext import commands # type: ignore
import asyncio
import random
from datetime import datetime

class Events(commands.Cog):
    """🎉 Events - Chào mừng & tạm biệt thành viên"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Welcome messages
        self.welcome_messages = [
            "Chào mừng {user} đã gia nhập {server}! 🎉",
            "Xin chào {user}! Chúc bạn có những trải nghiệm tuyệt vời tại {server}! ✨",
            "Một thành viên mới đã xuất hiện! Chào mừng {user}! 🌟",
            "Hey {user}! Cảm ơn bạn đã tham gia {server}! 🚀",
            "Welcome aboard {user}! Hãy tận hưởng thời gian ở {server} nhé! 🎊",
            "Chào {user}! Hy vọng bạn sẽ thích {server}! 💖",
            "Look who just joined {server}! Chào mừng {user}! 🎈",
            "Xin chào {user}! Bạn là thành viên thứ {member_count} của {server}! 🏆"
        ]
        
        # Goodbye messages
        self.goodbye_messages = [
            "Tạm biệt {user}! Cảm ơn bạn đã là một phần của {server}! 👋",
            "{user} đã rời khỏi {server}. Chúc bạn mọi điều tốt đẹp! 🌈",
            "Goodbye {user}! Chúng tôi sẽ nhớ bạn! 💔",
            "See you later {user}! Cửa {server} luôn mở chào đón bạn trở lại! 🚪",
            "{user} đã bay đi! Tạm biệt và hẹn gặp lại! 🕊️",
            "Farewell {user}! Chúc bạn có một hành trình tuyệt vời! ⭐",
            "{user} rời khỏi {server}. Hy vọng sẽ gặp lại bạn sớm! 🌸",
            "Tạm biệt {user}! Bạn luôn được chào đón tại {server}! 💙"
        ]
        
        # Welcome channel - chỉ tìm channel có tên chính xác
        self.welcome_channel_name = '👋・welcome'

    def get_welcome_channel(self, guild):
        """Tìm channel welcome - chỉ channel có tên '👋・welcome'"""
        # Chỉ tìm channel có tên chính xác là "👋・welcome"
        channel = discord.utils.get(guild.text_channels, name=self.welcome_channel_name)
        return channel

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Event khi có thành viên mới join server"""
        try:
            guild = member.guild
            channel = self.get_welcome_channel(guild)
            
            if not channel:
                return
            
            # Chọn message ngẫu nhiên
            welcome_msg = random.choice(self.welcome_messages)
            
            # Format message
            formatted_msg = welcome_msg.format(
                user=member.mention,
                server=guild.name,
                member_count=guild.member_count
            )
            
            # Tạo embed welcome
            embed = discord.Embed(
                title="🎉 Thành viên mới!",
                description=formatted_msg,
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            # Thêm avatar của user
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Thêm thông tin thành viên
            embed.add_field(
                name="👤 Thông tin thành viên",
                value=f"**Tên:** {member.display_name}\n**ID:** {member.id}\n**Tài khoản tạo:** {member.created_at.strftime('%d/%m/%Y')}",
                inline=True
            )
            
            embed.add_field(
                name="📊 Thống kê server",
                value=f"**Tổng thành viên:** {guild.member_count}\n**Server:** {guild.name}\n**Bạn là thành viên thứ:** #{guild.member_count}",
                inline=True
            )
            
            # Thêm hướng dẫn
            embed.add_field(
                name="💡 Hướng dẫn",
                value="• Đọc quy tắc server\n• Giới thiệu bản thân\n• Gõ `!help` để xem các lệnh\n• Tham gia các cuộc trò chuyện!",
                inline=False
            )
            
            embed.set_footer(
                text=f"ID: {member.id} • Joined",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            await channel.send(embed=embed)
            
            # Gửi DM welcome cho user (tùy chọn)
            try:
                dm_embed = discord.Embed(
                    title=f"🎉 Chào mừng đến với {guild.name}!",
                    description=f"Xin chào {member.mention}!\n\nCảm ơn bạn đã tham gia **{guild.name}**! Chúng tôi rất vui được chào đón bạn.",
                    color=0x7289DA
                )
                
                dm_embed.add_field(
                    name="🎮 Bắt đầu với GenZ Assistant",
                    value="• Gõ `!help` để xem tất cả lệnh\n• Thử `!meme` để xem meme vui\n• Dùng `!play <bài hát>` để nghe nhạc\n• Chat với AI bằng `!ask <câu hỏi>`",
                    inline=False
                )
                
                dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                dm_embed.set_footer(text=f"Chúc bạn có trải nghiệm tuyệt vời tại {guild.name}!")
                
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                # User có thể đã tắt DM
                pass
                
        except Exception as e:
            print(f"Error in welcome event: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Event khi thành viên rời server"""
        try:
            # Check if member is None
            if not member:
                print("Error in goodbye event: member is None")
                return
                
            guild = member.guild
            if not guild:
                print("Error in goodbye event: guild is None")
                return
                
            channel = self.get_welcome_channel(guild)
            
            if not channel:
                return
            
            # Chọn message ngẫu nhiên
            goodbye_msg = random.choice(self.goodbye_messages)
            
            # Format message
            formatted_msg = goodbye_msg.format(
                user=member.display_name,
                server=guild.name
            )
            
            # Tạo embed goodbye
            embed = discord.Embed(
                title="👋 Thành viên đã rời",
                description=formatted_msg,
                color=0xff9900,
                timestamp=datetime.utcnow()
            )
            
            # Thêm avatar của user
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Thêm thông tin
            join_date = "Không xác định"
            if hasattr(member, 'joined_at') and member.joined_at:
                join_date = member.joined_at.strftime('%d/%m/%Y')
            
            embed.add_field(
                name="👤 Thông tin thành viên",
                value=f"**Tên:** {member.display_name}\n**ID:** {member.id}\n**Joined:** {join_date}",
                inline=True
            )
            
            embed.add_field(
                name="📊 Thống kê server",
                value=f"**Thành viên còn lại:** {guild.member_count}\n**Server:** {guild.name}",
                inline=True
            )
            
            embed.set_footer(
                text=f"ID: {member.id} • Left",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error in goodbye event: {e}")

    @commands.command(name='setwelcome', aliases=['setup-welcome'])
    @commands.has_permissions(manage_guild=True)
    async def set_welcome_channel(self, ctx, channel: discord.TextChannel = None):
        """Thiết lập channel welcome (chỉ admin)"""
        if not channel:
            channel = ctx.channel
        
        # Lưu vào database hoặc config (tạm thời dùng memory)
        if not hasattr(self.bot, 'welcome_channels'):
            self.bot.welcome_channels = {}
        
        self.bot.welcome_channels[ctx.guild.id] = channel.id
        
        embed = discord.Embed(
            title="✅ Đã thiết lập kênh welcome!",
            description=f"Channel welcome đã được thiết lập thành {channel.mention}",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📝 Lưu ý",
            value="• Bot sẽ gửi tin nhắn chào mừng khi có thành viên mới\n• Bot sẽ gửi tin nhắn tạm biệt khi thành viên rời đi\n• Đảm bảo bot có quyền gửi tin nhắn trong channel này",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.command(name='welcomestats', aliases=['wstats'])
    async def welcome_stats(self, ctx):
        """Hiển thị thống kê welcome"""
        guild = ctx.guild
        
        # Đếm thành viên mới trong 24h
        now = datetime.utcnow()
        new_members_today = 0
        
        for member in guild.members:
            if member.joined_at and (now - member.joined_at).days < 1:
                new_members_today += 1
        
        embed = discord.Embed(
            title="📊 Thống kê Welcome",
            color=0x7289DA
        )
        
        embed.add_field(
            name="👥 Thành viên",
            value=f"**Tổng:** {guild.member_count}\n**Mới hôm nay:** {new_members_today}\n**Online:** {len([m for m in guild.members if m.status != discord.Status.offline])}",
            inline=True
        )
        
        embed.add_field(
            name="🏠 Server",
            value=f"**Tên:** {guild.name}\n**Tạo:** {guild.created_at.strftime('%d/%m/%Y')}\n**Owner:** {guild.owner.mention if guild.owner else 'N/A'}",
            inline=True
        )
        
        # Channel welcome hiện tại
        welcome_channel = self.get_welcome_channel(guild)
        embed.add_field(
            name="📺 Welcome Channel",
            value=welcome_channel.mention if welcome_channel else "Chưa thiết lập",
            inline=False
        )
        
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"Server ID: {guild.id}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Events(bot))
