import discord
from discord.ext import commands
from enum import Enum
import logging

class MusicSource(Enum):
    """Enum để xác định nguồn nhạc"""
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    SPOTIFY = "spotify"

class MusicManager:
    """
    Central Music Manager để quản lý conflicts giữa các music sources
    Đảm bảo chỉ một source phát nhạc tại một thời điểm
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.guild_music_states = {}  # guild_id -> {'current_source': MusicSource, 'queue_size': int, 'track_info': dict}
        self.logger = logging.getLogger(__name__)
    
    def get_guild_state(self, guild_id):
        """Lấy trạng thái music của guild"""
        if guild_id not in self.guild_music_states:
            self.guild_music_states[guild_id] = {
                'current_source': None,
                'queue_size': 0,
                'track_info': None,
                'is_playing': False,
                'volume': 50
            }
        return self.guild_music_states[guild_id]
    
    def set_guild_state(self, guild_id, source, track_info=None, is_playing=False, queue_size=0):
        """Cập nhật trạng thái music của guild"""
        state = self.get_guild_state(guild_id)
        state['current_source'] = source
        state['track_info'] = track_info
        state['is_playing'] = is_playing
        state['queue_size'] = queue_size
        
        self.logger.info(f"Guild {guild_id} - Music state updated: {source.value if source else 'None'}")
    
    async def request_music_control(self, guild_id, requested_source, ctx=None, interaction=None):
        """
        Request để kiểm soát music system
        Returns: (can_proceed: bool, message: str, conflict_source: MusicSource)
        """
        current_state = self.get_guild_state(guild_id)
        current_source = current_state['current_source']
        
        # Nếu không có nhạc đang phát, cho phép
        if not current_source or not current_state['is_playing']:
            self.logger.info(f"Guild {guild_id} - Music control granted to {requested_source.value}")
            return True, None, None
        
        # Nếu cùng source, cho phép
        if current_source == requested_source:
            return True, None, None
        
        # Có conflict - tạo embed warning
        conflict_embed = discord.Embed(
            title="🎵 Music Conflict Detected!",
            description=f"**Hiện tại đang phát:** {current_source.value.title()}\n"
                       f"**Bạn muốn phát:** {requested_source.value.title()}",
            color=0xFF6B6B
        )
        
        current_track = current_state.get('track_info')
        if current_track:
            conflict_embed.add_field(
                name="🎵 Đang phát:",
                value=f"**{current_track.get('title', 'Unknown')}**\nby {current_track.get('uploader', 'Unknown')}",
                inline=False
            )
        
        conflict_embed.add_field(
            name="⚠️ Lưu ý:",
            value="Phát nhạc từ source khác sẽ **dừng** nhạc hiện tại!\n"
                  "Queue hiện tại sẽ bị **xóa**.",
            inline=False
        )
        
        conflict_embed.add_field(
            name="💡 Gợi ý:",
            value=f"• Sử dụng `!pause` để tạm dừng {current_source.value}\n"
                  f"• Sử dụng `!stop` để dừng hoàn toàn\n"
                  f"• Hoặc tiếp tục để thay thế",
            inline=False
        )
        
        return False, conflict_embed, current_source
    
    async def handle_music_switch(self, guild_id, new_source, guild):
        """Xử lý việc chuyển đổi giữa các music sources"""
        try:
            # Dừng music hiện tại
            if guild.voice_client and guild.voice_client.is_playing():
                guild.voice_client.stop()
                self.logger.info(f"Guild {guild_id} - Stopped current music for source switch")
            
            # Clear queues của source cũ
            await self._clear_old_queues(guild_id)
            
            # Update state
            self.set_guild_state(guild_id, new_source, is_playing=False)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error switching music source: {e}")
            return False
    
    async def _clear_old_queues(self, guild_id):
        """Clear queues của tất cả music sources"""
        try:
            # Clear YouTube queue
            music_cog = self.bot.get_cog('MusicCog')
            if music_cog and guild_id in music_cog.music_queues:
                music_cog.music_queues[guild_id].clear()
                self.logger.info(f"Guild {guild_id} - YouTube queue cleared")
            
            # Clear SoundCloud queue  
            soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
            if soundcloud_cog and guild_id in soundcloud_cog.queues:
                soundcloud_cog.queues[guild_id].clear()
                self.logger.info(f"Guild {guild_id} - SoundCloud queue cleared")
                
        except Exception as e:
            self.logger.error(f"Error clearing old queues: {e}")
    
    def create_conflict_resolution_view(self, guild_id, requested_source, current_source):
        """Tạo View với buttons để resolve conflict"""
        return MusicConflictView(self, guild_id, requested_source, current_source)
    
    async def force_switch_source(self, guild_id, new_source, guild):
        """Force switch music source (được gọi khi user chọn continue)"""
        success = await self.handle_music_switch(guild_id, new_source, guild)
        return success


class MusicConflictView(discord.ui.View):
    """View với buttons để resolve music conflict"""
    
    def __init__(self, music_manager, guild_id, requested_source, current_source):
        super().__init__(timeout=60)
        self.music_manager = music_manager
        self.guild_id = guild_id
        self.requested_source = requested_source
        self.current_source = current_source
    
    @discord.ui.button(label='🔄 Continue & Switch', style=discord.ButtonStyle.danger, emoji='🔄')
    async def continue_switch(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Tiếp tục và chuyển sang source mới"""
        success = await self.music_manager.force_switch_source(
            self.guild_id, 
            self.requested_source, 
            interaction.guild
        )
        
        if success:
            embed = discord.Embed(
                title="✅ Switched Music Source",
                description=f"Đã chuyển sang **{self.requested_source.value.title()}**",
                color=0x00FF00
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(
                title="❌ Switch Failed",
                description="Không thể chuyển đổi music source",
                color=0xFF0000
            )
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Hủy request phát nhạc mới"""
        embed = discord.Embed(
            title="🚫 Request Cancelled",
            description=f"Tiếp tục phát nhạc từ **{self.current_source.value.title()}**",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label='⏸️ Pause Current', style=discord.ButtonStyle.primary, emoji='⏸️')
    async def pause_current(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pause nhạc hiện tại"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            
            embed = discord.Embed(
                title="⏸️ Music Paused",
                description=f"Đã tạm dừng **{self.current_source.value.title()}**\nBạn có thể phát nhạc từ source khác",
                color=0xFFCC00
            )
            
            # Update state
            self.music_manager.set_guild_state(self.guild_id, self.current_source, is_playing=False)
            
        else:
            embed = discord.Embed(
                title="❌ Cannot Pause",
                description="Không có nhạc đang phát",
                color=0xFF0000
            )
        
        await interaction.response.edit_message(embed=embed, view=None)


class MusicManagerCog(commands.Cog):
    """Cog để quản lý Music Manager"""
    
    def __init__(self, bot):
        self.bot = bot
        self.music_manager = MusicManager(bot)
        # Make music manager accessible globally
        bot.music_manager = self.music_manager
    
    @commands.command(name='musicstatus', aliases=['mstatus', 'music_info'])
    async def music_status(self, ctx):
        """Xem trạng thái music hiện tại"""
        state = self.music_manager.get_guild_state(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎵 Music Status",
            color=0x7289DA
        )
        
        if state['current_source']:
            embed.add_field(
                name="📻 Current Source", 
                value=state['current_source'].value.title(),
                inline=True
            )
            embed.add_field(
                name="▶️ Playing", 
                value="Yes" if state['is_playing'] else "No",
                inline=True
            )
            embed.add_field(
                name="📝 Queue Size", 
                value=str(state['queue_size']),
                inline=True
            )
            
            if state['track_info']:
                track = state['track_info']
                embed.add_field(
                    name="🎵 Current Track",
                    value=f"**{track.get('title', 'Unknown')}**\nby {track.get('uploader', 'Unknown')}",
                    inline=False
                )
        else:
            embed.description = "**No music currently playing**"
        
        # Voice connection status
        if ctx.voice_client:
            embed.add_field(
                name="🔊 Voice Status",
                value=f"Connected to **{ctx.voice_client.channel.name}**",
                inline=False
            )
        else:
            embed.add_field(
                name="🔊 Voice Status", 
                value="Not connected to voice channel",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='switchsource', aliases=['switch', 'change_source'])
    async def force_switch_source(self, ctx, source: str):
        """Force switch music source"""
        source_map = {
            'youtube': MusicSource.YOUTUBE,
            'soundcloud': MusicSource.SOUNDCLOUD,
            'yt': MusicSource.YOUTUBE,
            'sc': MusicSource.SOUNDCLOUD
        }
        
        if source.lower() not in source_map:
            await ctx.send("❌ Valid sources: `youtube`, `soundcloud`, `yt`, `sc`")
            return
        
        new_source = source_map[source.lower()]
        success = await self.music_manager.handle_music_switch(ctx.guild.id, new_source, ctx.guild)
        
        if success:
            embed = discord.Embed(
                title="✅ Source Switched",
                description=f"Music source switched to **{new_source.value.title()}**",
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="❌ Switch Failed",
                description="Could not switch music source",
                color=0xFF0000
            )
        
        await ctx.send(embed=embed)
async def setup(bot):
    await bot.add_cog(MusicManagerCog(bot))
