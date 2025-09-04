import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import asyncio
import io
import base64
from PIL import Image

class AIImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="generate", aliases=["gen", "aiimg"])
    async def generate_image(self, ctx, *, prompt):
        """Tạo ảnh AI từ mô tả văn bản"""
        await ctx.send("🎨 Đang tạo ảnh... Vui lòng đợi...")
        
        try:
            # Sử dụng Pollinations AI (miễn phí)
            await self._generate_with_pollinations(ctx, prompt)
        except Exception as e:
            print(f"Pollinations error: {e}")
            try:
                # Fallback: Sử dụng Craiyon (miễn phí)
                await self._generate_with_craiyon(ctx, prompt)
            except Exception as e2:
                print(f"Craiyon error: {e2}")
                await ctx.send(f"❌ Lỗi khi tạo ảnh: {str(e2)}")
    
    async def _generate_with_pollinations(self, ctx, prompt):
        """Tạo ảnh với Pollinations AI"""
        url = f"https://image.pollinations.ai/prompt/{prompt}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Tạo file từ image data
                    file = discord.File(io.BytesIO(image_data), filename="generated_image.png")
                    
                    embed = discord.Embed(
                        title="🎨 Ảnh AI được tạo",
                        description=f"**Prompt:** {prompt}",
                        color=discord.Color.purple()
                    )
                    embed.set_image(url="attachment://generated_image.png")
                    embed.set_footer(text="Powered by Pollinations AI")
                    
                    await ctx.send(embed=embed, file=file)
                else:
                    raise Exception(f"HTTP {response.status}")
    
    async def _generate_with_craiyon(self, ctx, prompt):
        """Tạo ảnh với Craiyon (DALL-E mini)"""
        url = "https://bf.dallemini.ai/generate"
        
        payload = {
            "prompt": prompt
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    images = data.get('images', [])
                    
                    if images:
                        # Lấy ảnh đầu tiên
                        image_data = base64.b64decode(images[0])
                        file = discord.File(io.BytesIO(image_data), filename="generated_image.png")
                        
                        embed = discord.Embed(
                            title="🎨 Ảnh AI được tạo",
                            description=f"**Prompt:** {prompt}",
                            color=discord.Color.purple()
                        )
                        embed.set_image(url="attachment://generated_image.png")
                        embed.set_footer(text="Powered by Craiyon AI")
                        
                        await ctx.send(embed=embed, file=file)
                    else:
                        raise Exception("Không nhận được ảnh từ API")
                else:
                    raise Exception(f"HTTP {response.status}")
    
    @commands.command(name="imagine")
    async def imagine_image(self, ctx, *, description):
        """Tạo nhiều ảnh AI từ mô tả"""
        await ctx.send("🎨 Đang tạo nhiều ảnh... Vui lòng đợi...")
        
        try:
            # Tạo 3 ảnh khác nhau với variations
            prompts = [
                f"{description}",
                f"{description}, artistic style",
                f"{description}, detailed, high quality"
            ]
            
            images = []
            for i, prompt in enumerate(prompts):
                try:
                    url = f"https://image.pollinations.ai/prompt/{prompt}"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                images.append((f"image_{i+1}.png", image_data))
                    
                    # Delay để tránh rate limit
                    await asyncio.sleep(1)
                except:
                    continue
            
            if images:
                files = [discord.File(io.BytesIO(data), filename=name) for name, data in images]
                
                embed = discord.Embed(
                    title="🎨 Bộ sưu tập ảnh AI",
                    description=f"**Mô tả:** {description}",
                    color=discord.Color.purple()
                )
                embed.set_footer(text=f"Đã tạo {len(images)} ảnh • Powered by Pollinations AI")
                
                await ctx.send(embed=embed, files=files)
            else:
                await ctx.send("❌ Không thể tạo ảnh!")
                
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tạo ảnh: {str(e)}")
    
    @commands.command(name="aiavatar")
    async def generate_avatar(self, ctx, *, description):
        """Tạo avatar AI"""
        await ctx.send("👤 Đang tạo avatar... Vui lòng đợi...")
        
        try:
            # Thêm style cho avatar
            avatar_prompt = f"portrait, avatar, {description}, professional, high quality, centered"
            
            url = f"https://image.pollinations.ai/prompt/{avatar_prompt}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # Resize ảnh thành avatar size (256x256)
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((256, 256), Image.Resampling.LANCZOS)
                        
                        # Save lại
                        output = io.BytesIO()
                        image.save(output, format='PNG')
                        output.seek(0)
                        
                        file = discord.File(output, filename="avatar.png")
                        
                        embed = discord.Embed(
                            title="👤 Avatar AI được tạo",
                            description=f"**Mô tả:** {description}",
                            color=discord.Color.gold()
                        )
                        embed.set_image(url="attachment://avatar.png")
                        embed.set_footer(text="Avatar 256x256 • Powered by Pollinations AI")
                        
                        await ctx.send(embed=embed, file=file)
                    else:
                        await ctx.send("❌ Không thể tạo avatar!")
                        
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tạo avatar: {str(e)}")
    
    @commands.command(name="style")
    async def style_image(self, ctx, style, *, description):
        """Tạo ảnh AI với style cụ thể"""
        await ctx.send("🎨 Đang tạo ảnh với style... Vui lòng đợi...")
        
        styles = {
            "anime": "anime style, manga, japanese animation",
            "cartoon": "cartoon style, animated, colorful",
            "realistic": "photorealistic, detailed, high quality",
            "oil": "oil painting, classical art, brush strokes",
            "watercolor": "watercolor painting, soft colors, artistic",
            "pixel": "pixel art, 8bit, retro gaming style",
            "sketch": "pencil sketch, hand drawn, artistic",
            "cyberpunk": "cyberpunk style, neon, futuristic, sci-fi",
            "fantasy": "fantasy art, magical, mystical",
            "vintage": "vintage style, retro, old photograph"
        }
        
        if style.lower() not in styles:
            available_styles = ", ".join(styles.keys())
            await ctx.send(f"❌ Style không hợp lệ! Các style có sẵn: {available_styles}")
            return
        
        try:
            style_prompt = f"{description}, {styles[style.lower()]}"
            
            url = f"https://image.pollinations.ai/prompt/{style_prompt}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        file = discord.File(io.BytesIO(image_data), filename=f"{style}_image.png")
                        
                        embed = discord.Embed(
                            title=f"🎨 Ảnh AI - Style {style.title()}",
                            description=f"**Mô tả:** {description}",
                            color=discord.Color.purple()
                        )
                        embed.set_image(url=f"attachment://{style}_image.png")
                        embed.set_footer(text=f"Style: {style.title()} • Powered by Pollinations AI")
                        
                        await ctx.send(embed=embed, file=file)
                    else:
                        await ctx.send("❌ Không thể tạo ảnh!")
                        
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tạo ảnh: {str(e)}")
    
    @commands.command(name="enhance")
    async def enhance_prompt(self, ctx, *, simple_prompt):
        """Tạo ảnh với prompt được cải thiện"""
        await ctx.send("✨ Đang cải thiện prompt và tạo ảnh...")
        
        try:
            # Cải thiện prompt
            enhanced_prompt = f"{simple_prompt}, highly detailed, masterpiece, best quality, ultra-detailed, sharp focus, physically-based rendering, extreme detail description, professional, vivid colors, bokeh"
            
            url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        file = discord.File(io.BytesIO(image_data), filename="enhanced_image.png")
                        
                        embed = discord.Embed(
                            title="✨ Ảnh AI với Prompt được cải thiện",
                            color=discord.Color.gold()
                        )
                        embed.add_field(name="Prompt gốc", value=simple_prompt, inline=False)
                        embed.add_field(name="Prompt cải thiện", value=enhanced_prompt[:1000] + "..." if len(enhanced_prompt) > 1000 else enhanced_prompt, inline=False)
                        embed.set_image(url="attachment://enhanced_image.png")
                        embed.set_footer(text="Enhanced Quality • Powered by Pollinations AI")
                        
                        await ctx.send(embed=embed, file=file)
                    else:
                        await ctx.send("❌ Không thể tạo ảnh!")
                        
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tạo ảnh: {str(e)}")
    
    # Slash Commands
    @app_commands.command(name="generate", description="Tạo ảnh AI từ mô tả văn bản")
    @app_commands.describe(prompt="Mô tả ảnh bạn muốn tạo")
    async def slash_generate(self, interaction: discord.Interaction, prompt: str):
        """Slash command cho tạo ảnh AI"""
        await interaction.response.defer()
        
        try:
            await interaction.followup.send("🎨 Đang tạo ảnh... Vui lòng đợi...")
            
            url = f"https://image.pollinations.ai/prompt/{prompt}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        file = discord.File(io.BytesIO(image_data), filename="generated_image.png")
                        
                        embed = discord.Embed(
                            title="🎨 Ảnh AI được tạo",
                            description=f"**Prompt:** {prompt}",
                            color=discord.Color.purple()
                        )
                        embed.set_image(url="attachment://generated_image.png")
                        embed.set_footer(text="Powered by Pollinations AI")
                        
                        await interaction.followup.send(embed=embed, file=file)
                    else:
                        await interaction.followup.send("❌ Không thể tạo ảnh!")
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi tạo ảnh: {str(e)}")
    
    @commands.command(name="aihelp")
    async def ai_help(self, ctx):
        """Hướng dẫn sử dụng AI Image Generation"""
        embed = discord.Embed(title="🎨 AI Image Generation Commands", color=discord.Color.purple())
        embed.add_field(name="!generate <mô tả>", value="Tạo ảnh AI từ mô tả", inline=False)
        embed.add_field(name="!imagine <mô tả>", value="Tạo nhiều ảnh khác nhau", inline=False)
        embed.add_field(name="!avatar <mô tả>", value="Tạo avatar AI", inline=False)
        embed.add_field(name="!style <style> <mô tả>", value="Tạo ảnh với style cụ thể", inline=False)
        embed.add_field(name="!enhance <mô tả>", value="Tạo ảnh với prompt được cải thiện", inline=False)
        embed.add_field(name="/generate <prompt>", value="Slash command tạo ảnh", inline=False)
        
        embed.add_field(
            name="📋 Styles có sẵn", 
            value="anime, cartoon, realistic, oil, watercolor, pixel, sketch, cyberpunk, fantasy, vintage", 
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Mô tả càng chi tiết, ảnh càng đẹp\n• Sử dụng tiếng Anh cho kết quả tốt nhất\n• Thêm từ khóa như 'detailed', 'high quality'",
            inline=False
        )
        
        embed.set_footer(text="Powered by Pollinations AI & Craiyon")
        await ctx.send(embed=embed)

    # Helper methods for menu system interactions
    async def generate_command(self, interaction, prompt):
        """Helper method for generate command via interaction"""
        await interaction.response.defer()
        
        if not prompt.strip():
            await interaction.followup.send("❌ Vui lòng nhập mô tả cho ảnh!", ephemeral=True)
            return
            
        try:
            # Use existing generate logic
            image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
            
            embed = discord.Embed(
                title="🎨 AI Image Generated",
                description=f"**Prompt:** {prompt}",
                color=discord.Color.purple()
            )
            embed.set_image(url=image_url)
            embed.set_footer(text="Powered by Pollinations AI")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Có lỗi xảy ra: {str(e)}", ephemeral=True)

    async def style_command(self, interaction, style, prompt):
        """Helper method for style command via interaction"""
        await interaction.response.defer()
        
        if not prompt.strip():
            await interaction.followup.send("❌ Vui lòng nhập mô tả cho ảnh!", ephemeral=True)
            return
            
        try:
            # Add style to prompt
            styled_prompt = f"{prompt}, {style} style, high quality, detailed"
            image_url = f"https://image.pollinations.ai/prompt/{styled_prompt.replace(' ', '%20')}"
            
            embed = discord.Embed(
                title=f"🎨 AI Image - {style.title()} Style",
                description=f"**Prompt:** {prompt}\n**Style:** {style}",
                color=discord.Color.purple()
            )
            embed.set_image(url=image_url)
            embed.set_footer(text="Powered by Pollinations AI")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Có lỗi xảy ra: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AIImageCog(bot))
