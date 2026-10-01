import asyncio
import hashlib
import io
import logging
import os
import random
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from branding import BRAND_MASCOT_PATH

from ..models import PlaybackSnapshot, TrackSource, format_duration


logger = logging.getLogger(__name__)
WIDTH = 1200
HEIGHT = 675

BACKGROUND = (16, 18, 26)
PANEL = (27, 31, 45, 218)
TEXT = (249, 250, 251)
SECONDARY = (173, 178, 196)
MUTED = (116, 121, 141)
PINK = (249, 168, 212)
LAVENDER = (196, 181, 253)
BLUE = (125, 211, 252)
MINT = (110, 231, 183)


class PlayerCardRenderer:
    def __init__(self, *, cache_size: int = 24) -> None:
        self.cache_size = cache_size
        self._artwork_cache: OrderedDict[str, bytes] = OrderedDict()
        self._session: Optional[aiohttp.ClientSession] = None
        self._brand_mascot = self._load_brand_mascot()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def render(self, snapshot: PlaybackSnapshot, *, paused: bool) -> bytes:
        artwork = None
        if snapshot.current and snapshot.current.thumbnail:
            artwork = await self._get_artwork(snapshot.current.thumbnail)
        return await asyncio.to_thread(self._draw, snapshot, paused, artwork)

    async def _get_artwork(self, url: str) -> Optional[bytes]:
        cached = self._artwork_cache.get(url)
        if cached is not None:
            self._artwork_cache.move_to_end(url)
            return cached

        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=8)
            self._session = aiohttp.ClientSession(timeout=timeout)
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                if response.content_length and response.content_length > 8 * 1024 * 1024:
                    return None
                data = await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            logger.info("artwork_fetch_failed error=%s", error)
            return None

        self._artwork_cache[url] = data
        self._artwork_cache.move_to_end(url)
        while len(self._artwork_cache) > self.cache_size:
            self._artwork_cache.popitem(last=False)
        return data

    def _draw(
        self,
        snapshot: PlaybackSnapshot,
        paused: bool,
        artwork_bytes: Optional[bytes],
    ) -> bytes:
        artwork = self._open_artwork(artwork_bytes)
        accent = self._accent_from_artwork(artwork, snapshot)
        image = self._background(artwork, accent)
        draw = ImageDraw.Draw(image, "RGBA")

        draw.rounded_rectangle((48, 40, 1152, 635), radius=28, fill=PANEL, outline=(255, 255, 255, 28), width=2)
        self._brand_mark(image, (68, 55), 54)
        draw = ImageDraw.Draw(image, "RGBA")
        self._draw_header(draw, snapshot, paused, accent)
        if snapshot.current:
            self._draw_active(image, draw, snapshot, artwork, accent)
        else:
            self._draw_idle(image, draw, accent)

        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _background(self, artwork: Optional[Image.Image], accent: tuple[int, int, int]) -> Image.Image:
        gradient = self._gradient((WIDTH, HEIGHT), self._mix(accent, PINK, 0.38), self._mix(accent, BLUE, 0.55))
        base = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
        base = Image.blend(base, gradient, 0.34)
        if artwork:
            blurred = ImageOps.fit(artwork.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
            blurred = ImageEnhance.Brightness(blurred).enhance(0.32).filter(ImageFilter.GaussianBlur(46))
            base = Image.blend(base, blurred, 0.24)
        shade = Image.new("RGBA", (WIDTH, HEIGHT), (8, 10, 16, 105))
        return Image.alpha_composite(base.convert("RGBA"), shade)

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        snapshot: PlaybackSnapshot,
        paused: bool,
        accent: tuple[int, int, int],
    ) -> None:
        draw.text((136, 72), "KSC MUSIC", font=self._font(24, bold=True), fill=TEXT)
        status = "TẠM DỪNG" if paused else ("ĐANG PHÁT" if snapshot.current else "SẴN SÀNG")
        width = draw.textbbox((0, 0), status, font=self._font(18, bold=True))[2] + 38
        x = 1118 - width
        draw.rounded_rectangle((x, 68, 1118, 105), radius=18, fill=(*accent, 52), outline=(*accent, 130), width=1)
        draw.text((x + 19, 76), status, font=self._font(18, bold=True), fill=(*BACKGROUND, 255))

    def _draw_active(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        snapshot: PlaybackSnapshot,
        artwork: Optional[Image.Image],
        accent: tuple[int, int, int],
    ) -> None:
        track = snapshot.current
        art_box = (80, 145, 455, 520)
        if artwork:
            art = ImageOps.fit(artwork.convert("RGB"), (375, 375), method=Image.Resampling.LANCZOS)
        else:
            art = self._gradient((375, 375), self._mix(accent, LAVENDER, 0.45), self._mix(accent, BLUE, 0.55))
            placeholder = ImageDraw.Draw(art)
            placeholder.text((187, 187), "♪", anchor="mm", font=self._font(120, bold=True), fill=TEXT)
        mask = Image.new("L", (375, 375), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 374, 374), radius=22, fill=255)
        shadow = Image.new("RGBA", (415, 415), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((20, 20, 395, 395), radius=26, fill=(*accent, 72))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        image.alpha_composite(shadow, (60, 125))
        image.paste(art, art_box[:2], mask)

        x = 515
        title = self._clean_text(track.title)
        uploader = self._clean_text(track.uploader or "Không rõ nghệ sĩ")
        self._draw_fitted(draw, title, (x, 165), 610, 50, bold=True, fill=TEXT, min_size=28)
        self._draw_fitted(draw, uploader, (x, 230), 570, 27, bold=False, fill=SECONDARY, min_size=19)

        source_color = MINT if track.source is TrackSource.SOUNDCLOUD else PINK
        self._chip(draw, (x, 286), track.source.value, source_color)
        self._chip(draw, (x + 170, 286), f"VOL {round(snapshot.volume * 100)}%", BLUE)
        self._chip(draw, (x + 340, 286), f"LOOP {snapshot.loop_mode.value.upper()}", LAVENDER)

        self._draw_waveform(draw, track.title, x, 355, 570, 78, accent, snapshot)
        elapsed = min(snapshot.elapsed, track.duration or snapshot.elapsed)
        duration = track.duration or 0
        draw.text((x, 452), format_duration(elapsed), font=self._font(18, bold=True), fill=TEXT)
        end_text = format_duration(duration) if duration else "LIVE"
        end_width = draw.textbbox((0, 0), end_text, font=self._font(18, bold=True))[2]
        draw.text((1085 - end_width, 452), end_text, font=self._font(18, bold=True), fill=TEXT)

        requester = self._clean_text(track.requester_name or "Không rõ")
        self._draw_fitted(
            draw,
            f"Yêu cầu bởi {requester}",
            (x, 510),
            570,
            20,
            bold=False,
            fill=SECONDARY,
            min_size=16,
        )
        draw.text((x, 551), f"{len(snapshot.queue)} bài đang chờ", font=self._font(18), fill=MUTED)
        status = []
        if snapshot.audio_profile.active:
            status.append(
                f"FX {snapshot.audio_profile.effect.label}  ·  "
                f"EQ {snapshot.audio_profile.equalizer.label}"
            )
        if snapshot.fair_queue:
            status.append("CÔNG BẰNG")
        if snapshot.autoplay:
            status.append("TỰ PHÁT")
        if status:
            self._draw_fitted(
                draw,
                "  ·  ".join(status),
                (x, 584),
                570,
                17,
                bold=True,
                fill=accent,
                min_size=14,
            )

    def _draw_idle(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        accent: tuple[int, int, int],
    ) -> None:
        tile = self._gradient((375, 375), self._mix(accent, PINK, 0.5), self._mix(accent, BLUE, 0.5)).convert("RGBA")
        tile = ImageEnhance.Brightness(tile).enhance(0.65)
        mask = Image.new("L", (375, 375), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 374, 374), radius=22, fill=255)
        image.paste(tile, (80, 145), mask)
        draw.ellipse((220, 330, 288, 398), fill=(*LAVENDER, 255))
        draw.rounded_rectangle((278, 242, 300, 367), radius=10, fill=(*LAVENDER, 255))
        draw.polygon([(294, 242), (360, 262), (360, 290), (294, 271)], fill=(*LAVENDER, 255))
        draw.text((515, 205), "Chưa có bài hát nào", font=self._font(43, bold=True), fill=TEXT)
        draw.text((515, 266), "đang được phát", font=self._font(43, bold=True), fill=TEXT)
        draw.text((515, 358), "Tìm nhạc bằng /phat", font=self._font(27), fill=SECONDARY)
        draw.rounded_rectangle((515, 420, 910, 480), radius=24, fill=(*accent, 48), outline=(*accent, 135), width=2)
        draw.text((712, 450), "SẴN SÀNG NGHE NHẠC", anchor="mm", font=self._font(20, bold=True), fill=(*BACKGROUND, 255))

    def _draw_waveform(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        accent: tuple[int, int, int],
        snapshot: PlaybackSnapshot,
    ) -> None:
        seed = int.from_bytes(hashlib.sha256(title.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        bars = 52
        gap = 4
        bar_width = max(3, (width - gap * (bars - 1)) // bars)
        progress = 0.0
        if snapshot.current and snapshot.current.duration:
            progress = min(1.0, snapshot.elapsed / snapshot.current.duration)
        active_bars = int(progress * bars)
        for index in range(bars):
            bar_height = rng.randint(12, height)
            left = x + index * (bar_width + gap)
            top = y + (height - bar_height) // 2
            color = (*accent, 235) if index <= active_bars else (116, 121, 141, 105)
            draw.rounded_rectangle((left, top, left + bar_width, top + bar_height), radius=bar_width // 2, fill=color)

    @staticmethod
    def _chip(draw: ImageDraw.ImageDraw, position: tuple[int, int], text: str, color: tuple[int, int, int]) -> None:
        x, y = position
        font = PlayerCardRenderer._font(17, bold=True)
        width = draw.textbbox((0, 0), text, font=font)[2] + 30
        draw.rounded_rectangle((x, y, x + width, y + 38), radius=18, fill=(*color, 38), outline=(*color, 105), width=1)
        draw.text((x + 15, y + 9), text, font=font, fill=(*BACKGROUND, 255))

    @classmethod
    def _draw_fitted(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        max_width: int,
        size: int,
        *,
        bold: bool,
        fill: tuple[int, int, int],
        min_size: int,
    ) -> None:
        font = cls._font(size, bold=bold, text=text)
        while size > min_size and draw.textbbox((0, 0), text, font=font)[2] > max_width:
            size -= 2
            font = cls._font(size, bold=bold, text=text)
        if draw.textbbox((0, 0), text, font=font)[2] > max_width:
            while text and draw.textbbox((0, 0), text + "…", font=font)[2] > max_width:
                text = text[:-1]
            text += "…"
        draw.text(position, text, font=font, fill=fill)

    @staticmethod
    def _open_artwork(data: Optional[bytes]) -> Optional[Image.Image]:
        if not data:
            return None
        try:
            return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        except Exception as error:
            logger.info("artwork_decode_failed error=%s", error)
            return None

    @staticmethod
    def _load_brand_mascot() -> Optional[Image.Image]:
        try:
            return Image.open(BRAND_MASCOT_PATH).convert("RGBA")
        except (OSError, ValueError) as error:
            logger.warning("player_brand_mascot_load_failed error=%s", error)
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

    @staticmethod
    def _accent_from_artwork(
        artwork: Optional[Image.Image],
        snapshot: PlaybackSnapshot,
    ) -> tuple[int, int, int]:
        if not artwork:
            if snapshot.current and snapshot.current.source is TrackSource.SOUNDCLOUD:
                return MINT
            return LAVENDER
        sample = artwork.resize((1, 1), Image.Resampling.LANCZOS).getpixel((0, 0))
        target = LAVENDER if sum(sample) < 260 else BLUE
        mixed = PlayerCardRenderer._mix(sample, target, 0.52)
        return tuple(max(105, min(235, channel)) for channel in mixed)

    @staticmethod
    def _gradient(
        size: tuple[int, int],
        start: tuple[int, int, int],
        end: tuple[int, int, int],
    ) -> Image.Image:
        width, height = size
        strip = Image.new("RGB", (width, 1))
        pixels = [
            tuple(int(start[channel] + (end[channel] - start[channel]) * index / max(1, width - 1)) for channel in range(3))
            for index in range(width)
        ]
        strip.putdata(pixels)
        return strip.resize((width, height))

    @staticmethod
    def _mix(
        first: tuple[int, int, int],
        second: tuple[int, int, int],
        amount: float,
    ) -> tuple[int, int, int]:
        return tuple(int(a * (1 - amount) + b * amount) for a, b in zip(first, second))

    @staticmethod
    def _clean_text(value: str) -> str:
        cleaned = "".join(
            character
            for character in value
            if unicodedata.category(character) not in {"So", "Cs", "Co", "Cn"}
            and character not in {"\ufe0f", "\u200d"}
        )
        return " ".join(cleaned.split()) or "Không rõ"

    @staticmethod
    def _font(
        size: int,
        *,
        bold: bool = False,
        text: str = "",
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = []
        if os.name == "nt":
            if any("CJK" in unicodedata.name(character, "") or "HANGUL" in unicodedata.name(character, "") for character in text):
                candidates.append(Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"))
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
