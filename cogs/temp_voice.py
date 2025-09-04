import discord
from discord.ext import commands
import json
import os
import asyncio
import logging
from utils.channel_manager import ChannelManager

logger = logging.getLogger(__name__)

class TempVoice(commands.Cog):
    """Auto Voice Channel / Join-to-Create VC System"""
    
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = {}  # {user_id: channel_id}
        self.temp_channel_settings = {}  # {guild_id: settings}
        self.data_file = "data/temp_voice_settings.json"
        self.load_settings()
    
    def load_settings(self):
        """Load temporary voice settings from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.temp_channel_settings = json.load(f)
            else:
                self.temp_channel_settings = {}
        except Exception as e:
            logger.error(f"Error loading temp voice settings: {e}")
            self.temp_channel_settings = {}
    
    def save_settings(self):
        """Save temporary voice settings to file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.temp_channel_settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving temp voice settings: {e}")
    
    def get_guild_settings(self, guild_id: int):
        """Get settings for a specific guild"""
        return self.temp_channel_settings.get(str(guild_id), {
            'enabled': False,
            'join_to_create_channel': None,
            'temp_channel_category': None,
            'default_name': "🎤 {user}'s Channel",
            'default_limit': 0,
            'auto_delete': True,
            'channel_prefix': "🎤"
        })
    
    @commands.hybrid_group(name='tempvc', description='Quản lý Temporary Voice Channels')
    @commands.has_permissions(manage_channels=True)
    async def tempvc(self, ctx):
        """Temporary Voice Channel management commands"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎤 Temporary Voice Channels",
                description="Hệ thống tạo voice channel tạm thời tự động",
                color=0x3498DB
            )
            embed.add_field(
                name="📝 Commands",
                value="`/tempvc setup` - Thiết lập hệ thống\n"
                      "`/tempvc enable` - Bật hệ thống\n"
                      "`/tempvc disable` - Tắt hệ thống\n"
                      "`/tempvc config` - Xem cấu hình\n"
                      "`/tempvc settings` - Thay đổi cài đặt",
                inline=False
            )
            embed.add_field(
                name="ℹ️ Cách hoạt động",
                value="• Tham gia **Join to Create** channel\n"
                      "• Bot tự động tạo voice channel riêng cho bạn\n"
                      "• Khi rời khỏi channel → tự động xóa\n"
                      "• Có thể tùy chỉnh tên, giới hạn người, v.v.",
                inline=False
            )
            await ctx.send(embed=embed)
    
    @tempvc.command(name='setup', description='Thiết lập Temporary Voice Channel system')
    @commands.has_permissions(manage_channels=True)
    async def setup_tempvc(self, ctx):
        """Setup the temporary voice channel system"""
        guild = ctx.guild
        guild_id = str(guild.id)
        
        try:
            # Create category for temp voice channels if not exists
            category = discord.utils.get(guild.categories, name="🎤 Temp Voice Channels")
            if not category:
                category = await guild.create_category("🎤 Temp Voice Channels")
            
            # Create the "Join to Create" channel
            join_channel = discord.utils.get(guild.voice_channels, name="➕ Join to Create")
            if not join_channel:
                join_channel = await guild.create_voice_channel(
                    "➕ Join to Create", 
                    category=category,
                    user_limit=1
                )
            
            # Update settings
            settings = self.get_guild_settings(int(guild_id))
            settings.update({
                'enabled': True,
                'join_to_create_channel': join_channel.id,
                'temp_channel_category': category.id
            })
            self.temp_channel_settings[guild_id] = settings
            self.save_settings()
            
            embed = discord.Embed(
                title="✅ Thiết lập thành công!",
                description="Hệ thống Temporary Voice Channel đã được cấu hình",
                color=0x27AE60
            )
            embed.add_field(
                name="📁 Category",
                value=category.mention,
                inline=True
            )
            embed.add_field(
                name="➕ Join Channel",
                value=join_channel.mention,
                inline=True
            )
            embed.add_field(
                name="🎯 Cách sử dụng",
                value=f"Tham gia {join_channel.mention} để tạo voice channel riêng!",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Lỗi thiết lập",
                description=f"Không thể thiết lập: {str(e)}",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
    
    @tempvc.command(name='enable', description='Bật hệ thống Temporary Voice Channel')
    @commands.has_permissions(manage_channels=True)
    async def enable_tempvc(self, ctx):
        """Enable the temporary voice channel system"""
        guild_id = str(ctx.guild.id)
        settings = self.get_guild_settings(int(guild_id))
        
        if not settings.get('join_to_create_channel'):
            embed = discord.Embed(
                title="⚠️ Chưa thiết lập",
                description="Vui lòng chạy `/tempvc setup` trước!",
                color=0xF39C12
            )
            await ctx.send(embed=embed)
            return
        
        settings['enabled'] = True
        self.temp_channel_settings[guild_id] = settings
        self.save_settings()
        
        embed = discord.Embed(
            title="✅ Đã bật",
            description="Hệ thống Temporary Voice Channel đã được kích hoạt!",
            color=0x27AE60
        )
        await ctx.send(embed=embed)
    
    @tempvc.command(name='disable', description='Tắt hệ thống Temporary Voice Channel')
    @commands.has_permissions(manage_channels=True)
    async def disable_tempvc(self, ctx):
        """Disable the temporary voice channel system"""
        guild_id = str(ctx.guild.id)
        settings = self.get_guild_settings(int(guild_id))
        settings['enabled'] = False
        self.temp_channel_settings[guild_id] = settings
        self.save_settings()
        
        embed = discord.Embed(
            title="❌ Đã tắt",
            description="Hệ thống Temporary Voice Channel đã được vô hiệu hóa!",
            color=0xE74C3C
        )
        await ctx.send(embed=embed)
    
    @tempvc.command(name='config', description='Xem cấu hình hiện tại')
    async def config_tempvc(self, ctx):
        """Show current configuration"""
        guild_id = str(ctx.guild.id)
        settings = self.get_guild_settings(int(guild_id))
        
        embed = discord.Embed(
            title="⚙️ Cấu hình Temporary Voice Channel",
            color=0x3498DB
        )
        
        # Status
        status = "🟢 Đang bật" if settings['enabled'] else "🔴 Đang tắt"
        embed.add_field(name="Trạng thái", value=status, inline=True)
        
        # Join to Create Channel
        join_channel = ctx.guild.get_channel(settings.get('join_to_create_channel'))
        join_channel_name = join_channel.mention if join_channel else "❌ Không tìm thấy"
        embed.add_field(name="Join Channel", value=join_channel_name, inline=True)
        
        # Category
        category = ctx.guild.get_channel(settings.get('temp_channel_category'))
        category_name = category.name if category else "❌ Không tìm thấy"
        embed.add_field(name="Category", value=category_name, inline=True)
        
        # Settings
        embed.add_field(name="Tên mặc định", value=settings['default_name'], inline=True)
        embed.add_field(name="Giới hạn người", value=settings['default_limit'] or "Không giới hạn", inline=True)
        embed.add_field(name="Tự động xóa", value="✅" if settings['auto_delete'] else "❌", inline=True)
        
        # Active temp channels
        guild_temp_channels = [ch_id for user_id, ch_id in self.temp_channels.items() 
                              if ctx.guild.get_channel(ch_id) is not None]
        embed.add_field(
            name="Temp Channels hiện tại", 
            value=f"{len(guild_temp_channels)} channels", 
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @tempvc.command(name='settings', description='Thay đổi cài đặt')
    @commands.has_permissions(manage_channels=True)
    async def settings_tempvc(self, ctx, setting: str = None, *, value: str = None):
        """Change settings for temporary voice channels"""
        if not setting:
            embed = discord.Embed(
                title="⚙️ Cài đặt có thể thay đổi",
                color=0x3498DB
            )
            embed.add_field(
                name="📝 Cách sử dụng",
                value="`/tempvc settings <setting> <value>`",
                inline=False
            )
            embed.add_field(
                name="🔧 Settings",
                value="• `name` - Tên mặc định channel\n"
                      "• `limit` - Giới hạn người (0 = không giới hạn)\n"
                      "• `prefix` - Prefix cho tên channel\n"
                      "• `auto_delete` - Tự động xóa (true/false)",
                inline=False
            )
            embed.add_field(
                name="💡 Ví dụ",
                value="`/tempvc settings name 🎤 {user}'s Room`\n"
                      "`/tempvc settings limit 5`\n"
                      "`/tempvc settings prefix 🎵`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        settings = self.get_guild_settings(int(guild_id))
        
        if setting.lower() == 'name':
            settings['default_name'] = value
            self.temp_channel_settings[guild_id] = settings
            self.save_settings()
            
            embed = discord.Embed(
                title="✅ Đã cập nhật",
                description=f"Tên mặc định: `{value}`",
                color=0x27AE60
            )
            await ctx.send(embed=embed)
            
        elif setting.lower() == 'limit':
            try:
                limit = int(value)
                if limit < 0 or limit > 99:
                    raise ValueError("Limit must be 0-99")
                
                settings['default_limit'] = limit
                self.temp_channel_settings[guild_id] = settings
                self.save_settings()
                
                embed = discord.Embed(
                    title="✅ Đã cập nhật",
                    description=f"Giới hạn người: `{limit if limit > 0 else 'Không giới hạn'}`",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            except ValueError:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Giới hạn phải là số từ 0-99",
                    color=0xE74C3C
                )
                await ctx.send(embed=embed)
                
        elif setting.lower() == 'prefix':
            settings['channel_prefix'] = value
            self.temp_channel_settings[guild_id] = settings
            self.save_settings()
            
            embed = discord.Embed(
                title="✅ Đã cập nhật",
                description=f"Prefix: `{value}`",
                color=0x27AE60
            )
            await ctx.send(embed=embed)
            
        elif setting.lower() == 'auto_delete':
            if value.lower() in ['true', '1', 'yes', 'on']:
                auto_delete = True
            elif value.lower() in ['false', '0', 'no', 'off']:
                auto_delete = False
            else:
                embed = discord.Embed(
                    title="❌ Lỗi",
                    description="Giá trị phải là `true` hoặc `false`",
                    color=0xE74C3C
                )
                await ctx.send(embed=embed)
                return
            
            settings['auto_delete'] = auto_delete
            self.temp_channel_settings[guild_id] = settings
            self.save_settings()
            
            embed = discord.Embed(
                title="✅ Đã cập nhật",
                description=f"Tự động xóa: `{'Bật' if auto_delete else 'Tắt'}`",
                color=0x27AE60
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Setting không hợp lệ! Dùng `/tempvc settings` để xem danh sách.",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name='vc', description='Quản lý voice channel cá nhân của bạn')
    async def vc_control(self, ctx, action: str = None, *, value: str = None):
        """Control your personal voice channel"""
        user_id = ctx.author.id
        
        if user_id not in self.temp_channels:
            embed = discord.Embed(
                title="❌ Không tìm thấy",
                description="Bạn không có voice channel tạm thời nào!",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.guild.get_channel(self.temp_channels[user_id])
        if not channel:
            # Clean up invalid channel
            del self.temp_channels[user_id]
            embed = discord.Embed(
                title="❌ Channel không tồn tại",
                description="Channel của bạn đã bị xóa.",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
            return
        
        if not action:
            embed = discord.Embed(
                title="🎤 Quản lý Voice Channel",
                description=f"Channel hiện tại: {channel.mention}",
                color=0x3498DB
            )
            embed.add_field(
                name="📝 Commands",
                value="`/vc name <tên>` - Đổi tên channel\n"
                      "`/vc limit <số>` - Đặt giới hạn người\n"
                      "`/vc lock` - Khóa channel\n"
                      "`/vc unlock` - Mở khóa channel\n"
                      "`/vc hide` - Ẩn channel\n"
                      "`/vc show` - Hiện channel\n"
                      "`/vc invite <@user>` - Mời người vào\n"
                      "`/vc kick <@user>` - Kick người ra\n"
                      "`/vc delete` - Xóa channel",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        try:
            if action.lower() == 'name':
                if not value:
                    embed = discord.Embed(
                        title="❌ Thiếu tên",
                        description="Vui lòng cung cấp tên mới cho channel!",
                        color=0xE74C3C
                    )
                    await ctx.send(embed=embed)
                    return
                
                await channel.edit(name=value[:32])  # Discord limit
                embed = discord.Embed(
                    title="✅ Đã đổi tên",
                    description=f"Channel: {channel.mention}",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'limit':
                if not value:
                    embed = discord.Embed(
                        title="❌ Thiếu số",
                        description="Vui lòng cung cấp giới hạn người (0-99)!",
                        color=0xE74C3C
                    )
                    await ctx.send(embed=embed)
                    return
                
                limit = int(value)
                if limit < 0 or limit > 99:
                    raise ValueError("Invalid limit")
                
                await channel.edit(user_limit=limit)
                embed = discord.Embed(
                    title="✅ Đã đặt giới hạn",
                    description=f"Giới hạn: {limit if limit > 0 else 'Không giới hạn'}",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'lock':
                await channel.set_permissions(ctx.guild.default_role, connect=False)
                embed = discord.Embed(
                    title="🔒 Đã khóa channel",
                    description="Chỉ những người đã ở trong channel mới có thể tham gia",
                    color=0xF39C12
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'unlock':
                await channel.set_permissions(ctx.guild.default_role, connect=None)
                embed = discord.Embed(
                    title="🔓 Đã mở khóa channel",
                    description="Mọi người có thể tham gia channel",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'hide':
                await channel.set_permissions(ctx.guild.default_role, view_channel=False)
                embed = discord.Embed(
                    title="👁️ Đã ẩn channel",
                    description="Channel không hiển thị với người khác",
                    color=0xF39C12
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'show':
                await channel.set_permissions(ctx.guild.default_role, view_channel=None)
                embed = discord.Embed(
                    title="👁️ Đã hiện channel",
                    description="Channel hiển thị với mọi người",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'invite':
                if not ctx.message.mentions:
                    embed = discord.Embed(
                        title="❌ Thiếu người dùng",
                        description="Vui lòng tag người bạn muốn mời!",
                        color=0xE74C3C
                    )
                    await ctx.send(embed=embed)
                    return
                
                user = ctx.message.mentions[0]
                await channel.set_permissions(user, connect=True)
                embed = discord.Embed(
                    title="✅ Đã mời",
                    description=f"Đã mời {user.mention} vào channel",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'kick':
                if not ctx.message.mentions:
                    embed = discord.Embed(
                        title="❌ Thiếu người dùng",
                        description="Vui lòng tag người bạn muốn kick!",
                        color=0xE74C3C
                    )
                    await ctx.send(embed=embed)
                    return
                
                user = ctx.message.mentions[0]
                if user.voice and user.voice.channel == channel:
                    await user.move_to(None)
                await channel.set_permissions(user, connect=False)
                embed = discord.Embed(
                    title="✅ Đã kick",
                    description=f"Đã kick {user.mention} khỏi channel",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            elif action.lower() == 'delete':
                await channel.delete(reason=f"Deleted by owner {ctx.author}")
                if user_id in self.temp_channels:
                    del self.temp_channels[user_id]
                embed = discord.Embed(
                    title="✅ Đã xóa channel",
                    description="Voice channel của bạn đã được xóa",
                    color=0x27AE60
                )
                await ctx.send(embed=embed)
                
            else:
                embed = discord.Embed(
                    title="❌ Action không hợp lệ",
                    description="Dùng `/vc` để xem danh sách commands!",
                    color=0xE74C3C
                )
                await ctx.send(embed=embed)
                
        except ValueError:
            embed = discord.Embed(
                title="❌ Giá trị không hợp lệ",
                description="Vui lòng kiểm tra lại giá trị bạn nhập!",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Không có quyền",
                description="Bot không có quyền thực hiện hành động này!",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Lỗi",
                description=f"Đã xảy ra lỗi: {str(e)}",
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for temporary channels"""
        guild_id = str(member.guild.id)
        settings = self.get_guild_settings(int(guild_id))
        
        if not settings['enabled']:
            return
        
        join_channel_id = settings.get('join_to_create_channel')
        category_id = settings.get('temp_channel_category')
        
        if not join_channel_id or not category_id:
            return
        
        # User joined the "Join to Create" channel
        if after.channel and after.channel.id == join_channel_id:
            await self.create_temp_channel(member, settings)
        
        # User left a voice channel
        if before.channel and settings['auto_delete']:
            await self.check_temp_channel_empty(before.channel, settings)
    
    async def create_temp_channel(self, member, settings):
        """Create a temporary voice channel for the user"""
        try:
            guild = member.guild
            category = guild.get_channel(settings['temp_channel_category'])
            
            if not category:
                logger.error(f"Category not found for guild {guild.id}")
                return
            
            # Generate channel name
            channel_name = settings['default_name'].format(user=member.display_name)
            if len(channel_name) > 32:
                channel_name = channel_name[:29] + "..."
            
            # Create the temporary channel
            temp_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                user_limit=settings['default_limit']
            )
            
            # Set permissions - owner has manage permissions
            await temp_channel.set_permissions(
                member, 
                manage_channels=True,
                manage_permissions=True,
                move_members=True,
                mute_members=True,
                deafen_members=True
            )
            
            # Move user to the new channel
            await member.move_to(temp_channel)
            
            # Track the channel
            self.temp_channels[member.id] = temp_channel.id
            
            logger.info(f"Created temp channel {temp_channel.name} for {member} in {guild.name}")
            
        except discord.Forbidden:
            logger.error(f"No permission to create temp channel in {guild.name}")
        except Exception as e:
            logger.error(f"Error creating temp channel: {e}")
    
    async def check_temp_channel_empty(self, channel, settings):
        """Check if temp channel is empty and delete if so"""
        try:
            # Check if this is a temp channel
            temp_channel_owner = None
            for user_id, ch_id in list(self.temp_channels.items()):
                if ch_id == channel.id:
                    temp_channel_owner = user_id
                    break
            
            if not temp_channel_owner:
                return  # Not a temp channel
            
            # Check if channel is empty
            if len(channel.members) == 0:
                await channel.delete(reason="Temporary channel auto-cleanup")
                
                # Remove from tracking
                if temp_channel_owner in self.temp_channels:
                    del self.temp_channels[temp_channel_owner]
                
                logger.info(f"Auto-deleted empty temp channel {channel.name}")
                
        except discord.NotFound:
            # Channel already deleted
            if temp_channel_owner and temp_channel_owner in self.temp_channels:
                del self.temp_channels[temp_channel_owner]
        except Exception as e:
            logger.error(f"Error checking temp channel: {e}")

async def setup(bot):
    await bot.add_cog(TempVoice(bot))
