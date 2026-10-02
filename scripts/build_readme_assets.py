"""Build lightweight, repository-local media used by the README."""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"


def build_animated_mascot() -> None:
    source = Image.open(ASSETS / "ksc-mascot.png").convert("RGBA")
    source.thumbnail((410, 410), Image.Resampling.LANCZOS)
    rng = random.Random(6174)
    sparkles = [
        (rng.randint(35, 445), rng.randint(45, 430), rng.randint(2, 5), rng.random() * math.tau)
        for _ in range(10)
    ]
    frames: list[Image.Image] = []
    for index in range(24):
        phase = index / 24 * math.tau
        frame = Image.new("RGBA", (480, 480), (0, 0, 0, 0))
        y = 31 + round(math.sin(phase) * 7)
        x = (480 - source.width) // 2

        glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow, "RGBA")
        pulse = 7 + round((math.sin(phase) + 1) * 3)
        glow_draw.ellipse(
            (x + 45 - pulse, y + 55 - pulse, x + source.width - 45 + pulse, y + source.height - 35 + pulse),
            fill=(83, 232, 215, 45),
        )
        frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(28)))
        frame.alpha_composite(source, (x, y))

        draw = ImageDraw.Draw(frame, "RGBA")
        for sx, sy, radius, offset in sparkles:
            alpha = int(40 + 150 * (math.sin(phase + offset) + 1) / 2)
            color = (104, 230, 216, alpha) if sx % 2 else (251, 146, 160, alpha)
            draw.line((sx - radius * 2, sy, sx + radius * 2, sy), fill=color, width=2)
            draw.line((sx, sy - radius * 2, sx, sy + radius * 2), fill=color, width=2)
        frames.append(frame)

    frames[0].save(
        ASSETS / "ksc-mascot-animated.png",
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        duration=85,
        loop=0,
        disposal=2,
        blend=0,
        optimize=True,
    )


def build_avatar() -> None:
    source = Image.open(ASSETS / "ksc-mascot.png").convert("RGBA")
    avatar = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    source.thumbnail((480, 480), Image.Resampling.LANCZOS)
    x = (512 - source.width) // 2
    y = (512 - source.height) // 2
    glow = Image.new("RGBA", avatar.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow, "RGBA").ellipse((42, 42, 470, 470), fill=(83, 232, 215, 52))
    avatar.alpha_composite(glow.filter(ImageFilter.GaussianBlur(34)))
    avatar.alpha_composite(source, (x, y))
    avatar.save(ASSETS / "ksc-mascot-avatar.png", optimize=True)


def build_animated_readme_hero() -> None:
    source = Image.open(ASSETS / "readme-hero.png").convert("RGB")
    width = 1280
    height = round(source.height * width / source.width)
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    rng = random.Random(925)
    sparkles = [
        (rng.randint(40, width - 40), rng.randint(30, height - 30), rng.randint(2, 5), rng.random() * math.tau)
        for _ in range(14)
    ]

    frames: list[Image.Image] = []
    frame_count = 10
    for index in range(frame_count):
        phase = index / frame_count * math.tau
        frame = ImageEnhance.Brightness(source).enhance(1.0 + math.sin(phase) * 0.018).convert("RGBA")
        effects = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(effects, "RGBA")

        sweep_x = round(-350 + (width + 700) * index / (frame_count - 1))
        draw.polygon(
            [
                (sweep_x - 150, 0),
                (sweep_x + 10, 0),
                (sweep_x + 300, height),
                (sweep_x + 140, height),
            ],
            fill=(255, 255, 255, 24),
        )
        effects = effects.filter(ImageFilter.GaussianBlur(24))
        frame = Image.alpha_composite(frame, effects)

        draw = ImageDraw.Draw(frame, "RGBA")
        for x, y, radius, offset in sparkles:
            alpha = int(35 + 150 * (math.sin(phase + offset) + 1) / 2)
            color = (122, 246, 235, alpha) if x % 2 else (255, 175, 213, alpha)
            draw.line((x - radius * 2, y, x + radius * 2, y), fill=color, width=2)
            draw.line((x, y - radius * 2, x, y + radius * 2), fill=color, width=2)
        frames.append(frame.convert("RGB"))

    palette = frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    gif_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
        for frame in frames
    ]
    gif_frames[0].save(
        ASSETS / "readme-hero-animated.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=130,
        loop=0,
        disposal=2,
        optimize=True,
    )


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_avatar()
    build_animated_mascot()
    build_animated_readme_hero()
