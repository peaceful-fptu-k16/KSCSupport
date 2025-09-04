import asyncio
import discord # type: ignore
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import yt_dlp # type: ignore
import os
import re
import random
from collections import deque
import logging
from utils.channel_manager import ChannelManager

# Suppress noise about console usage from errors
def _suppress_bug_reports(*args, **kwargs):
    return ''

yt_dlp.utils.bug_reports_message = _suppress_bug_reports

# YouTube music bot với yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': False,  # Cho phép playlist
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'ignoreerrors': True,  # Bỏ qua lỗi trong playlist
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'logtostderr': False,
    'age_limit': 18,
    'extract_flat': False,
    'playlistend': 50,  # Giới hạn 50 bài để tránh spam
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    }
}

# FFmpeg options - improved for stability
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.5"'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        print(f"🔧 YTDLSource.from_url called")
        print(f"🔗 URL: {url[:50]}...")
        print(f"📡 Stream: {stream}")
        
        loop = loop or asyncio.get_event_loop()
        
        def extract_info():
            print(f"📦 Extracting info from yt-dlp...")
            try:
                result = ytdl.extract_info(url, download=not stream)
                print(f"✅ Info extracted successfully")
                return result
            except Exception as e:
                print(f"❌ Error extracting info: {e}")
                raise
            
        try:
            data = await loop.run_in_executor(None, extract_info)
            if 'entries' in data:
                data = data['entries'][0]
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            print(f"🎵 Audio filename/URL: {filename[:50]}...")
            
            # Use the improved FFmpeg options
            print(f"🔊 Creating FFmpegPCMAudio...")
            audio_source = discord.FFmpegPCMAudio(
                filename, 
                before_options=ffmpeg_options['before_options'],
                options=ffmpeg_options['options']
            )
            print(f"✅ FFmpegPCMAudio created successfully")
            
            player = cls(audio_source, data=data)
            print(f"🎵 YTDLSource player created - Title: {player.title}")
            return player
            
        except Exception as e:
            print(f"❌ YTDLSource.from_url failed: {e}")
            print(f"🔍 Error type: {type(e).__name__}")
            raise

    @classmethod
    async def search_youtube(cls, search_term, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            def search_func():
                print(f"🔍 Searching YouTube for: {search_term}")
                return ytdl.extract_info(f"ytsearch:{search_term}", download=False)
            
            data = await loop.run_in_executor(None, search_func)
            if 'entries' in data and len(data['entries']) > 0:
                result = data['entries'][0]
                print(f"✅ Found: {result.get('title', 'Unknown title')}")
                return result
            else:
                print(f"❌ No results found for: {search_term}")
        except yt_dlp.utils.DownloadError as e:
            print(f"❌ YouTube download error: {e}")
            if "403" in str(e):
                print("⚠️ YouTube 403 error - may need to update yt-dlp")
        except Exception as e:
            print(f"❌ YouTube search error: {e}")
        return None




class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.loop_song = False
        self.loop_queue = False
        self.loop_mode = "off"  # "off", "song", "queue"
        self.auto_dj = False
        self.auto_dj_24_7 = False  # 24/7 mode
        self.history = []  # Store played songs
        self.playlists = {}  # user_id: {playlist_name: [songs]}
        self.preferred_genres = [
            "nhạc việt nam", "vpop", "ballad việt", "rap việt", "indie việt",
            "nhạc lofi việt", "acoustic việt", "nhạc trẻ việt nam"
        ]  # Ưu tiên nhạc Việt cho Auto DJ
        
        # State tracking
        self.is_paused = False

    def add(self, song):
        self.queue.append(song)

    def get_next(self):
        # Add current song to history if exists
        if self.current:
            self.history.append(self.current)
            # Keep only last 50 songs in history
            if len(self.history) > 50:
                self.history.pop(0)
        
        # Handle loop modes
        if self.loop_mode == "song" and self.current:
            return self.current
        
        if len(self.queue) > 0:
            song = self.queue.popleft()
            
            # If loop queue mode, add song back to end
            if self.loop_mode == "queue":
                self.queue.append(song)
            
            return song
        
        # Auto DJ 24/7 - return None to trigger auto search
        if self.auto_dj_24_7:
            return None
            
        return None

    def clear(self):
        self.queue.clear()
        self.current = None

    def skip(self):
        if len(self.queue) > 0:
            return self.queue.popleft()
        return None

    def shuffle(self):
        import random
        queue_list = list(self.queue)
        random.shuffle(queue_list)
        self.queue = deque(queue_list)
        
    def save_playlist(self, user_id, playlist_name, songs):
        """Lưu playlist của user"""
        if user_id not in self.playlists:
            self.playlists[user_id] = {}
        self.playlists[user_id][playlist_name] = songs
        
    def get_playlist(self, user_id, playlist_name):
        """Lấy playlist của user"""
        return self.playlists.get(user_id, {}).get(playlist_name, [])
        
    def list_playlists(self, user_id):
        """Liệt kê playlist của user"""
        return list(self.playlists.get(user_id, {}).keys())
        
    def delete_playlist(self, user_id, playlist_name):
        """Xóa playlist"""
        if user_id in self.playlists and playlist_name in self.playlists[user_id]:
            del self.playlists[user_id][playlist_name]
            return True
        return False


class MusicControlView(discord.ui.View):
    """Music control panel for current playing song"""
    
    def __init__(self, bot, guild_id):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.guild_id = guild_id
        self.message = None  # Store the message for editing
    
    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Đã tạm dừng nhạc!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có nhạc đang phát!", ephemeral=True)
    
    @discord.ui.button(emoji='▶️', style=discord.ButtonStyle.secondary)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client and guild.voice_client.is_paused():
            guild.voice_client.resume()
            await interaction.response.send_message("▶️ Đã tiếp tục phát nhạc!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nhạc không bị tạm dừng!", ephemeral=True)
    
    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Đã bỏ qua bài hát!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có nhạc đang phát!", ephemeral=True)
    
    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(self.guild_id)
            queue.clear()
            
            guild = self.bot.get_guild(self.guild_id)
            if guild and guild.voice_client:
                if guild.voice_client.is_playing():
                    guild.voice_client.stop()
                await guild.voice_client.disconnect()
                await interaction.response.send_message("⏹️ Đã dừng nhạc và rời khỏi voice channel!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Bot không ở trong voice channel!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
    
    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(self.guild_id)
            if len(queue.queue) > 1:
                queue.shuffle()
                await interaction.response.send_message("🔀 Đã xáo trộn queue!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Cần ít nhất 2 bài hát trong queue để xáo trộn!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
    
    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.secondary, row=1)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(self.guild_id)
            # Cycle through loop modes: off -> song -> queue -> off
            if queue.loop_mode == "off":
                queue.loop_mode = "song"
                queue.loop_song = True
                queue.loop_queue = False
                await interaction.response.send_message("🔁 Đặt chế độ lặp bài hát!", ephemeral=True)
            elif queue.loop_mode == "song":
                queue.loop_mode = "queue"
                queue.loop_song = False
                queue.loop_queue = True
                await interaction.response.send_message("🔁 Đặt chế độ lặp queue!", ephemeral=True)
            else:
                queue.loop_mode = "off"
                queue.loop_song = False
                queue.loop_queue = False
                await interaction.response.send_message("🔁 Tắt chế độ lặp!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
    
    @discord.ui.button(emoji='📝', style=discord.ButtonStyle.secondary, row=1)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(self.guild_id)
            
            if not queue.queue and not queue.current:
                await interaction.response.send_message("📝 Queue trống!", ephemeral=True)
                return

            embed = discord.Embed(title="🎵 Music Queue", color=0x0099ff)
            
            if queue.current:
                embed.add_field(
                    name="🎵 Đang phát",
                    value=f"**{queue.current['title']}**",
                    inline=False
                )

            if queue.queue:
                queue_list = []
                for i, song in enumerate(list(queue.queue)[:10], 1):
                    queue_list.append(f"**{i}.** {song['title']}")
                
                embed.add_field(
                    name="📝 Tiếp theo",
                    value="\n".join(queue_list),
                    inline=False
                )
                
                if len(queue.queue) > 10:
                    embed.add_field(
                        name="➕ Và hơn nữa",
                        value=f"**{len(queue.queue) - 10}** bài hát khác...",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
    
    @discord.ui.button(emoji='🔊', style=discord.ButtonStyle.secondary, row=1)
    async def volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client:
            if hasattr(guild.voice_client.source, 'volume'):
                current_volume = int(guild.voice_client.source.volume * 100)
                await interaction.response.send_message(f"🔊 Âm lượng hiện tại: **{current_volume}%**\nDùng `!volume <0-100>` để thay đổi", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Không thể xem âm lượng với nguồn âm thanh hiện tại!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bot không ở trong voice channel!", ephemeral=True)
    
    @discord.ui.button(emoji='🎵', style=discord.ButtonStyle.primary, row=1)
    async def add_song_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎵 **Thêm bài hát:**\nDùng lệnh `!play <tên bài hát>` hoặc `/play` để thêm nhạc vào queue!", ephemeral=True)
    
    async def on_timeout(self):
        # Disable all buttons when view times out
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
        # Disable all buttons when timeout
        for item in self.children:
            item.disabled = True
        
        try:
            # Try to edit the message to show it's expired
            if hasattr(self, 'message') and self.message:
                embed = discord.Embed(
                    title="⏰ Bộ điều khiển đã hết hạn",
                    description="Gõ `!controls` để tạo bộ điều khiển mới",
                    color=discord.Color.red()
                )
                await self.message.edit(embed=embed, view=self)
        except:
            pass


class VolumeModal(discord.ui.Modal, title='🔊 Điều chỉnh âm lượng'):
    volume = discord.ui.TextInput(
        label='Âm lượng (0-100)',
        placeholder='Nhập âm lượng từ 0 đến 100...',
        style=discord.TextStyle.short,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            vol = int(self.volume.value)
            if vol < 0 or vol > 100:
                await interaction.response.send_message("❌ Âm lượng phải từ 0 đến 100!", ephemeral=True)
                return
            
            # Direct implementation instead of calling non-existent method
            guild = interaction.guild
            if guild and guild.voice_client:
                if hasattr(guild.voice_client.source, 'volume'):
                    guild.voice_client.source.volume = vol / 100
                    await interaction.response.send_message(f"🔊 Đã đặt âm lượng thành **{vol}%**", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Không thể thay đổi âm lượng với nguồn âm thanh hiện tại!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Bot không ở trong voice channel!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Vui lòng nhập số hợp lệ!", ephemeral=True)


class MusicCog(commands.Cog):
    """Music commands for YouTube"""

    def __init__(self, bot):
        self.bot = bot
        self.music_queues = {}  # Guild ID -> MusicQueue
        # Per-guild HQ config
        self.hq_settings = {}  # guild_id -> {'normalize': bool}

    def get_queue(self, guild_id):
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = MusicQueue()
        return self.music_queues[guild_id]
    
    def format_duration(self, duration):
        """Format duration from seconds to MM:SS"""
        if not duration:
            return "N/A"
        try:
            duration = int(float(duration))
            minutes = duration // 60
            seconds = duration % 60
            return f"{minutes}:{seconds:02d}"
        except (ValueError, TypeError):
            return "N/A"
    
    def create_fake_context(self, interaction):
        """Create a fake context object for interaction compatibility"""
        class FakeContext:
            def __init__(self, interaction):
                self.guild = interaction.guild
                self.voice_client = interaction.guild.voice_client
                self.author = interaction.user
                self.channel = interaction.channel
                self.bot = interaction.client
                
            async def send(self, content=None, **kwargs):
                # Try to send as followup if possible
                try:
                    if hasattr(interaction, 'followup'):
                        return await interaction.followup.send(content, **kwargs)
                    else:
                        return await interaction.response.send_message(content, **kwargs)
                except:
                    # Fallback to channel send
                    return await self.channel.send(content, **kwargs)
        
        return FakeContext(interaction)

    def build_ffmpeg_args(self, guild_id: int):
        """Build FFmpeg arguments for YouTube streaming"""
        cfg = self.hq_settings.get(guild_id, {'normalize': False})
        
        # YouTube với chất lượng cao hơn và reconnect
        opts = "-vn -ar 48000 -ac 2 -loglevel quiet"
        before_opts = ffmpeg_options['before_options']
        print(f"🔧 Applying YouTube optimized config")
        
        # Thêm loudness normalization nếu được bật
        if cfg.get('normalize'):
            opts += " -af loudnorm=I=-14:LRA=11:TP=-1.5"
            print(f"🎚️ Added loudness normalization for YouTube")
            
        return before_opts, opts

    def is_ffmpeg_expected_error(self, error_str: str) -> bool:
        """Check if FFmpeg error is expected and can be safely ignored"""
        expected_codes = [
            "1",           # Generic exit code 1
            "255",         # FFmpeg termination
            "Connection reset by peer",  # Network issues
            "Server returned 4XX",       # HTTP errors
            "Server returned 5XX",       # Server errors
        ]
        
        error_lower = str(error_str).lower()
        for code in expected_codes:
            if code.lower() in error_lower:
                return True
        return False

    async def create_player(self, data, guild_id: int):
        try:
            webpage_url = data.get('webpage_url', '')
            extractor = data.get('extractor', '')
            
            print(f"🎵 Creating player for: {data.get('title', 'Unknown')}")
            print(f"🔗 URL: {webpage_url}")
            print(f"🎬 Platform: {extractor}")
            
            # Sử dụng YouTube player cho tất cả content
            print(f"🎬 Using YouTube optimized player")
            return await self._create_youtube_player(data, guild_id)
                
        except Exception as e:
            print(f"❌ Error creating player: {e}")
            raise Exception(f"Lỗi phát nhạc: {e}")

    async def _create_youtube_player(self, data, guild_id: int):
        """Tạo player cho YouTube với cấu hình tối ưu"""
        try:
            print(f"🎬 Using YouTube optimized approach")
            
            before_opts, ffmpeg_opts = self.build_ffmpeg_args(guild_id)
            print(f"🔧 FFmpeg options: {ffmpeg_opts}")
            print(f"🔧 FFmpeg before_opts: {before_opts}")
            
            # Debug: Log data structure
            print(f"📊 YouTube data keys: {list(data.keys())}")
            
            # YouTube thông thường với cấu hình tối ưu
            player = await YTDLSource.from_url(
                data.get('webpage_url', ''), 
                loop=self.bot.loop, 
                stream=True
            )
            
            # Debug: Check player properties
            print(f"🎵 Player created - Title: {getattr(player, 'title', 'No title')}")
            print(f"🔊 Player volume: {getattr(player, 'volume', 'No volume')}")
            print(f"✅ YouTube player created successfully!")
            return player
            
        except Exception as e:
            print(f"❌ YouTube player creation failed: {e}")
            print(f"🔍 Error details: {type(e).__name__}: {str(e)}")
            raise Exception(f"Lỗi phát YouTube: {e}")
        
    

    async def get_auto_dj_song(self, guild_id: int):
        """Tìm bài hát ngẫu nhiên cho Auto DJ 24/7 - ưu tiên nhạc Việt"""
        queue = self.get_queue(guild_id)
        
        # Danh sách từ khóa tìm kiếm nhạc Việt ưu tiên - tập trung vào MV
        vietnamese_terms = [
            "sơn tùng mtp mv", "đen vâu mv", "bích phương mv", "erik mv", "jack mv", "k-icm mv",
            "hoàng thùy linh mv", "amee mv", "min mv", "đức phúc mv", "justatee mv", "rhymastic mv",
            "hiền hồ mv", "cara mv", "orange mv", "vũ mv", "binz mv", "karik mv", "suboi mv",
            "vpop mv 2024", "nhạc trẻ việt nam mv", "ballad việt nam mv", "rap việt nam mv",
            "indie việt nam mv", "acoustic việt nam mv", "viral việt mv", "trending vpop mv"
        ]
        
        # Từ khóa chung backup - tập trung vào MV
        general_terms = [
            "pop mv 2024", "trending mv", "viral mv", "acoustic mv", "indie pop mv",
            "chill mv", "lofi mv", "electronic mv", "dance mv", "ballad mv"
        ]
        
        # Phân tích bài hát cuối để tìm nhạc liên quan
        if queue.history:
            last_song = queue.history[-1]
            title = last_song.get('title', '').lower()
            uploader = last_song.get('uploader', '').lower()
            
            # Detect Vietnamese content
            vietnamese_indicators = [
                'việt', 'viet', 'vietnam', 'vpop', 'vrap', 'sơn tùng', 'đen vâu',
                'bích phương', 'erik', 'jack', 'amee', 'min', 'hiền hồ', 'binz',
                'karik', 'rhymastic', 'justatee', 'suboi', 'orange', 'vũ', 'cara'
            ]
            
            is_vietnamese = any(indicator in title or indicator in uploader 
                              for indicator in vietnamese_indicators)
            
            # Tạo từ khóa thông minh
            smart_terms = []
            
            if is_vietnamese:
                # Nếu bài cuối là nhạc Việt, ưu tiên tìm nhạc Việt liên quan
                if 'sơn tùng' in title or 'sơn tùng' in uploader:
                    smart_terms.extend(['sơn tùng mtp mv', 'vpop ballad mv', 'nhạc trẻ việt mv'])
                elif 'đen' in title or 'đen' in uploader:
                    smart_terms.extend(['đen vâu mv', 'rap việt nam mv', 'underground việt mv'])
                elif 'erik' in title or 'erik' in uploader:
                    smart_terms.extend(['erik mv', 'vpop 2024 mv', 'nhạc trẻ hay mv'])
                elif 'jack' in title or 'jack' in uploader:
                    smart_terms.extend(['jack mv', 'k-icm mv', 'vpop trending mv'])
                elif 'bích phương' in title or 'bích phương' in uploader:
                    smart_terms.extend(['bích phương mv', 'vpop nữ mv', 'ballad việt mv'])
                elif 'amee' in title or 'amee' in uploader:
                    smart_terms.extend(['amee mv', 'min mv', 'vpop girl mv'])
                else:
                    # Extract artist name for Vietnamese music
                    artist_parts = uploader.split(' - ')[0].split('Official')[0].strip()
                    if len(artist_parts) > 2:
                        smart_terms.append(f"{artist_parts} mv")
                        smart_terms.append(f"{artist_parts} official mv")
                
                # Thêm các từ khóa Việt tổng quát
                smart_terms.extend(vietnamese_terms[:8])  # Top 8 Vietnamese terms
            else:
                # Nếu bài cuối là nhạc nước ngoài, vẫn ưu tiên nhạc Việt nhưng thêm chút đa dạng
                smart_terms.extend(vietnamese_terms[:5])  # Top 5 Vietnamese terms
                
                # Extract artist for international songs
                artist_parts = uploader.split(' - ')[0].split('Official')[0].split('VEVO')[0].strip()
                if len(artist_parts) > 2 and len(artist_parts) < 30:
                    smart_terms.append(f"{artist_parts} mv")
                
                smart_terms.extend(general_terms[:3])  # Add some general terms
        else:
            # Không có lịch sử, bắt đầu với nhạc Việt
            smart_terms = vietnamese_terms[:10]
        
        # Thử tìm kiếm với từ khóa thông minh
        import random
        random.shuffle(smart_terms)  # Trộn để đa dạng
        
        for attempt in range(5):  # Thử tối đa 5 lần
            try:
                search_term = smart_terms[attempt % len(smart_terms)]
                data = await YTDLSource.search_youtube(search_term)
                
                if data:
                    # Kiểm tra không phải bài đã phát gần đây
                    recent_urls = [song.get('webpage_url', '') for song in queue.history[-15:]]
                    if data.get('webpage_url') not in recent_urls:
                        return data
                        
            except Exception as e:
                print(f"Auto DJ search error for '{search_term}': {e}")
                continue
        
        # Fallback - tìm nhạc Việt cơ bản
        try:
            fallback_terms = ["vpop mv 2024", "nhạc việt mv", "trending vpop mv"]
            data = await YTDLSource.search_youtube(random.choice(fallback_terms))
            return data
        except:
            # Ultimate fallback
            try:
                return await YTDLSource.search_youtube("vietnam mv")
            except:
                return None

    async def play_next(self, ctx):
        """Play the next song in queue"""
        queue = self.get_queue(ctx.guild.id)
        next_song = queue.get_next()
        
        # Auto DJ 24/7 mode - tìm bài mới khi hết queue
        if next_song is None and queue.auto_dj_24_7:
            try:
                print("🔄 Auto DJ trying to find next song...")
                auto_song = await self.get_auto_dj_song(ctx.guild.id)
                if auto_song:
                    next_song = auto_song
                    # Thông báo Auto DJ
                    try:
                        platform_info = "🎬 YouTube"
                        
                        embed = discord.Embed(
                            title="🎵 Auto DJ 24/7",
                            description=f"Phát nhạc tự động: **{auto_song['title']}**",
                            color=discord.Color.purple()
                        )
                        embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                        embed.set_footer(text="Gõ !autodj off để tắt chế độ tự động")
                        await ctx.send(embed=embed)
                    except:
                        pass
            except Exception as e:
                print(f"❌ Auto DJ error: {e}")
                # Ngừng Auto DJ tạm thời để tránh lặp lỗi
                queue.auto_dj_24_7 = False
                try:
                    await ctx.send("⚠️ Auto DJ gặp lỗi và đã được tắt tạm thời. Gõ `!autodj on` để bật lại.")
                except:
                    pass
        
        if next_song:
            try:
                # Ensure bot is connected to voice
                if not ctx.voice_client:
                    await ctx.send("❌ Bot không còn trong voice channel!")
                    return
                
                if not ctx.voice_client.is_connected():
                    await ctx.send("❌ Mất kết nối voice channel!")
                    return
                
                player = await self.create_player(next_song, ctx.guild.id)
                queue.current = next_song
                
                def after_playing(error):
                    if error:
                        print(f"❌ Player error in play_next: {error}")
                        
                        # Use smart error checking
                        if self.is_ffmpeg_expected_error(str(error)):
                            print(f"✅ Expected FFmpeg error in play_next - continuing")
                        else:
                            print(f"⚠️ Unexpected error in play_next: {error}")
                    else:
                        print(f"✅ Song from play_next finished normally")
                    
                    # Continue to next song if voice client is connected
                    if ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
                        try:
                            coro = self.play_next(ctx)
                            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                        except Exception as e:
                            print(f"❌ Error in play_next recursion: {e}")
                
                ctx.voice_client.play(player, after=after_playing)
                
                # Update Music Manager state
                if hasattr(self.bot, 'music_manager'):
                    from .music_manager import MusicSource
                    self.bot.music_manager.set_guild_state(
                        ctx.guild.id,
                        MusicSource.YOUTUBE,
                        track_info={
                            'title': player.title,
                            'uploader': player.data.get('uploader', 'Unknown'),
                            'url': player.data.get('url', '')
                        },
                        is_playing=True,
                        queue_size=len(queue.queue)
                    )
                
                    # Chỉ hiển thị embed chi tiết cho nhạc thường, không phải Auto DJ
                if not queue.auto_dj_24_7 or len(queue.queue) > 0:
                    # Detect platform để hiển thị icon đúng
                    platform_info = "🎬 YouTube"
                    
                    embed = discord.Embed(
                        title="🎵 Đang phát",
                        description=f"**{player.title}**",
                        color=0x00ff00
                    )
                    embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                    if player.uploader:
                        embed.add_field(name="Kênh", value=player.uploader, inline=True)
                    if next_song.get('duration'):
                        duration_str = self.format_duration(next_song['duration'])
                        embed.add_field(name="Thời lượng", value=duration_str, inline=True)
                    if player.thumbnail:
                        embed.set_thumbnail(url=player.thumbnail)
                    
                    # Gộp bộ điều khiển vào message "Đang phát"
                    view = MusicControlView(self.bot, ctx.guild.id)
                    message = await ctx.send(embed=embed, view=view)
                    
                    # Lưu message để có thể edit khi timeout
                    view.message = message
                    
                    # Đăng ký message để auto cleanup sau 10 phút
                    auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                    if auto_cleanup_cog:
                        auto_cleanup_cog.add_message_for_cleanup(message, delete_after=600)  # 10 phút
            except Exception as e:
                print(f"❌ Error in play_next: {e}")
                await ctx.send(f"❌ Lỗi khi phát nhạc: {e}")
                
                # Nếu là Auto DJ và gặp lỗi, tắt tạm thời
                if queue.auto_dj_24_7:
                    queue.auto_dj_24_7 = False
                    await ctx.send("⚠️ Auto DJ gặp lỗi liên tục và đã được tắt. Hãy kiểm tra lại sau.")
        else:
            queue.current = None
            if not queue.auto_dj_24_7:
                await ctx.send("✅ Hết nhạc trong queue!")
            else:
                # Auto DJ 24/7 failed - try again in 30 seconds to avoid spam
                print("⏳ Auto DJ waiting 30s before retry...")
                await asyncio.sleep(30)
                await self.play_next(ctx)

    @commands.command(name='fix_volume')
    @commands.has_permissions(administrator=True)
    async def debug_audio(self, ctx):
        """Debug audio issues"""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Bot không trong voice channel!")
                return
            
            embed = discord.Embed(title="🔧 Audio Debug Info", color=discord.Color.blue())
            
            # Voice client status
            embed.add_field(
                name="� Voice Client Status",
                value=f"```\nConnected: {ctx.voice_client.is_connected()}\n" +
                      f"Playing: {ctx.voice_client.is_playing()}\n" +
                      f"Paused: {ctx.voice_client.is_paused()}\n" +
                      f"Channel: {ctx.voice_client.channel.name if ctx.voice_client.channel else 'None'}\n```",
                inline=False
            )
            
            # Volume info
            if ctx.voice_client.source and hasattr(ctx.voice_client.source, 'volume'):
                volume = ctx.voice_client.source.volume
                embed.add_field(
                    name="🔊 Volume Info",
                    value=f"```\nBot Volume: {volume:.2f} ({int(volume*100)}%)\n```",
                    inline=False
                )
            
            # Queue info
            queue = self.get_queue(ctx.guild.id)
            queue_info = f"Current: {queue.current['title'] if queue.current else 'None'}\n"
            queue_info += f"Queue size: {len(queue.queue)}\n"
            queue_info += f"Loop: {queue.loop}\n"
            queue_info += f"Shuffle: {queue.shuffle_mode}"
            
            embed.add_field(
                name="📝 Queue Info",
                value=f"```\n{queue_info}\n```",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Debug error: {e}")

    @commands.command(name='musichealth')
    async def music_health_check(self, ctx):
        """Kiểm tra tình trạng hệ thống nhạc"""
        embed = discord.Embed(
            title="🏥 Music System Health Check",
            color=0x00ff00
        )
        
        # Check voice connection
        if ctx.voice_client:
            embed.add_field(
                name="🔊 Voice Connection", 
                value=f"✅ Connected to `{ctx.voice_client.channel.name}`",
                inline=False
            )
            embed.add_field(
                name="🎵 Playing Status",
                value=f"Playing: {ctx.voice_client.is_playing()}\nPaused: {ctx.voice_client.is_paused()}",
                inline=True
            )
        else:
            embed.add_field(
                name="🔊 Voice Connection", 
                value="❌ Not connected to voice channel",
                inline=False
            )
        
        # Check queue
        queue = self.get_queue(ctx.guild.id)
        embed.add_field(
            name="📝 Queue Status",
            value=f"Songs in queue: {len(queue.queue)}\nCurrent: {queue.current.get('title', 'None') if queue.current else 'None'}",
            inline=True
        )
        
        # Check ffmpeg
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                embed.add_field(name="🔧 FFmpeg", value="✅ Available", inline=True)
            else:
                embed.add_field(name="🔧 FFmpeg", value="❌ Error", inline=True)
        except:
            embed.add_field(name="🔧 FFmpeg", value="❌ Not found", inline=True)
        
        # Check yt-dlp
        try:
            import yt_dlp
            embed.add_field(name="📥 yt-dlp", value=f"✅ Version: {yt_dlp.version.__version__}", inline=True)
        except:
            embed.add_field(name="📥 yt-dlp", value="❌ Error", inline=True)
        
        await ctx.send(embed=embed)

    @ChannelManager.music_only()
    @commands.command(name='play', aliases=['nhac'])
    async def play(self, ctx, *, search):
        """Phát nhạc từ YouTube hoặc URL"""
        if not ctx.author.voice:
            await ctx.send("❌ Bạn cần vào voice channel trước!")
            return

        # Kiểm tra conflict với Music Manager
        if hasattr(self.bot, 'music_manager'):
            from .music_manager import MusicSource
            can_proceed, conflict_message, conflict_source = await self.bot.music_manager.request_music_control(
                ctx.guild.id, MusicSource.YOUTUBE, ctx=ctx
            )
            
            if not can_proceed:
                # Tạo view để resolve conflict
                view = self.bot.music_manager.create_conflict_resolution_view(
                    ctx.guild.id, MusicSource.YOUTUBE, conflict_source
                )
                await ctx.send(embed=conflict_message, view=view)
                return

        voice_channel = ctx.author.voice.channel
        # Cảnh báo bitrate nếu thấp
        try:
            if voice_channel.bitrate and voice_channel.bitrate < 192000:
                await ctx.send("⚠️ Bitrate kênh voice thấp (<192kbps), chất lượng có thể bị giới hạn. Tăng bitrate nếu server được boost.")
        except Exception:
            pass
        # Ensure bot connects to voice channel
        try:
            if ctx.voice_client is None:
                await voice_channel.connect()
                await ctx.send(f"🔗 Đã kết nối tới **{voice_channel.name}**")
            elif ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
                await ctx.send(f"🔄 Đã chuyển tới **{voice_channel.name}**")
        except Exception as e:
            await ctx.send(f"❌ Không thể kết nối voice channel: {str(e)}")
            return

        async with ctx.typing():
            url_pattern = re.compile(r'https?://')
            if url_pattern.match(search):
                # Hỗ trợ YouTube URLs và Playlists
                try:
                    loop = self.bot.loop or asyncio.get_event_loop()
                    def extract_url_info():
                        # Cho phép playlist extraction
                        return ytdl.extract_info(search, download=False)
                    data = await loop.run_in_executor(None, extract_url_info)
                    
                    # Kiểm tra nếu là playlist
                    if 'entries' in data and len(data['entries']) > 1:
                        # Đây là playlist
                        playlist_title = data.get('title', 'YouTube Playlist')
                        entries = data['entries']
                        
                        await ctx.send(f"🎵 Đang thêm playlist: **{playlist_title}** ({len(entries)} bài hát)...")
                        
                        queue = self.get_queue(ctx.guild.id)
                        added_count = 0
                        
                        # Thêm từng bài vào queue
                        for i, entry in enumerate(entries):
                            if entry:  # Kiểm tra entry không null
                                try:
                                    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused() and i == 0:
                                        # Phát bài đầu tiên ngay
                                        player = await self.create_player(entry, ctx.guild.id)
                                        queue.current = entry
                                        
                                        def after_playing(error):
                                            if error:
                                                print(f"❌ Player error: {error}")
                                                if self.is_ffmpeg_expected_error(str(error)):
                                                    print(f"✅ Expected FFmpeg error - continuing normally")
                                                else:
                                                    print(f"⚠️ Unexpected error: {error}")
                                            else:
                                                print(f"✅ Song finished playing normally")
                                            
                                            if ctx.voice_client and ctx.voice_client.is_connected():
                                                try:
                                                    coro = self.play_next(ctx)
                                                    asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                                                except Exception as next_error:
                                                    print(f"❌ Error scheduling next song: {next_error}")
                                        
                                        ctx.voice_client.play(player, after=after_playing)
                                        added_count += 1
                                        
                                        # Hiển thị embed cho bài đầu tiên
                                        platform_info = "🎬 YouTube Playlist"
                                        embed = discord.Embed(title="🎵 Đang phát từ playlist", description=f"**{player.title}**", color=0x00ff00)
                                        embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                                        if player.uploader:
                                            embed.add_field(name="Kênh", value=player.uploader, inline=True)
                                        if entry.get('duration'):
                                            embed.add_field(name="Thời lượng", value=self.format_duration(entry['duration']), inline=True)
                                        embed.add_field(name="Playlist", value=f"{playlist_title} (bài 1/{len(entries)})", inline=False)
                                        if player.thumbnail:
                                            embed.set_thumbnail(url=player.thumbnail)
                                        
                                        view = MusicControlView(self.bot, ctx.guild.id)
                                        view.message = await ctx.send(embed=embed, view=view)
                                        
                                        # Đăng ký message để auto cleanup sau 10 phút
                                        auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                                        if auto_cleanup_cog:
                                            auto_cleanup_cog.add_message_for_cleanup(view.message, delete_after=600)
                                    else:
                                        # Thêm vào queue
                                        queue.add(entry)
                                        added_count += 1
                                except Exception as e:
                                    print(f"❌ Error processing playlist entry {i+1}: {e}")
                                    continue
                        
                        if added_count > 1:
                            await ctx.send(f"✅ Đã thêm **{added_count}** bài hát từ playlist vào queue!")
                        elif added_count == 0:
                            await ctx.send("❌ Không thể thêm bài hát nào từ playlist!")
                        return
                        
                    elif 'entries' in data:
                        # Single video from playlist URL
                        data = data['entries'][0]
                    
                    if not data:
                        await ctx.send("❌ Không thể tải nhạc từ URL này!")
                        return
                except Exception as e:
                    await ctx.send(f"❌ Lỗi: {e}")
                    return
            else:
                data = await YTDLSource.search_youtube(search)
                if not data:
                    await ctx.send("❌ Không tìm thấy bài hát trên YouTube!\n"
                                 "💡 **Gợi ý:**\n"
                                 "• Thử tìm với tên nghệ sĩ + tên bài\n"
                                 "• Thêm từ khóa 'official', 'mv', 'music video'\n"
                                 "• Kiểm tra chính tả tên bài hát")
                    return
            
            queue = self.get_queue(ctx.guild.id)
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                try:
                    player = await self.create_player(data, ctx.guild.id)
                    queue.current = data
                    
                    # Voice client status
                    print(f"🔊 Voice client status: Connected={ctx.voice_client.is_connected()}")
                    print(f"🔊 Voice channel: {ctx.voice_client.channel.name if ctx.voice_client.channel else 'None'}")
                    
                    def after_playing(error):
                        if error:
                            print(f"❌ Player error: {error}")
                            print(f"🔍 Error type: {type(error).__name__}")
                            
                            # Use smart error checking
                            if self.is_ffmpeg_expected_error(str(error)):
                                print(f"✅ Expected FFmpeg error - continuing normally")
                            else:
                                print(f"⚠️ Unexpected error, may need investigation: {error}")
                        else:
                            print(f"✅ Song finished playing normally")
                        
                        # Only continue to next song if voice client is still connected and no critical error
                        if ctx.voice_client and ctx.voice_client.is_connected():
                            try:
                                coro = self.play_next(ctx)
                                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                            except Exception as next_error:
                                print(f"❌ Error scheduling next song: {next_error}")
                    
                    print(f"🎵 Starting playback...")
                    ctx.voice_client.play(player, after=after_playing)
                    print(f"🔊 Is playing: {ctx.voice_client.is_playing()}")
                    print(f"🔊 Is paused: {ctx.voice_client.is_paused()}")
                    
                    # Detect platform để hiển thị icon đúng
                    platform_info = "🎬 YouTube"
                    
                    embed = discord.Embed(title="🎵 Đang phát", description=f"**{player.title}**", color=0x00ff00)
                    embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                    if player.uploader:
                        embed.add_field(name="Kênh", value=player.uploader, inline=True)
                    if data.get('duration'):
                        embed.add_field(name="Thời lượng", value=self.format_duration(data['duration']), inline=True)
                    if player.thumbnail:
                        embed.set_thumbnail(url=player.thumbnail)
                    view = MusicControlView(self.bot, ctx.guild.id)
                    view.message = await ctx.send(embed=embed, view=view)
                    
                    # Đăng ký message để auto cleanup sau 10 phút
                    auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                    if auto_cleanup_cog:
                        auto_cleanup_cog.add_message_for_cleanup(view.message, delete_after=600)
                except Exception as e:
                    await ctx.send(f"❌ Lỗi khi phát nhạc: {e}")
            else:
                queue.add(data)
                
                # Detect platform để hiển thị icon đúng
                platform_info = "🎬 YouTube"
                
                embed = discord.Embed(title="📝 Đã thêm vào queue", description=f"**{data['title']}**", color=0x0099ff)
                embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                embed.add_field(name="Vị trí", value=f"#{len(queue.queue)}", inline=True)
                if data.get('uploader'):
                    embed.add_field(name="Kênh", value=data['uploader'], inline=True)
                if data.get('duration'):
                    embed.add_field(name="Thời lượng", value=self.format_duration(data['duration']), inline=True)
                if data.get('thumbnail'):
                    embed.set_thumbnail(url=data['thumbnail'])
                await ctx.send(embed=embed)

    @ChannelManager.music_only()
    @commands.command(name='pause')
    async def pause(self, ctx):
        """Tạm dừng nhạc"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Đã tạm dừng nhạc!")
        else:
            await ctx.send("❌ Không có nhạc đang phát!")

    @ChannelManager.music_only()
    @commands.command(name='resume')
    async def resume(self, ctx):
        """Tiếp tục phát nhạc"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Đã tiếp tục phát nhạc!")
        else:
            await ctx.send("❌ Nhạc không bị tạm dừng!")

    @ChannelManager.music_only()
    @commands.command(name='skip', aliases=['boqua'])
    async def skip(self, ctx):
        """Bỏ qua bài hát hiện tại"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Đã bỏ qua bài hát!")
        else:
            await ctx.send("❌ Không có nhạc đang phát!")

    @ChannelManager.music_only()
    @commands.command(name='stop')
    async def stop(self, ctx):
        """Dừng nhạc và xóa queue"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Đã dừng nhạc và rời khỏi voice channel!")
        else:
            await ctx.send("❌ Bot không ở trong voice channel!")

    @ChannelManager.music_only()
    @commands.command(name='queue', aliases=['hangcho'])
    async def show_queue(self, ctx):
        """Hiển thị queue nhạc"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.queue and not queue.current:
            await ctx.send("📝 Queue trống!")
            return

        embed = discord.Embed(title="🎵 Music Queue", color=0x0099ff)
        
        if queue.current:
            embed.add_field(
                name="🎵 Đang phát",
                value=f"**{queue.current['title']}**",
                inline=False
            )

        if queue.queue:
            queue_list = []
            for i, song in enumerate(list(queue.queue)[:10], 1):
                queue_list.append(f"**{i}.** {song['title']}")
            
            embed.add_field(
                name="📝 Tiếp theo",
                value="\n".join(queue_list),
                inline=False
            )
            
            if len(queue.queue) > 10:
                embed.add_field(
                    name="➕ Và hơn nữa",
                    value=f"**{len(queue.queue) - 10}** bài hát khác...",
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(name='clearqueue')
    async def clear_queue(self, ctx):
        """Xóa tất cả nhạc trong queue"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        await ctx.send("🗑️ Đã xóa tất cả nhạc trong queue!")

    @commands.command(name='shuffle')
    async def shuffle_queue(self, ctx):
        """Xáo trộn queue"""
        queue = self.get_queue(ctx.guild.id)
        if len(queue.queue) > 1:
            queue.shuffle()
            await ctx.send("🔀 Đã xáo trộn queue!")
        else:
            await ctx.send("❌ Cần ít nhất 2 bài hát trong queue để xáo trộn!")

    @ChannelManager.music_only()
    @commands.command(name='volume', aliases=['vol'])
    async def volume(self, ctx, volume: int = None):
        """Thay đổi âm lượng (0-100)"""
        if ctx.voice_client is None:
            return await ctx.send("❌ Bot không ở trong voice channel!")

        if volume is None:
            current_volume = int(ctx.voice_client.source.volume * 100) if hasattr(ctx.voice_client.source, 'volume') else 50
            await ctx.send(f"🔊 Âm lượng hiện tại: **{current_volume}%**")
            return

        if volume < 0 or volume > 100:
            await ctx.send("❌ Âm lượng phải từ 0 đến 100!")
            return

        if hasattr(ctx.voice_client.source, 'volume'):
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 Đã đặt âm lượng thành **{volume}%**")
        else:
            await ctx.send("❌ Không thể thay đổi âm lượng!")

    @commands.command(name='nowplaying', aliases=['np'])
    async def now_playing(self, ctx):
        """Hiển thị bài hát đang phát"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.current:
            await ctx.send("❌ Không có nhạc đang phát!")
            return

        current = queue.current
        embed = discord.Embed(
            title="🎵 Đang phát",
            description=f"**{current['title']}**",
            color=0x00ff00
        )
        
        if current.get('uploader'):
            embed.add_field(name="Kênh", value=current['uploader'], inline=True)
        if current.get('duration'):
            duration_str = self.format_duration(current['duration'])
            embed.add_field(name="Thời lượng", value=duration_str, inline=True)
        if current.get('thumbnail'):
            embed.set_thumbnail(url=current['thumbnail'])
        
        embed.add_field(name="URL", value=f"[Liên kết]({current['webpage_url']})", inline=False)
        
        await ctx.send(embed=embed)

    # =============== SLASH COMMANDS ===============
    
    @app_commands.command(name="play", description="Phát nhạc từ YouTube")
    @app_commands.describe(search="Tên bài hát hoặc URL YouTube")
    async def slash_play(self, interaction: discord.Interaction, search: str):
        """Slash command for playing music"""
        await self.play_command(interaction, search)
    
    @app_commands.command(name="pause", description="Tạm dừng nhạc")
    async def slash_pause(self, interaction: discord.Interaction):
        """Slash command for pausing music"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Đã tạm dừng nhạc!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có nhạc đang phát!", ephemeral=True)
    
    @app_commands.command(name="resume", description="Tiếp tục phát nhạc")
    async def slash_resume(self, interaction: discord.Interaction):
        """Slash command for resuming music"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Đã tiếp tục phát nhạc!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nhạc không bị tạm dừng!", ephemeral=True)
    
    @app_commands.command(name="skip", description="Bỏ qua bài hát hiện tại")
    async def slash_skip(self, interaction: discord.Interaction):
        """Slash command for skipping song"""
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Đã bỏ qua bài hát!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có nhạc đang phát!", ephemeral=True)
    
    @app_commands.command(name="stop", description="Dừng nhạc và rời khỏi voice channel")
    async def slash_stop(self, interaction: discord.Interaction):
        """Slash command for stopping music"""
        queue = self.get_queue(interaction.guild.id)
        queue.clear()
        
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Đã dừng nhạc và rời khỏi voice channel!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bot không ở trong voice channel!", ephemeral=True)
    
    @app_commands.command(name="queue", description="Hiển thị queue nhạc")
    async def slash_queue(self, interaction: discord.Interaction):
        """Slash command for showing queue"""
        await interaction.response.defer()
        
        queue = self.get_queue(interaction.guild.id)
        
        if not queue.queue and not queue.current:
            await interaction.followup.send("📝 Queue trống!")
            return

        embed = discord.Embed(title="🎵 Music Queue", color=0x0099ff)
        
        if queue.current:
            embed.add_field(
                name="🎵 Đang phát",
                value=f"**{queue.current['title']}**",
                inline=False
            )

        if queue.queue:
            queue_list = []
            for i, song in enumerate(list(queue.queue)[:10], 1):
                queue_list.append(f"**{i}.** {song['title']}")
            
            embed.add_field(
                name="📝 Tiếp theo",
                value="\n".join(queue_list),
                inline=False
            )
            
            if len(queue.queue) > 10:
                embed.add_field(
                    name="➕ Và hơn nữa",
                    value=f"**{len(queue.queue) - 10}** bài hát khác...",
                    inline=False
                )

        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="shuffle", description="Xáo trộn queue nhạc")
    async def slash_shuffle(self, interaction: discord.Interaction):
        """Slash command for shuffling queue"""
        queue = self.get_queue(interaction.guild.id)
        if len(queue.queue) > 1:
            queue.shuffle()
            await interaction.response.send_message("🔀 Đã xáo trộn queue!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Cần ít nhất 2 bài hát trong queue để xáo trộn!", ephemeral=True)
    
    @app_commands.command(name="volume", description="Thay đổi âm lượng (0-100)")
    @app_commands.describe(level="Mức âm lượng từ 0 đến 100")
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        """Slash command for changing volume"""
        if level < 0 or level > 100:
            await interaction.response.send_message("❌ Âm lượng phải từ 0 đến 100!", ephemeral=True)
            return
        
        if interaction.guild.voice_client is None:
            await interaction.response.send_message("❌ Bot không ở trong voice channel!", ephemeral=True)
            return

        if hasattr(interaction.guild.voice_client.source, 'volume'):
            interaction.guild.voice_client.source.volume = level / 100
            await interaction.response.send_message(f"🔊 Đã đặt âm lượng thành **{level}%**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không thể thay đổi âm lượng!", ephemeral=True)
    
    @app_commands.command(name="nowplaying", description="Hiển thị bài hát đang phát")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        """Slash command for now playing"""
        await interaction.response.defer()
        
        queue = self.get_queue(interaction.guild.id)
        
        if not queue.current:
            await interaction.followup.send("❌ Không có nhạc đang phát!", ephemeral=True)
            return

        current = queue.current
        embed = discord.Embed(
            title="🎵 Đang phát",
            description=f"**{current['title']}**",
            color=discord.Color.green()
        )
        
        if current.get('uploader'):
            embed.add_field(name="Kênh", value=current['uploader'], inline=True)
        if current.get('duration'):
            duration_str = self.format_duration(current['duration'])
            embed.add_field(name="Thời lượng", value=duration_str, inline=True)
        if current.get('thumbnail'):
            embed.set_thumbnail(url=current['thumbnail'])
        
        embed.add_field(name="URL", value=f"[Liên kết]({current['webpage_url']})", inline=False)
        
        # Add control panel
        view = MusicControlView(self.bot, interaction.guild.id)
        message = await interaction.followup.send(embed=embed, view=view)
        
        # Đăng ký message để auto cleanup sau 10 phút
        auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
        if auto_cleanup_cog:
            auto_cleanup_cog.add_message_for_cleanup(message, delete_after=600)
    
    @app_commands.command(name="clearqueue", description="Xóa tất cả nhạc trong queue")
    async def slash_clearqueue(self, interaction: discord.Interaction):
        """Slash command for clearing queue"""
        await interaction.response.defer()
        
        queue = self.get_queue(interaction.guild.id)
        queue.clear()
        
        embed = discord.Embed(
            title="🗑️ Queue đã được xóa",
            description="Đã xóa tất cả nhạc trong queue!",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="loop", description="Thay đổi chế độ lặp lại")
    @app_commands.describe(mode="Chế độ lặp: off, song, queue")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Tắt", value="off"),
        app_commands.Choice(name="Lặp bài hát", value="song"),
        app_commands.Choice(name="Lặp queue", value="queue")
    ])
    async def slash_loop(self, interaction: discord.Interaction, mode: str):
        """Slash command for loop mode"""
        queue = self.get_queue(interaction.guild.id)
        queue.loop_mode = mode
        
        mode_text = {
            "off": "🔄 Đã tắt chế độ lặp lại",
            "song": "🔂 Đã bật lặp lại bài hát hiện tại",
            "queue": "🔁 Đã bật lặp lại queue"
        }
        
        await interaction.response.send_message(mode_text.get(mode, "❌ Chế độ không hợp lệ!"), ephemeral=True)
    
    @app_commands.command(name="lyrics", description="Tìm lời bài hát")
    @app_commands.describe(song_name="Tên bài hát (để trống để lấy bài đang phát)")
    async def slash_lyrics(self, interaction: discord.Interaction, song_name: str = None):
        """Slash command for lyrics"""
        await interaction.response.defer()
        
        if not song_name:
            queue = self.get_queue(interaction.guild.id)
            if queue.current:
                song_name = queue.current.get('title', None)
            
            if not song_name:
                await interaction.followup.send("❌ Vui lòng cung cấp tên bài hát hoặc phát nhạc trước!", ephemeral=True)
                return
        
        embed = discord.Embed(
            title=f"🎵 Lyrics: {song_name}",
            description="Tính năng lyrics đang được phát triển...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
    
    # =============== PLAYLIST SLASH COMMANDS ===============
    
    @app_commands.command(name="playlist-create", description="Tạo playlist từ queue hiện tại")
    @app_commands.describe(name="Tên playlist")
    async def slash_playlist_create(self, interaction: discord.Interaction, name: str):
        """Slash command for creating playlist"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        music_queue = self.get_queue(interaction.guild.id)
        
        current_songs = []
        if music_queue.current:
            current_songs.append({
                'title': music_queue.current.get('title', 'Unknown'),
                'url': music_queue.current.get('webpage_url', ''),
                'duration': music_queue.current.get('duration', 0)
            })
        
        for song in music_queue.queue:
            current_songs.append({
                'title': song.get('title', 'Unknown'),
                'url': song.get('webpage_url', ''),
                'duration': song.get('duration', 0)
            })
        
        if not current_songs:
            await interaction.followup.send("❌ Không có bài hát nào trong queue để tạo playlist!", ephemeral=True)
            return
        
        music_queue.save_playlist(user_id, name, current_songs)
        
        embed = discord.Embed(
            title="✅ Playlist đã được tạo",
            description=f"Đã tạo playlist **{name}** với {len(current_songs)} bài hát!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="playlist-load", description="Load playlist vào queue")
    @app_commands.describe(name="Tên playlist")
    async def slash_playlist_load(self, interaction: discord.Interaction, name: str):
        """Slash command for loading playlist"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        music_queue = self.get_queue(interaction.guild.id)
        
        playlist_songs = music_queue.get_playlist(user_id, name)
        if not playlist_songs:
            await interaction.followup.send(f"❌ Không tìm thấy playlist **{name}**!", ephemeral=True)
            return
        
        queue = self.get_queue(interaction.guild.id)
        queue.clear()
        loaded_count = 0
        
        for song_data in playlist_songs:
            try:
                queue.add(song_data)
                loaded_count += 1
            except:
                continue
        
        embed = discord.Embed(
            title="✅ Playlist đã được load",
            description=f"Đã load {loaded_count} bài hát từ playlist **{name}** vào queue!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="playlist-list", description="Hiển thị tất cả playlist")
    async def slash_playlist_list(self, interaction: discord.Interaction):
        """Slash command for listing playlists"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        music_queue = self.get_queue(interaction.guild.id)
        
        playlists = music_queue.list_playlists(user_id)
        if not playlists:
            await interaction.followup.send("📝 Bạn chưa có playlist nào!", ephemeral=True)
            return
        
        embed = discord.Embed(title="🎵 Danh sách Playlist", color=discord.Color.blue())
        for i, playlist in enumerate(playlists, 1):
            song_count = len(music_queue.get_playlist(user_id, playlist))
            embed.add_field(name=f"{i}. {playlist}", value=f"{song_count} bài hát", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="playlist-show", description="Hiển thị chi tiết playlist")
    @app_commands.describe(name="Tên playlist")
    async def slash_playlist_show(self, interaction: discord.Interaction, name: str):
        """Slash command for showing playlist details"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        music_queue = self.get_queue(interaction.guild.id)
        
        playlist_songs = music_queue.get_playlist(user_id, name)
        if not playlist_songs:
            await interaction.followup.send(f"❌ Không tìm thấy playlist **{name}**!", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"🎵 Playlist: {name}", color=discord.Color.blue())
        
        total_duration = 0
        for i, song in enumerate(playlist_songs[:10], 1):
            duration = song.get('duration', 0)
            total_duration += duration
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "N/A"
            embed.add_field(
                name=f"{i}. {song['title'][:50]}",
                value=f"⏱️ {duration_str}",
                inline=False
            )
        
        if len(playlist_songs) > 10:
            embed.add_field(name="...", value=f"Và {len(playlist_songs)-10} bài khác", inline=False)
        
        total_duration_str = f"{total_duration//60}:{total_duration%60:02d}"
        embed.set_footer(text=f"Tổng cộng: {len(playlist_songs)} bài hát • {total_duration_str}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="playlist-delete", description="Xóa playlist")
    @app_commands.describe(name="Tên playlist")
    async def slash_playlist_delete(self, interaction: discord.Interaction, name: str):
        """Slash command for deleting playlist"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        music_queue = self.get_queue(interaction.guild.id)
        
        if music_queue.delete_playlist(user_id, name):
            embed = discord.Embed(
                title="✅ Playlist đã được xóa",
                description=f"Đã xóa playlist **{name}**!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Lỗi",
                description=f"Không tìm thấy playlist **{name}**!",
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed)
    
    # =============== FAVORITE SLASH COMMANDS ===============
    
    @app_commands.command(name="favorite-add", description="Thêm bài đang phát vào yêu thích")
    async def slash_favorite_add(self, interaction: discord.Interaction):
        """Slash command for adding to favorites"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        queue = self.get_queue(interaction.guild.id)
        
        if not queue.current:
            await interaction.followup.send("❌ Không có bài hát nào đang phát!", ephemeral=True)
            return
        
        song_data = {
            'title': queue.current.get('title', 'Unknown'),
            'url': queue.current.get('webpage_url', ''),
            'duration': queue.current.get('duration', 0)
        }
        
        favorites = queue.get_playlist(user_id, "Favorites")
        if not any(song['url'] == song_data['url'] for song in favorites):
            favorites.append(song_data)
            queue.save_playlist(user_id, "Favorites", favorites)
            
            embed = discord.Embed(
                title="❤️ Đã thêm vào yêu thích",
                description=f"Đã thêm **{song_data['title']}** vào danh sách yêu thích!",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ Đã tồn tại",
                description="Bài hát này đã có trong danh sách yêu thích!",
                color=discord.Color.orange()
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="favorite-list", description="Hiển thị danh sách yêu thích")
    async def slash_favorite_list(self, interaction: discord.Interaction):
        """Slash command for showing favorites"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        queue = self.get_queue(interaction.guild.id)
        
        favorites = queue.get_playlist(user_id, "Favorites")
        if not favorites:
            await interaction.followup.send("💔 Bạn chưa có bài hát yêu thích nào!", ephemeral=True)
            return
        
        embed = discord.Embed(title="❤️ Bài hát yêu thích", color=discord.Color.red())
        for i, song in enumerate(favorites[:10], 1):
            duration = song.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "N/A"
            embed.add_field(
                name=f"{i}. {song['title'][:50]}",
                value=f"⏱️ {duration_str}",
                inline=False
            )
        
        if len(favorites) > 10:
            embed.add_field(name="...", value=f"Và {len(favorites)-10} bài khác", inline=False)
        
        embed.set_footer(text=f"Tổng cộng: {len(favorites)} bài hát")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="favorite-play", description="Phát tất cả bài hát yêu thích")
    async def slash_favorite_play(self, interaction: discord.Interaction):
        """Slash command for playing favorites"""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        queue = self.get_queue(interaction.guild.id)
        
        favorites = queue.get_playlist(user_id, "Favorites")
        if not favorites:
            await interaction.followup.send("💔 Bạn chưa có bài hát yêu thích nào!", ephemeral=True)
            return
        
        # Load favorites vào queue
        current_queue = self.get_queue(interaction.guild.id)
        current_queue.clear()
        
        for song_data in favorites:
            current_queue.add(song_data)
        
        embed = discord.Embed(
            title="❤️ Đã load yêu thích",
            description=f"Đã load {len(favorites)} bài hát yêu thích vào queue!",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
    
    # =============== CONTROLS SLASH COMMAND ===============
    
    @app_commands.command(name="controls", description="Hiển thị bộ điều khiển nhạc")
    async def slash_controls(self, interaction: discord.Interaction):
        """Slash command for music controls"""
        await interaction.response.defer()
        
        queue = self.get_queue(interaction.guild.id)
        
        if queue.current:
            embed = discord.Embed(
                title="🎛️ Bộ điều khiển nhạc",
                description=f"**{queue.current['title']}**",
                color=discord.Color.green()
            )
            if queue.current.get('thumbnail'):
                embed.set_thumbnail(url=queue.current['thumbnail'])
        else:
            embed = discord.Embed(
                title="🎛️ Bộ điều khiển nhạc",
                description="Không có bài hát nào đang phát",
                color=discord.Color.blue()
            )
        
        view = MusicControlView(self.bot, interaction.guild.id)
        message = await interaction.followup.send(embed=embed, view=view)
        
        # Đăng ký message để auto cleanup sau 10 phút
        auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
        if auto_cleanup_cog:
            auto_cleanup_cog.add_message_for_cleanup(message, delete_after=600)

    @commands.command(name="playlist", aliases=["pl"])
    async def playlist_command(self, ctx, action=None, playlist_name=None, *, song_query=None):
        """Quản lý playlist: create, save, load, list, delete, add"""
        if not action:
            # Hướng dẫn sử dụng
            embed = discord.Embed(title="🎵 Playlist Commands", color=discord.Color.blue())
            embed.add_field(name="!playlist create <tên>", value="Tạo playlist từ queue hiện tại", inline=False)
            embed.add_field(name="!playlist add <tên> <bài hát>", value="Thêm bài hát vào playlist", inline=False)
            embed.add_field(name="!playlist load <tên>", value="Load playlist vào queue", inline=False)
            embed.add_field(name="!playlist list", value="Hiển thị tất cả playlist", inline=False)
            embed.add_field(name="!playlist show <tên>", value="Hiển thị chi tiết playlist", inline=False)
            embed.add_field(name="!playlist delete <tên>", value="Xóa playlist", inline=False)
            await ctx.send(embed=embed)
            return
            
        user_id = ctx.author.id
        music_queue = self.get_queue(ctx.guild.id)
        
        if action.lower() == "create" and playlist_name:
            # Tạo playlist mới từ queue hiện tại
            current_songs = []
            if music_queue.current:
                current_songs.append({
                    'title': music_queue.current.get('title', 'Unknown'),
                    'url': music_queue.current.get('webpage_url', ''),
                    'duration': music_queue.current.get('duration', 0)
                })
            
            for song in music_queue.queue:
                current_songs.append({
                    'title': song.get('title', 'Unknown'),
                    'url': song.get('webpage_url', ''),
                    'duration': song.get('duration', 0)
                })
            
            music_queue.save_playlist(user_id, playlist_name, current_songs)
            await ctx.send(f"✅ Đã tạo playlist **{playlist_name}** với {len(current_songs)} bài hát!")
            
        elif action.lower() == "add" and playlist_name and song_query:
            # Thêm bài hát vào playlist
            current_playlist = music_queue.get_playlist(user_id, playlist_name)
            if not current_playlist:
                await ctx.send(f"❌ Không tìm thấy playlist **{playlist_name}**!")
                return
            
            try:
                # Tìm bài hát
                ytdl = YTDLSource.ytdl
                info = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{song_query}", download=False))
                
                if 'entries' in info and len(info['entries']) > 0:
                    entry = info['entries'][0]
                    song_data = {
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('webpage_url', entry.get('url', '')),
                        'duration': entry.get('duration', 0)
                    }
                    current_playlist.append(song_data)
                    music_queue.save_playlist(user_id, playlist_name, current_playlist)
                    await ctx.send(f"✅ Đã thêm **{song_data['title']}** vào playlist **{playlist_name}**!")
                else:
                    await ctx.send("❌ Không tìm thấy bài hát!")
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi thêm bài hát: {str(e)}")
            
        elif action.lower() == "load" and playlist_name:
            # Load playlist vào queue
            playlist_songs = music_queue.get_playlist(user_id, playlist_name)
            if not playlist_songs:
                await ctx.send(f"❌ Không tìm thấy playlist **{playlist_name}**!")
                return
            
            queue = self.get_queue(ctx.guild.id)
            queue.clear()
            loaded_count = 0
            
            for song_data in playlist_songs:
                try:
                    queue.add(song_data)
                    loaded_count += 1
                except:
                    continue
            
            await ctx.send(f"✅ Đã load {loaded_count} bài hát từ playlist **{playlist_name}** vào queue!")
            
        elif action.lower() == "list":
            # Liệt kê tất cả playlist
            playlists = music_queue.list_playlists(user_id)
            if not playlists:
                await ctx.send("📝 Bạn chưa có playlist nào!")
                return
            
            embed = discord.Embed(title="🎵 Danh sách Playlist", color=discord.Color.blue())
            for i, playlist in enumerate(playlists, 1):
                song_count = len(music_queue.get_playlist(user_id, playlist))
                embed.add_field(name=f"{i}. {playlist}", value=f"{song_count} bài hát", inline=False)
            
            await ctx.send(embed=embed)
            
        elif action.lower() == "show" and playlist_name:
            # Hiển thị chi tiết playlist
            playlist_songs = music_queue.get_playlist(user_id, playlist_name)
            if not playlist_songs:
                await ctx.send(f"❌ Không tìm thấy playlist **{playlist_name}**!")
                return
            
            embed = discord.Embed(title=f"🎵 Playlist: {playlist_name}", color=discord.Color.blue())
            
            total_duration = 0
            for i, song in enumerate(playlist_songs[:10], 1):  # Hiển thị 10 bài đầu
                duration = song.get('duration', 0)
                total_duration += duration
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "N/A"
                embed.add_field(
                    name=f"{i}. {song['title'][:50]}",
                    value=f"⏱️ {duration_str}",
                    inline=False
                )
            
            if len(playlist_songs) > 10:
                embed.add_field(name="...", value=f"Và {len(playlist_songs)-10} bài khác", inline=False)
            
            total_duration_str = f"{total_duration//60}:{total_duration%60:02d}"
            embed.set_footer(text=f"Tổng cộng: {len(playlist_songs)} bài hát • {total_duration_str}")
            
            await ctx.send(embed=embed)
            
        elif action.lower() == "delete" and playlist_name:
            # Xóa playlist
            if music_queue.delete_playlist(user_id, playlist_name):
                await ctx.send(f"✅ Đã xóa playlist **{playlist_name}**!")
            else:
                await ctx.send(f"❌ Không tìm thấy playlist **{playlist_name}**!")

    @commands.command(name="lyrics", aliases=["lyr"])
    async def lyrics_command(self, ctx, *, song_name=None):
        """Tìm lời bài hát"""
        if not song_name:
            queue = self.get_queue(ctx.guild.id)
            if queue.current:
                song_name = queue.current.get('title', None)
            if not song_name:
                await ctx.send("❌ Vui lòng cung cấp tên bài hát hoặc phát nhạc trước!")
                return
        try:
            import re  # still potentially used later
            embed = discord.Embed(
                title=f"🎵 Lyrics: {song_name}",
                description="Tính năng lyrics đang được phát triển...",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tìm lời bài hát: {str(e)}")

    @commands.command(name="favorite", aliases=["fav"])
    async def favorite_command(self, ctx, action=None):
        """Quản lý bài hát yêu thích"""
        user_id = ctx.author.id
        queue = self.get_queue(ctx.guild.id)
        
        if action == "add":
            current_queue = self.get_queue(ctx.guild.id)
            if not current_queue.current:
                await ctx.send("❌ Không có bài hát nào đang phát!")
                return
            
            song_data = {
                'title': current_queue.current.get('title', 'Unknown'),
                'url': current_queue.current.get('webpage_url', ''),
                'duration': current_queue.current.get('duration', 0)
            }
            
            # Thêm vào playlist "Favorites"
            favorites = queue.get_playlist(user_id, "Favorites")
            if not any(song['url'] == song_data['url'] for song in favorites):
                favorites.append(song_data)
                queue.save_playlist(user_id, "Favorites", favorites)
                await ctx.send(f"❤️ Đã thêm **{song_data['title']}** vào danh sách yêu thích!")
            else:
                await ctx.send("❌ Bài hát này đã có trong danh sách yêu thích!")
                
        elif action == "list":
            favorites = queue.get_playlist(user_id, "Favorites")
            if not favorites:
                await ctx.send("💔 Bạn chưa có bài hát yêu thích nào!")
                return
            
            embed = discord.Embed(title="❤️ Bài hát yêu thích", color=discord.Color.red())
            for i, song in enumerate(favorites[:10], 1):
                duration = song.get('duration', 0)
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "N/A"
                embed.add_field(
                    name=f"{i}. {song['title'][:50]}",
                    value=f"⏱️ {duration_str}",
                    inline=False
                )
            
            if len(favorites) > 10:
                embed.add_field(name="...", value=f"Và {len(favorites)-10} bài khác", inline=False)
            
            embed.set_footer(text=f"Tổng cộng: {len(favorites)} bài hát")
            await ctx.send(embed=embed)
            
        elif action == "play":
            favorites = queue.get_playlist(user_id, "Favorites")
            if not favorites:
                await ctx.send("💔 Bạn chưa có bài hát yêu thích nào!")
                return
            
            # Load favorites vào queue
            current_queue = self.get_queue(ctx.guild.id)
            current_queue.clear()
            
            for song_data in favorites:
                current_queue.add(song_data)
            
            await ctx.send(f"❤️ Đã load {len(favorites)} bài hát yêu thích vào queue!")
        else:
            embed = discord.Embed(title="❤️ Favorite Commands", color=discord.Color.red())
            embed.add_field(name="!favorite add", value="Thêm bài đang phát vào yêu thích", inline=False)
            embed.add_field(name="!favorite list", value="Hiển thị danh sách yêu thích", inline=False)
            embed.add_field(name="!favorite play", value="Phát tất cả bài yêu thích", inline=False)
            await ctx.send(embed=embed)

    # Helper methods for menu system interactions
    async def play_command(self, interaction, query):
        """Helper method for play command via interaction"""
        try:
            await interaction.response.defer()
        except:
            # Interaction đã được xử lý rồi
            pass
        
        if not query.strip():
            try:
                await interaction.followup.send("❌ Vui lòng nhập tên bài hát hoặc URL!", ephemeral=True)
            except:
                pass
            return
        
        # Kiểm tra voice channel
        if not interaction.user.voice:
            try:
                await interaction.followup.send("❌ Bạn cần vào voice channel trước!", ephemeral=True)
            except:
                pass
            return
        
        voice_channel = interaction.user.voice.channel
        
        try:
            # Đảm bảo bot kết nối voice channel
            if not interaction.guild.voice_client:
                await voice_channel.connect()
                connection_msg = f"🔗 Đã kết nối tới **{voice_channel.name}**"
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)
                connection_msg = f"🔄 Đã chuyển tới **{voice_channel.name}**"
            else:
                connection_msg = None
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Không thể kết nối voice channel: {e}", ephemeral=True)
            except:
                pass
            return
        
        # Gửi thông báo tìm kiếm
        try:
            search_msg = await interaction.followup.send(f"🔍 Đang tìm kiếm: **{query}**...")
        except:
            search_msg = None
        
        try:
            url_pattern = re.compile(r'https?://')
            if url_pattern.match(query):
                loop = self.bot.loop or asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
                if 'entries' in data:
                    data = data['entries'][0]
            else:
                data = await YTDLSource.search_youtube(query)
            if not data:
                if search_msg:
                    await search_msg.edit(content="❌ Không tìm thấy bài hát trên YouTube!")
                return
            queue = self.get_queue(interaction.guild.id)
            voice_client = interaction.guild.voice_client
            if not voice_client.is_playing() and not voice_client.is_paused():
                try:
                    player = await self.create_player(data, interaction.guild.id)
                    queue.current = data
                    def after_playing(error):
                        if error:
                            print(f"Player error: {error}")
                        if voice_client and voice_client.is_connected():
                            fake_ctx = self.create_fake_context(interaction)
                            coro = self.play_next(fake_ctx)
                            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                    voice_client.play(player, after=after_playing)
                    
                    # Detect platform cho slash command
                    platform_info = "🎬 YouTube"
                    
                    embed = discord.Embed(title="🎵 Đang phát", description=f"**{player.title}**", color=discord.Color.green())
                    embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                    if player.uploader:
                        embed.add_field(name="Kênh", value=player.uploader, inline=True)
                    if data.get('duration'):
                        embed.add_field(name="Thời lượng", value=self.format_duration(data['duration']), inline=True)
                    if player.thumbnail:
                        embed.set_thumbnail(url=player.thumbnail)
                    if connection_msg:
                        embed.add_field(name="Trạng thái", value=connection_msg, inline=False)
                    if search_msg:
                        await search_msg.edit(content="", embed=embed)
                    else:
                        await interaction.followup.send(embed=embed)
                    try:
                        await asyncio.sleep(1)
                        control_embed = discord.Embed(title="🎛️ Bộ điều khiển nhạc", description=f"**{player.title}**", color=discord.Color.green())
                        view = MusicControlView(self.bot, interaction.guild.id)
                        control_message = await interaction.followup.send(embed=control_embed, view=view)
                        
                        # Đăng ký message để auto cleanup sau 10 phút
                        auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                        if auto_cleanup_cog:
                            auto_cleanup_cog.add_message_for_cleanup(control_message, delete_after=600)
                    except:
                        pass
                except Exception as e:
                    if search_msg:
                        await search_msg.edit(content=f"❌ Lỗi khi phát nhạc: {e}")
                    else:
                        await interaction.followup.send(f"❌ Lỗi khi phát nhạc: {e}")
            else:
                queue.add(data)
                
                # Detect platform cho queue message
                platform_info = "🎬 YouTube"
                
                embed = discord.Embed(title="📝 Đã thêm vào queue", description=f"**{data['title']}**", color=discord.Color.blurple())
                embed.add_field(name="Nền tảng", value=platform_info, inline=True)
                embed.add_field(name="Vị trí", value=f"#{len(queue.queue)}", inline=True)
                if data.get('uploader'):
                    embed.add_field(name="Kênh", value=data['uploader'], inline=True)
                if data.get('duration'):
                    embed.add_field(name="Thời lượng", value=self.format_duration(data['duration']), inline=True)
                if data.get('thumbnail'):
                    embed.set_thumbnail(url=data['thumbnail'])
                if search_msg:
                    await search_msg.edit(content="", embed=embed)
                    # Đăng ký search message để auto cleanup
                    auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                    if auto_cleanup_cog:
                        auto_cleanup_cog.add_message_for_cleanup(search_msg, delete_after=300)  # 5 phút cho message thêm vào queue
                else:
                    queue_message = await interaction.followup.send(embed=embed)
                    # Đăng ký message để auto cleanup
                    auto_cleanup_cog = self.bot.get_cog('AutoCleanupCog')
                    if auto_cleanup_cog:
                        auto_cleanup_cog.add_message_for_cleanup(queue_message, delete_after=300)
        except Exception as e:
            if search_msg:
                await search_msg.edit(content=f"❌ Lỗi: {e}")
            else:
                try:
                    await interaction.followup.send(f"❌ Lỗi: {e}")
                except:
                    pass

    @commands.command(name='hqaudio')
    async def hq_audio(self, ctx, mode: str = None):
        """Bật/tắt tối ưu âm thanh (normalize). Dùng: !hqaudio on/off"""
        if mode is None:
            cfg = self.hq_settings.get(ctx.guild.id, {'normalize': False})
            await ctx.send(f"🎧 HQ Normalize: {'ON' if cfg.get('normalize') else 'OFF'}")
            return
        mode = mode.lower()
        if mode in ("on", "normalize"):
            self.hq_settings.setdefault(ctx.guild.id, {})['normalize'] = True
            await ctx.send("🎧 Đã bật loudness normalization!")
        elif mode in ("off", "disable"):
            self.hq_settings.setdefault(ctx.guild.id, {})['normalize'] = False
            await ctx.send("🎧 Đã tắt loudness normalization!")
        else:
            await ctx.send("❌ Tham số không hợp lệ! Dùng: on/off")

    @app_commands.command(name="hqaudio", description="Bật/tắt tối ưu âm thanh (normalize)")
    @app_commands.describe(mode="on/off")
    async def slash_hqaudio(self, interaction: discord.Interaction, mode: str = ""):
        mode = mode.lower()
        if mode in ("on", "normalize"):
            self.hq_settings.setdefault(interaction.guild.id, {})['normalize'] = True
            await interaction.response.send_message("🎧 Đã bật loudness normalization!", ephemeral=True)
        elif mode in ("off", "disable"):
            self.hq_settings.setdefault(interaction.guild.id, {})['normalize'] = False
            await interaction.response.send_message("🎧 Đã tắt loudness normalization!", ephemeral=True)
        else:
            cfg = self.hq_settings.get(interaction.guild.id, {'normalize': False})
            await interaction.response.send_message(f"🎧 HQ Normalize: {'ON' if cfg.get('normalize') else 'OFF'} (dùng /hqaudio on|off)", ephemeral=True)

    @commands.command(name='autodj')
    async def autodj_command(self, ctx, mode: str = None):
        """Bật/tắt Auto DJ 24/7 - phát nhạc liên tục khi hết queue"""
        queue = self.get_queue(ctx.guild.id)
        
        if mode is None:
            status = "🟢 BẬT" if queue.auto_dj_24_7 else "🔴 TẮT" 
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7",
                description=f"**Trạng thái:** {status}",
                color=discord.Color.green() if queue.auto_dj_24_7 else discord.Color.red()
            )
            embed.add_field(
                name="ℹ️ Thông tin",
                value="Auto DJ sẽ tự động phát nhạc liên quan khi hết bài trong queue",
                inline=False
            )
            embed.add_field(
                name="📝 Cách dùng",
                value="`!autodj on` - Bật\n`!autodj off` - Tắt",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        mode = mode.lower()
        if mode in ["on", "enable", "start", "1"]:
            queue.auto_dj_24_7 = True
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7 - Đã BẬT",
                description="Bot sẽ tự động phát nhạc liên tục khi hết queue!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="🎶 Tính năng",
                value="• Phát nhạc liên quan đến bài vừa nghe\n• Tự động tìm nhạc trending\n• Không bao giờ im lặng\n• Thông minh dựa trên lịch sử",
                inline=False
            )
            embed.set_footer(text="Gõ !autodj off để tắt")
            await ctx.send(embed=embed)
            
        elif mode in ["off", "disable", "stop", "0"]:
            queue.auto_dj_24_7 = False
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7 - Đã TẮT",
                description="Bot sẽ dừng khi hết nhạc trong queue",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Tham số không hợp lệ! Dùng: `!autodj on` hoặc `!autodj off`")

    @app_commands.command(name="autodj", description="Bật/tắt Auto DJ 24/7 - phát nhạc liên tục")
    @app_commands.describe(mode="on/off")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Bật", value="on"),
        app_commands.Choice(name="Tắt", value="off")
    ])
    async def slash_autodj(self, interaction: discord.Interaction, mode: str = ""):
        await interaction.response.defer()
        
        queue = self.get_queue(interaction.guild.id)
        
        if not mode:
            status = "🟢 BẬT" if queue.auto_dj_24_7 else "🔴 TẮT"
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7",
                description=f"**Trạng thái:** {status}",
                color=discord.Color.green() if queue.auto_dj_24_7 else discord.Color.red()
            )
            embed.add_field(
                name="ℹ️ Thông tin", 
                value="Auto DJ sẽ tự động phát nhạc liên quan khi hết bài trong queue",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return
        
        mode = mode.lower()
        if mode == "on":
            queue.auto_dj_24_7 = True
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7 - Đã BẬT",
                description="Bot sẽ tự động phát nhạc liên tục khi hết queue!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="🎶 Tính năng",
                value="• Phát nhạc liên quan đến bài vừa nghe\n• Tự động tìm nhạc trending\n• Không bao giờ im lặng\n• Thông minh dựa trên lịch sử",
                inline=False
            )
            embed.set_footer(text="Dùng /autodj off để tắt")
            await interaction.followup.send(embed=embed)
            
        elif mode == "off":
            queue.auto_dj_24_7 = False
            embed = discord.Embed(
                title="🎵 Auto DJ 24/7 - Đã TẮT", 
                description="Bot sẽ dừng khi hết nhạc trong queue",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))