import aiohttp
import json
import os
from discord.ext import commands
from discord import app_commands
import discord
from utils.channel_manager import ChannelManager


class AICog(commands.Cog):
    """AI Integration with Google Gemini"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        if not self.api_key:
            print("⚠️ Gemini API key not found. Get one free at: https://makersuite.google.com/app/apikey")

    async def ask_gemini(self, prompt):
        """Send request to Gemini API"""
        if not self.api_key:
            return "❌ Gemini API key chưa được cấu hình. Vui lòng liên hệ admin."
        
        # Thêm hướng dẫn trả lời bằng tiếng Việt
        vietnamese_prompt = f"""Hãy trả lời bằng tiếng Việt một cách tự nhiên và thân thiện. Sử dụng emoji phù hợp để làm cho câu trả lời sinh động hơn.

Câu hỏi/Yêu cầu: {prompt}

Trả lời:"""
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": vietnamese_prompt
                }]
            }],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}?key={self.api_key}"
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if 'candidates' in result and len(result['candidates']) > 0:
                            candidate = result['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                return candidate['content']['parts'][0]['text']
                            else:
                                return "❌ AI từ chối trả lời do nội dung không phù hợp."
                        else:
                            return "❌ Không nhận được phản hồi từ AI."
                    elif response.status == 400:
                        error_data = await response.json()
                        print(f"Gemini API 400 Error: {error_data}")
                        return "❌ Yêu cầu không hợp lệ. Vui lòng thử lại với nội dung khác."
                    elif response.status == 403:
                        return "❌ API key không hợp lệ hoặc đã hết quota."
                    else:
                        error_text = await response.text()
                        print(f"Gemini API Error: {response.status} - {error_text}")
                        return f"❌ Lỗi API: {response.status}"
        except Exception as e:
            print(f"Gemini request error: {e}")
            return "❌ Có lỗi xảy ra khi kết nối với AI."

    # Helper methods for menu system interactions
    async def ask_command(self, interaction, question):
        """Helper method for ask command via interaction"""
        await interaction.response.defer()
        
        if not question.strip():
            await interaction.followup.send("❌ Vui lòng nhập câu hỏi!", ephemeral=True)
            return
            
        response = await self.ask_gemini(question)
        
        # Split long responses
        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"🤖 **AI:** {chunk}")
                else:
                    await interaction.followup.send(chunk)
        else:
            await interaction.followup.send(f"🤖 **AI:** {response}")

    async def translate_command(self, interaction, text):
        """Helper method for translate command via interaction"""
        await interaction.response.defer()
        
        if not text.strip():
            await interaction.followup.send("❌ Vui lòng nhập văn bản cần dịch!", ephemeral=True)
            return
            
        prompt = f"Dịch văn bản này sang tiếng khác (tự động phát hiện ngôn ngữ nguồn và đích phù hợp): {text}"
        response = await self.ask_gemini(prompt)
        
        embed = discord.Embed(
            title="🌐 Kết quả dịch thuật",
            color=0x00ff00
        )
        embed.add_field(name="📝 Văn bản gốc", value=text[:1024], inline=False)
        embed.add_field(name="🔄 Kết quả dịch", value=response[:1024], inline=False)
        
        await interaction.followup.send(embed=embed)

    async def explain_command(self, interaction, concept):
        """Helper method for explain command via interaction"""
        await interaction.response.defer()
        
        if not concept.strip():
            await interaction.followup.send("❌ Vui lòng nhập khái niệm cần giải thích!", ephemeral=True)
            return
            
        prompt = f"Giải thích một cách đơn giản và dễ hiểu khái niệm: {concept}"
        response = await self.ask_gemini(prompt)
        
        embed = discord.Embed(
            title=f"💡 Giải thích: {concept}",
            description=response[:2048],
            color=0x0099ff
        )
        embed.set_footer(text="🤖 AI Assistant • KSC Support")
        
        await interaction.followup.send(embed=embed)

    async def summary_command(self, interaction, text):
        """Helper method for summary command via interaction"""
        await interaction.response.defer()
        
        if not text.strip():
            await interaction.followup.send("❌ Vui lòng nhập văn bản cần tóm tắt!", ephemeral=True)
            return
            
        prompt = f"Tóm tắt văn bản sau thành những điểm chính: {text}"
        response = await self.ask_gemini(prompt)
        
        embed = discord.Embed(
            title="📄 Tóm tắt nội dung",
            description=response[:2048],
            color=0xff9900
        )
        embed.add_field(
            name="📊 Thống kê",
            value=f"Văn bản gốc: {len(text)} ký tự\nTóm tắt: {len(response)} ký tự",
            inline=False
        )
        embed.set_footer(text="📝 Tóm tắt bởi AI")
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    """Setup function required for Discord.py cogs"""
    await bot.add_cog(AICog(bot))
