from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

WIDTH, HEIGHT = 1536, 1024
VERSION = "ai-v1"  # preserve the production URL contract while replacing the artwork
IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"

CREAM = (249, 245, 237)
CREAM_2 = (237, 226, 210)
NAVY = (7, 31, 56)
BURGUNDY = (143, 15, 29)
BURGUNDY_DARK = (96, 7, 17)
GREEN = (12, 101, 58)
GOLD = (198, 150, 67)
GOLD_LIGHT = (232, 196, 126)
WHITE = (255, 255, 255)

BAD_CHARS = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff□■▪▫�]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


def clean(value: str) -> str:
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = BAD_CHARS.sub("", s).replace("ـ", "")
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def first(*values, default="") -> str:
    for value in values:
        s = clean(value)
        if s and s not in {"غير مذكور", "غير مذكور في الإعلان", "None"}:
            return s
    return default


def short(value: str, limit: int) -> str:
    s = clean(value)
    if len(s) <= limit:
        return s
    cut = s[: limit + 1].rsplit(" ", 1)[0].strip()
    return (cut or s[:limit]).rstrip(" ،,؛:-") + "…"


def _font(size: int, weight: str = "black"):
    if weight == "black":
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Black.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-ExtraBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        ]
    elif weight == "bold":
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-SemiBold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _display(text: str):
    text = clean(text)
    if not ARABIC_RE.search(text):
        return text, {}
    if features.check_feature("raqm"):
        return text, {"direction": "rtl", "language": "ar"}
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text)), {}
    return text, {}


def _bbox(draw, text: str, font):
    rendered, kwargs = _display(text)
    return draw.textbbox((0, 0), rendered, font=font, **kwargs)


def _text(draw, xy, text: str, font, fill, anchor="mm", stroke_width=0, stroke_fill=None):
    rendered, kwargs = _display(text)
    draw.text(
        xy,
        rendered,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
        **kwargs,
    )


def _fit_font(draw, text: str, max_w: int, max_h: int, start=70, end=28):
    for size in range(start, end - 1, -2):
        font = _font(size, "black")
        b = _bbox(draw, text, font)
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            return font
    return _font(end, "black")


def _poly(draw, pts, fill, outline=None, width=1):
    draw.polygon(pts, fill=fill)
    if outline:
        draw.line(pts + [pts[0]], fill=outline, width=width, joint="curve")


def _draw_petra(draw: ImageDraw.ImageDraw):
    stone = (203, 159, 123)
    stone2 = (225, 197, 169)
    _poly(draw, [(0, 155), (235, 90), (365, 160), (390, 590), (0, 730)], stone2)
    x, y, w, h = 85, 280, 250, 340
    draw.rectangle((x + 25, y + 110, x + w - 25, y + h), fill=(220, 181, 145), outline=stone, width=3)
    for cx in [x + 55, x + 95, x + 155, x + 195]:
        draw.rectangle((cx, y + 150, cx + 18, y + h - 24), fill=(234, 208, 183), outline=stone, width=2)
        draw.ellipse((cx - 3, y + 140, cx + 21, y + 160), fill=(229, 200, 173), outline=stone)
    _poly(draw, [(x + 35, y + 145), (x + w // 2, y + 55), (x + w - 35, y + 145)], (225, 190, 157), stone, 3)
    draw.rectangle((x + 104, y + h - 115, x + 150, y + h), fill=(171, 126, 95))
    draw.arc((x + 95, y + h - 150, x + 160, y + h - 75), 180, 360, fill=stone, width=4)
    draw.ellipse((x + 107, y + 65, x + 145, y + 105), outline=stone, width=4)
    draw.rectangle((x + 119, y + 45, x + 133, y + 72), fill=(219, 180, 146))
    for k in range(18):
        yy = 140 + k * 28
        draw.line((5, yy, 70 + (k % 5) * 16, yy - 18), fill=(218, 184, 154), width=2)


def _draw_skyline(draw: ImageDraw.ImageDraw):
    base = HEIGHT - 2
    color = (211, 205, 194)
    color2 = (225, 219, 208)
    x = 290
    widths = [32, 44, 28, 50, 36, 58, 30, 46, 34, 62, 40, 31, 54, 42, 30, 66, 36, 48, 30, 55, 45, 33, 65, 38]
    for i, w in enumerate(widths):
        h = 80 + ((i * 37) % 165)
        yy = base - h
        fill = color if i % 3 else color2
        draw.rectangle((x, yy, x + w, base), fill=fill)
        if i % 4 == 1:
            draw.polygon([(x + w // 2, yy - 34), (x + w, yy), (x, yy)], fill=fill)
        if i % 5 == 2:
            draw.rectangle((x + w // 2 - 3, yy - 42, x + w // 2 + 3, yy), fill=fill)
        x += w + 13
        if x > WIDTH - 100:
            break
    draw.rectangle((1130, HEIGHT - 250, 1152, base), fill=(198, 192, 182))
    draw.rectangle((1140, HEIGHT - 300, 1143, HEIGHT - 250), fill=(198, 192, 182))
    draw.ellipse((1136, HEIGHT - 310, 1147, HEIGHT - 299), fill=(198, 192, 182))
    for bx in (1260, 1310):
        draw.rounded_rectangle((bx, HEIGHT - 290, bx + 34, base), radius=4, fill=(196, 190, 180))


def _draw_flag_ribbon(draw: ImageDraw.ImageDraw):
    draw.polygon([(1130, 0), (1536, 0), (1536, 72), (1200, 30)], fill=(18, 18, 19))
    draw.polygon([(1180, 0), (1536, 78), (1536, 140), (1250, 48)], fill=(249, 248, 244))
    draw.polygon([(1240, 0), (1536, 145), (1536, 212), (1300, 62)], fill=GREEN)
    draw.polygon([(1430, 0), (1536, 0), (1536, 170)], fill=BURGUNDY)
    cx, cy = 1490, 72
    pts = []
    for i in range(14):
        angle = -math.pi / 2 + i * math.pi / 7
        radius = 22 if i % 2 == 0 else 9
        pts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    draw.polygon(pts, fill=WHITE)


def _draw_corner_panels(draw: ImageDraw.ImageDraw):
    draw.polygon([(0, 720), (280, 1024), (0, 1024)], fill=NAVY)
    draw.polygon([(0, 806), (200, 1024), (0, 1024)], fill=BURGUNDY)
    draw.line([(0, 690), (310, 1024)], fill=GOLD, width=4)
    draw.line([(0, 760), (245, 1024)], fill=GOLD_LIGHT, width=2)
    cx, cy = 92, 895
    pts = []
    for i in range(16):
        angle = -math.pi / 2 + i * math.pi / 8
        radius = 58 if i % 2 == 0 else 34
        pts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    draw.line(pts + [pts[0]], fill=GOLD, width=3)


def _draw_header(draw: ImageDraw.ImageDraw):
    _text(draw, (768, 86), "وظائف الأردن", _font(58, "black"), NAVY, "mm")
    draw.line((620, 132, 920, 132), fill=GOLD, width=3)
    _text(draw, (768, 166), "فرص عمل موثقة وحديثة", _font(27, "bold"), (55, 58, 60), "mm")


def render(job: dict, title: str) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), CREAM)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        color = tuple(int(CREAM[i] * (1 - t * 0.05) + CREAM_2[i] * (t * 0.05)) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=color)

    _draw_petra(draw)
    _draw_skyline(draw)
    _draw_flag_ribbon(draw)
    _draw_corner_panels(draw)
    _draw_header(draw)

    for r in (64, 98, 132):
        draw.rectangle((1350 - r, 295 - r, 1350 + r, 295 + r), outline=(221, 210, 193), width=2)

    _text(draw, (835, 365), "توظيف", _font(96, "black"), BURGUNDY, "mm")
    _text(draw, (1170, 365), "إعلان", _font(96, "black"), NAVY, "mm")
    draw.line((530, 438, 1000, 438), fill=GOLD, width=3)
    draw.ellipse((752, 429, 770, 447), fill=GOLD)

    role = short(first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة"), 72)
    box = (565, 488, 1430, 640)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((box[0] + 8, box[1] + 12, box[2] + 8, box[3] + 12), radius=48, fill=(50, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    image = Image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=48, fill=BURGUNDY_DARK, outline=GOLD, width=5)
    draw.rounded_rectangle((box[0] + 8, box[1] + 8, box[2] - 8, box[3] - 8), radius=42, outline=BURGUNDY, width=3)

    arrow_x = 1375
    for offset in (0, 28):
        draw.line((arrow_x - offset, 546, arrow_x + 20 - offset, 564), fill=GOLD_LIGHT, width=5)
        draw.line((arrow_x + 20 - offset, 564, arrow_x - offset, 582), fill=GOLD_LIGHT, width=5)

    title_font = _fit_font(draw, role, 720, 102, start=64, end=30)
    _text(draw, (980, 563), role, title_font, WHITE, "mm", stroke_width=1, stroke_fill=WHITE)

    _text(
        draw,
        (1280, 715),
        "تفاصيل الوظيفة وطريقة التقديم داخل المقال",
        _font(25, "bold"),
        NAVY,
        "mm",
    )
    draw.ellipse((1075, 684, 1107, 716), fill=BURGUNDY)
    draw.polygon([(1091, 734), (1078, 708), (1104, 708)], fill=BURGUNDY)
    return image


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    role = first(job.get("job_title"), title, job.get("title"), default="job")
    employer = first(job.get("employer_name"), default="")
    digest = hashlib.sha1(f"{role}|{employer}".encode("utf-8")).hexdigest()[:24]
    path = IMAGE_DIR / f"{digest}-{VERSION}.png"
    render(job, title).save(path, "PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"


__all__ = ["generate", "render"]
