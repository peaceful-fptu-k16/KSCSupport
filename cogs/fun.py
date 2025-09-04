import discord
from discord.ext import commands
import aiohttp
import random
import asyncio
from typing import Optional

class Fun(commands.Cog):
    """🎮 Giải trí & Fun - Các lệnh vui nhộn và giải trí"""
    
    def __init__(self, bot):
        self.bot = bot
        self.eight_ball_responses = [
            "Chắc chắn rồi! ✅",
            "Không đâu! ❌", 
            "Có thể đấy! 🤔",
            "Tùy duyên thôi! 🎲",
            "Hỏi lại sau nhé! ⏰",
            "Khả năng cao! 📈",
            "Khó đấy! 📉",
            "Chắc là không! 🚫",
            "Tin tưởng đi! 💪",
            "Đừng mơ! 💭"
        ]
    
    async def fetch_json(self, url: str) -> Optional[dict]:
        """Helper function to fetch JSON from API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
        return None
    
    @commands.command(name='meme', aliases=['mem'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def meme(self, ctx):
        """Gửi meme ngẫu nhiên từ Reddit"""
        async with ctx.typing():
            # Thử các API khác nhau để đảm bảo hoạt động
            api_urls = [
                "https://meme-api.com/gimme",
                "https://meme-api.herokuapp.com/gimme", 
                "https://memes.blademaker.tv/api/random"
            ]
            
            data = None
            for url in api_urls:
                data = await self.fetch_json(url)
                if data and 'url' in data:
                    break
            
            if not data:
                # Fallback memes nếu API không hoạt động
                fallback_memes = [
                    {
                        "title": "Khi code chạy được lần đầu tiên",
                        "url": "https://i.imgflip.com/5c7lwq.jpg",
                        "subreddit": "ProgrammerHumor",
                        "ups": 9999
                    },
                    {
                        "title": "Trying to fix a bug",
                        "url": "https://i.imgflip.com/1bij2j.jpg", 
                        "subreddit": "memes",
                        "ups": 8888
                    }
                ]
                data = random.choice(fallback_memes)
            
            embed = discord.Embed(
                title=f"😂 {data.get('title', 'Random Meme')}",
                url=data.get('postLink', ''),
                color=0x7289DA
            )
            embed.set_image(url=data['url'])
            embed.set_footer(text=f"👍 {data.get('ups', 'N/A')} upvotes • r/{data.get('subreddit', 'memes')}")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='8ball', aliases=['8b', 'ball'])
    async def eight_ball(self, ctx, *, question: str = None):
        """Trả lời câu hỏi kiểu bói toán"""
        if not question:
            embed = discord.Embed(
                title="❓ Thiếu câu hỏi",
                description=f"Sử dụng: `{self.bot.config['prefix']}8ball <câu hỏi>`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        response = random.choice(self.eight_ball_responses)
        
        embed = discord.Embed(
            title="🎱 Quả cầu thần số 8",
            color=0x7289DA
        )
        embed.add_field(name="❓ Câu hỏi", value=question, inline=False)
        embed.add_field(name="💫 Trả lời", value=response, inline=False)
        embed.set_footer(text=f"Hỏi bởi {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='quote', aliases=['q'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def quote(self, ctx):
        """Gửi một câu quote truyền cảm hứng"""
        async with ctx.typing():
            data = await self.fetch_json(self.bot.config['api_endpoints']['quote_api'])
            
            if not data:
                # Fallback quotes
                fallback_quotes = [
                    "Hành trình ngàn dặm bắt đầu từ một bước chân. - Lão Tử",
                    "Thành công không phải là chìa khóa của hạnh phúc. Hạnh phúc là chìa khóa của thành công. - Albert Schweitzer",
                    "Điều duy nhất không thể thay đổi là sự thay đổi. - Heraclitus",
                    "Học hỏi như thể bạn sẽ sống mãi mãi. - Mahatma Gandhi",
                    "Tương lai thuộc về những ai tin vào vẻ đẹp của ước mơ. - Eleanor Roosevelt"
                ]
                quote_data = random.choice(fallback_quotes).split(' - ')
                content = quote_data[0]
                author = quote_data[1] if len(quote_data) > 1 else "Unknown"
            else:
                content = data['content']
                author = data['author']
            
            embed = discord.Embed(
                title="💭 Quote của ngày",
                description=f"*\"{content}\"*",
                color=0x7289DA
            )
            embed.set_footer(text=f"- {author}")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='fact', aliases=['f'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def fact(self, ctx):
        """Gửi một fact thú vị"""
        async with ctx.typing():
            data = await self.fetch_json(self.bot.config['api_endpoints']['fact_api'])
            
            if not data:
                # Fallback facts
                fallback_facts = [
                    "Bạn có biết rằng bạch tuộc có 3 trái tim không?",
                    "Mật ong không bao giờ hư hỏng. Các nhà khảo cổ đã tìm thấy mật ong 3000 năm tuổi vẫn ăn được!",
                    "Một con ốc sên có thể ngủ được 3 năm liên tục.",
                    "Chuối là quả mọng, còn dâu tây thì không phải!",
                    "Cá voi xanh có trái tim to bằng một chiếc xe hơi."
                ]
                fact_text = random.choice(fallback_facts)
            else:
                fact_text = data['text']
            
            embed = discord.Embed(
                title="🧠 Fact thú vị",
                description=fact_text,
                color=0x7289DA
            )
            embed.set_footer(text="Fact of the day!")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='cat', aliases=['meo'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cat(self, ctx):
        """Gửi ảnh mèo random"""
        async with ctx.typing():
            # Thử nhiều API khác nhau
            cat_apis = [
                "https://api.thecatapi.com/v1/images/search",
                "https://cataas.com/cat?json=true",
                "https://aws.random.cat/meow"
            ]
            
            data = None
            for api in cat_apis:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api) as response:
                            if response.status == 200:
                                json_data = await response.json()
                                if api == "https://aws.random.cat/meow":
                                    data = [{"url": json_data["file"]}]
                                elif api == "https://cataas.com/cat?json=true":
                                    data = [{"url": f"https://cataas.com{json_data['url']}"}]
                                else:
                                    data = json_data
                                break
                except:
                    continue
            
            if not data or not isinstance(data, list) or len(data) == 0:
                # Fallback cat images
                fallback_cats = [
                    "https://cataas.com/cat",
                    "https://placekitten.com/400/300",
                    "https://i.imgur.com/jRBBASV.jpg"
                ]
                cat_url = random.choice(fallback_cats)
            else:
                cat_url = data[0]['url']
            
            embed = discord.Embed(
                title="🐱 Mèo dễ thương!",
                color=0x7289DA
            )
            embed.set_image(url=cat_url)
            embed.set_footer(text="Meow! 🐾")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='dog', aliases=['cho'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def dog(self, ctx):
        """Gửi ảnh chó random"""
        async with ctx.typing():
            # Thử nhiều API khác nhau
            dog_apis = [
                "https://api.thedogapi.com/v1/images/search",
                "https://dog.ceo/api/breeds/image/random",
                "https://random.dog/woof.json"
            ]
            
            data = None
            for api in dog_apis:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api) as response:
                            if response.status == 200:
                                json_data = await response.json()
                                if api == "https://dog.ceo/api/breeds/image/random":
                                    data = [{"url": json_data["message"]}]
                                elif api == "https://random.dog/woof.json":
                                    data = [{"url": json_data["url"]}]
                                else:
                                    data = json_data
                                break
                except:
                    continue
            
            if not data or not isinstance(data, list) or len(data) == 0:
                # Fallback dog images
                fallback_dogs = [
                    "https://place.dog/400/300",
                    "https://i.imgur.com/MP9jAiW.jpg",
                    "https://images.dog.ceo/breeds/labrador/n02099712_1181.jpg"
                ]
                dog_url = random.choice(fallback_dogs)
            else:
                dog_url = data[0]['url']
            
            embed = discord.Embed(
                title="🐶 Chó dễ thương!",
                color=0x7289DA
            )
            embed.set_image(url=dog_url)
            embed.set_footer(text="Woof! 🐾")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='image', aliases=['img', 'pic'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def random_image(self, ctx, *, query: str = None):
        """Gửi ảnh random hoặc theo từ khóa"""
        async with ctx.typing():
            if not query:
                # Random images từ các nguồn khác nhau
                random_sources = [
                    "https://picsum.photos/400/300",
                    "https://source.unsplash.com/400x300/?nature",
                    "https://source.unsplash.com/400x300/?city",
                    "https://source.unsplash.com/400x300/?art",
                    "https://source.unsplash.com/400x300/?animal"
                ]
                image_url = random.choice(random_sources)
                title = "🖼️ Ảnh ngẫu nhiên"
                query_text = "Random"
            else:
                # Tìm ảnh theo từ khóa
                search_query = query.replace(" ", "%20")
                image_url = f"https://source.unsplash.com/400x300/?{search_query}"
                title = f"🔍 Ảnh về: {query}"
                query_text = query
            
            embed = discord.Embed(
                title=title,
                color=0x7289DA
            )
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Từ khóa: {query_text} • Powered by Unsplash")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='anime', aliases=['waifu'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_image(self, ctx):
        """Gửi ảnh anime random"""
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.waifu.pics/sfw/waifu") as response:
                        if response.status == 200:
                            data = await response.json()
                            image_url = data["url"]
                        else:
                            raise Exception("API not available")
            except:
                # Fallback anime images
                fallback_anime = [
                    "https://i.imgur.com/5Q5R5wM.jpg",
                    "https://i.imgur.com/yQVH6R4.jpg",
                    "https://i.imgur.com/8n8QKAW.jpg"
                ]
                image_url = random.choice(fallback_anime)
            
            embed = discord.Embed(
                title="🎌 Anime Random",
                color=0x7289DA
            )
            embed.set_image(url=image_url)
            embed.set_footer(text="Kawaii desu! ✨")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='pokemon', aliases=['poke'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pokemon(self, ctx, pokemon_name: str = None):
        """Hiển thị thông tin Pokemon"""
        async with ctx.typing():
            if not pokemon_name:
                # Random pokemon
                pokemon_id = random.randint(1, 151)  # Gen 1 pokemon
                url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
            else:
                url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                        else:
                            await ctx.send("❌ Không tìm thấy Pokemon này!")
                            return
            except:
                await ctx.send("❌ Lỗi khi tìm Pokemon!")
                return
            
            name = data["name"].title()
            pokemon_id = data["id"]
            height = data["height"] / 10  # Convert to meters
            weight = data["weight"] / 10  # Convert to kg
            types = [t["type"]["name"].title() for t in data["types"]]
            
            embed = discord.Embed(
                title=f"#{pokemon_id:03d} {name}",
                color=0x7289DA
            )
            embed.set_thumbnail(url=data["sprites"]["front_default"])
            embed.add_field(name="Loại", value=" / ".join(types), inline=True)
            embed.add_field(name="Chiều cao", value=f"{height}m", inline=True)
            embed.add_field(name="Cân nặng", value=f"{weight}kg", inline=True)
            embed.set_footer(text="Gotta catch 'em all! 🔥")
            
            await ctx.send(embed=embed)
    
    @commands.command(name='flip', aliases=['coinflip', 'coin'])
    async def flip_coin(self, ctx):
        """Tung đồng xu"""
        result = random.choice(['Ngửa', 'Sấp'])
        emoji = '🪙' if result == 'Ngửa' else '🥞'
        
        embed = discord.Embed(
            title="🪙 Tung đồng xu",
            description=f"{emoji} **{result}**!",
            color=0x7289DA
        )
        embed.set_footer(text=f"Tung bởi {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='dice', aliases=['roll', 'zar'])
    async def roll_dice(self, ctx, sides: int = 6):
        """Tung xúc xắc"""
        if sides < 2 or sides > 100:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Số mặt phải từ 2 đến 100!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        result = random.randint(1, sides)
        
        embed = discord.Embed(
            title="🎲 Tung xúc xắc",
            description=f"Xúc xắc {sides} mặt: **{result}**",
            color=0x7289DA
        )
        embed.set_footer(text=f"Tung bởi {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='choose', aliases=['pick'])
    async def choose(self, ctx, *, choices: str = None):
        """Chọn ngẫu nhiên từ danh sách (cách nhau bởi dấu phẩy)"""
        if not choices:
            embed = discord.Embed(
                title="❌ Thiếu lựa chọn",
                description=f"Sử dụng: `{self.bot.config['prefix']}choose option1, option2, option3`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        choice_list = [choice.strip() for choice in choices.split(',')]
        if len(choice_list) < 2:
            embed = discord.Embed(
                title="❌ Lỗi", 
                description="Cần ít nhất 2 lựa chọn, cách nhau bởi dấu phẩy!",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        chosen = random.choice(choice_list)
        
        embed = discord.Embed(
            title="🤔 Lựa chọn của tôi",
            description=f"Tôi chọn: **{chosen}**",
            color=0x7289DA
        )
        embed.add_field(
            name="Các lựa chọn",
            value=", ".join(choice_list),
            inline=False
        )
        embed.set_footer(text=f"Chọn cho {ctx.author.display_name}")
        
        await ctx.send(embed=embed)

    # Helper methods for menu system interactions
    async def meme_command(self, interaction):
        """Helper method for meme command via interaction"""
        await interaction.response.defer()
        
        # Try different APIs for memes
        api_urls = [
            "https://meme-api.com/gimme",
            "https://meme-api.herokuapp.com/gimme", 
            "https://memes.blademaker.tv/api/random"
        ]
        
        data = None
        for url in api_urls:
            data = await self.fetch_json(url)
            if data:
                break
        
        if not data:
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Không thể tải meme lúc này. Thử lại sau!",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Handle different API response formats
        title = data.get('title', 'Random Meme')
        image_url = data.get('url') or data.get('image')
        post_link = data.get('postLink', '')
        
        if not image_url:
            await interaction.followup.send("❌ Không thể tải ảnh meme!")
            return
        
        embed = discord.Embed(
            title="😂 Meme cho bạn!",
            description=title[:256],  # Limit title length
            color=0xFF6B35
        )
        embed.set_image(url=image_url)
        
        if post_link:
            embed.add_field(name="🔗 Nguồn", value=f"[Reddit]({post_link})", inline=False)
        
        embed.set_footer(text="🎯 Meme được tải từ Reddit")
        
        await interaction.followup.send(embed=embed)

    async def cat_command(self, interaction):
        """Helper method for cat command via interaction"""
        await interaction.response.defer()
        
        data = await self.fetch_json("https://api.thecatapi.com/v1/images/search")
        
        if not data or not data[0].get('url'):
            embed = discord.Embed(
                title="❌ Lỗi",
                description="Không thể tải ảnh mèo lúc này!",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🐱 Mèo dễ thương cho bạn!",
            color=0xFFB6C1
        )
        embed.set_image(url=data[0]['url'])
        embed.set_footer(text="🐾 Ảnh từ The Cat API")
        
        await interaction.followup.send(embed=embed)

    async def dog_command(self, interaction):
        """Helper method for dog command via interaction"""
        await interaction.response.defer()
        
        data = await self.fetch_json("https://api.thedogapi.com/v1/images/search")
        
        if not data or not data[0].get('url'):
            embed = discord.Embed(
                title="❌ Lỗi", 
                description="Không thể tải ảnh chó lúc này!",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🐶 Chó đáng yêu cho bạn!",
            color=0xDEB887
        )
        embed.set_image(url=data[0]['url'])
        embed.set_footer(text="🐕 Ảnh từ The Dog API")
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
