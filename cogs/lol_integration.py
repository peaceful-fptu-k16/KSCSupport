import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import json
import urllib.parse
from datetime import datetime, timedelta
import random
import re
from bs4 import BeautifulSoup

class LeagueOfLegends(commands.Cog):
    """League of Legends related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://ddragon.leagueoflegends.com"
        self.riot_api_base = "https://kr.api.riotgames.com"  # Thay đổi sang KR server
        self.riot_api_key = "RGAPI-b1ea1263-d2ff-4fa1-b214-e245b0f1adb6"
        
        # Cache cho champion data
        self.champions_cache = {}
        self.items_cache = {}
        self.cache_time = None
        
        # Cache cho rotation data
        self.rotation_cache = None
        self.rotation_cache_time = None
        
        # Dictionary tên items tiếng Việt
        self.items_vietnamese = {
            # Mythic Items
            "Kraken Slayer": "Kẻ Giết Kraken",
            "Galeforce": "Lực Gió",
            "Immortal Shieldbow": "Cung Khiên Bất Tử",
            "Duskblade of Draktharr": "Lưỡi Hoàng Hôn của Draktharr",
            "Prowler's Claw": "Móng Vuốt Thám Hiểm",
            "Eclipse": "Nhật Thực",
            "Luden's Tempest": "Bão Tố Luden",
            "Liandry's Anguish": "Nỗi Thống Khổ của Liandry",
            "Everfrost": "Băng Vĩnh Cửu",
            "Night Harvester": "Người Gặt Đêm",
            "Riftmaker": "Kẻ Tạo Vết Nứt",
            "Hextech Rocketbelt": "Thắt Lưng Tên Lửa Hextech",
            "Sunfire Aegis": "Lá Chắn Ánh Dương",
            "Frostfire Gauntlet": "Găng Tay Băng Lửa",
            "Turbo Chemtank": "Bình Chứa Hóa Chất Turbo",
            "Locket of the Iron Solari": "Mặt Dây Chuyền Solari Thép",
            "Shurelya's Battlesong": "Bài Ca Chiến Đấu của Shurelya",
            "Imperial Mandate": "Sắc Lệnh Hoàng Gia",
            
            # Legendary Items
            "Infinity Edge": "Lưỡi Dao Vô Cực",
            "Phantom Dancer": "Vũ Công Ma",
            "Rapid Firecannon": "Đại Bác Tốc Xạ",
            "Runaan's Hurricane": "Cơn Bão Runaan",
            "The Collector": "Người Sưu Tập",
            "Lord Dominik's Regards": "Lời Chúc của Lãnh Chủ Dominik",
            "Mortal Reminder": "Lời Nhắc Tử Thần",
            "Guardian Angel": "Thiên Thần Hộ Mệnh",
            "Bloodthirster": "Kẻ Khát Máu",
            "Wit's End": "Tận Cùng Trí Tuệ",
            "Blade of the Ruined King": "Lưỡi Dao Vua Hủy Diệt",
            "Youmuu's Ghostblade": "Kiếm Ma của Youmuu",
            "Edge of Night": "Bờ Vực Màn Đêm",
            "Serylda's Grudge": "Hận Thù Serylda",
            "Black Cleaver": "Rìu Đen",
            "Death's Dance": "Điệu Nhảy Tử Thần",
            "Sterak's Gage": "Thước Đo Sterak",
            "Chempunk Chainsword": "Kiếm Xích Chempunk",
            "Silvermere Dawn": "Bình Minh Silvermere",
            "Maw of Malmortius": "Hàm Malmortius",
            
            # Mage Items
            "Rabadon's Deathcap": "Mũ Tử Thần Rabadon",
            "Void Staff": "Gậy Hư Vô",
            "Zhonya's Hourglass": "Đồng Hồ Cát Zhonya",
            "Banshee's Veil": "Mạng Che Banshee",
            "Morellonomicon": "Morellonomicon",
            "Rylai's Crystal Scepter": "Trượng Pha Lê Rylai",
            "Cosmic Drive": "Động Lực Vũ Trụ",
            "Horizon Focus": "Tiêu Điểm Chân Trời",
            "Demonic Embrace": "Ôm Ấp Ác Quỷ",
            "Archangel's Staff": "Gậy Tổng Lãnh Thiên Thần",
            
            # Tank Items
            "Thornmail": "Áo Gai",
            "Randuin's Omen": "Điềm Báo Randuin",
            "Dead Man's Plate": "Tấm Giáp Người Chết",
            "Force of Nature": "Sức Mạnh Tự Nhiên",
            "Spirit Visage": "Mặt Nạ Linh Hồn",
            "Adaptive Helm": "Mũ Thích Nghi",
            "Gargoyle Stoneplate": "Tấm Đá Gargoyle",
            "Warmog's Armor": "Giáp Warmog",
            "Frozen Heart": "Trái Tim Băng Giá",
            "Righteous Glory": "Vinh Quang Chính Nghĩa",
            
            # Support Items
            "Redemption": "Cứu Rỗi",
            "Knight's Vow": "Lời Thề Hiệp Sĩ",
            "Ardent Censer": "Lư Hương Cuồng Nhiệt",
            "Staff of Flowing Water": "Gậy Nước Chảy",
            "Mikael's Blessing": "Phước Lành Mikael",
            "Chemtech Putrifier": "Máy Lọc Chemtech",
            
            # Boots
            "Berserker's Greaves": "Ủng Chiến Binh Cuồng",
            "Sorcerer's Shoes": "Giày Phù Thủy",
            "Plated Steelcaps": "Mũ Thép Được Mạ",
            "Mercury's Treads": "Giày Mercury",
            "Ionian Boots of Lucidity": "Ủng Sáng Suốt Ionia",
            "Boots of Mobility": "Ủng Di Chuyển",
            "Boots of Swiftness": "Ủng Nhanh Nhẹn"
        }
        
        # OP.GG URLs
        self.opgg_base_url = "https://op.gg/vi/lol/champions"
        self.opgg_champion_url = "https://op.gg/vi/lol/champions/{champion_name}"
        
        # Cache cho OP.GG data
        self.opgg_cache = {}
        self.opgg_cache_time = None
        
        # Database tướng counter (data mẫu - có thể được cập nhật từ API)
        self.counter_data = {
            "Yasuo": {
                "counters": ["Malzahar", "Pantheon", "Annie", "Renekton"],
                "good_against": ["Zed", "Katarina", "Azir", "Orianna"],
                "win_rate": "49.2%",
                "positions": ["Mid Lane", "Top Lane"],
                "difficulty": 10
            },
            "Zed": {
                "counters": ["Malzahar", "Lissandra", "Kayle", "Lulu"],
                "good_against": ["Yasuo", "Katarina", "LeBlanc", "Syndra"],
                "win_rate": "50.8%",
                "positions": ["Mid Lane"],
                "difficulty": 7
            },
            "Jinx": {
                "counters": ["Draven", "Lucian", "Tristana", "Miss Fortune"],
                "good_against": ["Kog'Maw", "Twitch", "Vayne", "Ezreal"],
                "win_rate": "51.5%",
                "positions": ["Bot Lane"],
                "difficulty": 6
            },
            "Thresh": {
                "counters": ["Morgana", "Sivir", "Ezreal", "Soraka"],
                "good_against": ["Vayne", "Jinx", "Kog'Maw", "Miss Fortune"],
                "win_rate": "49.8%",
                "positions": ["Support"],
                "difficulty": 7
            },
            "Lee Sin": {
                "counters": ["Rammus", "Jax", "Poppy", "Malphite"],
                "good_against": ["Karthus", "Graves", "Nidalee", "Kindred"],
                "win_rate": "48.9%",
                "positions": ["Jungle"],
                "difficulty": 8
            }
            # Có thể thêm nhiều tướng khác...
        }
        
    async def get_latest_version(self):
        """Get latest game version"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/versions.json") as resp:
                    if resp.status == 200:
                        versions = await resp.json()
                        return versions[0] if versions else "13.24.1"
        except:
            pass
        return "13.24.1"  # Fallback version

    async def get_champions_data(self):
        """Get champions data with caching"""
        now = datetime.now()
        
        # Check cache (refresh every hour)
        if (self.champions_cache and self.cache_time and 
            (now - self.cache_time) < timedelta(hours=1)):
            return self.champions_cache
        
        try:
            version = await self.get_latest_version()
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/cdn/{version}/data/vi_VN/champion.json"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.champions_cache = data.get('data', {})
                        self.cache_time = now
                        return self.champions_cache
        except:
            pass
        
        # Return cached data or empty dict if no cache
        return self.champions_cache or {}

    async def get_items_data(self):
        """Get items data with caching"""
        now = datetime.now()
        
        # Check cache
        if (self.items_cache and self.cache_time and 
            (now - self.cache_time) < timedelta(hours=1)):
            return self.items_cache
        
        try:
            version = await self.get_latest_version()
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/cdn/{version}/data/vi_VN/item.json"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.items_cache = data.get('data', {})
                        return self.items_cache
        except:
            pass
        
        return self.items_cache or {}

    async def get_champion_rotation(self):
        """Get free champion rotation from Riot API"""
        now = datetime.now()
        
        # Check cache (refresh every 6 hours since rotation changes weekly)
        if (self.rotation_cache and self.rotation_cache_time and 
            (now - self.rotation_cache_time) < timedelta(hours=6)):
            return self.rotation_cache
        
        # Try multiple regions
        regions = ["kr", "na1", "euw1", "eun1"]
        
        for region in regions:
            try:
                headers = {
                    'X-Riot-Token': self.riot_api_key
                }
                
                async with aiohttp.ClientSession() as session:
                    url = f"https://{region}.api.riotgames.com/lol/platform/v3/champion-rotations"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            rotation_data = await resp.json()
                            
                            # Get champion data to convert IDs to names
                            champions_data = await self.get_champions_data()
                            
                            # Convert champion IDs to names
                            free_champions = []
                            newbie_free_champions = []
                            
                            # Create ID to name mapping
                            id_to_name = {}
                            for champ_key, champ_data in champions_data.items():
                                champ_id = int(champ_data.get('key', 0))
                                id_to_name[champ_id] = champ_data['name']
                            
                            # Get free champions for all players
                            for champ_id in rotation_data.get('freeChampionIds', []):
                                if champ_id in id_to_name:
                                    free_champions.append(id_to_name[champ_id])
                            
                            # Get free champions for new players (level < 11)
                            for champ_id in rotation_data.get('freeChampionIdsForNewPlayers', []):
                                if champ_id in id_to_name:
                                    newbie_free_champions.append(id_to_name[champ_id])
                            
                            self.rotation_cache = {
                                'free_champions': free_champions,
                                'newbie_free_champions': newbie_free_champions,
                                'max_new_player_level': rotation_data.get('maxNewPlayerLevel', 10),
                                'last_updated': now.strftime('%Y-%m-%d %H:%M'),
                                'next_rotation': 'Thứ 3 hàng tuần (theo múi giờ Riot)',
                                'source_region': region.upper()
                            }
                            self.rotation_cache_time = now
                            print(f"Successfully fetched rotation data from {region.upper()}")
                            return self.rotation_cache
                            
                        elif resp.status == 403:
                            print(f"API key forbidden for region {region}")
                            continue
                        elif resp.status == 429:
                            print(f"Rate limit exceeded for region {region}")
                            continue
                        else:
                            print(f"API error {resp.status} for region {region}")
                            continue
                            
            except Exception as e:
                print(f"Error getting champion rotation from {region}: {e}")
                continue
        
        # If all regions fail, return fallback data
        if not self.rotation_cache:
            print("All regions failed, using fallback data")
            return self.get_fallback_rotation_data()
        
        # Return cached data if available
        return self.rotation_cache
    
    def get_fallback_rotation_data(self):
        """Return fallback rotation data when API fails"""
        now = datetime.now()
        return {
            'free_champions': [
                "Ashe", "Garen", "Lux", "Jinx", "Thresh", "Yasuo", "Zed", 
                "Ahri", "Lee Sin", "Darius", "Malzahar", "Morgana", "Sivir", "Annie"
            ],
            'newbie_free_champions': [
                "Ashe", "Garen", "Lux", "Annie", "Master Yi", 
                "Malzahar", "Soraka", "Sona", "Warwick", "Ryze"
            ],
            'max_new_player_level': 10,
            'last_updated': now.strftime('%Y-%m-%d %H:%M'),
            'next_rotation': 'Thứ 3 hàng tuần (theo múi giờ Riot)',
            'source_region': 'FALLBACK',
            'is_fallback': True
        }

    async def scrape_opgg_champion_data(self, champion_name):
        """Scrape champion data from OP.GG"""
        try:
            # Chuyển tên tướng thành format URL-friendly
            champion_url_name = champion_name.lower().replace("'", "").replace(" ", "")
            
            # Một số tướng có tên đặc biệt
            name_mapping = {
                "wukong": "monkeyking",
                "nunu": "nunuwillump",
                "aurelionsol": "aurelionsol",
                "jarvaniv": "jarvaniv",
                "leesin": "leesin",
                "masteryi": "masteryi",
                "missfortune": "missfortune",
                "twistedfate": "twistedfate",
                "xinzhao": "xinzhao"
            }
            
            champion_url_name = name_mapping.get(champion_url_name, champion_url_name)
            
            url = f"https://op.gg/vi/lol/champions/{champion_url_name}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract win rate
                    win_rate = "N/A"
                    win_rate_elem = soup.select_one('.champion-overview__data .win-rate')
                    if win_rate_elem:
                        win_rate = win_rate_elem.text.strip()
                    
                    # Extract pick rate
                    pick_rate = "N/A"
                    pick_rate_elem = soup.select_one('.champion-overview__data .pick-rate')
                    if pick_rate_elem:
                        pick_rate = pick_rate_elem.text.strip()
                    
                    # Extract ban rate
                    ban_rate = "N/A"
                    ban_rate_elem = soup.select_one('.champion-overview__data .ban-rate')
                    if ban_rate_elem:
                        ban_rate = ban_rate_elem.text.strip()
                    
                    # Extract tier
                    tier = "N/A"
                    tier_elem = soup.select_one('.champion-overview__tier')
                    if tier_elem:
                        tier = tier_elem.text.strip()
                    
                    # Extract positions
                    positions = []
                    position_elems = soup.select('.champion-position-stats__position')
                    for pos in position_elems:
                        pos_name = pos.select_one('.position-name')
                        if pos_name:
                            positions.append(pos_name.text.strip())
                    
                    # Extract counters (tướng mạnh nhất chống lại tướng này)
                    counters = []
                    counter_elems = soup.select('.champion-matchup-list__item--strong')[:5]
                    for counter in counter_elems:
                        counter_name = counter.select_one('.champion-name')
                        if counter_name:
                            counters.append(counter_name.text.strip())
                    
                    # Extract good against (tướng yếu nhất trước tướng này)
                    good_against = []
                    weak_elems = soup.select('.champion-matchup-list__item--weak')[:5]
                    for weak in weak_elems:
                        weak_name = weak.select_one('.champion-name')
                        if weak_name:
                            good_against.append(weak_name.text.strip())
                    
                    return {
                        'win_rate': win_rate,
                        'pick_rate': pick_rate,
                        'ban_rate': ban_rate,
                        'tier': tier,
                        'positions': positions if positions else ['Unknown'],
                        'counters': counters,
                        'good_against': good_against,
                        'source': 'OP.GG',
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                    
        except Exception as e:
            print(f"Error scraping OP.GG for {champion_name}: {e}")
            return None

    async def get_opgg_champion_data(self, champion_name):
        """Get champion data from OP.GG with caching"""
        now = datetime.now()
        
        # Check cache (refresh every 2 hours)
        cache_key = champion_name.lower()
        if (cache_key in self.opgg_cache and self.opgg_cache_time and 
            (now - self.opgg_cache_time) < timedelta(hours=2)):
            return self.opgg_cache[cache_key]
        
        # Scrape new data
        opgg_data = await self.scrape_opgg_champion_data(champion_name)
        
        if opgg_data:
            # Initialize cache if needed
            if not hasattr(self, 'opgg_cache_time') or not self.opgg_cache_time:
                self.opgg_cache_time = now
            
            self.opgg_cache[cache_key] = opgg_data
            return opgg_data
        
        return None

    def get_item_vietnamese_name(self, english_name):
        """Get Vietnamese name for item"""
        return self.items_vietnamese.get(english_name, english_name)
    
    def get_champion_counter_data(self, champion_name):
        """Get counter data for champion"""
        # Tìm tướng trong database counter
        for champ_key, champ_data in self.counter_data.items():
            if champ_key.lower() == champion_name.lower():
                return champ_data
        return None
    
    async def get_item_image_url(self, item_name, version=None):
        """Get item image URL"""
        if not version:
            version = await self.get_latest_version()
        
        # Convert Vietnamese name back to English if needed
        english_name = None
        for eng, viet in self.items_vietnamese.items():
            if viet == item_name or eng == item_name:
                english_name = eng
                break
        
        if not english_name:
            english_name = item_name
        
        # Get items data to find item ID
        items_data = await self.get_items_data()
        for item_id, item_info in items_data.items():
            if item_info.get('name') == english_name:
                return f"{self.base_url}/cdn/{version}/img/item/{item_id}.png"
        
        return None

    def find_champion(self, champions_data, search_term):
        """Find champion by name (supports partial matching)"""
        search_term = search_term.lower()
        
        # Exact match first
        for champ_key, champ_data in champions_data.items():
            if (champ_data['name'].lower() == search_term or 
                champ_data['id'].lower() == search_term or
                champ_key.lower() == search_term):
                return champ_data
        
        # Partial match
        for champ_key, champ_data in champions_data.items():
            if (search_term in champ_data['name'].lower() or 
                search_term in champ_data['id'].lower() or
                search_term in champ_key.lower()):
                return champ_data
        
        return None

    @commands.command(name='champion', aliases=['champ', 'tuong'])
    async def champion_info(self, ctx, *, champion_name):
        """Hiển thị thông tin tướng League of Legends"""
        async with ctx.typing():
            champions_data = await self.get_champions_data()
            
            if not champions_data:
                await ctx.send("❌ Không thể tải dữ liệu tướng!")
                return
            
            champion = self.find_champion(champions_data, champion_name)
            
            if not champion:
                # Gợi ý tướng tương tự
                suggestions = []
                search_lower = champion_name.lower()
                for champ_data in list(champions_data.values())[:10]:
                    if any(word in champ_data['name'].lower() for word in search_lower.split()):
                        suggestions.append(champ_data['name'])
                
                suggestion_text = f"\n💡 **Có thể bạn muốn tìm:** {', '.join(suggestions[:5])}" if suggestions else ""
                await ctx.send(f"❌ Không tìm thấy tướng **{champion_name}**!{suggestion_text}")
                return
            
            version = await self.get_latest_version()
            
            embed = discord.Embed(
                title=f"🏆 {champion['name']} - {champion['title']}",
                description=champion.get('blurb', 'Không có mô tả'),
                color=0x0F2027
            )
            
            # Champion image
            champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
            embed.set_thumbnail(url=champion_img)
            
            # Basic info
            embed.add_field(
                name="📊 Thông tin cơ bản",
                value=f"**Vai trò:** {', '.join(champion.get('tags', ['Unknown']))}\n"
                     f"**Độ khó:** {champion.get('info', {}).get('difficulty', 'N/A')}/10",
                inline=True
            )
            
            # Stats
            info = champion.get('info', {})
            embed.add_field(
                name="⚔️ Chỉ số",
                value=f"**Tấn công:** {info.get('attack', 0)}/10\n"
                     f"**Phòng thủ:** {info.get('defense', 0)}/10\n"
                     f"**Phép thuật:** {info.get('magic', 0)}/10",
                inline=True
            )
            
            # Thêm thông báo đang tải dữ liệu OP.GG
            loading_msg = await ctx.send(f"🔄 Đang tải thống kê real-time từ OP.GG cho **{champion['name']}**...")
            
            # Try to get OP.GG data
            opgg_data = await self.get_opgg_champion_data(champion['name'])
            
            if opgg_data:
                embed.add_field(
                    name="📈 Thống kê Meta (OP.GG Real-time)",
                    value=f"**Tỉ lệ thắng:** {opgg_data['win_rate']}\n"
                         f"**Tỉ lệ pick:** {opgg_data['pick_rate']}\n"
                         f"**Tỉ lệ ban:** {opgg_data['ban_rate']}\n"
                         f"**Tier:** {opgg_data['tier']}\n"
                         f"**Vị trí:** {', '.join(opgg_data['positions'])}",
                    inline=False
                )
                
                if opgg_data['counters']:
                    embed.add_field(
                        name="❌ Tướng Counter (OP.GG)",
                        value="\n".join([f"• {counter}" for counter in opgg_data['counters'][:4]]),
                        inline=True
                    )
                
                if opgg_data['good_against']:
                    embed.add_field(
                        name="✅ Tốt chống lại (OP.GG)",
                        value="\n".join([f"• {good}" for good in opgg_data['good_against'][:4]]),
                        inline=True
                    )
                
                embed.set_footer(text=f"Dữ liệu từ {opgg_data['source']} • Cập nhật: {opgg_data['last_updated']}")
            else:
                # Fallback to static data
                counter_data = self.get_champion_counter_data(champion['name'])
                if counter_data:
                    embed.add_field(
                        name="📈 Thống kê Meta (Database)",
                        value=f"**Tỉ lệ thắng:** {counter_data['win_rate']}\n"
                             f"**Vị trí thích hợp:** {', '.join(counter_data['positions'])}\n"
                             f"**Độ khó:** {counter_data['difficulty']}/10",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="❌ Tướng Counter",
                        value="\n".join([f"• {counter}" for counter in counter_data['counters'][:4]]),
                        inline=True
                    )
                    
                    embed.add_field(
                        name="✅ Tốt chống lại",
                        value="\n".join([f"• {good}" for good in counter_data['good_against'][:4]]),
                        inline=True
                    )
                
                embed.set_footer(text=f"League of Legends • Version {version} • Dữ liệu từ database")
            
            embed.add_field(
                name="🎯 Lệnh liên quan",
                value="• `!build <tên tướng>` - Xem build gợi ý\n"
                     "• `!counter <tên tướng>` - Chi tiết counter\n"
                     "• `!loltips <role>` - Tips chơi theo vị trí\n"
                     "• `!item <tên item>` - Thông tin item",
                inline=False
            )
            
            # Delete loading message and send final embed
            try:
                await loading_msg.delete()
            except:
                pass
            
            await ctx.send(embed=embed)

    @commands.command(name='build')
    async def champion_build(self, ctx, *, champion_name):
        """Hiển thị build gợi ý cho tướng"""
        async with ctx.typing():
            champions_data = await self.get_champions_data()
            items_data = await self.get_items_data()
            
            if not champions_data:
                await ctx.send("❌ Không thể tải dữ liệu!")
                return
            
            champion = self.find_champion(champions_data, champion_name)
            
            if not champion:
                await ctx.send(f"❌ Không tìm thấy tướng **{champion_name}**!")
                return
            
            embed = discord.Embed(
                title=f"🛠️ Build gợi ý cho {champion['name']}",
                color=0x0F2027
            )
            
            version = await self.get_latest_version()
            champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
            embed.set_thumbnail(url=champion_img)
            
            # Build recommendations based on champion tags
            tags = champion.get('tags', [])
            
            if 'Marksman' in tags:
                core_items = [
                    "Kẻ Giết Kraken / Lực Gió",
                    "Vũ Công Ma", 
                    "Lưỡi Dao Vô Cực",
                    "Lời Chúc của Lãnh Chủ Dominik",
                    "Kẻ Khát Máu",
                    "Thiên Thần Hộ Mệnh"
                ]
                embed.add_field(
                    name="🏹 Build ADC",
                    value="**Core Items:**\n" + "\n".join([f"• {item}" for item in core_items]),
                    inline=False
                )
                embed.add_field(
                    name="👟 Giày",
                    value="• Ủng Chiến Binh Cuồng",
                    inline=True
                )
            elif 'Assassin' in tags:
                core_items = [
                    "Lưỡi Hoàng Hôn của Draktharr",
                    "Kiếm Ma của Youmuu",
                    "Người Sưu Tập", 
                    "Bờ Vực Màn Đêm",
                    "Hận Thù Serylda",
                    "Thiên Thần Hộ Mệnh"
                ]
                embed.add_field(
                    name="🗡️ Build Assassin",
                    value="**Core Items:**\n" + "\n".join([f"• {item}" for item in core_items]),
                    inline=False
                )
            elif 'Mage' in tags:
                core_items = [
                    "Bão Tố Luden / Nỗi Thống Khổ của Liandry",
                    "Giày Phù Thủy",
                    "Đồng Hồ Cát Zhonya", 
                    "Gậy Hư Vô",
                    "Mũ Tử Thần Rabadon",
                    "Mạng Che Banshee"
                ]
                embed.add_field(
                    name="🔮 Build Pháp Sư",
                    value="**Core Items:**\n" + "\n".join([f"• {item}" for item in core_items]),
                    inline=False
                )
            elif 'Tank' in tags:
                core_items = [
                    "Lá Chắn Ánh Dương / Găng Tay Băng Lửa",
                    "Mũ Thép Được Mạ / Giày Mercury",
                    "Áo Gai",
                    "Sức Mạnh Tự Nhiên", 
                    "Tấm Đá Gargoyle",
                    "Giáp Warmog"
                ]
                embed.add_field(
                    name="🛡️ Build Tank",
                    value="**Core Items:**\n" + "\n".join([f"• {item}" for item in core_items]),
                    inline=False
                )
            elif 'Support' in tags:
                core_items = [
                    "Mặt Dây Chuyền Solari Thép",
                    "Cứu Rỗi",
                    "Lời Thề Hiệp Sĩ",
                    "Lư Hương Cuồng Nhiệt",
                    "Gậy Nước Chảy",
                    "Ủng Di Chuyển"
                ]
                embed.add_field(
                    name="💎 Build Support",
                    value="**Core Items:**\n" + "\n".join([f"• {item}" for item in core_items]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚔️ Build tổng quát",
                    value="**Lưu ý:** Build phụ thuộc vào vai trò và meta hiện tại\n"
                         "Hãy tham khảo các trang web chuyên nghiệp như:\n"
                         "• [U.GG](https://u.gg/)\n• [OP.GG](https://op.gg/)\n• [Mobafire](https://mobafire.com/)\n• [ProBuilds](https://probuilds.net/)",
                    inline=False
                )
            
            # Counter data for build adjustment
            counter_data = self.get_champion_counter_data(champion['name'])
            if counter_data:
                embed.add_field(
                    name="� Thống kê",
                    value=f"**Tỉ lệ thắng:** {counter_data['win_rate']}\n"
                         f"**Vị trí:** {', '.join(counter_data['positions'])}",
                    inline=True
                )
            
            embed.add_field(
                name="💡 Lưu ý quan trọng",
                value="• Build có thể thay đổi tùy theo meta hiện tại\n"
                     "• Điều chỉnh theo đội hình địch và đồng minh\n"
                     "• Thứ tự item có thể thay đổi theo tình huống\n"
                     "• Xem thêm: `!counter <tướng>` để biết cách build chống counter",
                inline=False
            )
            
            embed.set_footer(text="💡 Đây là build gợi ý cơ bản - hãy điều chỉnh theo tình huống thực tế!")
            
            await ctx.send(embed=embed)

    @commands.command(name='counter')
    async def champion_counter(self, ctx, *, champion_name):
        """Hiển thị thông tin counter chi tiết cho tướng"""
        async with ctx.typing():
            champions_data = await self.get_champions_data()
            
            if not champions_data:
                await ctx.send("❌ Không thể tải dữ liệu tướng!")
                return
            
            champion = self.find_champion(champions_data, champion_name)
            
            if not champion:
                await ctx.send(f"❌ Không tìm thấy tướng **{champion_name}**!")
                return
            
            # Loading message for OP.GG data
            loading_msg = await ctx.send(f"🔄 Đang phân tích counter cho **{champion['name']}** từ OP.GG...")
            
            version = await self.get_latest_version()
            
            embed = discord.Embed(
                title=f"⚔️ Counter Analysis: {champion['name']}",
                color=0x0F2027
            )
            
            # Champion image
            champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
            embed.set_thumbnail(url=champion_img)
            
            # Try to get OP.GG data first
            opgg_data = await self.get_opgg_champion_data(champion['name'])
            
            if opgg_data:
                # Use OP.GG real-time data
                embed.add_field(
                    name="� Thống kê Meta (OP.GG Real-time)",
                    value=f"🏆 **Win Rate:** {opgg_data['win_rate']}\n"
                         f"📊 **Pick Rate:** {opgg_data['pick_rate']}\n"
                         f"🚫 **Ban Rate:** {opgg_data['ban_rate']}\n"
                         f"⭐ **Tier:** {opgg_data['tier']}\n"
                         f"📍 **Positions:** {', '.join(opgg_data['positions'])}",
                    inline=False
                )
                
                if opgg_data['counters']:
                    counters_info = {
                        "Malzahar": "🔒 Suppress + Magic Shield",
                        "Pantheon": "🛡️ Block + Early Game Power", 
                        "Annie": "🐻 Instant Stun + Burst",
                        "Renekton": "🐊 Tank + Sustain",
                        "Lissandra": "❄️ AOE CC + Zhonya",
                        "Kayle": "⚡ Late Game + Range",
                        "Lulu": "🧚 Polymorph + Shield",
                        "Draven": "🪓 Early Game Damage",
                        "Lucian": "💨 Mobility + Burst",
                        "Tristana": "💣 Range + Escape",
                        "Miss Fortune": "🔫 AOE + Lane Control",
                        "Morgana": "🖤 Spell Shield + Root",
                        "Sivir": "🪃 Spell Shield + Waveclear",
                        "Ezreal": "🌟 Poke + Mobility",
                        "Soraka": "🌙 Sustain + Silence",
                        "Rammus": "🦔 Armor + Taunt",
                        "Jax": "👊 Counter-Strike + Scale",
                        "Poppy": "🔨 Wall Stun + Tank",
                        "Malphite": "🗿 Armor + AOE Engage"
                    }
                    
                    counter_list = []
                    for counter in opgg_data['counters'][:5]:
                        reason = counters_info.get(counter, "Strong Against")
                        counter_list.append(f"**{counter}**\n└ {reason}")
                    
                    embed.add_field(
                        name="❌ Tướng Counter (OP.GG)",
                        value="\n\n".join(counter_list),
                        inline=True
                    )
                
                if opgg_data['good_against']:
                    good_list = []
                    for good in opgg_data['good_against'][:5]:
                        good_list.append(f"**{good}**\n└ Matchup thuận lợi")
                    
                    embed.add_field(
                        name="✅ Tốt chống lại (OP.GG)",
                        value="\n\n".join(good_list),
                        inline=True
                    )
                
                embed.set_footer(text=f"Dữ liệu từ {opgg_data['source']} • Cập nhật: {opgg_data['last_updated']}")
            
            else:
                # Fallback to static data
                counter_data = self.get_champion_counter_data(champion['name'])
                
                if counter_data:
                    embed.add_field(
                        name="📊 Thống kê Meta (Database)",
                        value=f"🏆 **Win Rate:** {counter_data['win_rate']}\n"
                             f"📍 **Best Positions:** {', '.join(counter_data['positions'])}\n"
                             f"⚡ **Difficulty:** {counter_data['difficulty']}/10",
                        inline=False
                    )
                    
                    counters_info = {
                        "Malzahar": "🔒 Suppress + Magic Shield",
                        "Pantheon": "🛡️ Block + Early Game Power", 
                        "Annie": "🐻 Instant Stun + Burst",
                        "Renekton": "🐊 Tank + Sustain",
                        "Lissandra": "❄️ AOE CC + Zhonya",
                        "Kayle": "⚡ Late Game + Range",
                        "Lulu": "🧚 Polymorph + Shield",
                        "Draven": "🪓 Early Game Damage",
                        "Lucian": "💨 Mobility + Burst",
                        "Tristana": "💣 Range + Escape",
                        "Miss Fortune": "🔫 AOE + Lane Control",
                        "Morgana": "🖤 Spell Shield + Root",
                        "Sivir": "🪃 Spell Shield + Waveclear",
                        "Ezreal": "🌟 Poke + Mobility",
                        "Soraka": "🌙 Sustain + Silence",
                        "Rammus": "🦔 Armor + Taunt",
                        "Jax": "👊 Counter-Strike + Scale",
                        "Poppy": "🔨 Wall Stun + Tank",
                        "Malphite": "🗿 Armor + AOE Engage"
                    }
                    
                    counter_list = []
                    for counter in counter_data['counters'][:5]:
                        reason = counters_info.get(counter, "Strong Against")
                        counter_list.append(f"**{counter}**\n└ {reason}")
                    
                    embed.add_field(
                        name="❌ Tướng Counter (Database)",
                        value="\n\n".join(counter_list),
                        inline=True
                    )
                    
                    # Good against
                    good_list = []
                    for good in counter_data['good_against'][:5]:
                        good_list.append(f"**{good}**\n└ Matchup thuận lợi")
                    
                    embed.add_field(
                        name="✅ Tốt chống lại (Database)",
                        value="\n\n".join(good_list),
                        inline=True
                    )
                    
                    embed.set_footer(text=f"League of Legends • Database • Version {version}")
                else:
                    embed.add_field(
                        name="❓ Chưa có dữ liệu counter",
                        value="Dữ liệu counter cho tướng này chưa có sẵn.\n"
                             "• Tham khảo [U.GG](https://u.gg/)\n"
                             "• Xem [OP.GG](https://op.gg/)\n"
                             "• Hỏi cộng đồng tại [r/summonerschool](https://reddit.com/r/summonerschool)",
                        inline=False
                    )
            
            # Tips chống counter
            embed.add_field(
                name="🎯 Cách chơi khi bị counter",
                value="• **Farm an toàn** - Tránh trade không cần thiết\n"
                     "• **Xin gank** - Call jungle hỗ trợ\n"
                     "• **Build phòng thủ** - Ưu tiên survivability\n"
                     "• **Roam** - Tìm cơ hội ở lane khác\n"
                     "• **Late game** - Chờ power spike",
                inline=False
            )
            
            # Items chống counter
            if 'Assassin' in champion.get('tags', []) or 'Mage' in champion.get('tags', []):
                anti_counter_items = ["Đồng Hồ Cát Zhonya", "Mạng Che Banshee", "Giày Mercury"]
            elif 'Marksman' in champion.get('tags', []):
                anti_counter_items = ["Thiên Thần Hộ Mệnh", "Tấm Giáp Malmortius", "Giày Mercury"]
            else:
                anti_counter_items = ["Mặt Nạ Linh Hồn", "Áo Gai", "Giáp Warmog"]
            
            embed.add_field(
                name="🛡️ Items phòng thủ khuyến nghị",
                value="\n".join([f"• {item}" for item in anti_counter_items]),
                inline=True
            )
            
            # Delete loading message and send final embed
            try:
                await loading_msg.delete()
            except:
                pass
            
            await ctx.send(embed=embed)

    @commands.command(name='lolmeta', aliases=['meta'])
    async def meta_info(self, ctx, *, champion_name):
        """Hiển thị thông tin meta real-time từ OP.GG"""
        async with ctx.typing():
            champions_data = await self.get_champions_data()
            
            if not champions_data:
                await ctx.send("❌ Không thể tải dữ liệu tướng!")
                return
            
            champion = self.find_champion(champions_data, champion_name)
            
            if not champion:
                await ctx.send(f"❌ Không tìm thấy tướng **{champion_name}**!")
                return
            
            loading_msg = await ctx.send(f"🔄 Đang tải dữ liệu meta real-time cho **{champion['name']}** từ OP.GG...")
            
            opgg_data = await self.get_opgg_champion_data(champion['name'])
            
            if not opgg_data:
                await loading_msg.edit(content=f"❌ Không thể tải dữ liệu OP.GG cho **{champion['name']}**!\nVui lòng thử lại sau.")
                return
            
            version = await self.get_latest_version()
            
            embed = discord.Embed(
                title=f"📊 Meta Analysis - {champion['name']}",
                description=f"Dữ liệu real-time từ {opgg_data['source']}",
                color=0x1E88E5
            )
            
            # Champion image
            champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
            embed.set_thumbnail(url=champion_img)
            
            # Core stats
            embed.add_field(
                name="🏆 Thống kê chính",
                value=f"**Win Rate:** {opgg_data['win_rate']}\n"
                     f"**Pick Rate:** {opgg_data['pick_rate']}\n"
                     f"**Ban Rate:** {opgg_data['ban_rate']}\n"
                     f"**Tier Rank:** {opgg_data['tier']}",
                inline=True
            )
            
            # Positions
            embed.add_field(
                name="📍 Vị trí phù hợp",
                value="\n".join([f"• {pos}" for pos in opgg_data['positions']]) or "N/A",
                inline=True
            )
            
            # Performance indicator
            try:
                win_rate_num = float(opgg_data['win_rate'].replace('%', ''))
                pick_rate_num = float(opgg_data['pick_rate'].replace('%', ''))
                
                if win_rate_num >= 52 and pick_rate_num >= 5:
                    performance = "🔥 **Meta Strong** - Tướng mạnh trong meta hiện tại"
                elif win_rate_num >= 50:
                    performance = "✅ **Viable** - Tướng khá tốt, có thể pick"
                elif win_rate_num >= 47:
                    performance = "⚠️ **Average** - Tướng trung bình, cần skill cao"
                else:
                    performance = "❌ **Weak** - Tướng yếu trong meta hiện tại"
            except:
                performance = "📊 **Data Available** - Xem thống kê chi tiết"
            
            embed.add_field(
                name="⚡ Đánh giá Meta",
                value=performance,
                inline=False
            )
            
            # Counters và good against
            if opgg_data['counters']:
                embed.add_field(
                    name="❌ Hard Counters",
                    value="\n".join([f"• {counter}" for counter in opgg_data['counters'][:4]]),
                    inline=True
                )
            
            if opgg_data['good_against']:
                embed.add_field(
                    name="✅ Strong Against",
                    value="\n".join([f"• {good}" for good in opgg_data['good_against'][:4]]),
                    inline=True
                )
            
            # Tips dựa trên meta
            embed.add_field(
                name="💡 Gợi ý Meta",
                value="• Kiểm tra build mới nhất trên OP.GG\n"
                     "• Theo dõi pro builds và runes\n"
                     "• Chú ý vào matchup phổ biến\n"
                     "• Tham khảo thống kê theo rank",
                inline=False
            )
            
            embed.set_footer(text=f"Cập nhật: {opgg_data['last_updated']} • Nguồn: {opgg_data['source']}")
            
            # Delete loading message and send final embed
            try:
                await loading_msg.delete()
            except:
                pass
            
            await ctx.send(embed=embed)

    @commands.command(name='item', aliases=['items'])
    async def item_info(self, ctx, *, item_name):
        """Hiển thị thông tin chi tiết về item"""
        async with ctx.typing():
            items_data = await self.get_items_data()
            version = await self.get_latest_version()
            
            if not items_data:
                await ctx.send("❌ Không thể tải dữ liệu items!")
                return
            
            # Tìm item (hỗ trợ tên tiếng Việt)
            found_item = None
            found_item_id = None
            
            # Tìm bằng tên tiếng Việt trước
            english_name = None
            for eng, viet in self.items_vietnamese.items():
                if viet.lower() == item_name.lower() or eng.lower() == item_name.lower():
                    english_name = eng
                    break
            
            if english_name:
                # Tìm item data
                for item_id, item_info in items_data.items():
                    if item_info.get('name', '').lower() == english_name.lower():
                        found_item = item_info
                        found_item_id = item_id
                        break
            else:
                # Tìm trực tiếp bằng tên
                for item_id, item_info in items_data.items():
                    if item_name.lower() in item_info.get('name', '').lower():
                        found_item = item_info
                        found_item_id = item_id
                        break
            
            if not found_item:
                await ctx.send(f"❌ Không tìm thấy item **{item_name}**!\n"
                              "💡 Thử tìm với tên tiếng Anh hoặc tiếng Việt")
                return
            
            vietnamese_name = self.get_item_vietnamese_name(found_item['name'])
            
            embed = discord.Embed(
                title=f"🏬 {vietnamese_name}",
                description=f"*{found_item['name']}*" if vietnamese_name != found_item['name'] else "",
                color=0x0F2027
            )
            
            # Item image
            item_img = f"{self.base_url}/cdn/{version}/img/item/{found_item_id}.png"
            embed.set_thumbnail(url=item_img)
            
            # Price và stats
            if found_item.get('gold'):
                gold_info = found_item['gold']
                embed.add_field(
                    name="💰 Giá cả",
                    value=f"**Tổng:** {gold_info.get('total', 0)} gold\n"
                         f"**Cơ bản:** {gold_info.get('base', 0)} gold\n"
                         f"**Bán:** {gold_info.get('sell', 0)} gold",
                    inline=True
                )
            
            # Stats
            if found_item.get('stats'):
                stats_list = []
                stats_map = {
                    'FlatHPPoolMod': '❤️ Health',
                    'FlatMPPoolMod': '💙 Mana', 
                    'FlatArmorMod': '🛡️ Armor',
                    'FlatSpellBlockMod': '🔮 Magic Resist',
                    'FlatPhysicalDamageMod': '⚔️ Attack Damage',
                    'FlatMagicDamageMod': '✨ Ability Power',
                    'PercentAttackSpeedMod': '💨 Attack Speed',
                    'FlatCritChanceMod': '💥 Crit Chance',
                    'PercentLifeStealMod': '🩸 Life Steal',
                    'FlatMovementSpeedMod': '👟 Move Speed'
                }
                
                for stat_key, stat_value in found_item['stats'].items():
                    display_name = stats_map.get(stat_key, stat_key)
                    if 'Percent' in stat_key:
                        stats_list.append(f"{display_name}: +{stat_value * 100:.0f}%")
                    else:
                        stats_list.append(f"{display_name}: +{stat_value}")
                
                if stats_list:
                    embed.add_field(
                        name="📊 Chỉ số",
                        value="\n".join(stats_list[:8]),  # Limit to 8 stats
                        inline=True
                    )
            
            # Description (passive/active)
            if found_item.get('description'):
                # Clean HTML tags
                import re
                clean_desc = re.sub(r'<[^>]+>', '', found_item['description'])
                if len(clean_desc) > 200:
                    clean_desc = clean_desc[:200] + "..."
                
                embed.add_field(
                    name="📖 Mô tả",
                    value=clean_desc,
                    inline=False
                )
            
            # Build path (items needed)
            if found_item.get('from'):
                build_items = []
                for component_id in found_item['from']:
                    if component_id in items_data:
                        comp_name = items_data[component_id]['name']
                        viet_comp = self.get_item_vietnamese_name(comp_name)
                        build_items.append(viet_comp)
                
                if build_items:
                    embed.add_field(
                        name="🔧 Nguyên liệu",
                        value=" + ".join(build_items),
                        inline=False
                    )
            
            # Builds into
            if found_item.get('into'):
                builds_into = []
                for upgrade_id in found_item['into'][:3]:  # Limit to 3
                    if upgrade_id in items_data:
                        upgrade_name = items_data[upgrade_id]['name']
                        viet_upgrade = self.get_item_vietnamese_name(upgrade_name)
                        builds_into.append(viet_upgrade)
                
                if builds_into:
                    embed.add_field(
                        name="⬆️ Nâng cấp thành",
                        value="\n".join([f"• {item}" for item in builds_into]),
                        inline=False
                    )
            
            embed.set_footer(text=f"League of Legends Items • Version {version}")
            
            await ctx.send(embed=embed)

    @commands.command(name='rotation', aliases=['free'])
    async def free_rotation(self, ctx):
        """Hiển thị tướng miễn phí tuần này từ Riot API"""
        async with ctx.typing():
            rotation_data = await self.get_champion_rotation()
            
            if not rotation_data:
                embed = discord.Embed(
                    title="❌ Không thể tải dữ liệu rotation",
                    description="Có lỗi khi kết nối tới tất cả các Riot API region.",
                    color=0xFF6B35
                )
                embed.add_field(
                    name="🔑 Riot API Status",
                    value="• API key có thể đã hết hạn\n"
                         "• Tất cả regions (KR, NA, EUW, EUNE) không khả dụng\n"
                         "• Thử lại sau vài phút\n"
                         "• Liên hệ admin để cập nhật API key",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
            
            # Check if using fallback data
            is_fallback = rotation_data.get('is_fallback', False)
            source_region = rotation_data.get('source_region', 'UNKNOWN')
            
            embed = discord.Embed(
                title="🔄 Tướng miễn phí tuần này",
                description=f"{'⚠️ Dữ liệu mẫu (API không khả dụng)' if is_fallback else f'✅ Dữ liệu real-time từ Riot API ({source_region})'}",
                color=0xFFA500 if is_fallback else 0x0F2027
            )
            
            # Free champions for all players
            if rotation_data['free_champions']:
                champions_text = ""
                for i, champ in enumerate(rotation_data['free_champions'], 1):
                    champions_text += f"{i:2d}. **{champ}**\n"
                
                embed.add_field(
                    name="🆓 Tướng miễn phí (Tất cả người chơi)",
                    value=champions_text,
                    inline=False
                )
            
            # Free champions for new players
            if rotation_data['newbie_free_champions']:
                newbie_text = ""
                for i, champ in enumerate(rotation_data['newbie_free_champions'], 1):
                    newbie_text += f"{i:2d}. **{champ}**\n"
                
                embed.add_field(
                    name=f"🔰 Tướng miễn phí (Level ≤{rotation_data['max_new_player_level']})",
                    value=newbie_text,
                    inline=False
                )
            
            # API Status info
            embed.add_field(
                name="📊 Thông tin API",
                value=f"**Nguồn:** {source_region}\n"
                     f"**Cập nhật:** {rotation_data['last_updated']}\n"
                     f"**Tổng tướng free:** {len(rotation_data['free_champions'])} tướng\n"
                     f"**Newbie rotation:** {len(rotation_data['newbie_free_champions'])} tướng",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Thông tin Rotation",
                value=f"• **Rotation mới:** {rotation_data['next_rotation']}\n"
                     "• Tận dụng tướng free để thử nghiệm\n"
                     "• Luyện tập với tướng mới trước khi mua\n"
                     f"• Dùng `!champion <tên>` để xem chi tiết tướng",
                inline=False
            )
            
            if is_fallback:
                embed.add_field(
                    name="⚠️ Lưu ý",
                    value="Đây là dữ liệu mẫu do API không khả dụng.\n"
                         "Danh sách tướng có thể không chính xác với rotation hiện tại.",
                    inline=False
                )
                embed.set_footer(text="🔑 Fallback Data • API không khả dụng")
            else:
                embed.set_footer(text=f"🔑 Powered by Riot Games API ({source_region}) • Real-time data")
            
            await ctx.send(embed=embed)

    @commands.command(name='lolpatch', aliases=['patch'])
    async def patch_info(self, ctx):
        """Hiển thị thông tin patch hiện tại"""
        version = await self.get_latest_version()
        
        embed = discord.Embed(
            title=f"🔧 League of Legends Patch {version}",
            color=0x0F2027
        )
        
        embed.add_field(
            name="📅 Thông tin patch",
            value=f"**Version hiện tại:** {version}\n"
                 f"**Cập nhật:** Khoảng 2 tuần một lần\n"
                 f"**Khu vực:** Toàn cầu",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Liên kết hữu ích",
            value="• [Patch Notes chính thức](https://www.leagueoflegends.com/en-us/news/tags/patch-notes/)\n"
                 "• [ProBuilds](https://probuilds.net/)\n"
                 "• [U.GG](https://u.gg/)\n"
                 "• [OP.GG](https://op.gg/)",
            inline=False
        )
        
        embed.add_field(
            name="💡 Lời khuyên",
            value="• Đọc patch notes để biết thay đổi\n"
                 "• Thử build mới sau mỗi patch\n"
                 "• Theo dõi meta từ pro players",
            inline=False
        )
        
        embed.set_footer(text="🎮 League of Legends")
        
        await ctx.send(embed=embed)

    @commands.command(name='loltips', aliases=['tips'])
    async def lol_tips(self, ctx, role=None):
        """Hiển thị tips chơi League of Legends theo vai trò"""
        
        if not role:
            embed = discord.Embed(
                title="🎯 League of Legends Tips",
                description="Chọn vai trò để xem tips cụ thể:",
                color=0x0F2027
            )
            embed.add_field(
                name="📝 Vai trò có sẵn",
                value="`!loltips adc` - AD Carry\n"
                     "`!loltips support` - Support\n"
                     "`!loltips jungle` - Jungle\n"
                     "`!loltips mid` - Mid Lane\n"
                     "`!loltips top` - Top Lane\n"
                     "`!loltips general` - Tips chung",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        role = role.lower()
        embed = discord.Embed(color=0x0F2027)
        
        if role in ['adc', 'marksman', 'carry']:
            embed.title = "🏹 Tips cho ADC"
            embed.add_field(
                name="🎯 Farming & Last-hit",
                value="• Tập trung farm minion\n• Học cách last-hit chính xác\n• Đừng miss cannon minion",
                inline=False
            )
            embed.add_field(
                name="⚔️ Trading & Positioning",
                value="• Giữ khoảng cách an toàn\n• Trade khi địch farm\n• Luôn ở phía sau frontline",
                inline=False
            )
            
        elif role in ['support', 'sup']:
            embed.title = "💎 Tips cho Support"
            embed.add_field(
                name="👁️ Vision Control",
                value="• Ward các bush quan trọng\n• Clear enemy wards\n• Mua Control Ward",
                inline=False
            )
            embed.add_field(
                name="🤝 Protection & Roaming",
                value="• Bảo vệ ADC\n• Roam khi có cơ hội\n• Engage khi team ready",
                inline=False
            )
            
        elif role in ['jungle', 'jg']:
            embed.title = "🌲 Tips cho Jungle"
            embed.add_field(
                name="🗺️ Pathing & Objectives",
                value="• Plan jungle route\n• Secure objectives (Dragon, Baron)\n• Track enemy jungler",
                inline=False
            )
            embed.add_field(
                name="⚡ Ganking",
                value="• Gank lanes có CC\n• Counter-gank enemy jungler\n• Farm efficiently",
                inline=False
            )
            
        elif role in ['mid', 'middle']:
            embed.title = "⭐ Tips cho Mid Lane"
            embed.add_field(
                name="📍 Map Control",
                value="• Ward both sides\n• Roam to help teammates\n• Control river vision",
                inline=False
            )
            embed.add_field(
                name="💥 Trading",
                value="• Poke with abilities\n• All-in when enemy low\n• Manage mana efficiently",
                inline=False
            )
            
        elif role in ['top']:
            embed.title = "⛰️ Tips cho Top Lane"
            embed.add_field(
                name="🛡️ Laning",
                value="• Manage wave properly\n• Ward tri-bush\n• Trade when minions favor you",
                inline=False
            )
            embed.add_field(
                name="📱 TP Usage",
                value="• TP for objectives\n• Help team in fights\n• Don't waste TP for lane",
                inline=False
            )
            
        elif role in ['general', 'chung', 'all']:
            embed.title = "🎮 Tips chung cho League of Legends"
            embed.add_field(
                name="🧠 Game Sense",
                value="• Nhìn minimap thường xuyên\n• Biết khi nào nên fight/retreat\n• Communicate với team",
                inline=False
            )
            embed.add_field(
                name="📈 Improvement",
                value="• Watch replays\n• Learn from mistakes\n• Practice in training mode\n• Watch pro players",
                inline=False
            )
            embed.add_field(
                name="🎯 Focus Areas",
                value="• CS/min (aim for 7+)\n• Death count (keep low)\n• Ward score\n• Objective participation",
                inline=False
            )
        else:
            embed.title = "❌ Vai trò không hợp lệ"
            embed.description = "Sử dụng: `!loltips adc/support/jungle/mid/top/general`"
        
        if role != 'invalid':
            embed.set_footer(text="💡 Practice makes perfect!")
        
        await ctx.send(embed=embed)

    # =============== SLASH COMMANDS ===============
    
    @app_commands.command(name="champion", description="Xem thông tin tướng League of Legends")
    @app_commands.describe(champion_name="Tên tướng cần tra cứu")
    async def slash_champion(self, interaction: discord.Interaction, champion_name: str):
        """Slash command for champion info"""
        await interaction.response.defer()
        
        champions_data = await self.get_champions_data()
        
        if not champions_data:
            await interaction.followup.send("❌ Không thể tải dữ liệu tướng!", ephemeral=True)
            return
        
        champion = self.find_champion(champions_data, champion_name)
        
        if not champion:
            suggestions = []
            search_lower = champion_name.lower()
            for champ_data in list(champions_data.values())[:10]:
                if any(word in champ_data['name'].lower() for word in search_lower.split()):
                    suggestions.append(champ_data['name'])
            
            suggestion_text = f"\n💡 **Có thể bạn muốn tìm:** {', '.join(suggestions[:5])}" if suggestions else ""
            await interaction.followup.send(f"❌ Không tìm thấy tướng **{champion_name}**!{suggestion_text}")
            return
        
        version = await self.get_latest_version()
        
        embed = discord.Embed(
            title=f"🏆 {champion['name']} - {champion['title']}",
            description=champion.get('blurb', 'Không có mô tả'),
            color=0x0F2027
        )
        
        champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
        embed.set_thumbnail(url=champion_img)
        
        embed.add_field(
            name="📊 Thông tin cơ bản",
            value=f"**Vai trò:** {', '.join(champion.get('tags', ['Unknown']))}\n"
                 f"**Độ khó:** {champion.get('info', {}).get('difficulty', 'N/A')}/10",
            inline=True
        )
        
        info = champion.get('info', {})
        embed.add_field(
            name="⚔️ Chỉ số",
            value=f"**Tấn công:** {info.get('attack', 0)}/10\n"
                 f"**Phòng thủ:** {info.get('defense', 0)}/10\n"
                 f"**Phép thuật:** {info.get('magic', 0)}/10",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Lời khuyên",
            value="Sử dụng `/build <tên tướng>` để xem build gợi ý\n"
                 "Sử dụng `/loltips <role>` để xem tips chơi",
            inline=False
        )
        
        embed.set_footer(text="League of Legends • Version {version}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="counter", description="Xem thông tin counter chi tiết cho tướng")
    @app_commands.describe(champion_name="Tên tướng cần xem counter")
    async def slash_counter(self, interaction: discord.Interaction, champion_name: str):
        """Slash command for champion counter info"""
        await interaction.response.defer()
        
        champions_data = await self.get_champions_data()
        
        if not champions_data:
            await interaction.followup.send("❌ Không thể tải dữ liệu tướng!", ephemeral=True)
            return
        
        champion = self.find_champion(champions_data, champion_name)
        
        if not champion:
            await interaction.followup.send(f"❌ Không tìm thấy tướng **{champion_name}**!")
            return
        
        counter_data = self.get_champion_counter_data(champion['name'])
        
        if not counter_data:
            embed = discord.Embed(
                title=f"❓ {champion['name']} - Chưa có dữ liệu counter",
                description="Dữ liệu counter cho tướng này chưa có sẵn.",
                color=0xFF6B35
            )
            await interaction.followup.send(embed=embed)
            return
        
        version = await self.get_latest_version()
        
        embed = discord.Embed(
            title=f"⚔️ Counter Analysis: {champion['name']}",
            color=0x0F2027
        )
        
        champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
        embed.set_thumbnail(url=champion_img)
        
        embed.add_field(
            name="📊 Thống kê chung",
            value=f"**Tỉ lệ thắng:** {counter_data['win_rate']}\n"
                 f"**Vị trí chính:** {', '.join(counter_data['positions'])}\n"
                 f"**Độ khó:** {counter_data['difficulty']}/10",
            inline=False
        )
        
        embed.add_field(
            name="❌ Tướng Counter",
            value="\n".join([f"• **{counter}**" for counter in counter_data['counters'][:4]]),
            inline=True
        )
        
        embed.add_field(
            name="✅ Tốt chống lại",
            value="\n".join([f"• **{good}**" for good in counter_data['good_against'][:4]]),
            inline=True
        )
        
        embed.set_footer(text="💡 Sử dụng /build để xem build chống counter")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="item", description="Xem thông tin chi tiết về item")
    @app_commands.describe(item_name="Tên item (tiếng Việt hoặc tiếng Anh)")
    async def slash_item(self, interaction: discord.Interaction, item_name: str):
        """Slash command for item info"""
        await interaction.response.defer()
        
        items_data = await self.get_items_data()
        version = await self.get_latest_version()
        
        if not items_data:
            await interaction.followup.send("❌ Không thể tải dữ liệu items!", ephemeral=True)
            return
        
        # Find item
        found_item = None
        found_item_id = None
        
        # Search by Vietnamese name first
        english_name = None
        for eng, viet in self.items_vietnamese.items():
            if viet.lower() == item_name.lower() or eng.lower() == item_name.lower():
                english_name = eng
                break
        
        if english_name:
            for item_id, item_info in items_data.items():
                if item_info.get('name', '').lower() == english_name.lower():
                    found_item = item_info
                    found_item_id = item_id
                    break
        else:
            for item_id, item_info in items_data.items():
                if item_name.lower() in item_info.get('name', '').lower():
                    found_item = item_info
                    found_item_id = item_id
                    break
        
        if not found_item:
            await interaction.followup.send(f"❌ Không tìm thấy item **{item_name}**!")
            return
        
        vietnamese_name = self.get_item_vietnamese_name(found_item['name'])
        
        embed = discord.Embed(
            title=f"🏬 {vietnamese_name}",
            description=f"*{found_item['name']}*" if vietnamese_name != found_item['name'] else "",
            color=0x0F2027
        )
        
        # Item image
        item_img = f"{self.base_url}/cdn/{version}/img/item/{found_item_id}.png"
        embed.set_thumbnail(url=item_img)
        
        # Price
        if found_item.get('gold'):
            gold_info = found_item['gold']
            embed.add_field(
                name="💰 Giá cả",
                value=f"**Tổng:** {gold_info.get('total', 0)} gold",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="build", description="Xem build gợi ý cho tướng")
    @app_commands.describe(champion_name="Tên tướng cần xem build")
    async def slash_build(self, interaction: discord.Interaction, champion_name: str):
        """Slash command for champion build"""
        await interaction.response.defer()
        
        champions_data = await self.get_champions_data()
        
        if not champions_data:
            await interaction.followup.send("❌ Không thể tải dữ liệu!", ephemeral=True)
            return
        
        champion = self.find_champion(champions_data, champion_name)
        
        if not champion:
            await interaction.followup.send(f"❌ Không tìm thấy tướng **{champion_name}**!")
            return
        
        embed = discord.Embed(
            title=f"🛠️ Build gợi ý cho {champion['name']}",
            color=0x0F2027
        )
        
        version = await self.get_latest_version()
        champion_img = f"{self.base_url}/cdn/{version}/img/champion/{champion['id']}.png"
        embed.set_thumbnail(url=champion_img)
        
        tags = champion.get('tags', [])
        
        if 'Marksman' in tags:
            embed.add_field(
                name="🏹 Build ADC",
                value="**Core Items:**\n• Kraken Slayer / Galeforce\n• Phantom Dancer\n• Infinity Edge\n• Lord Dominik's Regards\n• Bloodthirster\n• Guardian Angel",
                inline=False
            )
        elif 'Assassin' in tags:
            embed.add_field(
                name="🗡️ Build Assassin",
                value="**Core Items:**\n• Duskblade of Draktharr\n• Youmuu's Ghostblade\n• The Collector\n• Edge of Night\n• Serylda's Grudge\n• Guardian Angel",
                inline=False
            )
        elif 'Mage' in tags:
            embed.add_field(
                name="🔮 Build Mage",
                value="**Core Items:**\n• Luden's Tempest / Liandry's Anguish\n• Sorcerer's Shoes\n• Zhonya's Hourglass\n• Void Staff\n• Rabadon's Deathcap\n• Banshee's Veil",
                inline=False
            )
        elif 'Tank' in tags:
            embed.add_field(
                name="🛡️ Build Tank",
                value="**Core Items:**\n• Sunfire Aegis / Frostfire Gauntlet\n• Plated Steelcaps / Mercury's Treads\n• Thornmail\n• Force of Nature\n• Gargoyle Stoneplate\n• Warmog's Armor",
                inline=False
            )
        elif 'Support' in tags:
            embed.add_field(
                name="💎 Build Support",
                value="**Core Items:**\n• Locket of the Iron Solari\n• Redemption\n• Knight's Vow\n• Ardent Censer\n• Staff of Flowing Water\n• Mobility Boots",
                inline=False
            )
        else:
            embed.add_field(
                name="⚔️ Build tổng quát",
                value="**Lưu ý:** Build phụ thuộc vào vai trò và meta hiện tại\n"
                     "Hãy tham khảo các trang web chuyên nghiệp",
                inline=False
            )
        
        embed.set_footer(text="💡 Build có thể thay đổi tùy theo meta và tình huống!")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="loltips", description="Xem tips chơi League of Legends theo vai trò")
    @app_commands.describe(role="Vai trò: adc, support, jungle, mid, top, general")
    @app_commands.choices(role=[
        app_commands.Choice(name="ADC/Marksman", value="adc"),
        app_commands.Choice(name="Support", value="support"),
        app_commands.Choice(name="Jungle", value="jungle"),
        app_commands.Choice(name="Mid Lane", value="mid"),
        app_commands.Choice(name="Top Lane", value="top"),
        app_commands.Choice(name="Tips chung", value="general")
    ])
    async def slash_lol_tips(self, interaction: discord.Interaction, role: str):
        """Slash command for LoL tips"""
        await interaction.response.defer()
        
        embed = discord.Embed(color=0x0F2027)
        
        if role == 'adc':
            embed.title = "🏹 Tips cho ADC"
            embed.add_field(
                name="🎯 Farming & Last-hit",
                value="• Tập trung farm minion\n• Học cách last-hit chính xác\n• Đừng miss cannon minion",
                inline=False
            )
            embed.add_field(
                name="⚔️ Trading & Positioning",
                value="• Giữ khoảng cách an toàn\n• Trade khi địch farm\n• Luôn ở phía sau frontline",
                inline=False
            )
        elif role == 'support':
            embed.title = "💎 Tips cho Support"
            embed.add_field(
                name="👁️ Vision Control",
                value="• Ward các bush quan trọng\n• Clear enemy wards\n• Mua Control Ward",
                inline=False
            )
            embed.add_field(
                name="🤝 Protection & Roaming",
                value="• Bảo vệ ADC\n• Roam khi có cơ hội\n• Engage khi team ready",
                inline=False
            )
        elif role == 'jungle':
            embed.title = "🌲 Tips cho Jungle"
            embed.add_field(
                name="🗺️ Pathing & Objectives",
                value="• Plan jungle route\n• Secure objectives (Dragon, Baron)\n• Track enemy jungler",
                inline=False
            )
            embed.add_field(
                name="⚡ Ganking",
                value="• Gank lanes có CC\n• Counter-gank enemy jungler\n• Farm efficiently",
                inline=False
            )
        elif role == 'mid':
            embed.title = "⭐ Tips cho Mid Lane"
            embed.add_field(
                name="📍 Map Control",
                value="• Ward both sides\n• Roam to help teammates\n• Control river vision",
                inline=False
            )
            embed.add_field(
                name="💥 Trading",
                value="• Poke with abilities\n• All-in when enemy low\n• Manage mana efficiently",
                inline=False
            )
        elif role == 'top':
            embed.title = "⛰️ Tips cho Top Lane"
            embed.add_field(
                name="🛡️ Laning",
                value="• Manage wave properly\n• Ward tri-bush\n• Trade when minions favor you",
                inline=False
            )
            embed.add_field(
                name="📱 TP Usage",
                value="• TP for objectives\n• Help team in fights\n• Don't waste TP for lane",
                inline=False
            )
        elif role == 'general':
            embed.title = "🎮 Tips chung cho League of Legends"
            embed.add_field(
                name="🧠 Game Sense",
                value="• Nhìn minimap thường xuyên\n• Biết khi nào nên fight/retreat\n• Communicate với team",
                inline=False
            )
            embed.add_field(
                name="📈 Improvement",
                value="• Watch replays\n• Learn from mistakes\n• Practice in training mode\n• Watch pro players",
                inline=False
            )
            embed.add_field(
                name="🎯 Focus Areas",
                value="• CS/min (aim for 7+)\n• Death count (keep low)\n• Ward score\n• Objective participation",
                inline=False
            )
        
        embed.set_footer(text="💡 Practice makes perfect!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rotation", description="Xem tướng miễn phí tuần này")
    async def slash_rotation(self, interaction: discord.Interaction):
        """Slash command for free rotation"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔄 Tướng miễn phí tuần này",
            description="Tính năng này cần Riot API key để hoạt động.\n"
                       "Hiện tại đang hiển thị thông tin mẫu.",
            color=0x0F2027
        )
        
        sample_champions = [
            "Ashe", "Garen", "Lux", "Jinx", "Thresh",
            "Yasuo", "Zed", "Ahri", "Lee Sin", "Darius"
        ]
        
        embed.add_field(
            name="🆓 Tướng miễn phí",
            value="\n".join([f"• {champ}" for champ in sample_champions]),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Thông tin",
            value="• Tướng miễn phí thay đổi hàng tuần\n"
                 "• Rotation mới bắt đầu vào thứ 3\n"
                 "• Tài khoản dưới level 11 có rotation riêng",
            inline=False
        )
        
        embed.set_footer(text="🔑 Cần Riot API key để hiển thị dữ liệu real-time")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="rotation", description="Xem tướng miễn phí tuần này")
    async def slash_rotation(self, interaction: discord.Interaction):
        """Slash command for champion rotation"""
        await interaction.response.defer()
        
        rotation_data = await self.get_champion_rotation()
        
        if not rotation_data:
            embed = discord.Embed(
                title="❌ Không thể tải dữ liệu rotation",
                description="Có lỗi khi kết nối tới Riot API.",
                color=0xFF6B35
            )
            await interaction.followup.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🔄 Tướng miễn phí tuần này",
            description="Dữ liệu real-time từ Riot Games API",
            color=0x0F2027
        )
        
        # Show first 10 free champions to avoid embed length limit
        if rotation_data['free_champions']:
            champions_list = rotation_data['free_champions'][:10]
            champions_text = "\n".join([f"• **{champ}**" for champ in champions_list])
            
            if len(rotation_data['free_champions']) > 10:
                champions_text += f"\n*+{len(rotation_data['free_champions']) - 10} tướng khác...*"
            
            embed.add_field(
                name="🆓 Tướng miễn phí",
                value=champions_text,
                inline=False
            )
        
        embed.add_field(
            name="📊 Thống kê",
            value=f"**Tổng:** {len(rotation_data['free_champions'])} tướng\n"
                 f"**Newbie:** {len(rotation_data['newbie_free_champions'])} tướng\n"
                 f"**Cập nhật:** {rotation_data['last_updated']}",
            inline=True
        )
        
        embed.set_footer(text="🔑 Powered by Riot Games API")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lolpatch", description="Xem thông tin patch League of Legends hiện tại")
    async def slash_patch(self, interaction: discord.Interaction):
        """Slash command for patch info"""
        await interaction.response.defer()
        
        version = await self.get_latest_version()
        
        embed = discord.Embed(
            title=f"🔧 League of Legends Patch {version}",
            color=0x0F2027
        )
        
        embed.add_field(
            name="📅 Thông tin patch",
            value=f"**Version hiện tại:** {version}\n"
                 f"**Cập nhật:** Khoảng 2 tuần một lần\n"
                 f"**Khu vực:** Toàn cầu",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Liên kết hữu ích",
            value="• [Patch Notes chính thức](https://www.leagueoflegends.com/en-us/news/tags/patch-notes/)\n"
                 "• [ProBuilds](https://probuilds.net/)\n"
                 "• [U.GG](https://u.gg/)\n"
                 "• [OP.GG](https://op.gg/)",
            inline=False
        )
        
        embed.set_footer(text="🎮 League of Legends")
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LeagueOfLegends(bot))
