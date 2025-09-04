import discord # type: ignore
from discord.ext import commands # type: ignore
import random
import asyncio
from typing import Optional, Dict, List

class Games(commands.Cog):
    """🎯 Mini Games - Các trò chơi tương tác vui nhộn"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # Track active games per channel
        
        # Quiz questions database
        self.quiz_questions = [
            {
                "question": "Thủ đô của Việt Nam là gì?",
                "options": ["A. Hồ Chí Minh", "B. Hà Nội", "C. Đà Nẵng", "D. Cần Thơ"],
                "correct": "B",
                "explanation": "Hà Nội là thủ đô của Việt Nam từ năm 1010."
            },
            {
                "question": "Hành tinh nào gần Mặt Trời nhất?",
                "options": ["A. Sao Kim", "B. Trái Đất", "C. Sao Thủy", "D. Sao Hỏa"],
                "correct": "C",
                "explanation": "Sao Thủy là hành tinh gần Mặt Trời nhất trong hệ Mặt Trời."
            },
            {
                "question": "Ai là tác giả của tác phẩm 'Truyện Kiều'?",
                "options": ["A. Nguyễn Du", "B. Hồ Xuân Hương", "C. Nguyễn Khuyến", "D. Tú Xương"],
                "correct": "A",
                "explanation": "Nguyễn Du là tác giả của 'Truyện Kiều', tác phẩm vĩ đại của văn học Việt Nam."
            },
            {
                "question": "2 + 2 x 3 = ?",
                "options": ["A. 12", "B. 8", "C. 10", "D. 6"],
                "correct": "B",
                "explanation": "Theo thứ tự phép tính: 2 + (2 x 3) = 2 + 6 = 8"
            },
            {
                "question": "Ngôn ngữ lập trình nào được sử dụng để tạo ra bot Discord này?",
                "options": ["A. Java", "B. JavaScript", "C. Python", "D. C++"],
                "correct": "C",
                "explanation": "Bot này được viết bằng Python với thư viện discord.py"
            }
        ]
    
    @commands.command(name='tracnghiem', aliases=['quiz'])
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def quiz_game(self, ctx):
        """Tạo câu hỏi trắc nghiệm vui"""
        if ctx.channel.id in self.active_games:
            embed = discord.Embed(
                title="⚠️ Game đang diễn ra",
                description="Có một game khác đang diễn ra trong kênh này!",
                color=0xFFFF00
            )
            await ctx.send(embed=embed)
            return
        
        # Mark channel as having active game
        self.active_games[ctx.channel.id] = "quiz"
        
        try:
            question_data = random.choice(self.quiz_questions)
            
            embed = discord.Embed(
                title="🧠 Câu hỏi trắc nghiệm",
                description=question_data["question"],
                color=0x7289DA
            )
            
            options_text = "\n".join(question_data["options"])
            embed.add_field(name="📝 Lựa chọn", value=options_text, inline=False)
            embed.add_field(name="⏰ Thời gian", value="30 giây để trả lời", inline=False)
            embed.set_footer(text="Gõ A, B, C, hoặc D để trả lời!")
            
            await ctx.send(embed=embed)
            
            def check(message):
                return (message.channel == ctx.channel and 
                       message.content.upper() in ['A', 'B', 'C', 'D'] and
                       not message.author.bot)
            
            try:
                # Wait for answer
                answer_msg = await self.bot.wait_for('message', timeout=30.0, check=check)
                
                if answer_msg.content.upper() == question_data["correct"]:
                    # Correct answer
                    embed = discord.Embed(
                        title="🎉 Chính xác!",
                        description=f"{answer_msg.author.mention} đã trả lời đúng!",
                        color=0x00FF00
                    )
                    embed.add_field(name="💡 Giải thích", value=question_data["explanation"], inline=False)
                    
                else:
                    # Wrong answer
                    embed = discord.Embed(
                        title="❌ Sai rồi!",
                        description=f"Đáp án đúng là **{question_data['correct']}**",
                        color=0xFF0000
                    )
                    embed.add_field(name="💡 Giải thích", value=question_data["explanation"], inline=False)
                
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="⏰ Hết thời gian!",
                    description=f"Đáp án đúng là **{question_data['correct']}**",
                    color=0xFF0000
                )
                embed.add_field(name="💡 Giải thích", value=question_data["explanation"], inline=False)
                await ctx.send(embed=embed)
        
        finally:
            # Remove active game marker
            if ctx.channel.id in self.active_games:
                del self.active_games[ctx.channel.id]
    
    @commands.command(name='choinhanh', aliases=['quickgame'])
    @commands.cooldown(1, 45, commands.BucketType.channel)
    async def quick_game(self, ctx):
        """Trò chơi trả lời nhanh"""
        if ctx.channel.id in self.active_games:
            embed = discord.Embed(
                title="⚠️ Game đang diễn ra",
                description="Có một game khác đang diễn ra trong kênh này!",
                color=0xFFFF00
            )
            await ctx.send(embed=embed)
            return
        
        self.active_games[ctx.channel.id] = "quick"
        
        try:
            # Random quick questions
            quick_questions = [
                {"question": "Màu gì được tạo bởi đỏ + vàng?", "answer": ["cam", "orange", "màu cam"]},
                {"question": "Thủ đô của Nhật Bản?", "answer": ["tokyo", "tôkyô", "tokyo"]},
                {"question": "7 x 8 = ?", "answer": ["56"]},
                {"question": "Hành tinh lớn nhất hệ Mặt Trời?", "answer": ["sao mộc", "jupiter", "mộc tinh"]},
                {"question": "Ngành học về máy tính?", "answer": ["tin học", "khoa học máy tính", "cntt", "it"]},
                {"question": "Biểu tượng hóa học của nước?", "answer": ["h2o", "H2O"]},
                {"question": "Tác giả Harry Potter?", "answer": ["j.k. rowling", "rowling", "jk rowling"]},
                {"question": "1000 + 500 = ?", "answer": ["1500"]},
                {"question": "Thủ đô của Pháp?", "answer": ["paris", "pa ri", "pa-ri"]},
                {"question": "Con vật nào bay được?", "answer": ["chim", "bướm", "ong", "ruồi", "chim cánh cụt"]}
            ]
            
            question_data = random.choice(quick_questions)
            
            embed = discord.Embed(
                title="⚡ Trả lời nhanh!",
                description=question_data["question"],
                color=0xFFD700
            )
            embed.add_field(name="⏰ Thời gian", value="15 giây!", inline=False)
            embed.set_footer(text="Ai trả lời đúng đầu tiên sẽ thắng!")
            
            await ctx.send(embed=embed)
            
            def check(message):
                return (message.channel == ctx.channel and 
                       not message.author.bot and
                       any(ans.lower() in message.content.lower() for ans in question_data["answer"]))
            
            try:
                winner_msg = await self.bot.wait_for('message', timeout=15.0, check=check)
                
                embed = discord.Embed(
                    title="🏆 Có người thắng!",
                    description=f"{winner_msg.author.mention} đã trả lời đúng đầu tiên!",
                    color=0x00FF00
                )
                embed.add_field(name="✅ Đáp án", value=question_data["answer"][0].title(), inline=False)
                
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="⏰ Hết thời gian!",
                    description="Không ai trả lời đúng trong thời gian quy định",
                    color=0xFF0000
                )
                embed.add_field(name="💡 Đáp án", value=question_data["answer"][0].title(), inline=False)
                await ctx.send(embed=embed)
        
        finally:
            if ctx.channel.id in self.active_games:
                del self.active_games[ctx.channel.id]
    
    @commands.command(name='guessnumber', aliases=['doanso'])
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def guess_number(self, ctx, max_number: int = 100):
        """Đoán số từ 1 đến max_number"""
        if ctx.channel.id in self.active_games:
            embed = discord.Embed(
                title="⚠️ Game đang diễn ra",
                description="Có một game khác đang diễn ra trong kênh này!",
                color=0xFFFF00
            )
            await ctx.send(embed=embed)
            return
        
        if max_number < 10 or max_number > 1000:
            embed = discord.Embed(
                title="❌ Số không hợp lệ",
                description="Số tối đa phải từ 10 đến 1000!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        self.active_games[ctx.channel.id] = "guess"
        
        try:
            secret_number = random.randint(1, max_number)
            attempts = 0
            max_attempts = min(10, max_number // 10 + 3)
            
            embed = discord.Embed(
                title="🔢 Đoán số!",
                description=f"Tôi đã nghĩ ra một số từ 1 đến {max_number}",
                color=0x7289DA
            )
            embed.add_field(name="🎯 Mục tiêu", value="Đoán đúng số tôi nghĩ!", inline=False)
            embed.add_field(name="🔢 Cách chơi", value="Gõ một số để đoán", inline=False)
            embed.add_field(name="⏰ Giới hạn", value=f"{max_attempts} lần đoán", inline=False)
            
            await ctx.send(embed=embed)
            
            while attempts < max_attempts:
                def check(message):
                    try:
                        number = int(message.content)
                        return (message.channel == ctx.channel and 
                               not message.author.bot and
                               1 <= number <= max_number)
                    except ValueError:
                        return False
                
                try:
                    guess_msg = await self.bot.wait_for('message', timeout=30.0, check=check)
                    guess = int(guess_msg.content)
                    attempts += 1
                    
                    if guess == secret_number:
                        # Winner!
                        embed = discord.Embed(
                            title="🎉 Chúc mừng!",
                            description=f"{guess_msg.author.mention} đã đoán đúng số **{secret_number}**!",
                            color=0x00FF00
                        )
                        embed.add_field(name="🏆 Kết quả", value=f"Đoán đúng sau {attempts} lần thử", inline=False)
                        
                        # Calculate XP based on attempts
                        await ctx.send(embed=embed)
                        return
                    
                    elif guess < secret_number:
                        hint = "📈 Số cần tìm lớn hơn!"
                        color = 0xFFFF00
                    else:
                        hint = "📉 Số cần tìm nhỏ hơn!"
                        color = 0xFFFF00
                    
                    embed = discord.Embed(
                        title=f"Lần thử {attempts}/{max_attempts}",
                        description=f"{guess_msg.author.mention}: **{guess}** - {hint}",
                        color=color
                    )
                    
                    if attempts < max_attempts:
                        embed.set_footer(text=f"Còn {max_attempts - attempts} lần thử!")
                    
                    await ctx.send(embed=embed)
                    
                except asyncio.TimeoutError:
                    embed = discord.Embed(
                        title="⏰ Hết thời gian!",
                        description=f"Không ai đoán trong 30 giây. Số cần tìm là **{secret_number}**",
                        color=0xFF0000
                    )
                    await ctx.send(embed=embed)
                    return
            
            # Max attempts reached
            embed = discord.Embed(
                title="💥 Game Over!",
                description=f"Đã hết {max_attempts} lần đoán. Số cần tìm là **{secret_number}**",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
        
        finally:
            if ctx.channel.id in self.active_games:
                del self.active_games[ctx.channel.id]
    
    @commands.command(name='rps', aliases=['keobuabao'])
    async def rock_paper_scissors(self, ctx, choice: str = None):
        """Kéo búa bao với bot"""
        if not choice:
            embed = discord.Embed(
                title="✂️ Kéo Búa Bao",
                description=f"Sử dụng: `{self.bot.config['prefix']}rps <kéo/búa/bao>`\n"
                           f"Hoặc: `{self.bot.config['prefix']}rps <rock/paper/scissors>`",
                color=0x7289DA
            )
            await ctx.send(embed=embed)
            return
        
        # Normalize choice
        choice = choice.lower()
        choice_map = {
            'kéo': 'scissors', 'keo': 'scissors', 'scissors': 'scissors',
            'búa': 'rock', 'bua': 'rock', 'rock': 'rock', 'đá': 'rock', 'da': 'rock',
            'bao': 'paper', 'paper': 'paper', 'giấy': 'paper', 'giay': 'paper'
        }
        
        if choice not in choice_map:
            embed = discord.Embed(
                title="❌ Lựa chọn không hợp lệ",
                description="Chọn: kéo, búa, hoặc bao",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        user_choice = choice_map[choice]
        bot_choice = random.choice(['rock', 'paper', 'scissors'])
        
        # Determine winner
        if user_choice == bot_choice:
            result = "Hòa!"
            color = 0xFFFF00
        elif (user_choice == 'rock' and bot_choice == 'scissors') or \
             (user_choice == 'paper' and bot_choice == 'rock') or \
             (user_choice == 'scissors' and bot_choice == 'paper'):
            result = "Bạn thắng!"
            color = 0x00FF00
        else:
            result = "Bot thắng!"
            color = 0xFF0000
        
        # Emoji mapping
        emoji_map = {
            'rock': '🪨',
            'paper': '📄', 
            'scissors': '✂️'
        }
        
        embed = discord.Embed(
            title="✂️ Kéo Búa Bao",
            description=f"**{result}**",
            color=color
        )
        embed.add_field(name="Bạn chọn", value=f"{emoji_map[user_choice]} {user_choice.title()}", inline=True)
        embed.add_field(name="Bot chọn", value=f"{emoji_map[bot_choice]} {bot_choice.title()}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='trivia', aliases=['hoidap'])
    async def trivia_question(self, ctx):
        """Câu hỏi tổng hợp kiến thức"""
        # Use existing quiz system but single question
        question_data = random.choice(self.quiz_questions)
        
        embed = discord.Embed(
            title="🤔 Câu hỏi Trivia",
            description=question_data["question"],
            color=0x7289DA
        )
        
        # Shuffle options
        options = question_data["options"].copy()
        random.shuffle(options)
        
        options_text = "\n".join(options)
        embed.add_field(name="📝 Lựa chọn", value=options_text, inline=False)
        embed.set_footer(text="React với 🇦 🇧 🇨 🇩 để trả lời!")
        
        message = await ctx.send(embed=embed)
        
        # Add reaction options
        reactions = ['🇦', '🇧', '🇨', '🇩']
        for reaction in reactions:
            await message.add_reaction(reaction)
        
        # The rest would require reaction handling which is more complex
        # For now, just show the question

    # Helper methods for menu system interactions
    async def rps_command(self, interaction, user_choice):
        """Helper method for rock paper scissors via interaction"""
        await interaction.response.defer()
        
        choices = ['rock', 'paper', 'scissors']
        choice_mapping = {
            'rock': 'rock', 'búa': 'rock', 'đá': 'rock',
            'paper': 'paper', 'bao': 'paper', 'giấy': 'paper', 
            'scissors': 'scissors', 'kéo': 'scissors'
        }
        
        # Normalize user choice
        user_choice = user_choice.lower().strip()
        if user_choice in choice_mapping:
            user_choice = choice_mapping[user_choice]
        
        if user_choice not in choices:
            await interaction.followup.send("❌ Lựa chọn không hợp lệ! Chọn: rock/búa, paper/bao, scissors/kéo", ephemeral=True)
            return
        
        bot_choice = random.choice(choices)
        
        # Determine winner
        if user_choice == bot_choice:
            result = "🤝 Hòa!"
            color = 0xffff00
            xp_bonus = 1
        elif (
            (user_choice == 'rock' and bot_choice == 'scissors') or
            (user_choice == 'paper' and bot_choice == 'rock') or
            (user_choice == 'scissors' and bot_choice == 'paper')
        ):
            result = "🎉 Bạn thắng!"
            color = 0x00ff00
            xp_bonus = 3
        else:
            result = "😢 Bot thắng!"
            color = 0xff0000
            xp_bonus = 1
        
        # Emoji mapping
        emoji_map = {
            'rock': '✊',
            'paper': '✋', 
            'scissors': '✌️'
        }
        
        embed = discord.Embed(
            title="✂️ Kéo Búa Bao",
            description=f"**{result}**",
            color=color
        )
        embed.add_field(name="Bạn chọn", value=f"{emoji_map[user_choice]} {user_choice.title()}", inline=True)
        embed.add_field(name="Bot chọn", value=f"{emoji_map[bot_choice]} {bot_choice.title()}", inline=True)
        
        if xp_bonus > 0:
            try:
                await self.bot.db.add_xp(interaction.user.id, interaction.guild.id, xp_bonus)
                embed.add_field(name="🎁 XP", value=f"+{xp_bonus}", inline=False)
            except:
                pass  # XP system might not be available
        
        await interaction.followup.send(embed=embed)

    async def eightball_command(self, interaction, question):
        """Helper method for 8ball command via interaction"""
        await interaction.response.defer()
        
        if not question.strip():
            await interaction.followup.send("❌ Vui lòng nhập một câu hỏi!", ephemeral=True)
            return
        
        responses = [
            "🎯 Chắc chắn!", "✅ Có!", "🌟 Hoàn toàn đúng!", 
            "💯 Không nghi ngờ gì!", "👍 Có thể tin tưởng!",
            "🤔 Có lẽ...", "⚖️ Khó nói...", "🎲 Hỏi lại sau!",
            "🌫️ Không rõ...", "⏳ Chờ xem...",
            "❌ Không!", "👎 Không chắc!", "🚫 Tôi không nghĩ vậy!",
            "⛔ Chắc chắn không!", "🙅‍♂️ Đừng mơ!"
        ]
        
        response = random.choice(responses)
        
        embed = discord.Embed(
            title="🎱 Quả cầu thần trả lời",
            color=0x8B00FF
        )
        embed.add_field(name="❓ Câu hỏi", value=question, inline=False)
        embed.add_field(name="🎱 Trả lời", value=response, inline=False)
        embed.set_footer(text="🔮 Chỉ mang tính giải trí!")
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Games(bot))
