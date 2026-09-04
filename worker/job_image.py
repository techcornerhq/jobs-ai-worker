from __future__ import annotations

import re
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, features

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH = 1200
HEIGHT = 630
IMAGE_VERSION = "v3"
HAS_RAQM = bool(features.check_feature("raqm"))

# Premium job-poster palette.
BG = (245, 248, 250)
CARD = (255, 255, 255)
NAVY = (19, 32, 51)
TEAL = (16, 117, 108)
TEAL_DARK = (10, 87, 81)
TEAL_SOFT = (229, 245, 242)
BLUE_SOFT = (236, 243, 255)
BLUE = (39, 91, 173)
GOLD_SOFT = (255, 245, 218)
GOLD = (166, 105, 15)
MUTED = (103, 116, 135)
BORDER = (220, 228, 235)


def fallback_visual(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def text_kwargs() -> dict:
    if HAS_RAQM:
        return {"direction": "rtl", "language": "ar"}
    return {}


def prepared(text: str) -> str:
    text = str(text or "").strip()
    return text if HAS_RAQM else fallback_visual(text)


def measure(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    bbox = draw.textbbox((0, 0), prepared(text), font=fnt, **text_kwargs())
    return bbox[2] - bbox[0]


def draw_ar(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, anchor: str = "ra") -> None:
    draw.text(xy, prepared(text), font=fnt, fill=fill, anchor=anchor, **text_kwargs())


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 3) -> list[str]:
    words = str(text or "").split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        if measure(draw, test, fnt) <= max_width or not current:
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


def extract_salary(text: str) -> str | None:
    t = str(text or "")
    patterns = [
        r"(?:رواتب?|راتب)\s+متوقعة?\s*(?:من\s*)?(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})",
        r"(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار",
        r"(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})\s*دينار",
    ]
    for p in patterns:
        m = re.search(p, t, re.I)
        if not m:
            continue
        if len(m.groups()) == 2 and m.group(2):
            return f"راتب متوقع {m.group(1)}–{m.group(2)} د.أ"
        return f"راتب متوقع حتى {m.group(1)} د.أ"
    return None


def chip(draw: ImageDraw.ImageDraw, x_right: int, y: int, text: str, fnt, fill, text_fill, min_width: int = 150) -> int:
    pad_x = 26
    width = max(min_width, measure(draw, text, fnt) + pad_x * 2)
    x_left = x_right - width
    draw.rounded_rectangle((x_left, y, x_right, y + 54), radius=18, fill=fill)
    draw_ar(draw, (x_right - pad_x, y + 27), text, fnt, text_fill, anchor="rm")
    return x_left - 14


def generate(job: dict, title: str) -> tuple[str, str]:
    campaign_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job.get("campaign_id") or "job"))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{campaign_id}-{IMAGE_VERSION}.png"

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Soft background decorations for a more editorial/poster look.
    draw.ellipse((-70, -90, 300, 280), fill=(232, 244, 242))
    draw.ellipse((980, 450, 1290, 760), fill=(238, 243, 251))

    # Shadow and main card.
    draw.rounded_rectangle((64, 54, 1148, 592), radius=38, fill=(224, 231, 236))
    draw.rounded_rectangle((54, 44, 1138, 582), radius=38, fill=CARD, outline=BORDER, width=2)

    # Right premium accent bar.
    draw.rounded_rectangle((1105, 44, 1138, 582), radius=16, fill=TEAL)
    draw.rectangle((1105, 75, 1138, 550), fill=TEAL)

    # Top brand strip.
    draw.rounded_rectangle((84, 70, 1080, 138), radius=22, fill=TEAL_DARK)

    brand_font = font(32, bold=True)
    badge_font = font(23, bold=True)
    employer_font = font(27, bold=True)
    title_font = font(49, bold=True)
    chip_font = font(21, bold=True)
    footer_font = font(20, bold=False)

    draw_ar(draw, (1040, 104), "وظائف الأردن", brand_font, (255, 255, 255), anchor="rm")

    # Left badge in header.
    draw.rounded_rectangle((105, 84, 330, 124), radius=15, fill=(255, 255, 255))
    draw_ar(draw, (300, 104), "فرصة عمل جديدة", badge_font, TEAL_DARK, anchor="rm")

    employer = str(job.get("employer_name") or "جهة توظيف في الأردن").strip()
    location = str(job.get("location_text") or "الأردن").strip()

    # Employer label and decorative dot.
    draw.ellipse((1025, 171, 1045, 191), fill=TEAL)
    draw_ar(draw, (1008, 181), employer, employer_font, TEAL_DARK, anchor="rm")

    # Main headline area.
    y = 226
    lines = wrap(draw, title, title_font, 865, max_lines=3)
    for line in lines:
        draw_ar(draw, (1035, y), line, title_font, NAVY, anchor="ra")
        y += 66

    # Information chips. Salary is emphasized if present in title/source title.
    salary = extract_salary(title) or extract_salary(str(job.get("title") or ""))
    x = 1035
    chip_y = 445
    if salary:
        x = chip(draw, x, chip_y, salary, chip_font, GOLD_SOFT, GOLD, min_width=260)
    x = chip(draw, x, chip_y, location, chip_font, BLUE_SOFT, BLUE, min_width=205)

    # Secondary chip/category derived safely from title.
    category = "وظائف متنوعة" if any(w in title for w in ["متنوعة", "عدة", "فرص", "شواغر"]) else "فرصة توظيف"
    if x > 240:
        chip(draw, x, chip_y, category, chip_font, TEAL_SOFT, TEAL_DARK, min_width=175)

    # Bottom bar and CTA-like message.
    draw.line((100, 530, 1065, 530), fill=BORDER, width=2)
    draw_ar(draw, (1035, 557), "التفاصيل وطريقة التقديم داخل الإعلان", footer_font, MUTED, anchor="ra")

    # Small visual mark on the left to avoid empty space.
    draw.rounded_rectangle((108, 540, 235, 570), radius=12, fill=TEAL_SOFT)
    draw_ar(draw, (220, 555), "محدّث", footer_font, TEAL_DARK, anchor="rm")

    img.save(path, format="PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"
