import asyncio
import io
import logging
import math
import os
import random
import textwrap
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from branding import BRAND_MASCOT_PATH


logger = logging.getLogger(__name__)
WIDTH = 1200
HEIGHT = 675
BACKGROUND = (14, 17, 25)
SURFACE = (25, 29, 42, 220)
GLASS = (34, 39, 55, 255)
TEXT = (248, 250, 252)
SECONDARY = (177, 183, 202)
MUTED = (116, 123, 146)
PINK = (249, 168, 212)
LAVENDER = (196, 181, 253)
BLUE = (125, 211, 252)
MINT = (110, 231, 183)
PEACH = (253, 186, 140)


class CommunityCardRenderer:
    def __init__(self, *, cache_size: int = 64) -> None:
        self.cache_size = cache_size
        self._avatar_cache: OrderedDict[str, bytes] = OrderedDict()
        self._session: Optional[aiohttp.ClientSession] = None
        self._brand_mascot = self._load_brand_mascot()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def render_welcome(
        self,
        *,
        avatar_url: str,
        display_name: str,
        server_name: str,
        member_count: int,
    ) -> bytes:
        avatar = await self._fetch_image(avatar_url)
        return await asyncio.to_thread(
            self._draw_welcome,
            avatar,
            display_name,
            server_name,
            member_count,
        )

    async def render_birthday(
        self,
        *,
        avatar_url: str,
        display_name: str,
    ) -> bytes:
        avatar = await self._fetch_image(avatar_url)
        return await asyncio.to_thread(self._draw_birthday, avatar, display_name)

    async def render_profile(
        self,
        *,
        avatar_url: str,
        display_name: str,
        days: int,
        messages: int,
        voice_seconds: int,
        birthday: str,
        introduced: bool,
        featured: Sequence[str] = (),
        birthday_today: bool = False,
    ) -> bytes:
        avatar = await self._fetch_image(avatar_url)
        return await asyncio.to_thread(
            self._draw_profile,
            avatar,
            display_name,
            days,
            messages,
            voice_seconds,
            birthday,
            introduced,
            featured,
            birthday_today,
        )

    async def render_introduction(
        self,
        *,
        avatar_url: str,
        display_name: str,
        preferred_name: str,
        about: str,
        interests: str,
    ) -> bytes:
        avatar = await self._fetch_image(avatar_url)
        return await asyncio.to_thread(
            self._draw_introduction,
            avatar,
            display_name,
            preferred_name,
            about,
            interests,
        )

    async def render_analytics(self, *, snapshot, server_name: str) -> bytes:
        return await asyncio.to_thread(self._draw_analytics, snapshot, server_name)

    async def render_weekly(self, *, snapshot, server_name: str) -> bytes:
        return await asyncio.to_thread(self._draw_weekly, snapshot, server_name)

    async def _fetch_image(self, url: str) -> Optional[bytes]:
        cached = self._avatar_cache.get(url)
        if cached is not None:
            self._avatar_cache.move_to_end(url)
            return cached
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8))
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                if response.content_length and response.content_length > 8 * 1024 * 1024:
                    return None
                data = await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            logger.info("community_avatar_fetch_failed error=%s", error)
            return None
        self._avatar_cache[url] = data
        while len(self._avatar_cache) > self.cache_size:
            self._avatar_cache.popitem(last=False)
        return data

    def _draw_welcome(
        self,
        avatar_bytes: Optional[bytes],
        display_name: str,
        server_name: str,
        member_count: int,
    ) -> bytes:
        base = self._base_canvas((LAVENDER, BLUE), "KSC COMMUNITY", "NEW MEMBER")
        draw = ImageDraw.Draw(base, "RGBA")
        self._avatar(base, avatar_bytes, (108, 176), 300, LAVENDER)

        draw.text((475, 178), "WELCOME TO", font=self._font(20, bold=True), fill=BLUE)
        self._fitted(draw, display_name, (475, 218), 625, 54, min_size=30, bold=True, fill=TEXT)
        self._fitted(draw, server_name.upper(), (475, 292), 625, 27, min_size=18, bold=True, fill=SECONDARY)
        draw.line((475, 348, 1080, 348), fill=(255, 255, 255, 24), width=2)
        self._metric(draw, (475, 390), "MEMBER", f"#{member_count:,}", LAVENDER)
        self._metric(draw, (735, 390), "STATUS", "JUST ARRIVED", BLUE)
        draw.text(
            (475, 535),
            "Your next chapter starts here.",
            font=self._font(22),
            fill=SECONDARY,
        )

        frames = []
        for index in range(14):
            frame = base.copy()
            overlay = ImageDraw.Draw(frame, "RGBA")
            phase = index / 14
            pulse = int(5 + 3 * math.sin(phase * math.tau))
            overlay.ellipse(
                (108 - pulse, 176 - pulse, 408 + pulse, 476 + pulse),
                outline=(*LAVENDER, 90),
                width=3,
            )
            self._shimmer(overlay, index, LAVENDER, BLUE)
            self._sparkles(overlay, index, (LAVENDER, BLUE), count=9)
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=192))
        return self._gif(frames, duration=105)

    def _draw_birthday(self, avatar_bytes: Optional[bytes], display_name: str) -> bytes:
        base = self._base_canvas((PEACH, PINK), "KSC CELEBRATION", "BIRTHDAY")
        draw = ImageDraw.Draw(base, "RGBA")
        self._avatar(base, avatar_bytes, (100, 178), 300, PINK)
        draw.text((470, 166), "HAPPY BIRTHDAY", font=self._font(22, bold=True), fill=PEACH)
        self._fitted(draw, display_name, (470, 211), 630, 58, min_size=30, bold=True, fill=TEXT)
        draw.text((470, 300), "A new year. New memories.", font=self._font(28), fill=SECONDARY)
        draw.text((470, 342), "And a whole lot more to celebrate.", font=self._font(28), fill=SECONDARY)
        draw.rounded_rectangle(
            (470, 430, 1042, 518),
            radius=22,
            fill=GLASS,
            outline=(*PINK, 88),
            width=2,
        )
        draw.text((756, 474), "MAKE A WISH", anchor="mm", font=self._font(22, bold=True), fill=TEXT)

        rng = random.Random(display_name)
        confetti = [
            (rng.randint(65, 1135), rng.randint(-650, 640), rng.choice((PINK, PEACH, LAVENDER, BLUE, MINT)))
            for _ in range(34)
        ]
        frames = []
        for index in range(18):
            frame = base.copy()
            overlay = ImageDraw.Draw(frame, "RGBA")
            for item, (x, initial_y, color) in enumerate(confetti):
                y = (initial_y + index * (17 + item % 5)) % 760 - 45
                angle = (index + item) % 2
                width, height = ((5, 14) if angle else (13, 5))
                overlay.rounded_rectangle((x, y, x + width, y + height), radius=2, fill=(*color, 210))
            self._shimmer(overlay, index, PEACH, PINK)
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=192))
        return self._gif(frames, duration=95)

    def _draw_profile(
        self,
        avatar_bytes: Optional[bytes],
        display_name: str,
        days: int,
        messages: int,
        voice_seconds: int,
        birthday: str,
        introduced: bool,
        featured: Sequence[str],
        birthday_today: bool = False,
    ) -> bytes:
        accents = (PINK, LAVENDER) if birthday_today else (BLUE, MINT)
        badge = "BIRTHDAY CELEBRATION" if birthday_today else "MEMBER PROFILE"
        image = self._base_canvas(accents, "KSC COMMUNITY", badge)
        draw = ImageDraw.Draw(image, "RGBA")
        self._avatar(image, avatar_bytes, (90, 176), 260, PINK if birthday_today else BLUE)
        self._fitted(draw, display_name, (90, 468), 340, 38, min_size=24, bold=True, fill=TEXT)
        draw.text(
            (90, 520),
            "BIRTHDAY MEMBER" if birthday_today else "COMMUNITY MEMBER",
            font=self._font(17, bold=True),
            fill=PINK if birthday_today else MUTED,
        )

        hours, remainder = divmod(max(0, voice_seconds), 3600)
        minutes = remainder // 60
        metrics = (
            ("MEMBERSHIP", f"{days:,} days", LAVENDER),
            ("MESSAGES", f"{messages:,}", BLUE),
            ("VOICE TIME", f"{hours}h {minutes}m", MINT),
        )
        for index, metric in enumerate(metrics):
            self._metric(draw, (470 + index * 205, 200), *metric, compact=True)
        draw.line((470, 345, 1085, 345), fill=(255, 255, 255, 24), width=2)
        self._profile_row(draw, 400, "BIRTHDAY", birthday)
        self._profile_row(draw, 470, "INTRODUCTION", "COMPLETED" if introduced else "NOT YET")
        self._featured_badges(image, draw, 540, featured)
        return self._png(image)

    def _featured_badges(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        y: int,
        featured: Sequence[str],
    ) -> None:
        draw.text((470, y + 20), "FEATURED", font=self._font(15, bold=True), fill=MUTED)
        keys = tuple(featured[:5])
        start_x = 730
        for index in range(5):
            x = start_x + index * 73
            if index < len(keys):
                self._badge_icon(image, (x, y), keys[index])
            else:
                draw.ellipse(
                    (x + 7, y + 7, x + 61, y + 61),
                    fill=(255, 255, 255, 5),
                    outline=(255, 255, 255, 18),
                    width=2,
                )

    def _badge_icon(self, image: Image.Image, position: tuple[int, int], key: str) -> None:
        x, y = position
        palettes = {
            "tenure": (MINT, (13, 56, 53)),
            "chat": (PEACH, (65, 38, 31)),
            "voice": (BLUE, (19, 48, 69)),
            "special": (LAVENDER, (49, 37, 77)),
        }
        category = "tenure" if key.startswith("member_") else key.split("_", 1)[0]
        accent, core = palettes.get(category, (SECONDARY, (42, 46, 61)))

        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow, "RGBA")
        glow_draw.ellipse((x + 3, y + 3, x + 65, y + 65), fill=(*accent, 56))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
        badge = Image.new("RGBA", (68, 68), (0, 0, 0, 0))
        icon = ImageDraw.Draw(badge, "RGBA")
        points = ((34, 2), (58, 12), (66, 34), (58, 56), (34, 66), (10, 56), (2, 34), (10, 12))
        icon.polygon(points, fill=(*core, 255), outline=(*accent, 235), width=2)
        icon.ellipse((11, 11, 57, 57), fill=(255, 255, 255, 8), outline=(255, 255, 255, 30), width=1)
        self._badge_symbol(icon, key, accent)
        image.alpha_composite(badge, (x, y))

    @staticmethod
    def _badge_symbol(draw: ImageDraw.ImageDraw, key: str, color: tuple[int, int, int]) -> None:
        white = (248, 250, 252, 245)
        soft = (*color, 245)
        if key in {"member_new", "member_familiar"}:
            scale = 0 if key == "member_new" else 3
            draw.line((34, 50, 34, 30 - scale), fill=white, width=4)
            draw.ellipse((19 - scale, 19 - scale, 35, 35), fill=soft)
            draw.ellipse((33, 14 - scale, 51 + scale, 32), fill=soft)
        elif key == "member_longtime":
            draw.rectangle((30, 35, 38, 53), fill=white)
            draw.ellipse((16, 14, 40, 39), fill=soft)
            draw.ellipse((29, 10, 53, 39), fill=soft)
        elif key == "member_veteran":
            draw.polygon(((15, 26), (34, 13), (53, 26)), fill=soft)
            for px in (19, 30, 41):
                draw.rectangle((px, 28, px + 7, 48), fill=white)
            draw.rectangle((14, 49, 54, 54), fill=soft)
        elif key.startswith("chat_"):
            draw.rounded_rectangle((13, 17, 48, 43), radius=8, fill=soft)
            draw.polygon(((22, 41), (21, 52), (33, 42)), fill=soft)
            if key == "chat_start":
                draw.ellipse((27, 28, 33, 34), fill=white)
            elif key == "chat_regular":
                for px in (22, 31, 40):
                    draw.ellipse((px, 28, px + 5, 33), fill=white)
            elif key == "chat_active":
                draw.polygon(((48, 53), (43, 42), (49, 35), (51, 43), (56, 38), (57, 48)), fill=white)
            else:
                draw.line((19, 30, 42, 30), fill=white, width=3)
                draw.line((24, 36, 38, 36), fill=white, width=3)
        elif key == "voice_start":
            draw.rounded_rectangle((27, 14, 41, 42), radius=7, fill=soft)
            draw.arc((20, 25, 48, 50), 0, 180, fill=white, width=4)
            draw.line((34, 49, 34, 55), fill=white, width=4)
        elif key == "voice_regular":
            draw.arc((15, 14, 53, 52), 180, 360, fill=soft, width=6)
            draw.rounded_rectangle((13, 31, 23, 50), radius=4, fill=white)
            draw.rounded_rectangle((45, 31, 55, 50), radius=4, fill=white)
        elif key == "voice_veteran":
            draw.polygon(((34, 10), (23, 30), (29, 30), (20, 53), (45, 32), (38, 32), (47, 14)), fill=soft)
        elif key == "voice_legend":
            draw.polygon(((13, 25), (24, 34), (34, 16), (44, 34), (55, 25), (51, 49), (17, 49)), fill=soft)
            draw.rectangle((18, 51, 50, 55), fill=white)
        elif key == "special_founder":
            draw.polygon(((34, 10), (52, 27), (34, 56), (16, 27)), fill=soft)
            draw.polygon(((34, 10), (40, 27), (34, 56), (28, 27)), fill=white)
        elif key == "special_contributor":
            draw.polygon(((34, 9), (40, 25), (57, 26), (44, 37), (48, 54), (34, 44), (20, 54), (24, 37), (11, 26), (28, 25)), fill=soft)
        elif key == "special_helper":
            draw.ellipse((14, 15, 35, 37), fill=soft)
            draw.ellipse((33, 15, 54, 37), fill=soft)
            draw.polygon(((15, 28), (34, 55), (53, 28), (34, 39)), fill=soft)
            draw.ellipse((29, 27, 39, 37), fill=white)
        elif key == "special_champion":
            draw.pieslice((20, 11, 48, 42), 0, 180, fill=soft)
            draw.arc((10, 15, 29, 39), 80, 280, fill=white, width=4)
            draw.arc((39, 15, 58, 39), 260, 100, fill=white, width=4)
            draw.rectangle((31, 39, 37, 50), fill=white)
            draw.rounded_rectangle((23, 49, 45, 55), radius=3, fill=soft)
        else:
            draw.ellipse((25, 25, 43, 43), fill=soft)

    def _draw_introduction(
        self,
        avatar_bytes: Optional[bytes],
        display_name: str,
        preferred_name: str,
        about: str,
        interests: str,
    ) -> bytes:
        image = self._base_canvas((LAVENDER, BLUE), "KSC COMMUNITY", "INTRODUCTION")
        draw = ImageDraw.Draw(image, "RGBA")
        self._avatar(image, avatar_bytes, (86, 185), 250, LAVENDER)
        self._fitted(draw, preferred_name, (405, 175), 680, 46, min_size=27, bold=True, fill=TEXT)
        self._fitted(draw, f"@{display_name}", (405, 234), 680, 20, min_size=16, bold=True, fill=BLUE)

        quote = self._wrapped(about, width=48, lines=5)
        y = 302
        draw.rounded_rectangle((405, 286, 1080, 455), radius=20, fill=GLASS)
        for line in quote:
            draw.text((435, y), line, font=self._font(23), fill=SECONDARY)
            y += 31
        interest_text = interests.strip() or "Chưa chia sẻ sở thích"
        draw.text((405, 500), "INTERESTS", font=self._font(15, bold=True), fill=MUTED)
        self._fitted(draw, interest_text, (405, 528), 660, 20, min_size=15, bold=True, fill=LAVENDER)
        draw.text((82, 72), "KSC COMMUNITY", font=self._font(19, bold=True), fill=TEXT)
        return self._png(image)

    def _draw_analytics(self, snapshot, server_name: str) -> bytes:
        image = self._base_canvas((BLUE, MINT), server_name.upper(), f"{snapshot.days} DAY ANALYTICS")
        draw = ImageDraw.Draw(image, "RGBA")
        metrics = (
            ("MEMBERS", f"{snapshot.total_members:,}", BLUE),
            ("MESSAGES", f"{snapshot.messages:,}", LAVENDER),
            ("VOICE", f"{snapshot.voice_seconds / 3600:,.1f}h", MINT),
            ("ACTIVE", f"{snapshot.active_members:,}", PINK),
        )
        for index, metric in enumerate(metrics):
            self._metric(draw, (82 + index * 260, 154), *metric)

        growth = getattr(snapshot, "growth", ())
        draw.text((82, 302), "MEMBER GROWTH" if growth else "ACTIVITY TREND", font=self._font(15, bold=True), fill=MUTED)
        chart = (82, 342, 780, 558)
        draw.rounded_rectangle(chart, radius=18, fill=GLASS, outline=(255, 255, 255, 20))
        for step in range(1, 4):
            y = chart[1] + step * (chart[3] - chart[1]) / 4
            draw.line((chart[0] + 22, y, chart[2] - 22, y), fill=(255, 255, 255, 14), width=1)
        values = [point.total for point in growth] if growth else [point.messages for point in snapshot.daily]
        if len(values) > 32:
            stride = math.ceil(len(values) / 32)
            values = [sum(values[index:index + stride]) for index in range(0, len(values), stride)]
        maximum = max(values, default=0) or 1
        points = []
        for index, value in enumerate(values):
            x = chart[0] + 24 + index * (chart[2] - chart[0] - 48) / max(1, len(values) - 1)
            y = chart[3] - 28 - value / maximum * (chart[3] - chart[1] - 56)
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=(*BLUE, 235), width=5, joint="curve")
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=TEXT, outline=(*BLUE, 255), width=2)
        draw.text((104, 570), snapshot.start_day, font=self._font(13), fill=MUTED)
        draw.text((758, 570), snapshot.end_day, anchor="ra", font=self._font(13), fill=MUTED)

        draw.text((830, 302), "COMMUNITY SIGNALS", font=self._font(15, bold=True), fill=MUTED)
        signals = (
            ("NET GROWTH", f"{snapshot.new_members - snapshot.left_members:+,}", MINT),
            ("ACHIEVEMENTS", f"{snapshot.achievements:,}", LAVENDER),
            ("7D RETENTION", f"{snapshot.retention_7d:.0f}%", BLUE),
        )
        for index, (label, value, color) in enumerate(signals):
            y = 342 + index * 74
            draw.rounded_rectangle((830, y, 1118, y + 58), radius=15, fill=GLASS, outline=(*color, 75))
            draw.text((850, y + 12), label, font=self._font(13, bold=True), fill=MUTED)
            draw.text((1096, y + 10), value, anchor="ra", font=self._font(23, bold=True), fill=TEXT)
        draw.text((830, 574), "UPDATED DAILY · KSC GAMING", font=self._font(13, bold=True), fill=MUTED)
        return self._png(image)

    def _draw_weekly(self, snapshot, server_name: str) -> bytes:
        analytics = snapshot.analytics
        image = self._base_canvas((PINK, LAVENDER), server_name.upper(), "WEEKLY RECAP")
        draw = ImageDraw.Draw(image, "RGBA")
        draw.text((82, 162), "THIS WEEK, TOGETHER", font=self._font(18, bold=True), fill=PINK)
        draw.text(
            (82, 202),
            f"{snapshot.start_day}  /  {snapshot.end_day}",
            font=self._font(34, bold=True),
            fill=TEXT,
        )
        draw.text(
            (82, 258),
            "A look back at the people and moments that shaped our week.",
            font=self._font(20),
            fill=SECONDARY,
        )
        metrics = (
            ("NEW MEMBERS", f"+{analytics.new_members:,}", PINK),
            ("MESSAGES", f"{analytics.messages:,}", LAVENDER),
            ("VOICE TIME", f"{analytics.voice_seconds / 3600:,.1f}h", BLUE),
            ("ACHIEVEMENTS", f"{analytics.achievements:,}", MINT),
        )
        for index, metric in enumerate(metrics):
            self._metric(draw, (82 + index * 260, 342), *metric)
        draw.line((82, 500, 1118, 500), fill=(255, 255, 255, 24), width=2)
        draw.text(
            (82, 540),
            f"{analytics.active_members:,} active members",
            font=self._font(20, bold=True),
            fill=TEXT,
        )
        net = analytics.new_members - analytics.left_members
        draw.text(
            (1118, 540),
            f"NET GROWTH  {net:+,}",
            anchor="ra",
            font=self._font(20, bold=True),
            fill=MINT if net >= 0 else PEACH,
        )
        return self._png(image)

    def _base_canvas(
        self,
        accents: tuple[tuple[int, int, int], tuple[int, int, int]],
        brand: str,
        badge: str,
    ) -> Image.Image:
        start, end = accents
        gradient = self._gradient((WIDTH, HEIGHT), self._mix(start, PINK, 0.32), self._mix(end, BLUE, 0.34))
        base = Image.blend(Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND), gradient, 0.20).convert("RGBA")
        draw = ImageDraw.Draw(base, "RGBA")
        for x in range(0, WIDTH, 80):
            draw.line((x, 0, x, HEIGHT), fill=(255, 255, 255, 7), width=1)
        for y in range(0, HEIGHT, 80):
            draw.line((0, y, WIDTH, y), fill=(255, 255, 255, 7), width=1)
        shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow, "RGBA")
        shadow_draw.rounded_rectangle((45, 42, 1155, 638), radius=32, fill=(0, 0, 0, 125))
        shadow = shadow.filter(ImageFilter.GaussianBlur(24))
        base = Image.alpha_composite(base, shadow)
        draw = ImageDraw.Draw(base, "RGBA")
        draw.rounded_rectangle((50, 40, 1150, 630), radius=30, fill=SURFACE, outline=(255, 255, 255, 28), width=2)
        self._brand_mark(base, (72, 55), 54)
        draw = ImageDraw.Draw(base, "RGBA")
        draw.text((138, 72), brand, font=self._font(19, bold=True), fill=TEXT)
        badge_font = self._font(15, bold=True)
        badge_width = draw.textbbox((0, 0), badge, font=badge_font)[2] + 34
        draw.rounded_rectangle(
            (1118 - badge_width, 66, 1118, 102),
            radius=18,
            fill=(*self._mix(BACKGROUND, start, 0.24), 255),
            outline=(*start, 90),
        )
        draw.text((1135 - badge_width, 76), badge, font=badge_font, fill=TEXT)
        draw.line((82, 125, 1118, 125), fill=(255, 255, 255, 20), width=1)
        return base

    @staticmethod
    def _load_brand_mascot() -> Optional[Image.Image]:
        try:
            return Image.open(BRAND_MASCOT_PATH).convert("RGBA")
        except (OSError, ValueError) as error:
            logger.warning("community_brand_mascot_load_failed error=%s", error)
            return None

    def _brand_mark(self, image: Image.Image, position: tuple[int, int], size: int) -> None:
        if not self._brand_mascot:
            return
        mascot = ImageOps.contain(
            self._brand_mascot,
            (size, size),
            method=Image.Resampling.LANCZOS,
        )
        image.alpha_composite(mascot, position)

    def _avatar(
        self,
        image: Image.Image,
        avatar_bytes: Optional[bytes],
        position: tuple[int, int],
        size: int,
        accent: tuple[int, int, int],
    ) -> None:
        x, y = position
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow, "RGBA")
        glow_draw.ellipse((x - 16, y - 16, x + size + 16, y + size + 16), fill=(*accent, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(22))
        image.alpha_composite(glow)
        avatar = self._open_image(avatar_bytes)
        if avatar:
            avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS)
        else:
            avatar = self._gradient((size, size), LAVENDER, BLUE)
            placeholder = ImageDraw.Draw(avatar)
            placeholder.text((size // 2, size // 2), "K", anchor="mm", font=self._font(size // 3, bold=True), fill=TEXT)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        image.paste(avatar, (x, y), mask)
        draw = ImageDraw.Draw(image, "RGBA")
        draw.ellipse((x - 5, y - 5, x + size + 5, y + size + 5), outline=(*accent, 230), width=5)
        draw.ellipse((x - 10, y - 10, x + size + 10, y + size + 10), outline=(255, 255, 255, 35), width=2)

    def _metric(
        self,
        draw: ImageDraw.ImageDraw,
        position: tuple[int, int],
        label: str,
        value: str,
        color: tuple[int, int, int],
        compact: bool = False,
    ) -> None:
        x, y = position
        width = 180 if compact else 220
        height = 116
        draw.rounded_rectangle((x, y, x + width, y + height), radius=18, fill=GLASS, outline=(*color, 105), width=1)
        draw.text((x + 20, y + 22), label, font=self._font(14, bold=True), fill=MUTED)
        self._fitted(draw, value, (x + 20, y + 57), width - 40, 25, min_size=17, bold=True, fill=TEXT)

    def _profile_row(self, draw: ImageDraw.ImageDraw, y: int, label: str, value: str) -> None:
        draw.text((470, y), label, font=self._font(15, bold=True), fill=MUTED)
        self._fitted(draw, value, (760, y - 3), 320, 20, min_size=15, bold=True, fill=TEXT)

    def _shimmer(
        self,
        draw: ImageDraw.ImageDraw,
        frame: int,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
    ) -> None:
        progress = frame / 14
        x = int(50 + progress * 1000)
        color = self._mix(start, end, progress)
        draw.line((x, 40, min(1150, x + 100), 40), fill=(*color, 235), width=3)
        draw.line((1150 - (x - 50), 630, max(50, 1050 - (x - 50)), 630), fill=(*color, 145), width=2)

    def _sparkles(
        self,
        draw: ImageDraw.ImageDraw,
        frame: int,
        colors: tuple[tuple[int, int, int], tuple[int, int, int]],
        *,
        count: int,
    ) -> None:
        rng = random.Random(6174)
        for index in range(count):
            x = rng.randint(65, 1135)
            y = rng.randint(145, 610)
            phase = (frame + index * 2) % 14
            alpha = int(45 + 150 * abs(math.sin(phase / 14 * math.pi)))
            radius = 2 + index % 3
            color = colors[index % 2]
            draw.line((x - radius * 2, y, x + radius * 2, y), fill=(*color, alpha), width=1)
            draw.line((x, y - radius * 2, x, y + radius * 2), fill=(*color, alpha), width=1)

    @staticmethod
    def _wrapped(text: str, *, width: int, lines: int) -> list[str]:
        clean = " ".join(text.split())
        wrapped = textwrap.wrap(clean, width=width)[:lines]
        if len(textwrap.wrap(clean, width=width)) > lines and wrapped:
            wrapped[-1] = wrapped[-1].rstrip(" .") + "..."
        return wrapped or ["Chưa có lời giới thiệu."]

    @classmethod
    def _fitted(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        max_width: int,
        size: int,
        *,
        min_size: int,
        bold: bool,
        fill: tuple[int, int, int],
    ) -> None:
        original = " ".join(str(text).split())
        text = original
        font = cls._font(size, bold=bold)
        while size > min_size and draw.textbbox((0, 0), text, font=font)[2] > max_width:
            size -= 2
            font = cls._font(size, bold=bold)
        while text and draw.textbbox((0, 0), text, font=font)[2] > max_width:
            text = text[:-1]
        if text != original:
            text = text.rstrip() + "..."
        draw.text(position, text, font=font, fill=fill)

    @staticmethod
    def _open_image(data: Optional[bytes]) -> Optional[Image.Image]:
        if not data:
            return None
        try:
            return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        except Exception as error:
            logger.info("community_avatar_decode_failed error=%s", error)
            return None

    @staticmethod
    def _gradient(
        size: tuple[int, int],
        start: tuple[int, int, int],
        end: tuple[int, int, int],
    ) -> Image.Image:
        width, height = size
        strip = Image.new("RGB", (width, 1))
        strip.putdata(
            [
                tuple(
                    int(start[channel] + (end[channel] - start[channel]) * index / max(1, width - 1))
                    for channel in range(3)
                )
                for index in range(width)
            ]
        )
        return strip.resize((width, height))

    @staticmethod
    def _mix(
        first: tuple[int, int, int],
        second: tuple[int, int, int],
        amount: float,
    ) -> tuple[int, int, int]:
        return tuple(int(a * (1 - amount) + b * amount) for a, b in zip(first, second))

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = []
        if os.name == "nt":
            candidates.extend(
                [
                    Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
                    Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
                ]
            )
        candidates.extend(
            [
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            ]
        )
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        return ImageFont.load_default()

    @staticmethod
    def _png(image: Image.Image) -> bytes:
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG", optimize=True)
        return output.getvalue()

    @staticmethod
    def _gif(frames: list[Image.Image], *, duration: int) -> bytes:
        output = io.BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,
            optimize=True,
            disposal=2,
        )
        return output.getvalue()
