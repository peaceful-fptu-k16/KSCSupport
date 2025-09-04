import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
from collections import deque
import json
import aiohttp
from datetime import datetime, timedelta
import random
import re
from utils.channel_manager import ChannelManager

class SoundCloudQueue:
    """Advanced Queue System cho SoundCloud"""
    def __init__(self):
        self.queue = deque()
        self.history = deque(maxlen=50)  # Lưu 50 bài gần nhất
        self.current = None
        self.loop_mode = "off"  # off, single, queue
        self.shuffle = False
        self.autoplay = False
        self.repeat_count = 0

    def add(self, track):
        self.queue.append(track)

    def add_to_front(self, track):
        self.queue.appendleft(track)

    def get_next(self):
        if not self.queue:
            return None
        return self.queue.popleft()

    def clear(self):
        self.queue.clear()

    def remove(self, index):
        try:
            self.queue.remove(list(self.queue)[index])
            return True
        except:
            return False

    def move(self, from_pos, to_pos):
        try:
            queue_list = list(self.queue)
            item = queue_list.pop(from_pos)
            queue_list.insert(to_pos, item)
            self.queue = deque(queue_list)
            return True
        except:
            return False

    def shuffle_queue(self):
        queue_list = list(self.queue)
        random.shuffle(queue_list)
        self.queue = deque(queue_list)

class SoundCloudSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Unknown Title')
        self.url = data.get('webpage_url', 'Unknown URL')
        self.duration = data.get('duration', 0)
        self.uploader = data.get('uploader', 'Unknown Artist')
        self.thumbnail = data.get('thumbnail', '')
        self.view_count = data.get('view_count', 0)
        self.like_count = data.get('like_count', 0)
        self.description = data.get('description', '')
        self.upload_date = data.get('upload_date', '')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        """Create a SoundCloud source from URL with enhanced options"""
        ytdl_format_options = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'scsearch:',
            'source_address': '0.0.0.0',
            'extract_flat': False,
            'noplaylist': True,
            'restrictfilenames': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'extractaudio': True,
            'audioformat': 'best',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'referer': 'https://soundcloud.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
            }
        }
        
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -user_agent "Mozilla/5.0"',
            'options': '-vn -ar 48000 -ac 2 -b:a 192k -loglevel quiet'
        }
        
        ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
        
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                data = data['entries'][0]
            
            if stream:
                filename = data['url']
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
            else:
                filename = ytdl.prepare_filename(data)
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            raise Exception(f"Error extracting SoundCloud info: {str(e)}")

    @classmethod
    async def search_tracks(cls, query, limit=10):
        """Search multiple tracks from SoundCloud"""
        ytdl_options = {
            'quiet': True,
            'no_warnings': True,
            'default_search': f'scsearch{limit}:',
            'extract_flat': True,
        }
        
        ytdl = yt_dlp.YoutubeDL(ytdl_options)
        
        try:
            search_results = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ytdl.extract_info(f"scsearch{limit}:{query}", download=False)
            )
            
            if 'entries' in search_results:
                tracks = []
                for entry in search_results['entries'][:limit]:
                    if entry:
                        tracks.append({
                            'title': entry.get('title', 'Unknown'),
                            'url': entry.get('url', ''),
                            'uploader': entry.get('uploader', 'Unknown'),
                            'duration': entry.get('duration', 0),
                            'view_count': entry.get('view_count', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'webpage_url': entry.get('webpage_url', '')
                        })
                return tracks
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []

class SoundCloudPlaylistManager:
    """Quản lý playlist SoundCloud"""
    def __init__(self):
        self.playlists = {}
        self.file_path = "data/soundcloud_playlists.json"
        self.load_playlists()

    def load_playlists(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.playlists = json.load(f)
        except:
            self.playlists = {}

    def save_playlists(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.playlists, f, ensure_ascii=False, indent=2)

    def create_playlist(self, user_id, name, tracks):
        if user_id not in self.playlists:
            self.playlists[user_id] = {}
        
        self.playlists[user_id][name] = {
            'tracks': tracks,
            'created': datetime.now().isoformat(),
            'play_count': 0
        }
        self.save_playlists()
        return True

    def add_to_playlist(self, user_id, playlist_name, track):
        if user_id not in self.playlists or playlist_name not in self.playlists[user_id]:
            return False
        
        self.playlists[user_id][playlist_name]['tracks'].append(track)
        self.save_playlists()
        return True

    def get_playlist(self, user_id, name):
        return self.playlists.get(user_id, {}).get(name)

    def list_playlists(self, user_id):
        return list(self.playlists.get(user_id, {}).keys())

    def delete_playlist(self, user_id, name):
        if user_id in self.playlists and name in self.playlists[user_id]:
            del self.playlists[user_id][name]
            self.save_playlists()
            return True
        return False

class SoundCloudStats:
    """Thống kê SoundCloud"""
    def __init__(self):
        self.stats = {}
        self.file_path = "data/soundcloud_stats.json"
        self.load_stats()

    def load_stats(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.stats = json.load(f)
        except:
            self.stats = {}

    def save_stats(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    def track_play(self, user_id, track_info):
        user_id = str(user_id)
        if user_id not in self.stats:
            self.stats[user_id] = {
                'total_plays': 0,
                'favorite_artists': {},
                'listening_time': 0,
                'tracks_played': []
            }
        
        self.stats[user_id]['total_plays'] += 1
        
        # Track favorite artists
        artist = track_info.get('uploader', 'Unknown')
        if artist in self.stats[user_id]['favorite_artists']:
            self.stats[user_id]['favorite_artists'][artist] += 1
        else:
            self.stats[user_id]['favorite_artists'][artist] = 1
        
        # Track listening time
        duration = track_info.get('duration', 0)
        self.stats[user_id]['listening_time'] += duration
        
        # Track recent plays
        self.stats[user_id]['tracks_played'].append({
            'title': track_info.get('title', 'Unknown'),
            'artist': artist,
            'played_at': datetime.now().isoformat()
        })
        
        # Keep only last 100 plays
        if len(self.stats[user_id]['tracks_played']) > 100:
            self.stats[user_id]['tracks_played'] = self.stats[user_id]['tracks_played'][-100:]
        
        self.save_stats()

    def get_user_stats(self, user_id):
        return self.stats.get(str(user_id), {})

class SoundCloudAdvanced(commands.Cog):
    """🎵 SoundCloud Music Player - Nâng cao với Queue, Playlist & Statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Guild ID -> SoundCloudQueue
        self.current_players = {}  # Guild ID -> Current Player
        self.playlist_manager = SoundCloudPlaylistManager()
        self.stats_manager = SoundCloudStats()
        
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = SoundCloudQueue()
        return self.queues[guild_id]

    def format_duration(self, seconds):
        """Format duration to mm:ss"""
        if not seconds:
            return "N/A"
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    async def _play_track(self, ctx, player):
        """Internal method to play a track"""
        def after_play(error):
            if error:
                print(f'Player error: {error}')
            
            coro = self._handle_track_end(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except:
                pass

        ctx.voice_client.play(player, after=after_play)
        
        # Update Music Manager state
        if hasattr(self.bot, 'music_manager'):
            from .music_manager import MusicSource
            self.bot.music_manager.set_guild_state(
                ctx.guild.id,
                MusicSource.SOUNDCLOUD,
                track_info={
                    'title': player.title,
                    'uploader': player.uploader,
                    'url': player.url
                },
                is_playing=True,
                queue_size=len(self.get_queue(ctx.guild.id).queue)
            )
        
        # Track statistics
        self.stats_manager.track_play(ctx.author.id, player.data)

    async def _handle_track_end(self, ctx):
        """Handle what happens when a track ends"""
        queue = self.get_queue(ctx.guild.id)
        
        # Handle loop modes
        if queue.loop_mode == "single" and queue.current:
            # Replay current track
            try:
                player = await SoundCloudSource.from_url(
                    queue.current['url'], loop=self.bot.loop, stream=True
                )
                await self._play_track(ctx, player)
                return
            except:
                pass
        
        # Get next track
        next_track = queue.get_next()
        
        if next_track:
            try:
                player = await SoundCloudSource.from_url(
                    next_track['url'], loop=self.bot.loop, stream=True
                )
                queue.history.append(queue.current)
                queue.current = next_track
                self.current_players[ctx.guild.id] = player
                await self._play_track(ctx, player)
                
                # Send now playing message
                embed = discord.Embed(
                    title="▶️ Đang phát tiếp theo",
                    description=f"**{player.title}**\nby {player.uploader}",
                    color=0xFF5500
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi phát bài tiếp theo: {e}")
        
        elif queue.loop_mode == "queue" and queue.history:
            # Restart queue from history
            for track in reversed(queue.history):
                queue.add_to_front(track)
            queue.history.clear()
            await self._handle_track_end(ctx)

    # ===== MAIN COMMANDS =====
    
    @commands.group(name='sc', invoke_without_command=True)
    @ChannelManager.music_only()
    async def soundcloud_group(self, ctx, *, search: str = None):
        """SoundCloud command group - !sc play <search>"""
        if search:
            await self.play_soundcloud(ctx, search=search)
        else:
            embed = discord.Embed(
                title="🎵 SoundCloud Advanced Commands",
                color=0xFF5500
            )
            embed.add_field(
                name="🎧 Phát nhạc",
                value="`!sc play <search>` - Phát/thêm bài hát\n"
                      "`!sc search <query>` - Tìm kiếm nhiều bài\n"
                      "`!sc playnow <search>` - Phát ngay lập tức",
                inline=False
            )
            embed.add_field(
                name="🎛️ Điều khiển",
                value="`!sc stop` - Dừng nhạc\n"
                      "`!sc skip` - Chuyển bài\n"
                      "`!sc pause/resume` - Tạm dừng/tiếp tục\n"
                      "`!sc volume <0-200>` - Chỉnh âm lượng",
                inline=False
            )
            embed.add_field(
                name="📋 Queue & Loop",
                value="`!sc queue` - Xem hàng đợi\n"
                      "`!sc shuffle` - Xáo trộn queue\n"
                      "`!sc loop <off/single/queue>` - Chế độ lặp\n"
                      "`!sc clear` - Xóa hàng đợi",
                inline=False
            )
            embed.add_field(
                name="💾 Playlist",
                value="`!sc playlist create <name>` - Tạo playlist\n"
                      "`!sc playlist play <name>` - Phát playlist\n"
                      "`!sc playlist add <name>` - Thêm bài hiện tại\n"
                      "`!sc playlist list` - Danh sách playlist",
                inline=False
            )
            embed.add_field(
                name="📊 Thống kê & Khác",
                value="`!sc stats` - Thống kê cá nhân\n"
                      "`!sc history` - Lịch sử phát\n"
                      "`!sc nowplaying` - Bài đang phát\n"
                      "`!sc lyrics` - Tìm lời bài hát",
                inline=False
            )
            await ctx.send(embed=embed)

    @soundcloud_group.command(name='play', aliases=['p'])
    async def play_soundcloud(self, ctx, *, search: str):
        """🎵 Phát nhạc từ SoundCloud (có queue system)"""
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Lỗi Voice Channel",
                description="Bạn cần tham gia voice channel trước!",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return

        # Kiểm tra conflict với Music Manager
        if hasattr(self.bot, 'music_manager'):
            from .music_manager import MusicSource
            can_proceed, conflict_message, conflict_source = await self.bot.music_manager.request_music_control(
                ctx.guild.id, MusicSource.SOUNDCLOUD, ctx=ctx
            )
            
            if not can_proceed:
                # Tạo view để resolve conflict
                view = self.bot.music_manager.create_conflict_resolution_view(
                    ctx.guild.id, MusicSource.SOUNDCLOUD, conflict_source
                )
                await ctx.send(embed=conflict_message, view=view)
                return

        channel = ctx.author.voice.channel
        queue = self.get_queue(ctx.guild.id)

        # Kết nối voice
        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)

        loading_embed = discord.Embed(
            title="🔍 Đang tìm kiếm SoundCloud...",
            description=f"Đang tìm: `{search}`",
            color=0xFF5500
        )
        loading_msg = await ctx.send(embed=loading_embed)

        try:
            if not search.startswith('http'):
                search = f"scsearch:{search}"
            
            player = await SoundCloudSource.from_url(search, loop=self.bot.loop, stream=True)
            
            # Thêm vào queue hoặc phát ngay
            if ctx.voice_client.is_playing():
                queue.add(player.data)
                embed = discord.Embed(
                    title="➕ Đã thêm vào queue",
                    description=f"**{player.title}**\nby {player.uploader}",
                    color=0xFF5500
                )
                embed.add_field(
                    name="📊 Thông tin",
                    value=f"⏱️ Thời lượng: {self.format_duration(player.duration)}\n"
                          f"📍 Vị trí trong queue: #{len(queue.queue)}\n"
                          f"👥 Lượt nghe: {player.view_count:,}",
                    inline=False
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                await loading_msg.edit(embed=embed)
            else:
                await self._play_track(ctx, player)
                queue.current = player.data
                self.current_players[ctx.guild.id] = player
                
                # Success embed with enhanced info
                embed = discord.Embed(
                    title="🎵 Đang phát từ SoundCloud",
                    description=f"**{player.title}**",
                    color=0xFF5500
                )
                embed.add_field(
                    name="🎤 Artist",
                    value=player.uploader,
                    inline=True
                )
                embed.add_field(
                    name="⏱️ Thời lượng",
                    value=self.format_duration(player.duration),
                    inline=True
                )
                embed.add_field(
                    name="👥 Lượt nghe",
                    value=f"{player.view_count:,}",
                    inline=True
                )
                embed.add_field(
                    name="🔊 Âm lượng",
                    value=f"{int(player.volume * 100)}%",
                    inline=True
                )
                embed.add_field(
                    name="📋 Queue",
                    value=f"{len(queue.queue)} bài chờ",
                    inline=True
                )
                embed.add_field(
                    name="🔁 Loop",
                    value=queue.loop_mode.title(),
                    inline=True
                )
                
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                
                embed.add_field(
                    name="🔗 Link",
                    value=f"[Nghe trên SoundCloud]({player.url})",
                    inline=False
                )
                embed.set_footer(text="💡 Dùng !sc để xem thêm lệnh")
                
                await loading_msg.edit(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Lỗi SoundCloud",
                description=f"Không thể phát nhạc: {str(e)}",
                color=0xFF6B35
            )
            await loading_msg.edit(embed=error_embed)

    @soundcloud_group.command(name='search', aliases=['find'])
    async def search_soundcloud(self, ctx, *, query: str):
        """🔍 Tìm kiếm nhiều bài hát SoundCloud"""
        loading_embed = discord.Embed(
            title="🔍 Đang tìm kiếm...",
            description=f"Đang tìm: `{query}`",
            color=0xFF5500
        )
        loading_msg = await ctx.send(embed=loading_embed)
        
        try:
            tracks = await SoundCloudSource.search_tracks(query, limit=10)
            
            if not tracks:
                embed = discord.Embed(
                    title="❌ Không tìm thấy kết quả",
                    description=f"Không có bài hát nào cho: `{query}`",
                    color=0xFF6B35
                )
                await loading_msg.edit(embed=embed)
                return
            
            # Create search results embed
            embed = discord.Embed(
                title=f"🔍 Kết quả tìm kiếm: {query}",
                description="React với số để chọn bài hát:",
                color=0xFF5500
            )
            
            reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            for i, track in enumerate(tracks[:10]):
                embed.add_field(
                    name=f"{reactions[i]} {track['title'][:50]}...",
                    value=f"by {track['uploader']}\n⏱️ {self.format_duration(track['duration'])} | 👥 {track['view_count']:,}",
                    inline=False
                )
            
            await loading_msg.edit(embed=embed)
            
            # Add reactions
            for i in range(len(tracks)):
                await loading_msg.add_reaction(reactions[i])
            await loading_msg.add_reaction("❌")  # Cancel option
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in reactions[:len(tracks)] + ["❌"] and reaction.message.id == loading_msg.id
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                if str(reaction.emoji) == "❌":
                    embed = discord.Embed(
                        title="❌ Đã hủy tìm kiếm",
                        color=0xFF6B35
                    )
                    await loading_msg.edit(embed=embed)
                    return
                
                # Get selected track
                selected_index = reactions.index(str(reaction.emoji))
                selected_track = tracks[selected_index]
                
                # Play selected track
                await self.play_soundcloud(ctx, search=selected_track['webpage_url'])
                
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="⏰ Hết thời gian chọn",
                    color=0xFF6B35
                )
                await loading_msg.edit(embed=embed)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Lỗi tìm kiếm",
                description=f"Lỗi: {str(e)}",
                color=0xFF6B35
            )
            await loading_msg.edit(embed=error_embed)

    @soundcloud_group.command(name='playnow', aliases=['pn'])
    async def play_now(self, ctx, *, search: str):
        """▶️ Phát bài hát ngay lập tức (bỏ qua queue)"""
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Lỗi Voice Channel",
                description="Bạn cần tham gia voice channel trước!",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)

        loading_embed = discord.Embed(
            title="⚡ Đang tải để phát ngay...",
            description=f"Đang tìm: `{search}`",
            color=0xFF5500
        )
        loading_msg = await ctx.send(embed=loading_embed)

        try:
            if not search.startswith('http'):
                search = f"scsearch:{search}"
            
            player = await SoundCloudSource.from_url(search, loop=self.bot.loop, stream=True)
            queue = self.get_queue(ctx.guild.id)
            
            # Stop current and play immediately
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            
            # Add current to front of queue if exists
            if queue.current:
                queue.add_to_front(queue.current)
            
            await self._play_track(ctx, player)
            queue.current = player.data
            self.current_players[ctx.guild.id] = player
            
            embed = discord.Embed(
                title="⚡ Đang phát ngay lập tức",
                description=f"**{player.title}**\nby {player.uploader}",
                color=0xFF5500
            )
            if player.thumbnail:
                embed.set_thumbnail(url=player.thumbnail)
            
            await loading_msg.edit(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Lỗi",
                description=f"Không thể phát nhạc: {str(e)}",
                color=0xFF6B35
            )
            await loading_msg.edit(embed=error_embed)

    # ===== QUEUE MANAGEMENT =====
    
    @soundcloud_group.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx, page: int = 1):
        """📋 Hiển thị hàng đợi nhạc"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.current and not queue.queue:
            embed = discord.Embed(
                title="📋 Queue trống",
                description="Không có bài hát nào trong queue.\nDùng `!sc play <search>` để thêm nhạc.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 SoundCloud Queue",
            color=0xFF5500
        )
        
        # Currently playing
        if queue.current:
            embed.add_field(
                name="🎵 Đang phát",
                value=f"**{queue.current['title']}**\nby {queue.current.get('uploader', 'Unknown')}",
                inline=False
            )
        
        # Queue
        if queue.queue:
            queue_list = list(queue.queue)
            items_per_page = 10
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            
            queue_text = ""
            for i, track in enumerate(queue_list[start_idx:end_idx], start=start_idx + 1):
                queue_text += f"`{i}.` **{track['title'][:40]}...**\n"
                queue_text += f"     by {track.get('uploader', 'Unknown')[:30]} • {self.format_duration(track.get('duration'))}\n\n"
            
            if queue_text:
                embed.add_field(
                    name=f"📝 Queue (Trang {page}/{(len(queue_list)-1)//items_per_page + 1})",
                    value=queue_text[:1024],
                    inline=False
                )
            
            # Queue stats
            total_duration = sum(track.get('duration', 0) for track in queue_list)
            embed.add_field(
                name="📊 Thống kê",
                value=f"🎵 Tổng: {len(queue_list)} bài\n"
                      f"⏱️ Thời lượng: {self.format_duration(total_duration)}\n"
                      f"🔁 Loop: {queue.loop_mode.title()}\n"
                      f"🔀 Shuffle: {'✅' if queue.shuffle else '❌'}",
                inline=True
            )
        
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='skip', aliases=['s'])
    async def skip_track(self, ctx, amount: int = 1):
        """⏭️ Chuyển bài (có thể skip nhiều bài)"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = discord.Embed(
                title="❌ Không có nhạc đang phát",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue = self.get_queue(ctx.guild.id)
        
        if amount > 1:
            # Skip multiple tracks
            for _ in range(amount - 1):
                if queue.queue:
                    skipped = queue.get_next()
                    if skipped:
                        queue.history.append(skipped)
        
        ctx.voice_client.stop()
        
        embed = discord.Embed(
            title=f"⏭️ Đã skip {amount} bài",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='shuffle')
    async def shuffle_queue(self, ctx):
        """🔀 Xáo trộn queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.queue:
            embed = discord.Embed(
                title="❌ Queue trống",
                description="Không có bài hát nào để xáo trộn.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue.shuffle_queue()
        queue.shuffle = not queue.shuffle
        
        embed = discord.Embed(
            title=f"🔀 Shuffle {'Bật' if queue.shuffle else 'Tắt'}",
            description=f"Đã xáo trộn {len(queue.queue)} bài hát trong queue.",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='loop')
    async def loop_mode(self, ctx, mode: str = None):
        """🔁 Chế độ lặp: off/single/queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if mode is None:
            embed = discord.Embed(
                title="🔁 Chế độ Loop hiện tại",
                description=f"**{queue.loop_mode.title()}**",
                color=0xFF5500
            )
            embed.add_field(
                name="📖 Các chế độ",
                value="`off` - Không lặp\n`single` - Lặp bài hiện tại\n`queue` - Lặp toàn bộ queue",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        mode = mode.lower()
        if mode not in ['off', 'single', 'queue']:
            embed = discord.Embed(
                title="❌ Chế độ không hợp lệ",
                description="Chế độ hợp lệ: `off`, `single`, `queue`",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue.loop_mode = mode
        
        icons = {'off': '❌', 'single': '🔂', 'queue': '🔁'}
        embed = discord.Embed(
            title=f"{icons[mode]} Loop mode: {mode.title()}",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='clear')
    async def clear_queue(self, ctx):
        """🗑️ Xóa toàn bộ queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.queue:
            embed = discord.Embed(
                title="❌ Queue đã trống",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        cleared_count = len(queue.queue)
        queue.clear()
        
        embed = discord.Embed(
            title="🗑️ Đã xóa queue",
            description=f"Đã xóa {cleared_count} bài hát khỏi queue.",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='remove', aliases=['rm'])
    async def remove_from_queue(self, ctx, position: int):
        """➖ Xóa bài hát khỏi queue theo vị trí"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.queue:
            embed = discord.Embed(
                title="❌ Queue trống",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        if position < 1 or position > len(queue.queue):
            embed = discord.Embed(
                title="❌ Vị trí không hợp lệ",
                description=f"Vị trí phải từ 1 đến {len(queue.queue)}",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue_list = list(queue.queue)
        removed_track = queue_list[position - 1]
        
        if queue.remove(position - 1):
            embed = discord.Embed(
                title="➖ Đã xóa khỏi queue",
                description=f"**{removed_track['title']}**\nby {removed_track.get('uploader', 'Unknown')}",
                color=0xFF5500
            )
            await ctx.send(embed=embed)

    # ===== PLAYBACK CONTROL =====
    
    @soundcloud_group.command(name='pause')
    async def pause_track(self, ctx):
        """⏸️ Tạm dừng nhạc"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            embed = discord.Embed(
                title="⏸️ Đã tạm dừng",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Không có nhạc đang phát",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    @soundcloud_group.command(name='resume')
    async def resume_track(self, ctx):
        """▶️ Tiếp tục phát nhạc"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            embed = discord.Embed(
                title="▶️ Đã tiếp tục phát",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Nhạc không bị tạm dừng",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    @soundcloud_group.command(name='stop')
    async def stop_track(self, ctx):
        """⏹️ Dừng nhạc và xóa queue"""
        if ctx.voice_client:
            queue = self.get_queue(ctx.guild.id)
            queue.clear()
            queue.current = None
            ctx.voice_client.stop()
            
            embed = discord.Embed(
                title="⏹️ Đã dừng nhạc",
                description="Queue đã được xóa.",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Bot không trong voice channel",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    @soundcloud_group.command(name='volume', aliases=['vol'])
    async def volume_control(self, ctx, volume: int = None):
        """🔊 Điều chỉnh âm lượng (0-200)"""
        if not ctx.voice_client or not ctx.voice_client.source:
            embed = discord.Embed(
                title="❌ Không có nhạc đang phát",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return

        if volume is None:
            current_vol = int(ctx.voice_client.source.volume * 100)
            embed = discord.Embed(
                title="🔊 Âm lượng hiện tại",
                description=f"**{current_vol}%**",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
            return

        if not 0 <= volume <= 200:
            embed = discord.Embed(
                title="❌ Âm lượng không hợp lệ",
                description="Âm lượng phải từ 0-200%",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return

        ctx.voice_client.source.volume = volume / 100
        
        # Volume emoji
        if volume == 0:
            emoji = "🔇"
        elif volume <= 33:
            emoji = "🔈"
        elif volume <= 66:
            emoji = "🔉"
        else:
            emoji = "🔊"
        
        embed = discord.Embed(
            title=f"{emoji} Âm lượng: {volume}%",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='leave', aliases=['disconnect'])
    async def leave_voice(self, ctx):
        """👋 Rời khỏi voice channel"""
        if ctx.voice_client:
            queue = self.get_queue(ctx.guild.id)
            queue.clear()
            queue.current = None
            await ctx.voice_client.disconnect()
            
            embed = discord.Embed(
                title="👋 Đã rời voice channel",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Bot không trong voice channel",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    # ===== PLAYLIST MANAGEMENT =====
    
    @soundcloud_group.group(name='playlist', aliases=['pl'], invoke_without_command=True)
    async def playlist_group(self, ctx):
        """💾 Quản lý playlist SoundCloud"""
        embed = discord.Embed(
            title="💾 SoundCloud Playlist Commands",
            color=0xFF5500
        )
        embed.add_field(
            name="📁 Quản lý",
            value="`!sc playlist create <name>` - Tạo playlist mới\n"
                  "`!sc playlist list` - Danh sách playlist\n"
                  "`!sc playlist delete <name>` - Xóa playlist",
            inline=False
        )
        embed.add_field(
            name="🎵 Phát nhạc",
            value="`!sc playlist play <name>` - Phát playlist\n"
                  "`!sc playlist shuffle <name>` - Phát playlist (xáo trộn)",
            inline=False
        )
        embed.add_field(
            name="➕ Chỉnh sửa",
            value="`!sc playlist add <name>` - Thêm bài hiện tại\n"
                  "`!sc playlist show <name>` - Xem nội dung playlist",
            inline=False
        )
        await ctx.send(embed=embed)

    @playlist_group.command(name='create')
    async def create_playlist(self, ctx, *, name: str):
        """📁 Tạo playlist mới từ queue hiện tại"""
        if len(name) > 50:
            embed = discord.Embed(
                title="❌ Tên playlist quá dài",
                description="Tên playlist không được vượt quá 50 ký tự.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue = self.get_queue(ctx.guild.id)
        tracks = []
        
        # Add current track
        if queue.current:
            tracks.append(queue.current)
        
        # Add queue tracks
        tracks.extend(list(queue.queue))
        
        if not tracks:
            embed = discord.Embed(
                title="❌ Không có bài hát nào",
                description="Phát một số bài hát trước khi tạo playlist.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        if self.playlist_manager.create_playlist(ctx.author.id, name, tracks):
            embed = discord.Embed(
                title="✅ Đã tạo playlist",
                description=f"**{name}**\n📝 {len(tracks)} bài hát",
                color=0x00FF00
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Lỗi tạo playlist",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    @playlist_group.command(name='list')
    async def list_playlists(self, ctx):
        """📋 Danh sách playlist của bạn"""
        playlists = self.playlist_manager.list_playlists(ctx.author.id)
        
        if not playlists:
            embed = discord.Embed(
                title="📋 Bạn chưa có playlist nào",
                description="Dùng `!sc playlist create <name>` để tạo playlist.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Playlist của bạn",
            color=0xFF5500
        )
        
        for playlist_name in playlists:
            playlist_data = self.playlist_manager.get_playlist(ctx.author.id, playlist_name)
            if playlist_data:
                track_count = len(playlist_data['tracks'])
                created_date = datetime.fromisoformat(playlist_data['created']).strftime("%d/%m/%Y")
                embed.add_field(
                    name=f"💾 {playlist_name}",
                    value=f"🎵 {track_count} bài hát\n📅 Tạo: {created_date}\n🔄 Đã phát: {playlist_data['play_count']} lần",
                    inline=True
                )
        
        await ctx.send(embed=embed)

    @playlist_group.command(name='play')
    async def play_playlist(self, ctx, *, name: str):
        """▶️ Phát playlist"""
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Lỗi Voice Channel",
                description="Bạn cần tham gia voice channel trước!",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        playlist_data = self.playlist_manager.get_playlist(ctx.author.id, name)
        if not playlist_data:
            embed = discord.Embed(
                title="❌ Không tìm thấy playlist",
                description=f"Playlist `{name}` không tồn tại.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
        
        # Add all tracks to queue
        queue = self.get_queue(ctx.guild.id)
        tracks = playlist_data['tracks']
        
        for track in tracks:
            queue.add(track)
        
        # Update play count
        playlist_data['play_count'] += 1
        self.playlist_manager.save_playlists()
        
        # Start playing if nothing is playing
        if not ctx.voice_client.is_playing():
            ctx.voice_client.stop()  # Trigger next song
        
        embed = discord.Embed(
            title="▶️ Đang phát playlist",
            description=f"**{name}**\n🎵 Đã thêm {len(tracks)} bài vào queue",
            color=0xFF5500
        )
        await ctx.send(embed=embed)

    @playlist_group.command(name='add')
    async def add_to_playlist(self, ctx, *, name: str):
        """➕ Thêm bài hiện tại vào playlist"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.current:
            embed = discord.Embed(
                title="❌ Không có bài hát đang phát",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        playlist_data = self.playlist_manager.get_playlist(ctx.author.id, name)
        if not playlist_data:
            embed = discord.Embed(
                title="❌ Không tìm thấy playlist",
                description=f"Playlist `{name}` không tồn tại.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        if self.playlist_manager.add_to_playlist(ctx.author.id, name, queue.current):
            embed = discord.Embed(
                title="✅ Đã thêm vào playlist",
                description=f"**{queue.current['title']}**\n➡️ Playlist: {name}",
                color=0x00FF00
            )
            await ctx.send(embed=embed)

    @playlist_group.command(name='delete', aliases=['remove'])
    async def delete_playlist(self, ctx, *, name: str):
        """🗑️ Xóa playlist"""
        if self.playlist_manager.delete_playlist(ctx.author.id, name):
            embed = discord.Embed(
                title="🗑️ Đã xóa playlist",
                description=f"Playlist `{name}` đã được xóa.",
                color=0xFF5500
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Không tìm thấy playlist",
                description=f"Playlist `{name}` không tồn tại.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)

    # ===== STATISTICS & INFO =====
    
    @soundcloud_group.command(name='stats')
    async def show_stats(self, ctx):
        """📊 Thống kê nghe nhạc cá nhân"""
        user_stats = self.stats_manager.get_user_stats(ctx.author.id)
        
        if not user_stats:
            embed = discord.Embed(
                title="📊 Chưa có thống kê",
                description="Phát một số bài hát để xem thống kê!",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        # Calculate listening hours
        total_seconds = user_stats.get('listening_time', 0)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Get top artists
        favorite_artists = user_stats.get('favorite_artists', {})
        top_artists = sorted(favorite_artists.items(), key=lambda x: x[1], reverse=True)[:5]
        
        embed = discord.Embed(
            title=f"📊 Thống kê của {ctx.author.display_name}",
            color=0xFF5500
        )
        
        embed.add_field(
            name="🎵 Tổng quan",
            value=f"🎧 Tổng lượt phát: {user_stats.get('total_plays', 0)}\n"
                  f"⏰ Tổng thời gian: {hours}h {minutes}m\n"
                  f"💾 Playlists: {len(self.playlist_manager.list_playlists(ctx.author.id))}",
            inline=True
        )
        
        if top_artists:
            top_artists_text = ""
            for i, (artist, count) in enumerate(top_artists, 1):
                top_artists_text += f"{i}. **{artist[:20]}** ({count} lần)\n"
            
            embed.add_field(
                name="🎤 Top Artists",
                value=top_artists_text,
                inline=True
            )
        
        # Recent tracks
        recent_tracks = user_stats.get('tracks_played', [])[-5:]
        if recent_tracks:
            recent_text = ""
            for track in reversed(recent_tracks):
                recent_text += f"• **{track['title'][:30]}...**\n"
            
            embed.add_field(
                name="🕒 Gần đây",
                value=recent_text,
                inline=False
            )
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='nowplaying', aliases=['np'])
    async def now_playing(self, ctx):
        """🎵 Thông tin bài hát đang phát"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = discord.Embed(
                title="❌ Không có nhạc đang phát",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        queue = self.get_queue(ctx.guild.id)
        if not queue.current:
            return
        
        current_player = self.current_players.get(ctx.guild.id)
        if not current_player:
            return
        
        embed = discord.Embed(
            title="🎵 Đang phát",
            description=f"**{current_player.title}**",
            color=0xFF5500
        )
        
        embed.add_field(
            name="🎤 Artist",
            value=current_player.uploader,
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Thời lượng",
            value=self.format_duration(current_player.duration),
            inline=True
        )
        
        embed.add_field(
            name="👥 Lượt nghe",
            value=f"{current_player.view_count:,}",
            inline=True
        )
        
        embed.add_field(
            name="🔊 Âm lượng",
            value=f"{int(current_player.volume * 100)}%",
            inline=True
        )
        
        embed.add_field(
            name="📋 Queue",
            value=f"{len(queue.queue)} bài chờ",
            inline=True
        )
        
        embed.add_field(
            name="🔁 Loop",
            value=queue.loop_mode.title(),
            inline=True
        )
        
        if current_player.thumbnail:
            embed.set_thumbnail(url=current_player.thumbnail)
        
        # Description with more info
        if hasattr(current_player, 'description') and current_player.description:
            desc_short = current_player.description[:200] + "..." if len(current_player.description) > 200 else current_player.description
            embed.add_field(
                name="📝 Mô tả",
                value=desc_short,
                inline=False
            )
        
        embed.add_field(
            name="🔗 Links",
            value=f"[SoundCloud]({current_player.url})",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @soundcloud_group.command(name='history')
    async def show_history(self, ctx):
        """🕒 Lịch sử phát nhạc"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.history:
            embed = discord.Embed(
                title="🕒 Chưa có lịch sử",
                description="Chưa có bài hát nào được phát.",
                color=0xFF6B35
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🕒 Lịch sử phát nhạc",
            color=0xFF5500
        )
        
        history_list = list(queue.history)[-10:]  # Last 10 tracks
        history_text = ""
        
        for i, track in enumerate(reversed(history_list), 1):
            history_text += f"`{i}.` **{track['title'][:40]}...**\n"
            history_text += f"     by {track.get('uploader', 'Unknown')[:25]}\n\n"
        
        embed.description = history_text[:2048]
        embed.set_footer(text=f"Hiển thị {len(history_list)} bài gần nhất")
        
        await ctx.send(embed=embed)

    # ===== MODAL INTEGRATION METHODS =====
    
    async def play_from_modal(self, interaction: discord.Interaction, search: str):
        """Method để gọi từ modal, không cần context"""
        # Kiểm tra voice channel
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ Bạn phải ở trong voice channel để phát nhạc SoundCloud!",
                ephemeral=True
            )
            return

        # Kiểm tra conflict với Music Manager
        if hasattr(self.bot, 'music_manager'):
            from .music_manager import MusicSource
            can_proceed, conflict_message, conflict_source = await self.bot.music_manager.request_music_control(
                interaction.guild.id, MusicSource.SOUNDCLOUD, interaction=interaction
            )
            
            if not can_proceed:
                # Tạo view để resolve conflict
                view = self.bot.music_manager.create_conflict_resolution_view(
                    interaction.guild.id, MusicSource.SOUNDCLOUD, conflict_source
                )
                await interaction.response.send_message(embed=conflict_message, view=view, ephemeral=True)
                return

        # Create fake ctx for compatibility
        class FakeCtx:
            def __init__(self, interaction):
                self.author = interaction.user
                self.guild = interaction.guild
                self.voice_client = interaction.guild.voice_client
                self.send = interaction.followup.send
        
        fake_ctx = FakeCtx(interaction)
        voice_channel = interaction.user.voice.channel
        
        # Loading message
        loading_embed = discord.Embed(
            title="🎵 Đang tải SoundCloud...",
            description=f"Đang tìm và tải: `{search}`",
            color=0xFF5500
        )
        await interaction.response.send_message(embed=loading_embed)
        
        try:
            # Kết nối voice nếu chưa có
            if not interaction.guild.voice_client:
                voice_client = await voice_channel.connect()
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)
                voice_client = interaction.guild.voice_client
            else:
                voice_client = interaction.guild.voice_client
                
            fake_ctx.voice_client = voice_client

            # Call the main play method
            if not search.startswith('http'):
                search = f"scsearch:{search}"
            
            player = await SoundCloudSource.from_url(search, loop=self.bot.loop, stream=True)
            queue = self.get_queue(interaction.guild.id)
            
            # Thêm vào queue hoặc phát ngay
            if voice_client.is_playing():
                queue.add(player.data)
                embed = discord.Embed(
                    title="➕ Đã thêm vào queue",
                    description=f"**{player.title}**\nby {player.uploader}",
                    color=0xFF5500
                )
                embed.add_field(
                    name="📍 Vị trí",
                    value=f"#{len(queue.queue)} trong queue",
                    inline=True
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                await interaction.edit_original_response(embed=embed)
            else:
                await self._play_track(fake_ctx, player)
                queue.current = player.data
                self.current_players[interaction.guild.id] = player
                
                embed = discord.Embed(
                    title="🎵 Đang phát từ SoundCloud",
                    description=f"**{player.title}**\nby {player.uploader}",
                    color=0xFF5500
                )
                embed.add_field(
                    name="⏱️ Thời lượng",
                    value=self.format_duration(player.duration),
                    inline=True
                )
                embed.add_field(
                    name="👥 Lượt nghe",
                    value=f"{player.view_count:,}",
                    inline=True
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                
                await interaction.edit_original_response(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Lỗi SoundCloud",
                description=f"Không thể phát nhạc từ SoundCloud.\n**Lỗi:** {str(e)}",
                color=0xFF6B35
            )
            await interaction.edit_original_response(embed=error_embed)

    async def volume_from_modal(self, interaction: discord.Interaction, volume: int):
        """Method để điều chỉnh volume từ modal"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.source:
            await interaction.response.send_message("❌ Không có nhạc SoundCloud nào đang phát.", ephemeral=True)
            return
            
        if not 0 <= volume <= 200:
            await interaction.response.send_message("❌ Âm lượng phải từ 0-200.", ephemeral=True)
            return
            
        interaction.guild.voice_client.source.volume = volume / 100
        
        if volume == 0:
            emoji = "🔇"
        elif volume <= 33:
            emoji = "🔈"
        elif volume <= 66:
            emoji = "🔉"
        else:
            emoji = "🔊"
        
        embed = discord.Embed(
            title=f"{emoji} Âm lượng SoundCloud: {volume}%",
            color=0xFF5500
        )
        await interaction.response.send_message(embed=embed)

    async def stop_from_modal(self, interaction: discord.Interaction):
        """Method để dừng nhạc từ modal/button"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            queue = self.get_queue(interaction.guild.id)
            queue.clear()
            queue.current = None
            interaction.guild.voice_client.stop()
            embed = discord.Embed(
                title="⏹️ Đã dừng SoundCloud",
                description="Nhạc và queue đã được xóa.",
                color=0xFF5500
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Không có nhạc SoundCloud nào đang phát.", ephemeral=True)

    async def leave_from_modal(self, interaction: discord.Interaction):
        """Method để rời voice channel từ modal/button"""
        if interaction.guild.voice_client:
            queue = self.get_queue(interaction.guild.id)
            queue.clear()
            queue.current = None
            await interaction.guild.voice_client.disconnect()
            embed = discord.Embed(
                title="👋 Đã rời voice channel",
                description="SoundCloud bot đã rời khỏi voice channel.",
                color=0xFF5500
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Bot không có trong voice channel nào.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SoundCloudAdvanced(bot))
