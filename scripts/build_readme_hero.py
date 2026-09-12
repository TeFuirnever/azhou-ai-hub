#!/usr/bin/env python3
"""Deterministically compose the Azhou AI Hub README hero image.

Follows azhou-covers github_readme_image_16_9 profile:
- canvas 1280x720, cream paper background
- title / result / evidence regions per profile
- canonical Azhou character composited at exact registered pixels (no resampling)
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CREAM = (0xFE, 0xF9, 0xEB)
CHOCOLATE = (0x6F, 0x38, 0x10)
ORANGE = (0xFA, 0x94, 0x39)
PINK = (0xFA, 0xA6, 0x7C)

ROOT = Path("/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub")
RUNTIME = Path("/Users/guanxueliang/Library/Application Support/kimi-desktop/daimon-share/daimon/runtime/python")
FONT_CJK_BOLD = RUNTIME / "fonts/NotoSansSC-Bold.ttf"
FONT_CJK_REG = RUNTIME / "fonts/NotoSansSC-Regular.ttf"
CHARACTER = Path("/Users/guanxueliang/.agents/skills/azhou-covers/authority/v1.9/character/canonical-front.png")
OUT = ROOT / "assets/github/readme-hero.png"

random.seed(20260913)

img = Image.new("RGB", (1280, 720), CREAM)
d = ImageDraw.Draw(img)


def wavy_line(x0, y0, x1, y1, color, width=3, amp=2.2, waves=None):
    """Hand-drawn wobbly line between two points."""
    length = math.hypot(x1 - x0, y1 - y0)
    steps = max(int(length / 6), 8)
    if waves is None:
        waves = max(length / 90, 2)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        # perpendicular wobble + jitter
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        off = math.sin(t * math.pi * waves) * amp + random.uniform(-0.8, 0.8)
        pts.append((x + nx * off, y + ny * off))
    d.line(pts, fill=color, width=width, joint="curve")


def hand_circle(cx, cy, rx, ry, color, width=3):
    pts = []
    for i in range(73):
        t = i / 72 * 2 * math.pi
        pts.append(
            (
                cx + rx * math.cos(t) + random.uniform(-1.6, 1.6),
                cy + ry * math.sin(t) + random.uniform(-1.6, 1.6),
            )
        )
    d.line(pts, fill=color, width=width, joint="curve")


# ---- subtle paper edge: a few short hand strokes in corners ----
wavy_line(64, 668, 240, 668, PINK, width=3, amp=1.6)
wavy_line(1040, 56, 1216, 56, PINK, width=3, amp=1.6)

# ---- title region (72,86)-(680,272) ----
f_title = ImageFont.truetype(str(FONT_CJK_BOLD), 84)
f_sub = ImageFont.truetype(str(FONT_CJK_REG), 30)
d.text((72, 92), "AZHOU AI HUB", font=f_title, fill=CHOCOLATE)
wavy_line(76, 196, 76 + 560, 196, ORANGE, width=5, amp=2.6)
d.text((76, 216), "Agent skills that stay useful after the demo.", font=f_sub, fill=CHOCOLATE)

# ---- result region (72,298)-(672,392) ----
f_result = ImageFont.truetype(str(FONT_CJK_BOLD), 40)
d.text((72, 308), "Installable. Verifiable. Traceable.", font=f_result, fill=CHOCOLATE)
hand_circle(580, 330, 70, 34, PINK, width=3)

# ---- evidence region (72,414)-(672,594): three check lines ----
f_item = ImageFont.truetype(str(FONT_CJK_REG), 28)
items = [
    "16 installable skill packages",
    "one deterministic repository gate",
    "human-approved evolution only",
]
y = 424
for i, text in enumerate(items):
    # hand-drawn check mark
    d.line([(76, y + 16), (88, y + 28)], fill=ORANGE, width=5, joint="curve")
    d.line([(88, y + 28), (110, y + 2)], fill=ORANGE, width=5, joint="curve")
    d.text((128, y), text, font=f_item, fill=CHOCOLATE)
    y += 56

# ---- small annotation near the character ----
f_note = ImageFont.truetype(str(FONT_CJK_REG), 24)
d.text((72, 616), "skills as products: precise trigger, portable runtime, honest evidence", font=f_note, fill=CHOCOLATE)
wavy_line(72, 656, 620, 656, PINK, width=3, amp=1.8)

# ---- character: exact registered pixels, transform none ----
ch = Image.open(CHARACTER).convert("RGBA")
assert ch.size == (485, 560)
base = img.convert("RGBA")
base.alpha_composite(ch, (715, 96))
img = base.convert("RGB")

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, format="PNG", optimize=True)
print(OUT, OUT.stat().st_size, "bytes")

# review thumbnails
for w in (120, 240, 360):
    t = img.copy()
    t.thumbnail((w, 10_000), Image.LANCZOS)
    p = ROOT / f"assets/github/readme-hero-thumb{w}.png"
    t.save(p)
    print(p)
