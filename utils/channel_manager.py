import discord
from discord.ext import commands
import functools

class ChannelManager:
    """Quản lý các hạn chế kênh cho bot"""
    
    CHANNEL_CONFIG = {
        'welcome': '👋・welcome',    # Kênh welcome messages
        'music': '🎶・music',       # Kênh music commands  
        'bot': '🤖・bot',          # Kênh bot commands khác
    }
    
    MUSIC_COMMANDS = [
        'play', 'pause', 'stop', 'skip', 'queue', 'nowplaying', 'volume',
        'shuffle', 'repeat', 'clear', 'remove', 'move', 'jump', 'seek',
        'lyrics', 'soundcloud', 'sc', 'universal', 'mix'
    ]
    
    @staticmethod
    def get_required_channel(command_name: str) -> str:
        """Lấy tên kênh yêu cầu cho command"""
        if command_name.lower() in ChannelManager.MUSIC_COMMANDS:
            return ChannelManager.CHANNEL_CONFIG['music']
        return ChannelManager.CHANNEL_CONFIG['bot']
    
    @staticmethod
    def is_correct_channel(ctx, required_channel: str) -> bool:
        """Kiểm tra xem command có được chạy trong đúng kênh không"""
        return ctx.channel.name == required_channel
    
    @staticmethod
    def channel_only(channel_name: str):
        """Decorator để hạn chế command chỉ chạy trong kênh cụ thể"""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(self, ctx, *args, **kwargs):
                if not ChannelManager.is_correct_channel(ctx, channel_name):
                    embed = discord.Embed(
                        title="⚠️ Sai kênh",
                        description=f"Lệnh này chỉ có thể sử dụng trong <#{discord.utils.get(ctx.guild.text_channels, name=channel_name).id if discord.utils.get(ctx.guild.text_channels, name=channel_name) else channel_name}>",
                        color=0xF39C12
                    )
                    msg = await ctx.send(embed=embed)
                    # Xóa message sau 5 giây
                    await msg.delete(delay=5)
                    try:
                        await ctx.message.delete(delay=5)
                    except:
                        pass
                    return
                
                return await func(self, ctx, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def music_only():
        """Decorator cho music commands"""
        return ChannelManager.channel_only(ChannelManager.CHANNEL_CONFIG['music'])
    
    @staticmethod  
    def bot_only():
        """Decorator cho bot commands"""
        return ChannelManager.channel_only(ChannelManager.CHANNEL_CONFIG['bot'])

# Global check function
async def check_channel_permissions(ctx):
    """Global check cho tất cả commands"""
    # Cho phép admin bypass channel restrictions
    if ctx.author.guild_permissions.administrator:
        return True
    
    # Lấy tên command
    command_name = ctx.command.name if ctx.command else ''
    
    # Xác định kênh yêu cầu
    required_channel = ChannelManager.get_required_channel(command_name)
    
    # Kiểm tra kênh hiện tại
    if not ChannelManager.is_correct_channel(ctx, required_channel):
        target_channel = discord.utils.get(ctx.guild.text_channels, name=required_channel)
        embed = discord.Embed(
            title="⚠️ Sai kênh",
            description=f"Lệnh `{command_name}` chỉ có thể sử dụng trong {target_channel.mention if target_channel else f'#{required_channel}'}",
            color=0xF39C12
        )
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=5)
        try:
            await ctx.message.delete(delay=5)
        except:
            pass
        return False
    
    return True
