import discord
from discord.ext import commands

class InteractiveCommandsSystem(commands.Cog):
    """Interactive Commands System - Clean & Working"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='interactive', aliases=['int', 'buttons'])
    async def interactive_menu(self, ctx):
        """Main interactive menu"""
        view = MainMenuView(self.bot)
        embed = discord.Embed(
            title="KSC Support Bot - Interactive Menu",
            description="Choose what you want to do:",
            color=0x7289DA
        )
        embed.add_field(
            name="Available Options",
            value="🎵 Universal Music System\n🎮 Games & Fun\n🛠️ Admin Tools",
            inline=False
        )
        await ctx.send(embed=embed, view=view)

class MainMenuView(discord.ui.View):
    """Main menu view with working buttons"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label='🎵 Universal Music', style=discord.ButtonStyle.primary, row=0)
    async def music_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show music options"""
        view = MusicMenuView(self.bot)
        embed = discord.Embed(
            title="🎵 Universal Music System",
            description="Mix SoundCloud + YouTube in one queue!",
            color=0xFF5500
        )
        embed.add_field(
            name="Features",
            value="• Universal Play (Mix sources)\n• SoundCloud Only\n• YouTube Only\n• View Queue\n• Music Controls",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='🎮 Games', style=discord.ButtonStyle.success, row=0)
    async def games_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show games"""
        embed = discord.Embed(
            title="🎮 Games & Fun",
            description="Fun features coming soon!",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='🛠️ Admin', style=discord.ButtonStyle.secondary, row=0)
    async def admin_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show admin tools"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🛠️ Admin Tools",
            description="Admin features available!",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MusicMenuView(discord.ui.View):
    """Music menu with all music options"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label='🌟 Universal Play', style=discord.ButtonStyle.success, row=0)
    async def universal_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Universal play modal"""
        modal = UniversalPlayModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='🟠 SoundCloud', style=discord.ButtonStyle.primary, row=0)
    async def soundcloud_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """SoundCloud only"""
        modal = SoundCloudModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='🔴 YouTube', style=discord.ButtonStyle.danger, row=0)
    async def youtube_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """YouTube only"""
        modal = YouTubeModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='🎥 Video', style=discord.ButtonStyle.secondary, row=0)
    async def youtube_video(self, interaction: discord.Interaction, button: discord.ui.Button):
        """YouTube video viewer"""
        modal = VideoModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='📋 View Queue', style=discord.ButtonStyle.secondary, row=1)
    async def view_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View universal queue"""
        # Check Universal Player
        universal_player = getattr(self.bot, 'universal_player', None)
        
        if universal_player:
            queue = universal_player.get_queue(interaction.guild.id)
            embed = discord.Embed(title="🎵 Universal Queue", color=0x7289DA)
            
            if queue.current:
                embed.add_field(
                    name="▶️ Now Playing", 
                    value=f"**{queue.current.title}**\nSource: {queue.current.source.value}",
                    inline=False
                )
            
            if queue.queue:
                next_tracks = []
                for i, track in enumerate(list(queue.queue)[:5], 1):
                    next_tracks.append(f"{i}. **{track.title[:40]}**... ({track.source.value})")
                
                if len(queue.queue) > 5:
                    next_tracks.append(f"... and {len(queue.queue) - 5} more")
                
                embed.add_field(
                    name="📋 Up Next",
                    value="\n".join(next_tracks),
                    inline=False
                )
            
            stats = queue.get_stats()
            embed.add_field(
                name="📊 Stats", 
                value=f"Total: {stats['total_tracks']} tracks",
                inline=True
            )
            
        else:
            embed = discord.Embed(
                title="📋 Queue Status",
                description="Universal Music System not loaded yet.",
                color=0xFF6B35
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='🎛️ Controls', style=discord.ButtonStyle.secondary, row=1)
    async def music_controls(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show music controls"""
        view = MusicControlView(self.bot)
        embed = discord.Embed(
            title="🎛️ Music Controls",
            description="Control your music:",
            color=0x7289DA
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label='⬅️ Back', style=discord.ButtonStyle.secondary, row=2)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Back to main menu"""
        view = MainMenuView(self.bot)
        embed = discord.Embed(
            title="KSC Support Bot - Interactive Menu",
            description="Choose what you want to do:",
            color=0x7289DA
        )
        embed.add_field(
            name="Available Options",
            value="🎵 Universal Music System\n🎮 Games & Fun\n🛠️ Admin Tools",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=view)

class MusicControlView(discord.ui.View):
    """Music control buttons"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label='⏭️ Skip', style=discord.ButtonStyle.primary, row=0)
    async def skip_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip current track"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)

    @discord.ui.button(label='🔀 Shuffle', style=discord.ButtonStyle.secondary, row=0)
    async def shuffle_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shuffle queue"""
        universal_player = getattr(self.bot, 'universal_player', None)
        if universal_player:
            queue = universal_player.get_queue(interaction.guild.id)
            if queue.queue:
                queue.shuffle_queue()
                await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Queue is empty!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Universal player not available!", ephemeral=True)

    @discord.ui.button(label='🗑️ Clear', style=discord.ButtonStyle.danger, row=0)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear queue"""
        universal_player = getattr(self.bot, 'universal_player', None)
        if universal_player:
            queue = universal_player.get_queue(interaction.guild.id)
            if queue.queue:
                count = len(queue.queue)
                queue.clear()
                await interaction.response.send_message(f"🗑️ Cleared {count} tracks!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Queue is already empty!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Universal player not available!", ephemeral=True)

# Modals
class UniversalPlayModal(discord.ui.Modal, title='🌟 Universal Music Player'):
    """Universal play modal"""
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    song = discord.ui.TextInput(
        label='🎵 Song Name or URL',
        placeholder='Enter song name or URL...',
        required=True,
        max_length=500
    )
    
    source = discord.ui.TextInput(
        label='🎯 Source (optional)',
        placeholder='sc=SoundCloud, yt=YouTube, auto=automatic',
        required=False,
        max_length=10,
        default='auto'
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle universal play submission"""
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Connect to voice
            if not interaction.guild.voice_client:
                await interaction.user.voice.channel.connect()
            
            # Get universal player
            universal_player = getattr(self.bot, 'universal_player', None)
            if not universal_player:
                await interaction.followup.send("❌ Universal Music System not loaded!", ephemeral=True)
                return
            
            source_input = self.source.value.lower().strip()
            song_query = self.song.value.strip()
            
            # Determine source
            if source_input == 'sc':
                chosen_source = 'soundcloud'
            elif source_input == 'yt':
                chosen_source = 'youtube'
            elif 'soundcloud.com' in song_query:
                chosen_source = 'soundcloud'
            elif 'youtube.com' in song_query or 'youtu.be' in song_query:
                chosen_source = 'youtube'
            else:
                chosen_source = 'soundcloud'  # Default
            
            # Add to queue
            if chosen_source == 'soundcloud':
                track, position = await universal_player.add_soundcloud_track(
                    interaction.guild.id, song_query, interaction.user
                )
                source_emoji = "🟠"
            else:
                track, position = await universal_player.add_youtube_track(
                    interaction.guild.id, song_query, interaction.user
                )
                source_emoji = "🔴"
            
            queue = universal_player.get_queue(interaction.guild.id)
            
            if interaction.guild.voice_client.is_playing():
                embed = discord.Embed(
                    title="🌟 Added to Universal Queue",
                    description=f"{source_emoji} **{track.title}**\nby {track.uploader}",
                    color=0x00FF00
                )
                embed.add_field(name="Position", value=f"#{position}", inline=True)
                embed.add_field(name="Queue Size", value=f"{len(queue.queue)} tracks", inline=True)
            else:
                # Start playing
                class FakeContext:
                    def __init__(self, guild, voice_client):
                        self.guild = guild
                        self.voice_client = voice_client
                
                fake_ctx = FakeContext(interaction.guild, interaction.guild.voice_client)
                await universal_player.play_next_track(fake_ctx)
                
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"{source_emoji} **{track.title}**\nby {track.uploader}",
                    color=0x00FF00
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

class SoundCloudModal(discord.ui.Modal, title='🟠 SoundCloud Player'):
    """SoundCloud only modal"""
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    query = discord.ui.TextInput(
        label='🎵 SoundCloud Song',
        placeholder='Song name or SoundCloud URL...',
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle SoundCloud play"""
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
            return
        
        soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
        if soundcloud_cog:
            try:
                await soundcloud_cog.play_from_modal(interaction, self.query.value)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ SoundCloud not available!", ephemeral=True)

class YouTubeModal(discord.ui.Modal, title='🔴 YouTube Player'):
    """YouTube only modal"""
    
    query = discord.ui.TextInput(
        label='🎵 YouTube Song',
        placeholder='Song name to search on YouTube...',
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle YouTube play"""
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Connect to voice
            if not interaction.guild.voice_client:
                await interaction.user.voice.channel.connect()
            
            # Simple YouTube play using music cog
            music_cog = interaction.client.get_cog('MusicCog')
            if music_cog:
                # Create fake context
                from discord.ext import commands
                ctx = commands.Context(
                    message=interaction.message if hasattr(interaction, 'message') else None,
                    bot=interaction.client,
                    args=[self.query.value],
                    prefix='!',
                    command=None
                )
                ctx.author = interaction.user
                ctx.channel = interaction.channel
                ctx.guild = interaction.guild
                ctx.voice_client = interaction.guild.voice_client
                
                await music_cog.play(ctx, query=self.query.value)
                
                embed = discord.Embed(
                    title="🔴 YouTube Player",
                    description=f"Playing: **{self.query.value}**",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ YouTube player not available!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

class VideoModal(discord.ui.Modal, title="🎥 YouTube Video Viewer"):
    """Modal for YouTube video viewing"""
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    query = discord.ui.TextInput(
        label='Video Name or URL',
        placeholder='Enter video name or YouTube URL...',
        max_length=200,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get video cog
            video_cog = self.bot.get_cog('YouTubeVideoViewer')
            if video_cog:
                # Call the video extraction directly instead of using play_video
                query = self.query.value
                
                # Extract video info
                search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch:{query}"
                
                import asyncio
                data = await asyncio.to_thread(
                    video_cog.ytdl.extract_info,
                    search_query,
                    download=False
                )
                
                if not data:
                    await interaction.followup.send("❌ Không thể truy cập video!", ephemeral=True)
                    return
                
                # Handle search results vs direct URL
                if 'entries' in data:
                    if not data['entries'] or len(data['entries']) == 0:
                        await interaction.followup.send("❌ Không tìm thấy video!", ephemeral=True)
                        return
                    video_info = data['entries'][0]
                else:
                    video_info = data
                
                # Validate video info
                if not video_info.get('title'):
                    await interaction.followup.send("❌ Video không hợp lệ!", ephemeral=True)
                    return
                
                # Create embed and view
                embed = await video_cog.create_video_embed(video_info)
                
                # Create mock context for VideoControlView
                class MockContext:
                    def __init__(self, interaction):
                        self.author = interaction.user
                        self.guild = interaction.guild
                        self.channel = interaction.channel
                        self.bot = interaction.client
                
                mock_ctx = MockContext(interaction)
                
                # Import VideoControlView from youtube_video cog
                from cogs.youtube_video import VideoControlView
                view = VideoControlView(mock_ctx, video_info, self.bot)
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
            else:
                await interaction.followup.send("❌ Video viewer not available!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(InteractiveCommandsSystem(bot))
