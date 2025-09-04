import discord # type: ignore
from discord.ext import commands # type: ignore
import json
import os
import asyncio
import logging
from dotenv import load_dotenv # type: ignore
from utils.database import DatabaseManager

# Load environment variables
# Ưu tiên .env.local (cho development) rồi mới .env (template)
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("🔧 Loaded development environment (.env.local)")
else:
    load_dotenv()
    print("🔧 Loaded production environment (.env)")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GenZAssistant(commands.Bot):
    def __init__(self):
        # Load configuration
        with open('config.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # Cần cho welcome/goodbye events
        intents.guilds = True   # Cần cho server events
        
        # Initialize bot
        super().__init__(
            command_prefix=self.config['prefix'],
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        # Initialize database
        self.db = DatabaseManager(self.config['database_path'])
        
    async def setup_hook(self):
        """Setup hook called when bot is starting up"""
        # Initialize database
        await self.db.initialize()
        
        # Load all cogs - Clean organized structure
        cogs_to_load = [
            # Core Music System
            'cogs.music_manager',        # Music conflict management system
            'cogs.universal_music',      # Universal Music Player (Mix SC+YT)
            'cogs.music',               # YouTube music player
            'cogs.soundcloud_advanced',  # Advanced SoundCloud features
            
            # Voice Features
            'cogs.temp_voice',          # Temporary Voice Channels (Join-to-Create)
            
            # Interactive & UI
            'cogs.interactive',          # Button-based command interface
            'cogs.menu_system',         # Menu navigation system
            
            # Bot Features
            'cogs.fun',                 # Fun commands and entertainment
            'cogs.games',               # Mini games and interactive content
            'cogs.ai',                  # AI chat and responses
            'cogs.ai_image_gen',        # AI image generation
            'cogs.admin',               # Administration and moderation
            'cogs.scheduler',           # Reminders and scheduling
            'cogs.utils_commands',      # Utility commands
            
            # System & Analytics
            'cogs.events',              # Server events and logging
            'cogs.analytics',           # Server analytics and stats
            'cogs.cleanup',             # Auto cleanup and maintenance
            'cogs.lol_integration'      # League of Legends integration
        ]
        
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f'Loaded {cog}')
            except Exception as e:
                logger.error(f'Failed to load {cog}: {e}')
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} slash commands')
        except Exception as e:
            logger.error(f'Failed to sync slash commands: {e}')
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{self.config['prefix']}help | /ask | KSC Support"
        )
        await self.change_presence(activity=activity)
    
    async def on_message(self, message):
        """Process messages"""
        if message.author.bot:
            return
        
        # Process commands
        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            # Don't respond to unknown commands to avoid spam
            return
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Không đủ quyền",
                description="Bạn không có quyền sử dụng lệnh này!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Cooldown",
                description=f"Vui lòng đợi {error.retry_after:.1f} giây trước khi sử dụng lệnh này lại!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f'Command error: {error}')
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Đã xảy ra lỗi khi thực hiện lệnh!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)

# Custom help command
class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Hiển thị menu trợ giúp',
            'aliases': ['h']
        })
    
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="🤖 GenZ Assistant - Menu Trợ Giúp",
            description="Bot đa chức năng dành cho GenZ! Dưới đây là các danh mục lệnh:",
            color=0x7289DA
        )
        
        categories = {
            "🎮 Giải trí": "fun",
            "🧠 AI & ChatGPT": "ai", 
            "📅 Lịch & Nhắc nhở": "scheduler",
            " Mini Games": "games",
            "🛠️ Quản trị": "admin",
            "⚙️ Tiện ích": "utils"
        }
        
        for category, cog_name in categories.items():
            cog = self.context.bot.get_cog(cog_name)
            if cog:
                commands_list = [cmd.name for cmd in cog.get_commands()][:5]
                if commands_list:
                    embed.add_field(
                        name=category,
                        value=f"`{'`, `'.join(commands_list)}`{'...' if len(cog.get_commands()) > 5 else ''}",
                        inline=True
                    )
        
        embed.add_field(
            name="📖 Cách sử dụng",
            value=f"Dùng `{self.context.prefix}help [lệnh]` để xem chi tiết một lệnh cụ thể",
            inline=False
        )
        
        embed.set_footer(text="GenZ Assistant • Made with ❤️")
        await self.get_destination().send(embed=embed)

async def main():
    """Main function to run the bot"""
    bot = GenZAssistant()
    bot.help_command = CustomHelpCommand()
    
    # Get token from environment or config
    token = os.getenv('DISCORD_BOT_TOKEN') or bot.config.get('bot_token')
    
    if not token or token == "YOUR_DISCORD_BOT_TOKEN_HERE":
        logger.error("Discord bot token not found! Please set DISCORD_BOT_TOKEN in .env file or config.json")
        return
    
    try:
        async with bot:
            await bot.start(token)
    except discord.LoginFailure:
        logger.error("Invalid bot token!")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
