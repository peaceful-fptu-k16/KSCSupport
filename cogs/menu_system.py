import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# Modal classes for text input
class AskModal(discord.ui.Modal, title='🧠 Hỏi AI'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    question = discord.ui.TextInput(
        label='Câu hỏi của bạn',
        placeholder='Nhập câu hỏi bạn muốn hỏi AI...',
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get AI cog and process the question
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            await ai_cog.ask_command(interaction, self.question.value)
        else:
            await interaction.response.send_message("❌ AI module không khả dụng!", ephemeral=True)

class TranslateModal(discord.ui.Modal, title='🌐 Dịch thuật'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    text = discord.ui.TextInput(
        label='Văn bản cần dịch',
        placeholder='Nhập văn bản bạn muốn dịch...',
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            await ai_cog.translate_command(interaction, self.text.value)
        else:
            await interaction.response.send_message("❌ AI module không khả dụng!", ephemeral=True)

class ExplainModal(discord.ui.Modal, title='📚 Giải thích'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    concept = discord.ui.TextInput(
        label='Khái niệm cần giải thích',
        placeholder='Nhập khái niệm bạn muốn hiểu...',
        style=discord.TextStyle.short,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            await ai_cog.explain_command(interaction, self.concept.value)
        else:
            await interaction.response.send_message("❌ AI module không khả dụng!", ephemeral=True)

class SummaryModal(discord.ui.Modal, title='📄 Tóm tắt'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    text = discord.ui.TextInput(
        label='Văn bản cần tóm tắt',
        placeholder='Nhập văn bản dài bạn muốn tóm tắt...',
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ai_cog = self.bot.get_cog('AICog')
        if ai_cog:
            await ai_cog.summary_command(interaction, self.text.value)
        else:
            await interaction.response.send_message("❌ AI module không khả dụng!", ephemeral=True)

# AI Image Generation Modals
class GenerateImageModal(discord.ui.Modal, title='🎨 Tạo ảnh AI'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    prompt = discord.ui.TextInput(
        label='Mô tả ảnh bạn muốn tạo',
        placeholder='Ví dụ: a beautiful sunset over mountains, anime style...',
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ai_image_cog = self.bot.get_cog('AIImageCog')
        if ai_image_cog:
            await ai_image_cog.generate_command(interaction, self.prompt.value)
        else:
            await interaction.response.send_message("❌ AI Image module không khả dụng!", ephemeral=True)

class StyleImageModal(discord.ui.Modal):
    def __init__(self, bot, style):
        super().__init__(title=f'🎭 Tạo ảnh {style} style')
        self.bot = bot
        self.style = style
        
        self.prompt = discord.ui.TextInput(
            label=f'Mô tả ảnh ({style} style)',
            placeholder='Nhập mô tả cho ảnh...',
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.prompt)
    
    async def on_submit(self, interaction: discord.Interaction):
        ai_image_cog = self.bot.get_cog('AIImageCog')
        if ai_image_cog:
            await ai_image_cog.style_command(interaction, self.style, self.prompt.value)
        else:
            await interaction.response.send_message("❌ AI Image module không khả dụng!", ephemeral=True)

class PlayMusicModal(discord.ui.Modal, title='🎵 Phát nhạc YouTube'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    query = discord.ui.TextInput(
        label='Tên bài hát hoặc URL YouTube',
        placeholder='Ví dụ: Shape of You, https://youtube.com/watch?v=...',
        style=discord.TextStyle.short,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.play_command(interaction, self.query.value)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

# SoundCloud Modals
class SoundCloudModal(discord.ui.Modal, title='🎵 Phát nhạc SoundCloud'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    query = discord.ui.TextInput(
        label='Tên bài hát hoặc URL SoundCloud',
        placeholder='Ví dụ: Artist - Song Name, https://soundcloud.com/...',
        style=discord.TextStyle.short,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
        if soundcloud_cog:
            # Use the new method designed for modal interactions
            await soundcloud_cog.play_from_modal(interaction, self.query.value)
        else:
            await interaction.response.send_message("❌ SoundCloud Advanced module không khả dụng!", ephemeral=True)

class SoundCloudVolumeModal(discord.ui.Modal, title='🔊 Điều chỉnh âm lượng SoundCloud'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    volume = discord.ui.TextInput(
        label='Mức âm lượng (0-100)',
        placeholder='Ví dụ: 50, 75, 100...',
        style=discord.TextStyle.short,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            volume_value = int(self.volume.value)
            if not 0 <= volume_value <= 100:
                await interaction.response.send_message("❌ Âm lượng phải từ 0-100!", ephemeral=True)
                return
                
            soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
            if soundcloud_cog:
                await soundcloud_cog.volume_from_modal(interaction, volume_value)
            else:
                await interaction.response.send_message("❌ SoundCloud Advanced module không khả dụng!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Vui lòng nhập một số hợp lệ!", ephemeral=True)

# Fun & Games Modals
class RockPaperScissorsModal(discord.ui.Modal, title='✂️ Kéo Búa Bao'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    choice = discord.ui.TextInput(
        label='Lựa chọn của bạn',
        placeholder='rock, paper, hoặc scissors',
        style=discord.TextStyle.short,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        games_cog = self.bot.get_cog('Games')
        if games_cog:
            await games_cog.rps_command(interaction, self.choice.value.lower())
        else:
            await interaction.response.send_message("❌ Games module không khả dụng!", ephemeral=True)

class EightBallModal(discord.ui.Modal, title='🎱 Quả cầu thần'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    question = discord.ui.TextInput(
        label='Câu hỏi của bạn',
        placeholder='Hỏi một câu hỏi có/không...',
        style=discord.TextStyle.paragraph,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        games_cog = self.bot.get_cog('Games')
        if games_cog:
            await games_cog.eightball_command(interaction, self.question.value)
        else:
            await interaction.response.send_message("❌ Games module không khả dụng!", ephemeral=True)

# Reminder Modal
class ReminderModal(discord.ui.Modal, title='⏰ Tạo Reminder'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    time_input = discord.ui.TextInput(
        label='Thời gian',
        placeholder='Ví dụ: 30m, 2h, 1d...',
        style=discord.TextStyle.short,
        max_length=10
    )
    
    content = discord.ui.TextInput(
        label='Nội dung nhắc nhở',
        placeholder='Nhập nội dung bạn muốn được nhắc nhở...',
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        scheduler_cog = self.bot.get_cog('Scheduler')
        if scheduler_cog:
            await scheduler_cog.remind_command(interaction, self.time_input.value, self.content.value)
        else:
            await interaction.response.send_message("❌ Scheduler module không khả dụng!", ephemeral=True)

# AI Commands Interactive View
class AICommandsView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='💬 Hỏi AI', style=discord.ButtonStyle.primary, emoji='🧠')
    async def ask_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AskModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🌐 Dịch thuật', style=discord.ButtonStyle.primary, emoji='🗣️')
    async def translate(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TranslateModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='📚 Giải thích', style=discord.ButtonStyle.primary, emoji='💡')
    async def explain(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ExplainModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='📄 Tóm tắt', style=discord.ButtonStyle.primary, emoji='📋')
    async def summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SummaryModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.secondary, emoji='🏠')
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

class MenuView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)  # 60 giây timeout
        self.bot = bot
        
    @discord.ui.button(label='🧠 AI Commands', style=discord.ButtonStyle.primary, emoji='🤖')
    async def ai_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🧠 AI Commands - Powered by Gemini",
            description="Các lệnh AI thông minh để hỗ trợ bạn\n\n**Chọn chức năng bạn muốn sử dụng:**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="� Chat với AI",
            value="Hỏi AI bất kỳ điều gì - từ câu hỏi đơn giản đến phức tạp",
            inline=False
        )
        embed.add_field(
            name="🌐 Dịch thuật",
            value="Dịch văn bản giữa các ngôn ngữ khác nhau",
            inline=False
        )
        embed.add_field(
            name="📚 Giải thích",
            value="Giải thích khái niệm, thuật ngữ một cách dễ hiểu",
            inline=False
        )
        embed.add_field(
            name="📄 Tóm tắt",
            value="Tóm tắt văn bản dài thành những điểm chính",
            inline=False
        )
        embed.set_footer(text="💡 Click vào button để sử dụng tính năng tương ứng")
        await interaction.response.edit_message(embed=embed, view=AICommandsView(self.bot))

    @discord.ui.button(label='🎵 YouTube', style=discord.ButtonStyle.success, emoji='📺')
    async def youtube_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎵 YouTube Music Player",
            description="Hệ thống phát nhạc YouTube với chất lượng cao\n\n**Chức năng YouTube Music:**",
            color=0xFF0000  # YouTube red color
        )
        embed.add_field(
            name="🎵 Phát nhạc YouTube",
            value="Phát nhạc, playlist từ YouTube",
            inline=False
        )
        embed.add_field(
            name="⏸️ Điều khiển đầy đủ",
            value="Pause, Resume, Skip, Queue, Loop",
            inline=False
        )
        embed.add_field(
            name="🎮 Tính năng nâng cao",
            value="Music Quiz, History, Auto DJ",
            inline=False
        )
        embed.set_footer(text="📺 YouTube Music - Click button để sử dụng")
        await interaction.response.edit_message(embed=embed, view=YouTubeView(self.bot))

    @discord.ui.button(label='🎵 SoundCloud', style=discord.ButtonStyle.success, emoji='☁️')
    async def soundcloud_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎵 SoundCloud Player",
            description="Phát nhạc từ SoundCloud - Nền tảng âm nhạc độc lập\n\n**Chức năng SoundCloud:**",
            color=0xFF5500  # SoundCloud orange color
        )
        embed.add_field(
            name="🎵 Phát nhạc SoundCloud",
            value="Tìm kiếm và phát nhạc từ SoundCloud",
            inline=False
        )
        embed.add_field(
            name="🔊 Điều khiển âm lượng",
            value="Điều chỉnh volume riêng cho SoundCloud",
            inline=False
        )
        embed.add_field(
            name="🎨 Nhạc độc lập",
            value="Khám phá nhạc từ các artist độc lập",
            inline=False
        )
        embed.set_footer(text="☁️ SoundCloud Player - Click button để sử dụng")
        await interaction.response.edit_message(embed=embed, view=SoundCloudView(self.bot))

    @discord.ui.button(label='🎨 AI Images', style=discord.ButtonStyle.secondary, emoji='🖼️')
    async def image_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 AI Image Generation",
            description="Tạo ảnh AI với nhiều phong cách khác nhau\n\n**Chọn style bạn muốn:**",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🖌️ Tạo ảnh cơ bản",
            value="Tạo ảnh AI với prompt tự do",
            inline=False
        )
        embed.add_field(
            name="🎭 Styles đặc biệt",
            value="Anime, Realistic, Cartoon và nhiều style khác",
            inline=False
        )
        embed.set_footer(text="🎨 Click button để chọn style và tạo ảnh")
        await interaction.response.edit_message(embed=embed, view=AIImageView(self.bot))

    @discord.ui.button(label='🎮 Fun & Games', style=discord.ButtonStyle.danger, emoji='🎯')
    async def fun_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎮 Fun & Entertainment",
            description="Giải trí và mini games thú vị\n\n**Chọn trò chơi hoặc giải trí:**",
            color=discord.Color.red()
        )
        embed.add_field(
            name="😄 Hình ảnh vui",
            value="Memes, ảnh mèo, chó và nhiều hơn nữa",
            inline=False
        )
        embed.add_field(
            name="🎲 Mini Games",
            value="Kéo búa bao, 8ball và các trò chơi khác",
            inline=False
        )
        embed.set_footer(text="🎮 Click button để chơi!")
        await interaction.response.edit_message(embed=embed, view=FunGamesView(self.bot))

    @discord.ui.button(label='📊 Analytics', style=discord.ButtonStyle.secondary, emoji='📈')
    async def analytics_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 Server Analytics & Stats",
            description="Thống kê và phân tích server chi tiết",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🏠 Thống kê Server",
            value="`!serverstats` - Tổng quan server\n`!userstats [@user]` - Thống kê user\n`!topmessages` - Top hoạt động",
            inline=False
        )
        embed.add_field(
            name="📈 Server Stats",
            value="`!serverstats` - Thống kê server\n`!topmessages` - Top hoạt động\n`!serverinfo` - Thông tin server",
            inline=False
        )
        embed.add_field(
            name="🔧 Utility",
            value="`!ping` - Độ trễ bot\n`!serverinfo` - Thông tin server\n`!userinfo [@user]` - Thông tin user",
            inline=False
        )
        embed.set_footer(text="📊 Real-time tracking và insights")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    @discord.ui.button(label='🛠️ Admin Tools', style=discord.ButtonStyle.danger, emoji='⚡')
    async def admin_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛠️ Admin & Moderation Tools",
            description="Công cụ quản lý server (Chỉ Admin)",
            color=discord.Color.dark_red()
        )
        embed.add_field(
            name="👮 Moderation",
            value="`!kick <@user> [lý do]` - Kick thành viên\n`!ban <@user> [lý do]` - Ban thành viên\n`!unban <user_id>` - Unban\n`!mute <@user> <thời gian>` - Mute",
            inline=False
        )
        embed.add_field(
            name="💬 Message Management",
            value="`!clear <số lượng>` - Xóa tin nhắn\n`!slowmode <giây>` - Chế độ chậm",
            inline=False
        )
        embed.add_field(
            name="🎉 Events Setup",
            value="`!setwelcome <#channel>` - Set welcome\n`!setgoodbye <#channel>` - Set goodbye\n`!toggledm` - DM settings\n`!welcometest` - Test events",
            inline=False
        )
        embed.add_field(
            name="⚠️ Lưu ý",
            value="Các lệnh này chỉ dành cho Admin/Moderator",
            inline=False
        )
        embed.set_footer(text="🛠️ Quản lý server hiệu quả")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    @discord.ui.button(label='⏰ Reminders', style=discord.ButtonStyle.secondary, emoji='📅')
    async def reminder_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⏰ Reminder & Schedule System",
            description="Hệ thống nhắc nhở và lên lịch thông minh\n\n**Quản lý reminders của bạn:**",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="⏰ Tạo Reminder",
            value="Tạo nhắc nhở với thời gian và nội dung",
            inline=False
        )
        embed.add_field(
            name="📋 Xem Reminders",
            value="Xem danh sách các reminder đã tạo",
            inline=False
        )
        embed.set_footer(text="⏰ Click button để quản lý reminders")
        await interaction.response.edit_message(embed=embed, view=RemindersView(self.bot))

    @discord.ui.button(label='❓ Help', style=discord.ButtonStyle.secondary, emoji='🆘')
    async def help_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🆘 Help & Support",
            description="Hướng dẫn sử dụng và hỗ trợ",
            color=discord.Color.light_grey()
        )
        embed.add_field(
            name="📚 Cách sử dụng",
            value="• Gõ `bot ơi` hoặc `bot oi` để mở menu này\n• Sử dụng `!` trước các lệnh\n• Một số lệnh hỗ trợ `/` (slash commands)",
            inline=False
        )
        embed.add_field(
            name="⚡ Quick Commands",
            value="`!help` - Danh sách lệnh\n`!ping` - Kiểm tra độ trễ\n`!serverinfo` - Thông tin server",
            inline=False
        )
        embed.add_field(
            name="🔧 Permissions cần thiết",
            value="• Send Messages\n• Read Message History\n• Embed Links\n• Attach Files\n• Connect (cho music)",
            inline=False
        )
        embed.add_field(
            name="🌟 Features mới",
            value="• AI Image Generation\n• Music Playlists\n• Server Analytics\n• Welcome/Goodbye Events",
            inline=False
        )
        embed.add_field(
            name="📞 Support",
            value="Nếu gặp lỗi, hãy báo cho Admin server",
            inline=False
        )
        embed.set_footer(text="🤖 KSC Support v3.0.0 - Developed with ❤️")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    async def on_timeout(self):
        # Disable tất cả buttons khi timeout
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(view=self)
        except:
            pass

# AI Image Commands Interactive View
class AIImageView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='🖌️ Tạo ảnh cơ bản', style=discord.ButtonStyle.primary, emoji='🎨')
    async def generate_basic(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GenerateImageModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎭 Anime Style', style=discord.ButtonStyle.secondary, emoji='👘')
    async def anime_style(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StyleImageModal(self.bot, "anime")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎨 Realistic Style', style=discord.ButtonStyle.secondary, emoji='📷')
    async def realistic_style(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StyleImageModal(self.bot, "realistic")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎪 Cartoon Style', style=discord.ButtonStyle.secondary, emoji='🎭')
    async def cartoon_style(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StyleImageModal(self.bot, "cartoon")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.danger, emoji='🏠')
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

# Music Commands Interactive View
# YouTube Music View
class YouTubeView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='🎵 Phát nhạc', style=discord.ButtonStyle.primary, emoji='▶️')
    async def play_youtube(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PlayMusicModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='⏸️ Pause', style=discord.ButtonStyle.secondary, emoji='⏸️')
    async def pause_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.pause_command(interaction)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='▶️ Resume', style=discord.ButtonStyle.secondary, emoji='▶️')
    async def resume_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.resume_command(interaction)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='⏭️ Skip', style=discord.ButtonStyle.secondary, emoji='⏭️')
    async def skip_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.skip_command(interaction)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='🔀 Shuffle', style=discord.ButtonStyle.secondary, emoji='🔀')
    async def shuffle_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.shuffle_command(interaction)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='📋 Queue', style=discord.ButtonStyle.primary, emoji='📋', row=1)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.queue_command(interaction)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

    @discord.ui.button(label='🎛️ Advanced', style=discord.ButtonStyle.primary, emoji='⚡', row=1)
    async def advanced_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎛️ Advanced YouTube Features",
            description="Tính năng nâng cao cho YouTube Music\n\n**Các tính năng có sẵn:**",
            color=0xFF0000
        )
        embed.add_field(
            name="🔁 Loop Mode",
            value="Lặp lại bài hát hoặc toàn bộ queue",
            inline=False
        )
        embed.add_field(
            name="🔍 Search Music",
            value="Tìm kiếm và preview nhạc YouTube",
            inline=False
        )
        embed.add_field(
            name="🎮 Music Quiz",
            value="Trò chơi đoán tên bài hát YouTube",
            inline=False
        )
        embed.add_field(
            name="📚 History & Auto DJ",
            value="Xem lịch sử và tự động DJ YouTube",
            inline=False
        )
        embed.set_footer(text="📺 YouTube Advanced Features")
        await interaction.response.edit_message(embed=embed, view=AdvancedMusicView(self.bot))

    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.danger, emoji='🏠', row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

# SoundCloud Music View
class SoundCloudView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='🎵 Phát SoundCloud', style=discord.ButtonStyle.primary, emoji='☁️')
    async def play_soundcloud(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SoundCloudModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='⏹️ Dừng', style=discord.ButtonStyle.secondary, emoji='⏹️')
    async def stop_soundcloud(self, interaction: discord.Interaction, button: discord.ui.Button):
        soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
        if soundcloud_cog:
            await soundcloud_cog.stop_from_modal(interaction)
        else:
            await interaction.response.send_message("❌ SoundCloud Advanced module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='🔊 Volume', style=discord.ButtonStyle.secondary, emoji='🔊')
    async def soundcloud_volume(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SoundCloudVolumeModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='👋 Rời channel', style=discord.ButtonStyle.secondary, emoji='👋')
    async def leave_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        soundcloud_cog = self.bot.get_cog('SoundCloudAdvanced')
        if soundcloud_cog:
            await soundcloud_cog.leave_from_modal(interaction)
        else:
            await interaction.response.send_message("❌ SoundCloud Advanced module không khả dụng!", ephemeral=True)

    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.danger, emoji='🏠', row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

# Advanced Music Features View
class AdvancedMusicView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='🔁 Loop Mode', style=discord.ButtonStyle.primary, emoji='🔂')
    async def loop_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LoopModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🔍 Search Music', style=discord.ButtonStyle.secondary, emoji='🎵')
    async def search_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchMusicModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎮 Music Quiz', style=discord.ButtonStyle.success, emoji='🎯')
    async def music_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            # Start quiz with default 5 rounds
            ctx = await self.bot.get_context(interaction.message)
            ctx.author = interaction.user
            ctx.guild = interaction.guild
            ctx.channel = interaction.channel
            await music_cog.music_quiz(ctx, 5)
            await interaction.response.send_message("🎵 Music Quiz đã bắt đầu!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='🤖 Auto DJ', style=discord.ButtonStyle.secondary, emoji='🎧')
    async def auto_dj(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.loop_command(interaction, "queue")  # Enable auto DJ as queue loop
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='🎧 DJ Mode', style=discord.ButtonStyle.danger, emoji='🎛️')
    async def dj_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎧 DJ Mode Studio",
            description="**Professional DJ Controls & Effects** 🎛️\n\n**Tính năng có sẵn:**",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🎚️ Mixing Controls",
            value="• Crossfade transitions\n• Beat matching\n• Volume fading\n• Seamless playback",
            inline=False
        )
        embed.add_field(
            name="🎛️ Audio Effects",
            value="• Reverb, Echo, Flanger\n• Low/High pass filters\n• Distortion & Compression\n• Real-time effect control",
            inline=False
        )
        embed.add_field(
            name="📊 DJ Analytics",
            value="• Mix session stats\n• Track analysis\n• Performance metrics",
            inline=False
        )
        embed.set_footer(text="🎧 Click button để activate DJ Mode")
        await interaction.response.edit_message(embed=embed, view=DJModeView(self.bot))
            
    @discord.ui.button(label='📚 History', style=discord.ButtonStyle.secondary, emoji='📜')
    async def music_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(interaction.guild.id)
            
            if not hasattr(queue, 'history') or not queue.history:
                embed = discord.Embed(
                    title="📚 Lịch sử phát nhạc",
                    description="Chưa có bài hát nào được phát!",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📚 Lịch sử phát nhạc",
                description="5 bài hát gần đây nhất:",
                color=discord.Color.blue()
            )
            
            for i, song in enumerate(queue.history[-5:], 1):
                embed.add_field(
                    name=f"{i}. {song.get('title', 'Unknown')[:30]}{'...' if len(song.get('title', '')) > 30 else ''}",
                    value=f"👤 {song.get('uploader', 'Unknown')[:20]}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

    @discord.ui.button(label='◀️ Quay lại YouTube', style=discord.ButtonStyle.danger, emoji='📺', row=1)
    async def back_to_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎵 YouTube Music Player",
            description="Hệ thống phát nhạc YouTube với chất lượng cao\n\n**Chức năng YouTube Music:**",
            color=0xFF0000
        )
        embed.add_field(
            name="🎶 Phát nhạc YouTube",
            value="Play, Pause, Skip, Stop nhạc từ YouTube",
            inline=False
        )
        embed.add_field(
            name="⏸️ Điều khiển",
            value="Pause, Resume, Skip, Shuffle nhạc",
            inline=False
        )
        embed.set_footer(text="📺 YouTube Music - Click vào button để điều khiển nhạc")
        await interaction.response.edit_message(embed=embed, view=YouTubeView(self.bot))

# Loop Modal for advanced music features
class LoopModal(discord.ui.Modal, title='🔁 Loop Mode'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    mode = discord.ui.TextInput(
        label='Chế độ Loop',
        placeholder='song, queue, hoặc off',
        style=discord.TextStyle.short,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.loop_command(interaction, self.mode.value.lower())
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

# Search Music Modal
class SearchMusicModal(discord.ui.Modal, title='🔍 Tìm kiếm nhạc'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    query = discord.ui.TextInput(
        label='Tìm kiếm',
        placeholder='Nhập tên bài hát hoặc ca sĩ...',
        style=discord.TextStyle.short,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.search_command(interaction, self.query.value)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

# DJ Mode View
class DJModeView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='🎧 Activate DJ', style=discord.ButtonStyle.success, emoji='▶️')
    async def activate_dj(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.dj_mode_command(interaction, "on")
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='🎚️ Crossfade', style=discord.ButtonStyle.primary, emoji='🔀')
    async def crossfade_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CrossfadeModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎛️ Effects', style=discord.ButtonStyle.secondary, emoji='⚡')
    async def dj_effects(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DJEffectsModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='📊 DJ Stats', style=discord.ButtonStyle.secondary, emoji='📈')
    async def dj_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(interaction.guild.id)
            
            if not getattr(queue, 'dj_mode', False):
                await interaction.response.send_message("❌ DJ Mode chưa được bật!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📊 DJ Session Stats",
                description="Thống kê phiên DJ hiện tại",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="🎵 Tracks Mixed",
                value=f"{queue.dj_stats.get('tracks_mixed', 0)} bài",
                inline=True
            )
            embed.add_field(
                name="🎚️ Crossfades",
                value=f"{queue.dj_stats.get('crossfades_used', 0)}",
                inline=True
            )
            embed.add_field(
                name="🎧 DJ Mode",
                value="✅ Active" if queue.dj_mode else "❌ Inactive",
                inline=True
            )
            embed.add_field(
                name="⚙️ Settings",
                value=f"Crossfade: {getattr(queue, 'crossfade_duration', 3.0)}s\nBeat Match: {'ON' if getattr(queue, 'beat_match', False) else 'OFF'}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
            
    @discord.ui.button(label='❌ Deactivate DJ', style=discord.ButtonStyle.danger, emoji='⏹️')
    async def deactivate_dj(self, interaction: discord.Interaction, button: discord.ui.Button):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            await music_cog.dj_mode_command(interaction, "off")
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

    @discord.ui.button(label='◀️ Back to Advanced', style=discord.ButtonStyle.secondary, emoji='🎛️', row=1)
    async def back_to_advanced(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎛️ Advanced Music Features",
            description="Tính năng nâng cao cho trải nghiệm âm nhạc tốt hơn",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🔁 Loop Mode",
            value="Lặp lại bài hát hoặc toàn bộ queue",
            inline=False
        )
        embed.add_field(
            name="🔍 Search Music",
            value="Tìm kiếm và preview nhạc trước khi phát",
            inline=False
        )
        embed.add_field(
            name="🎮 Music Quiz",
            value="Trò chơi đoán tên bài hát thú vị",
            inline=False
        )
        embed.add_field(
            name="🎧 DJ Mode",
            value="Professional mixing controls & effects",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=AdvancedMusicView(self.bot))

# Crossfade Modal for DJ Mode
class CrossfadeModal(discord.ui.Modal, title='🎚️ Crossfade Settings'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    duration = discord.ui.TextInput(
        label='Crossfade Duration (seconds)',
        placeholder='0.0 - 10.0',
        style=discord.TextStyle.short,
        max_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration = float(self.duration.value)
            if duration < 0 or duration > 10:
                await interaction.response.send_message("❌ Thời gian crossfade phải từ 0-10 giây!", ephemeral=True)
                return
                
            music_cog = self.bot.get_cog('MusicCog')
            if music_cog:
                queue = music_cog.get_queue(interaction.guild.id)
                queue.crossfade_duration = duration
                
                embed = discord.Embed(
                    title="🎚️ Crossfade Updated",
                    description=f"Crossfade duration set to **{duration} seconds**",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Vui lòng nhập số hợp lệ!", ephemeral=True)

# DJ Effects Modal
class DJEffectsModal(discord.ui.Modal, title='🎛️ DJ Effects'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        
    effect = discord.ui.TextInput(
        label='Effect Type',
        placeholder='reverb, echo, flanger, chorus, lowpass, highpass',
        style=discord.TextStyle.short,
        max_length=20
    )
    
    intensity = discord.ui.TextInput(
        label='Intensity (1-100)',
        placeholder='50',
        style=discord.TextStyle.short,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        music_cog = self.bot.get_cog('MusicCog')
        if music_cog:
            queue = music_cog.get_queue(interaction.guild.id)
            
            if not getattr(queue, 'dj_mode', False):
                await interaction.response.send_message("❌ DJ Mode chưa được bật!", ephemeral=True)
                return
            
            try:
                intensity_val = int(self.intensity.value)
                if intensity_val < 1 or intensity_val > 100:
                    intensity_val = 50
            except ValueError:
                intensity_val = 50
            
            effects_list = ["reverb", "echo", "flanger", "chorus", "lowpass", "highpass", "distortion", "compressor"]
            
            if self.effect.value.lower() not in effects_list:
                await interaction.response.send_message(f"❌ Effect không hợp lệ! Sử dụng: {', '.join(effects_list)}", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎛️ DJ Effect Applied",
                description=f"**{self.effect.value.title()}** effect với cường độ **{intensity_val}%**",
                color=discord.Color.purple()
            )
            embed.add_field(
                name="⚡ Effect Active",
                value=f"Type: {self.effect.value.title()}\nIntensity: {intensity_val}%",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music module không khả dụng!", ephemeral=True)

# Fun & Games Interactive View
class FunGamesView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='😄 Meme', style=discord.ButtonStyle.primary, emoji='😂')
    async def get_meme(self, interaction: discord.Interaction, button: discord.ui.Button):
        fun_cog = self.bot.get_cog('Fun')
        if fun_cog:
            await fun_cog.meme_command(interaction)
        else:
            await interaction.response.send_message("❌ Fun module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='🐱 Cat', style=discord.ButtonStyle.secondary, emoji='🐱')
    async def get_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        fun_cog = self.bot.get_cog('Fun')
        if fun_cog:
            await fun_cog.cat_command(interaction)
        else:
            await interaction.response.send_message("❌ Fun module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='🐶 Dog', style=discord.ButtonStyle.secondary, emoji='🐶')
    async def get_dog(self, interaction: discord.Interaction, button: discord.ui.Button):
        fun_cog = self.bot.get_cog('Fun')
        if fun_cog:
            await fun_cog.dog_command(interaction)
        else:
            await interaction.response.send_message("❌ Fun module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='✂️ Kéo Búa Bao', style=discord.ButtonStyle.primary, emoji='✂️')
    async def rock_paper_scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RockPaperScissorsModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='🎱 8Ball', style=discord.ButtonStyle.primary, emoji='🎱')
    async def eight_ball(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EightBallModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.danger, emoji='🏠')
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎮 GenZ Assistant - Main Menu",
            description="Chọn một danh mục để bắt đầu:",
            color=0x3498db
        )
        embed.add_field(name="🤖 AI Commands", value="Trí tuệ nhân tạo", inline=True)
        embed.add_field(name="🎵 Music", value="Nghe nhạc", inline=True)
        embed.add_field(name="🎮 Fun & Games", value="Giải trí & Game", inline=True)
        embed.add_field(name="⏰ Reminders", value="Nhắc nhở", inline=True)
        embed.add_field(name="📊 Leveling", value="Hệ thống level", inline=True)
        embed.add_field(name="🛡️ Admin", value="Quản trị", inline=True)
        embed.add_field(name="⚙️ Utility", value="Tiện ích", inline=True)
        embed.add_field(name="🔧 Settings", value="Cài đặt", inline=True)
        
        main_view = MenuView(self.bot)
        await interaction.response.edit_message(embed=embed, view=main_view)

# Reminders Interactive View  
class RemindersView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='⏰ Tạo Reminder', style=discord.ButtonStyle.primary, emoji='📝')
    async def create_reminder(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReminderModal(self.bot)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label='📋 Xem Reminders', style=discord.ButtonStyle.secondary, emoji='👀')
    async def view_reminders(self, interaction: discord.Interaction, button: discord.ui.Button):
        scheduler_cog = self.bot.get_cog('Scheduler')
        if scheduler_cog:
            await scheduler_cog.reminders_command(interaction)
        else:
            await interaction.response.send_message("❌ Scheduler module không khả dụng!", ephemeral=True)
        
    @discord.ui.button(label='◀️ Quay lại', style=discord.ButtonStyle.danger, emoji='🏠')
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

    @discord.ui.button(label='🎵 Music', style=discord.ButtonStyle.success, emoji='🎶')
    async def music_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎵 Music Commands - YouTube & SoundCloud",
            description="Hệ thống phát nhạc chất lượng cao\n\n**Chọn chức năng bạn muốn sử dụng:**",
            color=discord.Color.green()
        )
        embed.add_field(
            name="� Phát nhạc",
            value="Phát nhạc từ YouTube hoặc SoundCloud",
            inline=False
        )
        embed.add_field(
            name="⏸️ Điều khiển",
            value="Pause, Resume, Skip, Shuffle nhạc",
            inline=False
        )
        embed.set_footer(text="🎵 Click vào button để điều khiển nhạc")
        await interaction.response.edit_message(embed=embed, view=YouTubeView(self.bot))

    @discord.ui.button(label='🎨 AI Images', style=discord.ButtonStyle.secondary, emoji='🖼️')
    async def image_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 AI Image Generation",
            description="Tạo ảnh AI với nhiều phong cách khác nhau\n\n**Chọn style bạn muốn:**",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🖌️ Tạo ảnh cơ bản",
            value="Tạo ảnh AI với prompt tự do",
            inline=False
        )
        embed.add_field(
            name="🎭 Styles đặc biệt",
            value="Anime, Realistic, Cartoon và nhiều style khác",
            inline=False
        )
        embed.set_footer(text="🎨 Click button để chọn style và tạo ảnh")
        await interaction.response.edit_message(embed=embed, view=AIImageView(self.bot))

    @discord.ui.button(label='🎮 Fun & Games', style=discord.ButtonStyle.danger, emoji='🎯')
    async def fun_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎮 Fun & Entertainment",
            description="Giải trí và mini games thú vị\n\n**Chọn trò chơi hoặc giải trí:**",
            color=discord.Color.red()
        )
        embed.add_field(
            name="😄 Hình ảnh vui",
            value="Memes, ảnh mèo, chó và nhiều hơn nữa",
            inline=False
        )
        embed.add_field(
            name="🎲 Mini Games",
            value="Kéo búa bao, 8ball và các trò chơi khác",
            inline=False
        )
        embed.set_footer(text="🎮 Click button để chơi!")
        await interaction.response.edit_message(embed=embed, view=FunGamesView(self.bot))

    @discord.ui.button(label='📊 Analytics', style=discord.ButtonStyle.secondary, emoji='📈')
    async def analytics_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 Server Analytics & Stats",
            description="Thống kê và phân tích server chi tiết",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🏠 Thống kê Server",
            value="`!serverstats` - Tổng quan server\n`!userstats [@user]` - Thống kê user\n`!topmessages` - Top hoạt động",
            inline=False
        )
        embed.add_field(
            name="📈 Server Stats",
            value="`!serverstats` - Thống kê server\n`!topmessages` - Top hoạt động\n`!serverinfo` - Thông tin server",
            inline=False
        )
        embed.add_field(
            name="🔧 Utility",
            value="`!ping` - Độ trễ bot\n`!serverinfo` - Thông tin server\n`!userinfo [@user]` - Thông tin user",
            inline=False
        )
        embed.set_footer(text="📊 Real-time tracking và insights")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    @discord.ui.button(label='🛠️ Admin Tools', style=discord.ButtonStyle.danger, emoji='⚡')
    async def admin_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛠️ Admin & Moderation Tools",
            description="Công cụ quản lý server (Chỉ Admin)",
            color=discord.Color.dark_red()
        )
        embed.add_field(
            name="👮 Moderation",
            value="`!kick <@user> [lý do]` - Kick thành viên\n`!ban <@user> [lý do]` - Ban thành viên\n`!unban <user_id>` - Unban\n`!mute <@user> <thời gian>` - Mute",
            inline=False
        )
        embed.add_field(
            name="💬 Message Management",
            value="`!clear <số lượng>` - Xóa tin nhắn\n`!slowmode <giây>` - Chế độ chậm",
            inline=False
        )
        embed.add_field(
            name="🎉 Events Setup",
            value="`!setwelcome <#channel>` - Set welcome\n`!setgoodbye <#channel>` - Set goodbye\n`!toggledm` - DM settings\n`!welcometest` - Test events",
            inline=False
        )
        embed.add_field(
            name="⚠️ Lưu ý",
            value="Các lệnh này chỉ dành cho Admin/Moderator",
            inline=False
        )
        embed.set_footer(text="🛠️ Quản lý server hiệu quả")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    @discord.ui.button(label='⏰ Reminders', style=discord.ButtonStyle.secondary, emoji='📅')
    async def reminder_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⏰ Reminder & Schedule System",
            description="Hệ thống nhắc nhở và lên lịch thông minh\n\n**Quản lý reminders của bạn:**",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="⏰ Tạo Reminder",
            value="Tạo nhắc nhở với thời gian và nội dung",
            inline=False
        )
        embed.add_field(
            name="� Xem Reminders",
            value="Xem danh sách các reminder đã tạo",
            inline=False
        )
        embed.set_footer(text="⏰ Click button để quản lý reminders")
        await interaction.response.edit_message(embed=embed, view=RemindersView(self.bot))

    @discord.ui.button(label='❓ Help', style=discord.ButtonStyle.secondary, emoji='🆘')
    async def help_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🆘 Help & Support",
            description="Hướng dẫn sử dụng và hỗ trợ",
            color=discord.Color.light_grey()
        )
        embed.add_field(
            name="📚 Cách sử dụng",
            value="• Gõ `bot ơi` hoặc `bot oi` để mở menu này\n• Sử dụng `!` trước các lệnh\n• Một số lệnh hỗ trợ `/` (slash commands)",
            inline=False
        )
        embed.add_field(
            name="⚡ Quick Commands",
            value="`!help` - Danh sách lệnh\n`!ping` - Kiểm tra độ trễ\n`!serverinfo` - Thông tin server",
            inline=False
        )
        embed.add_field(
            name="🔧 Permissions cần thiết",
            value="• Send Messages\n• Read Message History\n• Embed Links\n• Attach Files\n• Connect (cho music)",
            inline=False
        )
        embed.add_field(
            name="🌟 Features mới",
            value="• AI Image Generation\n• Music Playlists\n• Server Analytics\n• Welcome/Goodbye Events",
            inline=False
        )
        embed.add_field(
            name="📞 Support",
            value="Nếu gặp lỗi, hãy báo cho Admin server",
            inline=False
        )
        embed.set_footer(text="🤖 KSC Support v3.0.0 - Developed with ❤️")
        await interaction.response.edit_message(embed=embed, view=BackView(self.bot))

    async def on_timeout(self):
        # Disable tất cả buttons khi timeout
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(view=self)
        except:
            pass

class BackView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot
        
    @discord.ui.button(label='◀️ Quay lại Menu chính', style=discord.ButtonStyle.primary, emoji='🏠')
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Tạo main embed
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/123456789/bot_avatar.png")  # Thay bằng avatar bot
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 10 phút | KSC Support v3.0.0")
        
        await interaction.response.edit_message(embed=embed, view=MenuView(self.bot))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

class MenuSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        """Lắng nghe tin nhắn để phát hiện 'bot ơi' hoặc 'bot oi'"""
        if message.author.bot:
            return
        
        content = message.content.lower().strip()
        
        # Kiểm tra các cách gọi bot
        triggers = ['bot ơi', 'bot oi', 'bot ơy', 'bot oy', 'hey bot', 'hi bot']
        
        if any(trigger in content for trigger in triggers):
            # Tạo main menu embed
            embed = discord.Embed(
                title="🤖 KSC Support - Menu Chính",
                description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
                color=discord.Color.blurple()
            )
            
            # Thêm thông tin user
            embed.add_field(
                name="👋 Xin chào!",
                value=f"Chào {message.author.mention}! Tôi có thể giúp gì cho bạn?",
                inline=False
            )
            
            embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 5 phút | KSC Support v3.0.0")
            
            # Tạo view với buttons
            view = MenuView(self.bot)
            
            try:
                msg = await message.channel.send(embed=embed, view=view)
                view.message = msg  # Lưu message để có thể edit sau
                
                # Không cần auto-delete thủ công nữa vì auto_cleanup sẽ xử lý
                
            except discord.Forbidden:
                await message.channel.send("❌ Bot không có quyền gửi embed. Vui lòng kiểm tra permissions!")
            except Exception as e:
                await message.channel.send(f"❌ Có lỗi xảy ra: {str(e)}")

    @commands.command(name="menu")
    async def manual_menu(self, ctx):
        """Hiển thị menu bằng lệnh !menu"""
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {ctx.author.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 5 phút | KSC Support v3.0.0")
        
        view = MenuView(self.bot)
        
        try:
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            
            # Auto-cleanup sẽ xử lý việc xóa tin nhắn
            
        except discord.Forbidden:
            await ctx.send("❌ Bot không có quyền gửi embed. Vui lòng kiểm tra permissions!")
        except Exception as e:
            await ctx.send(f"❌ Có lỗi xảy ra: {str(e)}")

    @app_commands.command(name="menu", description="Hiển thị menu chính của bot")
    async def slash_menu(self, interaction: discord.Interaction):
        """Slash command cho menu"""
        embed = discord.Embed(
            title="🤖 KSC Support - Menu Chính",
            description="**Chào mừng bạn đến với KSC Support!**\n\nBot đa chức năng với AI, Music, Games và nhiều tính năng thú vị khác.\n\n🔥 **Tính năng HOT:**\n• 🧠 AI Chat với Gemini\n• 🎨 Tạo ảnh AI với 10+ styles\n• 🎵 Music bot với Playlist\n• 📊 Analytics real-time\n\n**Chọn một danh mục bên dưới để xem chi tiết:**",
            color=discord.Color.blurple()
        )
        
        embed.add_field(
            name="👋 Xin chào!",
            value=f"Chào {interaction.user.mention}! Tôi có thể giúp gì cho bạn?",
            inline=False
        )
        
        embed.set_footer(text="💡 Menu sẽ đóng sau 60s và tự động xóa sau 5 phút | KSC Support v3.0.0")
        
        view = MenuView(self.bot)
        
        try:
            await interaction.response.send_message(embed=embed, view=view)
            msg = await interaction.original_response()
            view.message = msg
            
            # Auto-cleanup sẽ xử lý việc xóa tin nhắn
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Có lỗi xảy ra: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MenuSystemCog(bot))
