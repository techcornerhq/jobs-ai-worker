from __future__ import annotations

import re
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH = 1200
HEIGHT = 630


def ar(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 3) -> list[str]:
    words = str(text or "").split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), ar(test), font=fnt)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    consumed = sum(len(x.split()) for x in lines)
    if consumed < len(words) and lines:
        lines[-1] = lines[-1].rstrip("،.- ") + "…"
    return lines


def generate(job: dict, title: str) -> tuple[str, str]:
    campaign_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job.get("campaign_id") or "job"))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{campaign_id}.png"

    img = Image.new("RGB", (WIDTH, HEIGHT), (247, 250, 252))
    draw = ImageDraw.Draw(img)

    # Header band and simple brand mark.
    draw.rounded_rectangle((60, 48, 1140, 582), radius=34, fill=(255, 255, 255), outline=(219, 228, 236), width=3)
    draw.rounded_rectangle((60, 48, 1140, 145), radius=34, fill=(15, 118, 110))
    draw.rectangle((60, 105, 1140, 145), fill=(15, 118, 110))

    brand_font = font(34, bold=True)
    kicker_font = font(25, bold=True)
    title_font = font(48, bold=True)
    body_font = font(29, bold=False)
    small_font = font(22, bold=False)

    draw.text((1090, 78), ar("وظائف الأردن"), font=brand_font, fill=(255, 255, 255), anchor="ra")
    draw.text((110, 82), ar("فرصة عمل جديدة"), font=kicker_font, fill=(255, 255, 255), anchor="la")

    employer = str(job.get("employer_name") or "جهة توظيف في الأردن").strip()
    location = str(job.get("location_text") or "الأردن").strip()

    draw.text((1080, 190), ar(employer), font=body_font, fill=(15, 118, 110), anchor="ra")

    y = 245
    for line in wrap(draw, title, title_font, 920, max_lines=3):
        draw.text((1080, y), ar(line), font=title_font, fill=(23, 32, 51), anchor="ra")
        y += 67

    draw.rounded_rectangle((760, 490, 1080, 545), radius=18, fill=(239, 246, 255))
    draw.text((1055, 517), ar(location), font=small_font, fill=(30, 64, 175), anchor="ra")

    draw.text((100, 548), ar("تفاصيل التقديم داخل الإعلان"), font=small_font, fill=(102, 112, 133), anchor="la")

    img.save(path, format="PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"
