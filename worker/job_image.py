from __future__ import annotations

import io
import re
from pathlib import Path
from urllib.parse import urljoin

import arabic_reshaper
import requests
from bs4 import BeautifulSoup
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, features

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH = 1536
HEIGHT = 1024
IMAGE_VERSION = "v5"
HAS_RAQM = bool(features.check_feature("raqm"))

NAVY = (3, 40, 75)
NAVY_DARK = (2, 31, 59)
NAVY_TEXT = (2, 43, 82)
GOLD = (250, 186, 60)
GOLD_DARK = (214, 142, 25)
RED = (226, 24, 48)
WHITE = (255, 255, 255)
PALE = (244, 248, 252)
PALE_2 = (238, 244, 249)
MUTED = (101, 115, 132)

UA = "Mozilla/5.0 (compatible; JordanJobsImageBot/2.0; +https://jobsinjordan2026.blogspot.com/)"


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
        "/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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


def draw_ar(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, anchor: str = "ra") -> None:
    draw.text(xy, prepared(text), font=fnt, fill=fill, anchor=anchor, **text_kwargs())


def measure(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    b = draw.textbbox((0, 0), prepared(text), font=fnt, **text_kwargs())
    return b[2] - b[0]


def fit_font(draw: ImageDraw.ImageDraw, text: str, start: int, min_size: int, max_width: int, bold: bool = True):
    for size in range(start, min_size - 1, -2):
        f = font(size, bold)
        if measure(draw, text, f) <= max_width:
            return f
    return font(min_size, bold)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 2) -> list[str]:
    words = str(text or "").replace("|", " ").split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        if not current or measure(draw, test, fnt) <= max_width:
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
    m = re.search(r"(?:رواتب?|راتب)[^\d]{0,30}(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})", t, re.I)
    if m:
        return f"رواتب متوقعة {m.group(1)} - {m.group(2)} دينار"
    m = re.search(r"(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})\s*دينار", t, re.I)
    if m:
        return f"رواتب متوقعة {m.group(1)} - {m.group(2)} دينار"
    m = re.search(r"(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار", t, re.I)
    if m:
        return f"راتب متوقع حتى {m.group(1)} دينار"
    return None


def cleaned_headline(title: str, employer: str) -> tuple[str, str]:
    t = str(title or "").strip()
    t = re.sub(r"\s*[|–-]\s*(?:رواتب?|راتب).*?$", "", t).strip()
    # Make the first line the employer, second line the hiring message like the approved master.
    short_emp = employer.replace(" (Zain Jordan)", "").replace("– مجموعة المناصير", "").strip()
    if len(short_emp) > 30:
        short_emp = short_emp.split("–")[0].strip()
    if short_emp and short_emp in t:
        rest = t.replace(short_emp, "", 1).strip(" :|-–")
    else:
        rest = t
    if not rest:
        rest = "تعلن عن فرص عمل جديدة"
    rest = re.sub(r"^(?:تعلن|تعلن عن|تفتح باب التوظيف|توظف)\s*", "", rest).strip()
    if not rest.startswith(("عن ", "فرص", "وظائف", "مطلوب", "شواغر")):
        rest = "عن " + rest
    return short_emp or "جهة توظيف", rest


def department_line(title: str) -> str:
    t = str(title or "")
    if any(x in t for x in ["Developer", "تقنية", "برمج", "IT", "تكامل"]):
        return "في عدة أقسام (تقنية – تطوير – دعم – عمليات – وغيرها)"
    if any(x in t for x in ["صيانة", "ميكاني", "كهرب", "حدادة", "دهان", "بودي"]):
        return "في عدة تخصصات (صيانة – ميكانيك – كهرباء – حدادة – وغيرها)"
    return "في عدة أقسام (إدارية – تقنية – تشغيلية – مبيعات – خدمة عملاء)"


def location_label(job: dict) -> str:
    loc = str(job.get("location_text") or "الأردن").strip()
    return loc.replace("الأردن - ", "").replace("– الأردن", "").strip() or "الأردن"


def _candidate_image_urls(page_url: str) -> list[str]:
    try:
        r = requests.get(page_url, timeout=15, headers={"User-Agent": UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []
    out: list[str] = []
    for selector, attr in [
        ("meta[property='og:image']", "content"),
        ("meta[name='twitter:image']", "content"),
        ("link[rel='image_src']", "href"),
    ]:
        el = soup.select_one(selector)
        if el and el.get(attr):
            out.append(urljoin(page_url, el.get(attr)))
    for img in soup.find_all("img", src=True)[:20]:
        src = urljoin(page_url, img.get("src"))
        low = src.lower()
        if any(x in low for x in ["logo", "icon", "sprite", "avatar"]):
            continue
        out.append(src)
    seen = set()
    return [u for u in out if not (u in seen or seen.add(u))]


def fetch_company_photo(job: dict) -> Image.Image | None:
    pages = [job.get("source_original_url"), job.get("application_url")]
    for page in [x for x in pages if x]:
        for url in _candidate_image_urls(str(page))[:8]:
            try:
                rr = requests.get(url, timeout=15, headers={"User-Agent": UA})
                rr.raise_for_status()
                im = Image.open(io.BytesIO(rr.content)).convert("RGB")
                if im.width < 500 or im.height < 300:
                    continue
                return im
            except Exception:
                continue
    return None


def fallback_photo() -> Image.Image:
    im = Image.new("RGB", (620, 810), (31, 41, 51))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 620, 810), fill=(28, 38, 48))
    d.rectangle((0, 505, 620, 810), fill=(18, 27, 34))
    # warm office/store glow
    for i, x in enumerate(range(35, 600, 95)):
        d.rounded_rectangle((x, 160 + (i % 2) * 25, x + 65, 490), radius=9, fill=(65, 69, 66), outline=(202, 170, 111), width=3)
        d.rectangle((x + 10, 210, x + 55, 430), fill=(159, 132, 87))
    d.rectangle((45, 92, 575, 118), fill=(236, 196, 119))
    return im.filter(ImageFilter.GaussianBlur(0.5))


def crop_photo(photo: Image.Image, size=(610, 810)) -> Image.Image:
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    photo = ImageEnhance.Contrast(photo).enhance(1.05)
    photo = ImageEnhance.Color(photo).enhance(0.93)
    return ImageOps.fit(photo, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def circle_icon(draw: ImageDraw.ImageDraw, center: tuple[int, int], kind: str) -> None:
    cx, cy = center
    if kind == "people":
        draw.ellipse((cx-15, cy-17, cx-1, cy-3), fill=NAVY_TEXT)
        draw.ellipse((cx+2, cy-17, cx+16, cy-3), fill=NAVY_TEXT)
        draw.ellipse((cx-7, cy-22, cx+7, cy-8), fill=NAVY_TEXT)
        draw.rounded_rectangle((cx-24, cy, cx+24, cy+18), radius=8, fill=NAVY_TEXT)
    elif kind == "pin":
        draw.ellipse((cx-16, cy-19, cx+16, cy+13), fill=NAVY_TEXT)
        draw.polygon([(cx, cy+29), (cx-13, cy+8), (cx+13, cy+8)], fill=NAVY_TEXT)
        draw.ellipse((cx-5, cy-8, cx+5, cy+2), fill=WHITE)
    elif kind == "briefcase":
        draw.rounded_rectangle((cx-24, cy-8, cx+24, cy+22), radius=5, fill=NAVY_TEXT)
        draw.rectangle((cx-10, cy-18, cx+10, cy-8), fill=NAVY_TEXT)
        draw.line((cx-24, cy+2, cx+24, cy+2), fill=WHITE, width=3)
    else:
        draw.ellipse((cx-22, cy-10, cx-3, cy+9), fill=NAVY_TEXT)
        draw.ellipse((cx-2, cy-18, cx+17, cy+1), fill=NAVY_TEXT)
        draw.ellipse((cx+8, cy-2, cx+27, cy+17), fill=NAVY_TEXT)


def info_card(draw: ImageDraw.ImageDraw, box, icon: str, title: str, value: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, fill=PALE_2)
    cx = (x1+x2)//2
    circle_icon(draw, (cx, y1+43), icon)
    title_f = font(24, True)
    value_f = font(28, True)
    draw_ar(draw, (cx, y1+95), title, title_f, NAVY_TEXT, anchor="mm")
    # allow max two lines
    lines = wrap(draw, value, value_f, x2-x1-32, max_lines=2)
    yy = y1+143
    for line in lines:
        draw_ar(draw, (cx, yy), line, value_f, NAVY_TEXT, anchor="mm")
        yy += 35


def generate(job: dict, title: str) -> tuple[str, str]:
    campaign_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job.get("campaign_id") or "job"))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{campaign_id}-{IMAGE_VERSION}.png"

    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    # MASTER STRUCTURE: identical proportions to the user-approved reference.
    header_h = 132
    footer_h = 94
    left_w = 610
    draw.rectangle((0, 0, WIDTH, header_h), fill=NAVY_DARK)
    draw.rectangle((0, HEIGHT-footer_h, WIDTH, HEIGHT), fill=NAVY_DARK)

    photo = fetch_company_photo(job) or fallback_photo()
    photo = crop_photo(photo, (left_w, HEIGHT-header_h-footer_h))
    img.paste(photo, (0, header_h))

    # soft white fade at the photo/text boundary, matching the approved composition.
    fade = Image.new("L", (180, HEIGHT-header_h-footer_h), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(180):
        fd.line((x, 0, x, fade.height), fill=int(255 * (x/179)))
    white_strip = Image.new("RGB", fade.size, WHITE)
    img.paste(white_strip, (left_w-90, header_h), fade)
    draw = ImageDraw.Draw(img)

    # Header brand block, Jordan flag motif, and gold announcement badge.
    brand_f = font(43, True)
    sub_f = font(20, False)
    draw_ar(draw, (560, 55), "وظائف الأردن", brand_f, WHITE, anchor="ra")
    draw_ar(draw, (555, 98), "أكبر منصة للوظائف في الأردن", sub_f, WHITE, anchor="ra")
    # simple Jordan flag mark
    fx, fy = 585, 32
    draw.rounded_rectangle((fx, fy, fx+62, fy+57), radius=6, fill=WHITE)
    draw.rectangle((fx+3, fy+3, fx+59, fy+20), fill=(0,0,0))
    draw.rectangle((fx+3, fy+20, fx+59, fy+38), fill=WHITE)
    draw.rectangle((fx+3, fy+38, fx+59, fy+54), fill=(0,122,61))
    draw.polygon([(fx+3,fy+3),(fx+3,fy+54),(fx+31,fy+28)], fill=(206,17,38))
    draw.ellipse((fx+12, fy+24, fx+16, fy+28), fill=WHITE)

    badge = (846, 16, 1485, 116)
    draw.rounded_rectangle(badge, radius=26, fill=GOLD)
    badge_f = font(47, True)
    draw_ar(draw, (1395, 66), "إعلان توظيف جديد", badge_f, NAVY_TEXT, anchor="rm")
    # megaphone icon
    draw.polygon([(1430,52),(1460,42),(1460,78),(1430,68)], fill=NAVY_TEXT)
    draw.rectangle((1420,58,1434,66), fill=NAVY_TEXT)

    employer = str(job.get("employer_name") or "جهة توظيف").strip()
    emp, rest = cleaned_headline(title, employer)
    right_x1 = 635
    right_x2 = 1495
    center_x = (right_x1+right_x2)//2

    # Main headline.
    emp_f = fit_font(draw, emp, 82, 54, 790, True)
    draw_ar(draw, (right_x2-25, 210), emp, emp_f, NAVY_TEXT, anchor="ra")
    rest_f = fit_font(draw, rest, 56, 38, 790, True)
    rest_lines = wrap(draw, rest, rest_f, 790, max_lines=2)
    y = 330
    for line in rest_lines:
        draw_ar(draw, (right_x2-25, y), line, rest_f, NAVY_TEXT, anchor="ra")
        y += 62

    salary = extract_salary(title) or extract_salary(str(job.get("title") or ""))
    salary_text = salary or "الراتب يحدد حسب الوظيفة والخبرة"
    draw.rounded_rectangle((640, 414, 1468, 498), radius=24, fill=GOLD)
    salary_f = fit_font(draw, salary_text, 43, 30, 760, True)
    draw_ar(draw, (1055, 456), salary_text, salary_f, (0,0,0), anchor="mm")

    # Four information cards exactly across one row.
    card_y1, card_y2 = 528, 710
    card_w, gap = 214, 18
    starts = [1280, 1048, 816, 584]
    loc = location_label(job)
    official_type = str(job.get("employment_type") or "").strip()
    type_value = "دوام كامل" if "كامل" in official_type else (official_type if official_type else "حسب الإعلان")
    many = "عدة وظائف" if any(x in title for x in ["متنوعة", "فرص", "وظائف", "شواغر", "عدة"]) else "شاغر متاح"
    salary_card = salary.replace("رواتب متوقعة ", "").replace("راتب متوقع ", "") if salary else "حسب الوظيفة والخبرة"
    values = [
        ("coins", "الراتب المتوقع", salary_card),
        ("briefcase", "نوع الوظيفة", type_value),
        ("pin", "مكان العمل", loc),
        ("people", "عدد الشواغر", many),
    ]
    for sx, data in zip(starts, values):
        info_card(draw, (sx, card_y1, sx+card_w, card_y2), *data)

    # Department strip.
    draw.rounded_rectangle((505, 726, 1493, 794), radius=16, fill=PALE)
    dep_f = fit_font(draw, department_line(title), 29, 22, 890, True)
    draw_ar(draw, (1410, 760), department_line(title), dep_f, NAVY_TEXT, anchor="rm")
    # gear visual marker
    draw.ellipse((1430, 741, 1470, 781), fill=NAVY_TEXT)
    draw.ellipse((1443, 754, 1457, 768), fill=WHITE)

    # Red CTA bar.
    draw.rounded_rectangle((468, 812, 1452, 914), radius=25, fill=RED)
    cta_f = font(42, True)
    draw_ar(draw, (1248, 863), "التفاصيل وطريقة التقديم داخل المقال", cta_f, WHITE, anchor="rm")
    draw.ellipse((1320, 831, 1384, 895), fill=WHITE)
    draw.line((1343, 862, 1363, 862), fill=RED, width=6)
    draw.line((1353, 852, 1363, 862), fill=RED, width=6)
    draw.line((1353, 872, 1363, 862), fill=RED, width=6)

    # Footer identical structure: URL left, follow message center/right, social circles.
    url_f = font(29, True)
    follow_f = font(27, False)
    draw.text((54, 974), "◎", font=font(39, True), fill=WHITE, anchor="lm")
    draw.text((102, 974), "jobsinjordan2026.blogspot.com", font=url_f, fill=WHITE, anchor="lm")
    draw.line((680, 946, 680, 1000), fill=(205,220,232), width=2)
    draw_ar(draw, (1075, 974), "تابعنا لمزيد من فرص العمل في الأردن", follow_f, WHITE, anchor="rm")
    for i, label in enumerate(["f", "◎", "in", "➤"]):
        cx = 1272 + i*65
        draw.ellipse((cx, 948, cx+45, 993), fill=WHITE)
        draw.text((cx+22, 970), label, font=font(17, True), fill=NAVY_TEXT, anchor="mm")

    img.save(path, format="PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"
