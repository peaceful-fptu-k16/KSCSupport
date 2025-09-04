import discord
from discord.ext import commands
from enum import Enum
from collections import deque
import asyncio
import json
from datetime import datetime
import logging
from utils.channel_manager import ChannelManager

class TrackSource(Enum):
    """Enum để xác định nguồn của track"""
    SOUNDCLOUD = "soundcloud"
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    LOCAL = "local"

class UniversalTrack:
    """Class đại diện cho một track từ bất kỳ source nào"""
    def __init__(self, title, url, source, uploader, duration=None, thumbnail=None, **kwargs):
        self.title = title
        self.url = url
        self.source = TrackSource(source)
        self.uploader = uploader
        self.duration = duration
        self.thumbnail = thumbnail
        self.added_by = kwargs.get('added_by')
        self.added_at = datetime.now()
        self.play_count = 0
        
        # Source-specific data
        self.source_data = kwargs
    
    def to_dict(self):
        """Convert track to dictionary for JSON storage"""
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source.value,
            'uploader': self.uploader,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'added_by': self.added_by.id if self.added_by else None,
            'added_at': self.added_at.isoformat(),
            'play_count': self.play_count,
            'source_data': self.source_data
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create track from dictionary"""
        track = cls(
            title=data['title'],
            url=data['url'], 
            source=data['source'],
            uploader=data['uploader'],
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            **data.get('source_data', {})
        )
        track.play_count = data.get('play_count', 0)
        return track

class UniversalQueue:
    """Universal queue có thể chứa tracks từ nhiều sources"""
    
    def __init__(self):
        self.queue = deque()
        self.history = deque(maxlen=50)
        self.current = None
        self.loop_mode = "off"  # off, single, queue
        self.shuffle = False
        self.autoplay = False
        self.volume = 50
    
    def add(self, track: UniversalTrack, position=None):
        """Thêm track vào queue"""
        if position is None:
            self.queue.append(track)
        else:
            # Insert at specific position
            queue_list = list(self.queue)
            queue_list.insert(position, track)
            self.queue = deque(queue_list)
    
    def add_next(self, track: UniversalTrack):
        """Thêm track vào đầu queue (phát tiếp theo)"""
        self.queue.appendleft(track)
    
    def get_next(self):
        """Lấy track tiếp theo"""
        if not self.queue:
            return None
        return self.queue.popleft()
    
    def remove(self, index):
        """Xóa track tại vị trí index"""
        try:
            queue_list = list(self.queue)
            removed = queue_list.pop(index)
            self.queue = deque(queue_list)
            return removed
        except (IndexError, ValueError):
            return None
    
    def move(self, from_pos, to_pos):
        """Di chuyển track từ vị trí này sang vị trí khác"""
        try:
            queue_list = list(self.queue)
            track = queue_list.pop(from_pos)
            queue_list.insert(to_pos, track)
            self.queue = deque(queue_list)
            return True
        except (IndexError, ValueError):
            return False
    
    def clear(self):
        """Xóa toàn bộ queue"""
        self.queue.clear()
    
    def get_queue_info(self):
        """Lấy thông tin queue để hiển thị"""
        tracks_info = []
        for i, track in enumerate(self.queue):
            source_emoji = {
                TrackSource.SOUNDCLOUD: "🟠",
                TrackSource.YOUTUBE: "🔴", 
                TrackSource.SPOTIFY: "🟢",
                TrackSource.LOCAL: "💿"
            }
            
            tracks_info.append({
                'position': i + 1,
                'title': track.title[:50] + "..." if len(track.title) > 50 else track.title,
                'uploader': track.uploader,
                'source': source_emoji.get(track.source, "❓"),
                'duration': track.duration,
                'added_by': track.added_by
            })
        
        return tracks_info
    
    def shuffle_queue(self):
        """Trộn queue"""
        import random
        queue_list = list(self.queue)
        random.shuffle(queue_list)
        self.queue = deque(queue_list)
    
    def get_stats(self):
        """Lấy thống kê queue"""
        total_tracks = len(self.queue)
        sources = {}
        total_duration = 0
        
        for track in self.queue:
            source = track.source.value
            sources[source] = sources.get(source, 0) + 1
            if track.duration:
                try:
                    total_duration += int(track.duration)
                except:
                    pass
        
        return {
            'total_tracks': total_tracks,
            'sources': sources,
            'total_duration': total_duration,
            'estimated_time': f"{total_duration // 60}:{total_duration % 60:02d}" if total_duration else "Unknown"
        }

class UniversalMusicPlayer:
    """Universal music player có thể phát từ nhiều sources"""
    
    def __init__(self, bot):
        self.bot = bot
        self.guild_queues = {}  # guild_id -> UniversalQueue
        self.logger = logging.getLogger(__name__)
    
    def get_queue(self, guild_id):
        """Lấy queue của guild"""
        if guild_id not in self.guild_queues:
            self.guild_queues[guild_id] = UniversalQueue()
        return self.guild_queues[guild_id]
    
    async def add_soundcloud_track(self, guild_id, search_term, added_by=None):
        """Thêm SoundCloud track vào universal queue"""
        try:
            # Get SoundCloud cog
            soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
            if not soundcloud_cog:
                raise Exception("SoundCloud cog not available")
            
            # Search SoundCloud
            if not search_term.startswith('http'):
                search_term = f"scsearch:{search_term}"
            
            # Use SoundCloud's search method
            from cogs.soundcloud_advanced import SoundCloudSource
            player = await SoundCloudSource.from_url(search_term, loop=self.bot.loop, stream=True)
            
            # Create universal track
            track = UniversalTrack(
                title=player.title,
                url=player.url,
                source="soundcloud",
                uploader=player.uploader,
                duration=player.data.get('duration'),
                thumbnail=player.data.get('thumbnail'),
                added_by=added_by,
                player_data=player.data
            )
            
            queue = self.get_queue(guild_id)
            queue.add(track)
            
            return track, len(queue.queue)
            
        except Exception as e:
            self.logger.error(f"Error adding SoundCloud track: {e}")
            raise
    
    async def add_youtube_track(self, guild_id, search_term, added_by=None):
        """Thêm YouTube track vào universal queue"""
        try:
            # Get YouTube music cog
            music_cog = self.bot.get_cog('MusicCog')
            if not music_cog:
                raise Exception("Music cog not available")
            
            # Use YouTube's search method
            from cogs.music import ytdl
            import asyncio
            
            loop = self.bot.loop or asyncio.get_event_loop()
            
            def search_youtube():
                return ytdl.extract_info(f"ytsearch:{search_term}", download=False)
            
            data = await loop.run_in_executor(None, search_youtube)
            
            if 'entries' in data and data['entries']:
                video_data = data['entries'][0]
                
                # Create universal track
                track = UniversalTrack(
                    title=video_data.get('title', 'Unknown'),
                    url=video_data.get('url', ''),
                    source="youtube",
                    uploader=video_data.get('uploader', 'Unknown'),
                    duration=video_data.get('duration'),
                    thumbnail=video_data.get('thumbnail'),
                    added_by=added_by,
                    player_data=video_data
                )
                
                queue = self.get_queue(guild_id)
                queue.add(track)
                
                return track, len(queue.queue)
            else:
                raise Exception("No YouTube results found")
                
        except Exception as e:
            self.logger.error(f"Error adding YouTube track: {e}")
            raise
    
    async def play_next_track(self, ctx):
        """Phát track tiếp theo trong universal queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.queue:
            # No more tracks
            queue.current = None
            return None
        
        next_track = queue.get_next()
        if not next_track:
            return None
        
        try:
            # Create player based on source
            if next_track.source == TrackSource.SOUNDCLOUD:
                player = await self._create_soundcloud_player(next_track)
            elif next_track.source == TrackSource.YOUTUBE:
                player = await self._create_youtube_player(next_track)
            else:
                raise Exception(f"Unsupported source: {next_track.source}")
            
            # Play track
            def after_playing(error):
                if error:
                    self.logger.error(f'Player error: {error}')
                
                # Add to history
                queue.history.append(next_track)
                next_track.play_count += 1
                
                # Handle loop modes
                if queue.loop_mode == "single":
                    # Add same track back to front
                    queue.add_next(next_track)
                elif queue.loop_mode == "queue" and not queue.queue:
                    # Add all history back to queue
                    for track in queue.history:
                        queue.add(track)
                
                # Play next track
                coro = self.play_next_track(ctx)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except:
                    pass
            
            ctx.voice_client.play(player, after=after_playing)
            queue.current = next_track
            
            # Update volume
            if hasattr(player, 'volume'):
                player.volume = queue.volume / 100
            
            return next_track
            
        except Exception as e:
            self.logger.error(f"Error playing track: {e}")
            # Skip to next track
            return await self.play_next_track(ctx)
    
    async def _create_soundcloud_player(self, track):
        """Tạo SoundCloud player"""
        from cogs.soundcloud_advanced import SoundCloudSource
        return await SoundCloudSource.from_url(track.url, loop=self.bot.loop, stream=True)
    
    async def _create_youtube_player(self, track):
        """Tạo YouTube player"""
        from cogs.music import YTDLSource
        return await YTDLSource.from_url(track.url, loop=self.bot.loop, stream=True)

class UniversalMusicCog(commands.Cog):
    """Universal Music System - Mix SoundCloud + YouTube trong cùng queue"""
    
    def __init__(self, bot):
        self.bot = bot
        self.player = UniversalMusicPlayer(bot)
        # Make accessible globally
        bot.universal_player = self.player
    
    @commands.group(name='uplay', aliases=['universalplay', 'mix'])
    @ChannelManager.music_only()
    async def universal_play_group(self, ctx):
        """🎵 Universal Music Player - Mix SoundCloud + YouTube"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎵 Universal Music Player",
                description="**Mix SoundCloud và YouTube trong cùng một queue!**",
                color=0x7289DA
            )
            embed.add_field(
                name="🎵 Phát nhạc",
                value="`!uplay sc <song>` - Thêm SoundCloud\n"
                      "`!uplay yt <song>` - Thêm YouTube\n"
                      "`!uplay auto <song>` - Auto detect source",
                inline=False
            )
            embed.add_field(
                name="📋 Quản lý Queue",
                value="`!uplay queue` - Xem queue mixed\n"
                      "`!uplay skip` - Skip bài hiện tại\n"
                      "`!uplay clear` - Clear queue\n"
                      "`!uplay shuffle` - Trộn queue",
                inline=False
            )
            await ctx.send(embed=embed)
    
    @universal_play_group.command(name='sc', aliases=['soundcloud'])
    async def add_soundcloud(self, ctx, *, search):
        """🟠 Thêm SoundCloud track vào universal queue"""
        if not ctx.author.voice:
            await ctx.send("❌ Bạn cần vào voice channel trước!")
            return
        
        # Connect to voice
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        
        try:
            async with ctx.typing():
                track, position = await self.player.add_soundcloud_track(
                    ctx.guild.id, search, ctx.author
                )
            
            queue = self.player.get_queue(ctx.guild.id)
            
            if ctx.voice_client.is_playing():
                embed = discord.Embed(
                    title="🟠 Đã thêm SoundCloud vào queue",
                    description=f"**{track.title}**\nby {track.uploader}",
                    color=0xFF5500
                )
                embed.add_field(name="📍 Vị trí", value=f"#{position}", inline=True)
                embed.add_field(name="🎵 Tổng queue", value=f"{len(queue.queue)} bài", inline=True)
            else:
                # Start playing immediately
                await self.player.play_next_track(ctx)
                embed = discord.Embed(
                    title="🟠 Đang phát SoundCloud",
                    description=f"**{track.title}**\nby {track.uploader}",
                    color=0xFF5500
                )
                
                if queue.queue:
                    embed.add_field(name="⏭️ Tiếp theo", value=f"{len(queue.queue)} bài trong queue", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Lỗi thêm SoundCloud: {str(e)}")
    
    @universal_play_group.command(name='yt', aliases=['youtube'])
    async def add_youtube(self, ctx, *, search):
        """🔴 Thêm YouTube track vào universal queue"""
        if not ctx.author.voice:
            await ctx.send("❌ Bạn cần vào voice channel trước!")
            return
        
        # Connect to voice
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        
        try:
            async with ctx.typing():
                track, position = await self.player.add_youtube_track(
                    ctx.guild.id, search, ctx.author
                )
            
            queue = self.player.get_queue(ctx.guild.id)
            
            if ctx.voice_client.is_playing():
                embed = discord.Embed(
                    title="🔴 Đã thêm YouTube vào queue",
                    description=f"**{track.title}**\nby {track.uploader}",
                    color=0xFF0000
                )
                embed.add_field(name="📍 Vị trí", value=f"#{position}", inline=True)
                embed.add_field(name="🎵 Tổng queue", value=f"{len(queue.queue)} bài", inline=True)
            else:
                # Start playing immediately
                await self.player.play_next_track(ctx)
                embed = discord.Embed(
                    title="🔴 Đang phát YouTube",
                    description=f"**{track.title}**\nby {track.uploader}",
                    color=0xFF0000
                )
                
                if queue.queue:
                    embed.add_field(name="⏭️ Tiếp theo", value=f"{len(queue.queue)} bài trong queue", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Lỗi thêm YouTube: {str(e)}")
    
    @universal_play_group.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx):
        """📋 Hiển thị universal queue với mixed sources"""
        queue = self.player.get_queue(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎵 Universal Queue - Mixed Sources",
            color=0x7289DA
        )
        
        # Current track
        if queue.current:
            source_emoji = {
                TrackSource.SOUNDCLOUD: "🟠",
                TrackSource.YOUTUBE: "🔴",
                TrackSource.SPOTIFY: "🟢"
            }
            
            embed.add_field(
                name="▶️ Đang phát",
                value=f"{source_emoji.get(queue.current.source, '❓')} **{queue.current.title}**\nby {queue.current.uploader}",
                inline=False
            )
        
        # Queue tracks
        if queue.queue:
            queue_info = queue.get_queue_info()
            queue_text = []
            
            for track_info in queue_info[:10]:  # Show first 10
                queue_text.append(
                    f"`{track_info['position']}.` {track_info['source']} **{track_info['title']}**\n"
                    f"     by {track_info['uploader']}"
                )
            
            if len(queue.queue) > 10:
                queue_text.append(f"... và {len(queue.queue) - 10} bài khác")
            
            embed.add_field(
                name="📋 Queue",
                value="\n".join(queue_text) if queue_text else "Queue trống",
                inline=False
            )
        
        # Stats
        stats = queue.get_stats()
        stats_text = f"**Tổng:** {stats['total_tracks']} bài\n"
        
        if stats['sources']:
            source_counts = []
            for source, count in stats['sources'].items():
                emoji = {"soundcloud": "🟠", "youtube": "🔴", "spotify": "🟢"}.get(source, "❓")
                source_counts.append(f"{emoji} {count}")
            stats_text += f"**Sources:** {' | '.join(source_counts)}\n"
        
        stats_text += f"**Thời gian:** ~{stats['estimated_time']}"
        
        embed.add_field(name="📊 Thống kê", value=stats_text, inline=True)
        
        # Settings
        settings_text = f"🔁 Loop: {queue.loop_mode}\n🔀 Shuffle: {'On' if queue.shuffle else 'Off'}\n🔊 Volume: {queue.volume}%"
        embed.add_field(name="⚙️ Settings", value=settings_text, inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UniversalMusicCog(bot))
