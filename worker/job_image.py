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
IMAGE_VERSION = "v4"
HAS_RAQM = bool(features.check_feature("raqm"))

# Approved V4 palette: bold Jordan jobs promo poster.
NAVY = (4, 30, 57)
NAVY_2 = (8, 47, 79)
TEAL = (8, 108, 103)
TEAL_2 = (14, 128, 119)
TEAL_DARK = (5, 72, 72)
GOLD = (245, 171, 53)
GOLD_DARK = (205, 126, 21)
WHITE = (255, 255, 255)
OFFWHITE = (246, 248, 250)
INK = (10, 35, 62)
MUTED = (105, 118, 135)
SOFT_TEAL = (229, 246, 242)


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
    return {"direction": "rtl", "language": "ar"} if HAS_RAQM else {}


def prepared(text: str) -> str:
    text = str(text or "").strip()
    return text if HAS_RAQM else fallback_visual(text)


def measure(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    bbox = draw.textbbox((0, 0), prepared(text), font=fnt, **text_kwargs())
    return bbox[2] - bbox[0]


def draw_ar(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, anchor: str = "ra") -> None:
    draw.text(xy, prepared(text), font=fnt, fill=fill, anchor=anchor, **text_kwargs())


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 2) -> list[str]:
    words = str(text or "").replace("|", " ").split()
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
    range_match = re.search(r"(?:رواتب?|راتب)[^\d]{0,25}(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})", t, re.I)
    if range_match:
        return f"رواتب متوقعة {range_match.group(1)}–{range_match.group(2)} دينار"
    range_match = re.search(r"(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})\s*دينار", t, re.I)
    if range_match:
        return f"رواتب متوقعة {range_match.group(1)}–{range_match.group(2)} دينار"
    upto = re.search(r"(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار", t, re.I)
    if upto:
        return f"راتب متوقع حتى {upto.group(1)} دينار"
    return None


def clean_headline(title: str, employer: str) -> str:
    t = str(title or "").strip()
    # Salary is already highlighted separately, so avoid repeating it in the headline.
    t = re.sub(r"\s*[|–-]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?[^|،]*?(?=$|\|)", "", t).strip(" |–-")
    if employer and employer not in t:
        return f"{employer} تعلن عن {t}" if t else f"{employer} تعلن عن فرص عمل جديدة"
    return t or f"{employer} تعلن عن فرص عمل جديدة"


def job_category(title: str) -> str:
    t = str(title or "")
    if any(x in t for x in ["تقنية", "Developer", "تطوير", "برمج", "IT"]):
        return "فرص في التقنية والتخصصات المهنية"
    if any(x in t for x in ["صيانة", "ميكاني", "كهرب", "فني"]):
        return "فرص فنية وهندسية متعددة"
    if any(x in t for x in ["متنوعة", "عدة", "شواغر", "فرص"]):
        return "فرص في الإدارة والتقنية والتشغيل"
    return "فرصة مهنية جديدة في الأردن"


def draw_icon_badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], kind: str) -> None:
    cx, cy = center
    draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=TEAL_DARK)
    if kind == "pin":
        draw.ellipse((cx - 7, cy - 11, cx + 7, cy + 3), outline=WHITE, width=3)
        draw.polygon([(cx, cy + 16), (cx - 8, cy + 1), (cx + 8, cy + 1)], fill=WHITE)
    elif kind == "people":
        draw.ellipse((cx - 6, cy - 11, cx + 6, cy + 1), fill=WHITE)
        draw.rounded_rectangle((cx - 13, cy + 2, cx + 13, cy + 13), radius=6, fill=WHITE)
    elif kind == "briefcase":
        draw.rounded_rectangle((cx - 14, cy - 8, cx + 14, cy + 12), radius=4, outline=WHITE, width=3)
        draw.rectangle((cx - 6, cy - 13, cx + 6, cy - 8), outline=WHITE, width=3)
    else:
        draw.polygon([(cx - 13, cy + 5), (cx + 15, cy - 9), (cx + 4, cy + 14), (cx - 1, cy + 4)], fill=WHITE)


def info_box(draw: ImageDraw.ImageDraw, box, label: str, icon: str, fnt) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=16, fill=OFFWHITE)
    draw_icon_badge(draw, (x2 - 38, (y1 + y2) // 2), icon)
    draw_ar(draw, (x2 - 72, (y1 + y2) // 2), label, fnt, INK, anchor="rm")


def draw_abstract_coffee_panel(draw: ImageDraw.ImageDraw) -> None:
    # A reusable, deterministic coffee-inspired motif (no external logo/image dependency).
    draw.ellipse((-120, 95, 300, 515), fill=(250, 244, 230))
    draw.arc((-120, 95, 300, 515), start=270, end=90, fill=WHITE, width=5)
    # simplified takeaway cup
    draw.rounded_rectangle((56, 278, 160, 430), radius=18, fill=NAVY_2)
    draw.rectangle((48, 260, 168, 292), fill=(235, 228, 211))
    draw.rounded_rectangle((66, 323, 150, 376), radius=20, outline=GOLD, width=4)
    # coffee beans
    for x, y in [(38, 447), (79, 461), (128, 448), (170, 468), (206, 444)]:
        draw.ellipse((x - 12, y - 7, x + 12, y + 7), fill=(89, 55, 35))
        draw.line((x - 7, y + 3, x + 7, y - 3), fill=(180, 132, 92), width=2)
    # subtle Amman/columns silhouette
    draw.rectangle((190, 188, 204, 315), fill=(221, 208, 183))
    draw.rectangle((222, 170, 236, 315), fill=(221, 208, 183))
    draw.rectangle((252, 195, 266, 315), fill=(221, 208, 183))
    draw.rectangle((178, 178, 277, 192), fill=(221, 208, 183))


def generate(job: dict, title: str) -> tuple[str, str]:
    campaign_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job.get("campaign_id") or "job"))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{campaign_id}-{IMAGE_VERSION}.png"

    img = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(img)

    # Deep navy/teal layered backdrop like the approved promotional concept.
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=NAVY)
    draw.polygon([(0, 0), (300, 0), (520, 235), (0, 235)], fill=TEAL_DARK)
    draw.polygon([(0, 0), (155, 0), (330, 180), (0, 180)], fill=TEAL_2)
    draw.rectangle((915, 0, 1200, 630), fill=NAVY_2)
    # decorative dots
    for yy in range(82, 212, 24):
        for xx in range(20, 150, 24):
            draw.ellipse((xx, yy, xx + 5, yy + 5), fill=(27, 109, 115))

    draw_abstract_coffee_panel(draw)

    brand_font = font(27, bold=True)
    badge_font = font(23, bold=True)
    headline_font = font(55, bold=True)
    salary_font = font(43, bold=True)
    support_font = font(27, bold=True)
    info_font = font(23, bold=True)
    cta_font = font(29, bold=True)

    # Header brand centered and announcement badge.
    draw.line((365, 58, 540, 58), fill=GOLD, width=2)
    draw.line((755, 58, 920, 58), fill=GOLD, width=2)
    draw.ellipse((550, 53, 560, 63), fill=GOLD)
    draw.ellipse((740, 53, 750, 63), fill=GOLD)
    draw_ar(draw, (650, 58), "وظائف الأردن", brand_font, WHITE, anchor="mm")
    draw.rounded_rectangle((900, 20, 1170, 82), radius=14, fill=GOLD)
    draw_ar(draw, (1145, 52), "إعلان توظيف جديد", badge_font, INK, anchor="rm")

    employer = str(job.get("employer_name") or "جهة توظيف في الأردن").strip()
    location = str(job.get("location_text") or "الأردن").strip()
    headline = clean_headline(title, employer)

    # Main headline: right aligned and dominant.
    y = 135
    for idx, line in enumerate(wrap(draw, headline, headline_font, 805, max_lines=2)):
        fill = GOLD if idx == 1 else WHITE
        draw_ar(draw, (1130, y), line, headline_font, fill, anchor="ra")
        y += 76

    salary = extract_salary(title) or extract_salary(str(job.get("title") or ""))
    salary_text = salary or "تفاصيل الراتب داخل الإعلان"
    draw.rounded_rectangle((395, 330, 1130, 410), radius=22, fill=TEAL_DARK)
    draw_ar(draw, (1100, 370), salary_text, salary_font if salary else support_font, GOLD if salary else WHITE, anchor="rm")

    # Supporting specialization line.
    support = job_category(title)
    draw.line((420, 449, 535, 449), fill=TEAL_2, width=3)
    draw.line((1000, 449, 1115, 449), fill=TEAL_2, width=3)
    draw_ar(draw, (775, 450), support, support_font, WHITE, anchor="mm")

    # Four compact information boxes.
    box_y1, box_y2 = 480, 546
    info_box(draw, (905, box_y1, 1140, box_y2), location, "pin", info_font)
    info_box(draw, (665, box_y1, 895, box_y2), "عدة شواغر" if any(x in title for x in ["متنوعة", "فرص", "شواغر", "عدة"]) else "شاغر متاح", "people", info_font)
    info_box(draw, (425, box_y1, 655, box_y2), "دوام حسب الإعلان", "briefcase", info_font)
    info_box(draw, (185, box_y1, 415, box_y2), "التقديم متاح الآن", "apply", info_font)

    # Strong gold CTA bar.
    draw.rounded_rectangle((270, 565, 1135, 620), radius=17, fill=GOLD)
    draw_ar(draw, (1090, 593), "التفاصيل وطريقة التقديم داخل المقال", cta_font, INK, anchor="rm")

    img.save(path, format="PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"
