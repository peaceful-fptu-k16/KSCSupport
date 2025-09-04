import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import re
from typing import Optional

class Scheduler(commands.Cog):
    """📅 Lịch & Nhắc nhở - Quản lý lịch trình và nhắc nhở"""
    
    def __init__(self, bot):
        self.bot = bot
        self.reminder_check.start()
    
    def cog_unload(self):
        self.reminder_check.cancel()
    
    @tasks.loop(seconds=30)
    async def reminder_check(self):
        """Check for pending reminders every 30 seconds"""
        try:
            reminders = await self.bot.db.get_pending_reminders()
            
            for reminder in reminders:
                reminder_id, user_id, channel_id, guild_id, message, remind_time = reminder
                
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        user = self.bot.get_user(user_id)
                        
                        embed = discord.Embed(
                            title="⏰ Nhắc nhở!",
                            description=message,
                            color=0x7289DA
                        )
                        embed.add_field(name="Cho", value=user.mention if user else f"<@{user_id}>", inline=False)
                        embed.set_footer(text="GenZ Assistant Reminder")
                        
                        await channel.send(embed=embed)
                    
                    # Mark as completed
                    await self.bot.db.complete_reminder(reminder_id)
                    
                except Exception as e:
                    print(f"Error sending reminder {reminder_id}: {e}")
                    
        except Exception as e:
            print(f"Error checking reminders: {e}")
    
    @reminder_check.before_loop
    async def before_reminder_check(self):
        await self.bot.wait_until_ready()
    
    def parse_time(self, time_str: str) -> Optional[timedelta]:
        """Parse time string into timedelta"""
        time_regex = re.match(r'^(\d+)([smhd])$', time_str.lower())
        if not time_regex:
            return None
        
        amount, unit = time_regex.groups()
        amount = int(amount)
        
        if unit == 's':
            return timedelta(seconds=amount)
        elif unit == 'm':
            return timedelta(minutes=amount)
        elif unit == 'h':
            return timedelta(hours=amount)
        elif unit == 'd':
            return timedelta(days=amount)
        
        return None
    
    @commands.command(name='remindme', aliases=['remind', 'nhacnho'])
    async def remind_me(self, ctx, time_str: str = None, *, message: str = None):
        """Tạo nhắc nhở
        
        Ví dụ: !remindme 10m học bài
        Đơn vị: s (giây), m (phút), h (giờ), d (ngày)
        """
        if not time_str or not message:
            embed = discord.Embed(
                title="❓ Thiếu thông tin",
                description=f"Sử dụng: `{self.bot.config['prefix']}remindme <thời gian> <tin nhắn>`\n"
                           f"Ví dụ: `{self.bot.config['prefix']}remindme 10m học bài`\n"
                           f"Đơn vị: s (giây), m (phút), h (giờ), d (ngày)",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        time_delta = self.parse_time(time_str)
        if not time_delta:
            embed = discord.Embed(
                title="❌ Định dạng thời gian sai",
                description="Định dạng: số + đơn vị (s/m/h/d)\nVí dụ: 10m, 2h, 1d",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if time_delta.total_seconds() < 10:
            embed = discord.Embed(
                title="❌ Thời gian quá ngắn",
                description="Thời gian nhắc nhở phải ít nhất 10 giây!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if time_delta.days > 365:
            embed = discord.Embed(
                title="❌ Thời gian quá dài",
                description="Thời gian nhắc nhở tối đa là 365 ngày!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        remind_time = datetime.now() + time_delta
        
        try:
            reminder_id = await self.bot.db.add_reminder(
                ctx.author.id,
                ctx.channel.id, 
                ctx.guild.id,
                message,
                remind_time
            )
            
            embed = discord.Embed(
                title="✅ Đã tạo nhắc nhở",
                description=f"Tôi sẽ nhắc bạn sau {time_str}",
                color=0x00FF00
            )
            embed.add_field(name="📝 Tin nhắn", value=message, inline=False)
            embed.add_field(name="⏰ Thời gian", value=remind_time.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
            embed.set_footer(text=f"ID: {reminder_id}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Không thể tạo nhắc nhở. Thử lại sau!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            print(f"Error creating reminder: {e}")
    
    @commands.command(name='schedule', aliases=['lich'])
    async def schedule_event(self, ctx, time_str: str = None, *, event: str = None):
        """Lên lịch một sự kiện (tương tự remindme nhưng với tên khác)"""
        await self.remind_me(ctx, time_str, message=event)
    
    @commands.command(name='todo', aliases=['todolist'])
    async def todo_list(self, ctx, action: str = None, *, task: str = None):
        """Quản lý danh sách việc cần làm
        
        !todo add <task> - Thêm việc
        !todo list - Xem danh sách
        !todo done <id> - Hoàn thành việc
        !todo remove <id> - Xóa việc
        """
        if not action:
            embed = discord.Embed(
                title="📝 Todo List - Hướng dẫn",
                description=f"**Các lệnh có sẵn:**\n"
                           f"`{self.bot.config['prefix']}todo add <việc cần làm>` - Thêm việc mới\n"
                           f"`{self.bot.config['prefix']}todo list` - Xem danh sách\n"
                           f"`{self.bot.config['prefix']}todo done <id>` - Đánh dấu hoàn thành\n"
                           f"`{self.bot.config['prefix']}todo remove <id>` - Xóa việc",
                color=0x7289DA
            )
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action in ['add', 'them']:
            if not task:
                embed = discord.Embed(
                    title="❌ Thiếu nội dung",
                    description=f"Sử dụng: `{self.bot.config['prefix']}todo add <việc cần làm>`",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
                return
            
            try:
                todo_id = await self.bot.db.add_todo(ctx.author.id, ctx.guild.id, task)
                
                embed = discord.Embed(
                    title="✅ Đã thêm việc mới",
                    description=task,
                    color=0x00FF00
                )
                embed.set_footer(text=f"ID: {todo_id}")
                await ctx.send(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Không thể thêm việc. Thử lại sau!",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
        
        elif action in ['list', 'xem']:
            try:
                todos = await self.bot.db.get_todos(ctx.author.id, ctx.guild.id)
                
                if not todos:
                    embed = discord.Embed(
                        title="📝 Todo List trống",
                        description="Bạn chưa có việc nào cần làm!",
                        color=0x7289DA
                    )
                    await ctx.send(embed=embed)
                    return
                
                embed = discord.Embed(
                    title=f"📝 Todo List của {ctx.author.display_name}",
                    color=0x7289DA
                )
                
                pending_tasks = []
                completed_tasks = []
                
                for todo_id, task, completed, created_at in todos:
                    status = "✅" if completed else "⏳"
                    task_text = f"`{todo_id}` {status} {task}"
                    
                    if completed:
                        completed_tasks.append(task_text)
                    else:
                        pending_tasks.append(task_text)
                
                if pending_tasks:
                    embed.add_field(
                        name="⏳ Đang chờ",
                        value="\n".join(pending_tasks[:10]),
                        inline=False
                    )
                
                if completed_tasks:
                    embed.add_field(
                        name="✅ Đã hoàn thành",
                        value="\n".join(completed_tasks[:5]),
                        inline=False
                    )
                
                embed.set_footer(text=f"Tổng cộng: {len(todos)} việc")
                await ctx.send(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Không thể lấy danh sách todo!",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
        
        elif action in ['done', 'complete', 'xong']:
            if not task or not task.isdigit():
                embed = discord.Embed(
                    title="❌ Thiếu ID",
                    description=f"Sử dụng: `{self.bot.config['prefix']}todo done <id>`",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
                return
            
            todo_id = int(task)
            
            try:
                success = await self.bot.db.complete_todo(todo_id, ctx.author.id)
                
                if success:
                    embed = discord.Embed(
                        title="✅ Đã hoàn thành",
                        description=f"Việc ID {todo_id} đã được đánh dấu hoàn thành!",
                        color=0x00FF00
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Không tìm thấy",
                        description=f"Không tìm thấy việc ID {todo_id} hoặc đã hoàn thành rồi!",
                        color=0xFF0000
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Không thể cập nhật todo!",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
        
        elif action in ['remove', 'delete', 'xoa']:
            if not task or not task.isdigit():
                embed = discord.Embed(
                    title="❌ Thiếu ID",
                    description=f"Sử dụng: `{self.bot.config['prefix']}todo remove <id>`",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
                return
            
            todo_id = int(task)
            
            try:
                success = await self.bot.db.delete_todo(todo_id, ctx.author.id)
                
                if success:
                    embed = discord.Embed(
                        title="🗑️ Đã xóa",
                        description=f"Việc ID {todo_id} đã được xóa!",
                        color=0x00FF00
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Không tìm thấy",
                        description=f"Không tìm thấy việc ID {todo_id}!",
                        color=0xFF0000
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Không thể xóa todo!",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
        
        else:
            embed = discord.Embed(
                title="❌ Lệnh không hợp lệ",
                description="Các lệnh hợp lệ: add, list, done, remove",
                color=0xFF0000
            )
            await ctx.send(embed=embed)

    # Helper methods for menu system interactions
    async def reminders_command(self, interaction):
        """Helper method for viewing reminders via interaction"""
        await interaction.response.defer()
        
        try:
            reminders = await self.bot.db.get_user_reminders(interaction.user.id)
            
            if not reminders:
                embed = discord.Embed(
                    title="📋 Danh sách Reminders",
                    description="Bạn chưa có reminder nào!",
                    color=0x7289DA
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="📋 Danh sách Reminders của bạn",
                color=0x7289DA
            )
            
            for i, reminder in enumerate(reminders[:10], 1):  # Limit to 10
                reminder_id, user_id, channel_id, guild_id, message, remind_time, created_at = reminder
                
                # Format time
                time_str = remind_time.strftime("%d/%m/%Y %H:%M")
                
                embed.add_field(
                    name=f"{i}. Reminder #{reminder_id}",
                    value=f"📝 {message[:100]}{'...' if len(message) > 100 else ''}\n⏰ {time_str}",
                    inline=False
                )
            
            if len(reminders) > 10:
                embed.add_field(
                    name="...",
                    value=f"Và {len(reminders) - 10} reminder khác",
                    inline=False
                )
            
            embed.set_footer(text=f"Tổng cộng: {len(reminders)} reminders")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Không thể tải danh sách reminders!",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)

    async def remind_command(self, interaction, time_str, message):
        """Helper method for creating reminder via interaction"""
        await interaction.response.defer()
        
        try:
            # Parse time using the same logic as remind_me command
            time_amount = self.parse_time(time_str)
            if not time_amount:
                await interaction.followup.send("❌ Định dạng thời gian không hợp lệ! Sử dụng: 30s, 5m, 2h, 1d", ephemeral=True)
                return
            
            # Calculate remind time
            from datetime import datetime, timedelta
            remind_time = datetime.now() + timedelta(seconds=time_amount)
            
            # Save to database
            reminder_id = await self.bot.db.add_reminder(
                user_id=interaction.user.id,
                channel_id=interaction.channel.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                message=message,
                remind_time=remind_time
            )
            
            # Confirmation embed
            embed = discord.Embed(
                title="✅ Reminder đã được tạo!",
                description=f"📝 **Nội dung:** {message}\n⏰ **Thời gian:** {remind_time.strftime('%d/%m/%Y %H:%M:%S')}\n🆔 **ID:** #{reminder_id}",
                color=0x00FF00
            )
            embed.set_footer(text="Bot sẽ nhắc nhở bạn khi đến giờ!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Lỗi tạo reminder",
                description="Có lỗi xảy ra khi tạo reminder. Vui lòng thử lại!",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
