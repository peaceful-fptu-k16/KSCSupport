import discord # type: ignore
from discord.ext import commands, tasks # type: ignore
import asyncio
from datetime import datetime, timedelta
import sqlite3
import os

class AutoCleanupCog(commands.Cog):
    """Tự động xóa tin nhắn của bot sau một khoảng thời gian"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/cleanup_messages.db"
        self.init_database()
        self.cleanup_task.start()
        self.old_messages_cleanup.start()
        
    def init_database(self):
        """Khởi tạo database để lưu trữ thông tin tin nhắn"""
        os.makedirs("data", exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_messages (
                id INTEGER PRIMARY KEY,
                message_id INTEGER,
                channel_id INTEGER,
                guild_id INTEGER,
                timestamp DATETIME,
                delete_after INTEGER DEFAULT 300
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def add_message_for_cleanup(self, message, delete_after=300):
        """Thêm tin nhắn vào danh sách chờ xóa (mặc định 5 phút = 300 giây)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bot_messages (message_id, channel_id, guild_id, timestamp, delete_after)
            VALUES (?, ?, ?, ?, ?)
        ''', (message.id, message.channel.id, message.guild.id if message.guild else None, 
              datetime.now(), delete_after))
        
        conn.commit()
        conn.close()
        
    @tasks.loop(minutes=1)  # Chạy mỗi phút
    async def cleanup_task(self):
        """Task chính để xóa tin nhắn đã hết hạn"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Lấy tin nhắn đã hết hạn
            cursor.execute('''
                SELECT message_id, channel_id, guild_id, id 
                FROM bot_messages 
                WHERE datetime('now') > datetime(timestamp, '+' || delete_after || ' seconds')
            ''')
            
            expired_messages = cursor.fetchall()
            
            for message_id, channel_id, guild_id, db_id in expired_messages:
                try:
                    # Lấy channel
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        # Nếu không tìm thấy channel, xóa khỏi database
                        cursor.execute('DELETE FROM bot_messages WHERE id = ?', (db_id,))
                        continue
                    
                    # Lấy và xóa tin nhắn
                    message = await channel.fetch_message(message_id)
                    if message and message.author.id == self.bot.user.id:
                        await message.delete()
                        print(f"✅ Đã xóa tin nhắn {message_id} trong {channel.name}")
                    
                    # Xóa khỏi database
                    cursor.execute('DELETE FROM bot_messages WHERE id = ?', (db_id,))
                    
                except discord.NotFound:
                    # Tin nhắn đã bị xóa rồi
                    cursor.execute('DELETE FROM bot_messages WHERE id = ?', (db_id,))
                except discord.Forbidden:
                    # Không có quyền xóa
                    cursor.execute('DELETE FROM bot_messages WHERE id = ?', (db_id,))
                    print(f"❌ Không có quyền xóa tin nhắn {message_id}")
                except Exception as e:
                    print(f"❌ Lỗi khi xóa tin nhắn {message_id}: {e}")
                    cursor.execute('DELETE FROM bot_messages WHERE id = ?', (db_id,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Lỗi trong cleanup task: {e}")
    
    @tasks.loop(hours=1)  # Chạy mỗi giờ
    async def old_messages_cleanup(self):
        """Xóa các tin nhắn cũ của bot (hơn 10 phút) trong tất cả channels"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=10)
            
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    try:
                        # Kiểm tra quyền
                        if not channel.permissions_for(guild.me).read_message_history:
                            continue
                            
                        if not channel.permissions_for(guild.me).manage_messages:
                            continue
                        
                        # Lấy tin nhắn của bot cũ hơn 10 phút
                        async for message in channel.history(limit=50, before=cutoff_time):
                            if message.author.id == self.bot.user.id:
                                try:
                                    await message.delete()
                                    print(f"🧹 Đã xóa tin nhắn cũ {message.id} trong {channel.name}")
                                    await asyncio.sleep(0.5)  # Tránh rate limit
                                except discord.NotFound:
                                    pass
                                except discord.Forbidden:
                                    break  # Dừng nếu không có quyền
                                except Exception as e:
                                    print(f"❌ Lỗi xóa tin nhắn cũ: {e}")
                                    
                    except discord.Forbidden:
                        continue
                    except Exception as e:
                        print(f"❌ Lỗi khi duyệt channel {channel.name}: {e}")
                        
        except Exception as e:
            print(f"❌ Lỗi trong old messages cleanup: {e}")
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()
        
    @old_messages_cleanup.before_loop
    async def before_old_cleanup_task(self):
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Tự động đăng ký tin nhắn của bot để xóa sau 5 phút"""
        # Chỉ theo dõi tin nhắn của bot
        if message.author.id == self.bot.user.id:
            # Không theo dõi tin nhắn DM
            if not message.guild:
                return
                
            # Thêm vào danh sách chờ xóa (5 phút = 300 giây)
            self.add_message_for_cleanup(message, delete_after=300)

    @commands.command(name="cleanup_stats")
    @commands.has_permissions(administrator=True)
    async def cleanup_stats(self, ctx):
        """Xem thống kê cleanup (chỉ admin)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM bot_messages')
            total_pending = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM bot_messages 
                WHERE datetime('now') > datetime(timestamp, '+' || delete_after || ' seconds')
            ''')
            ready_to_delete = cursor.fetchone()[0]
            
            conn.close()
            
            embed = discord.Embed(
                title="🧹 Auto Cleanup Stats",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📊 Thống kê",
                value=f"**Tin nhắn chờ xóa:** {total_pending}\n**Sẵn sàng xóa:** {ready_to_delete}",
                inline=False
            )
            embed.add_field(
                name="⚙️ Cấu hình",
                value="**Tự động xóa:** 5 phút\n**Dọn dẹp cũ:** 10 phút\n**Tần suất:** Mỗi phút",
                inline=False
            )
            embed.set_footer(text="KSC Support Auto Cleanup System")
            
            # Đăng ký tin nhắn này để xóa sau 2 phút
            msg = await ctx.send(embed=embed)
            self.add_message_for_cleanup(msg, delete_after=120)
            
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
    
    @commands.command(name="manual_cleanup")
    @commands.has_permissions(administrator=True)
    async def manual_cleanup(self, ctx, minutes: int = 10):
        """Dọn dẹp tin nhắn bot cũ hơn X phút (chỉ admin)"""
        if minutes < 1 or minutes > 60:
            await ctx.send("❌ Thời gian phải từ 1-60 phút!")
            return
            
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            deleted_count = 0
            
            await ctx.send(f"🧹 Bắt đầu dọn dẹp tin nhắn cũ hơn {minutes} phút...")
            
            async for message in ctx.channel.history(limit=100, before=cutoff_time):
                if message.author.id == self.bot.user.id:
                    try:
                        await message.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.5)
                    except:
                        pass
            
            result_msg = await ctx.send(f"✅ Đã xóa {deleted_count} tin nhắn cũ!")
            self.add_message_for_cleanup(result_msg, delete_after=120)
            
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
    
    def cog_unload(self):
        """Dừng tasks khi unload cog"""
        self.cleanup_task.cancel()
        self.old_messages_cleanup.cancel()

async def setup(bot):
    await bot.add_cog(AutoCleanupCog(bot))
