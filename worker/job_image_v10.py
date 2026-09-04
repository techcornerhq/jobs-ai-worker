from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from company_visual import fetch_official_photo

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH, HEIGHT = 1536, 1024
IMAGE_VERSION = "v10"
HAS_RAQM = bool(features.check_feature("raqm"))

NAVY = (2, 31, 59)
INK = (2, 43, 82)
GOLD = (250, 186, 60)
RED = (226, 24, 48)
WHITE = (255, 255, 255)
PALE = (238, 244, 249)
PALE2 = (246, 249, 252)
MUTED = (78, 98, 119)

_ALLOWED = re.compile(r"[^\u0600-\u06FFA-Za-z0-9\s.,:؛،()/%+\-]", re.UNICODE)


def clean(value: str) -> str:
    s = str(value or "")
    s = s.replace("–", "-").replace("—", "-").replace("|", " - ")
    s = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]", "", s)
    s = _ALLOWED.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def afont(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in names:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def lfont(size: int, bold: bool = False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size=size) if Path(p).exists() else ImageFont.load_default()


def ar_kwargs():
    return {"direction": "rtl", "language": "ar"} if HAS_RAQM else {}


def ar(draw, xy, text, font, fill, anchor="ra"):
    draw.text(xy, clean(text), font=font, fill=fill, anchor=anchor, **ar_kwargs())


def measure(draw, text, font):
    b = draw.textbbox((0, 0), clean(text), font=font, **ar_kwargs())
    return b[2] - b[0]


def fit(draw, text, start, minimum, width, bold=True):
    for size in range(start, minimum - 1, -2):
        f = afont(size, bold)
        if measure(draw, text, f) <= width:
            return f
    return afont(minimum, bold)


def wrap(draw, text, font, width, max_lines=2):
    words = clean(text).split()
    if not words:
        return []
    lines, current = [], []
    i = 0
    while i < len(words):
        word = words[i]
        trial = " ".join(current + [word])
        if not current or measure(draw, trial, font) <= width:
            current.append(word)
            i += 1
            continue
        lines.append(" ".join(current))
        current = []
        if len(lines) >= max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    consumed = sum(len(x.split()) for x in lines)
    if consumed < len(words) and lines:
        # keep truncation clean and predictable; no unsupported ellipsis glyph.
        lines[-1] = lines[-1].rstrip("،.- ")
    return lines


def display_employer(value: str) -> str:
    e = clean(value)
    if "المناصير" in e or "العاديات السريعة" in e:
        return "مجموعة المناصير"
    if "زين" in e or re.search(r"\bZain\b", e, re.I):
        return "زين الأردن"
    if "العميد" in e or re.search(r"\bAlameed\b", e, re.I):
        return "بن العميد"
    e = re.sub(r"\s*\([^)]*\)\s*", " ", e)
    e = re.sub(r"^(?:شركة|مؤسسة)\s+", "", e).strip()
    return clean(e)[:38] or "جهة توظيف"


def arabic_job_phrase(value: str) -> str:
    s = clean(value)
    replacements = [
        (r"Integration\s+Developer(?:\s+Team\s+Member)?", "مطور تكامل أنظمة"),
        (r"Software\s+Engineer", "مهندس برمجيات"),
        (r"Team\s+Member", ""),
        (r"Developer", "مطور برمجيات"),
        (r"Engineer", "مهندس"),
    ]
    for pattern, repl in replacements:
        s = re.sub(pattern, repl, s, flags=re.I)
    return clean(s)


def salary_from(*texts: str):
    for raw in texts:
        t = clean(raw)
        m = re.search(r"(\d{2,4})\s*(?:إلى|الى|-)\s*(\d{2,4})\s*دينار", t)
        if m:
            return f"رواتب متوقعة من {m.group(1)} إلى {m.group(2)} دينار"
        m = re.search(r"(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار", t)
        if m:
            return f"راتب متوقع حتى {m.group(1)} دينار"
    return None


def short_job_line(job: dict, title: str, employer: str) -> str:
    jt = arabic_job_phrase(job.get("job_title") or "")
    source = arabic_job_phrase(title)
    emp = display_employer(employer)
    if "زين" in emp:
        return "مطور تكامل أنظمة في عمان"
    if "العميد" in emp:
        return "فرص عمل متنوعة في عمان"
    if "المناصير" in emp:
        return "تخصصات فنية وهندسة ميكانيكية"
    if jt and jt != "غير مذكور في الإعلان":
        return jt[:62]
    source = re.sub(r"\s*[-:]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?.*$", "", source).strip(" :-")
    for token in [emp, clean(employer)]:
        if token and token in source:
            source = source.replace(token, "", 1).strip(" :-")
    source = re.sub(r"^(?:تعلن عن|تعلن|تفتح باب التوظيف|تطلب موظفين|توظف)\s*", "", source).strip()
    return (source or "فرص عمل جديدة")[:70]


def location(job: dict) -> str:
    x = clean(job.get("location_text") or "الأردن")
    x = x.replace("الأردن - ", "").replace("- الأردن", "").strip()
    return x or "الأردن"


def departments(job: dict, title: str) -> str:
    t = " ".join([arabic_job_phrase(title), arabic_job_phrase(job.get("job_title") or "")])
    if any(x in t for x in ["تكامل", "مطور", "برمج", "تقنية", "IT"]):
        return "التخصص: تطوير وتكامل الأنظمة التقنية"
    if any(x in t for x in ["صيانة", "ميكاني", "كهرب", "حدادة", "دهان", "بودي"]):
        return "التخصصات: صيانة، ميكانيك، كهرباء، حدادة، هندسة ميكانيكية"
    if any(x in t for x in ["مبيعات", "خدمة عملاء", "إدارية", "تشغيلية", "متنوعة"]):
        return "الأقسام: إدارية، تقنية، تشغيلية، مبيعات، خدمة عملاء"
    return "التخصصات والتفاصيل موضحة داخل الإعلان"


def category(job: dict, title: str) -> str:
    t = " ".join([clean(title), clean(job.get("job_title") or ""), clean(job.get("employer_name") or "")]).lower()
    if any(x in t for x in ["قهوة", "coffee", "العميد", "barista", "مطعم", "restaurant", "مبيعات"]):
        return "retail"
    if any(x in t for x in ["صيانة", "ميكاني", "كهرب", "حدادة", "دهان", "بودي", "آليات", "mechanic", "engineer"]):
        return "mechanical"
    if any(x in t for x in ["مطور", "برمج", "تكامل", "developer", "software", "تقنية", "it "]):
        return "tech"
    if any(x in t for x in ["تمريض", "طبيب", "صيدل", "medical", "health"]):
        return "health"
    return "office"


def category_visual(kind: str) -> Image.Image:
    """Text-free deterministic fallback artwork. Never depends on remote images."""
    w, h = 720, 860
    img = Image.new("RGB", (w, h), (15, 36, 57))
    d = ImageDraw.Draw(img)
    if kind == "mechanical":
        d.rectangle((0, 0, w, h), fill=(28, 43, 50))
        d.rectangle((0, 590, w, h), fill=(17, 27, 34))
        # machinery body
        d.rounded_rectangle((70, 470, 650, 660), radius=35, fill=(210, 151, 38))
        d.ellipse((80, 615, 240, 775), fill=(23, 28, 31))
        d.ellipse((480, 615, 640, 775), fill=(23, 28, 31))
        d.rectangle((300, 310, 560, 500), fill=(232, 178, 65))
        d.rectangle((350, 340, 525, 435), fill=(72, 103, 119))
        # wrench motif
        d.line((120, 170, 300, 350), fill=(225, 231, 235), width=32)
        d.ellipse((80, 120, 175, 215), outline=(225, 231, 235), width=24)
    elif kind == "retail":
        d.rectangle((0, 0, w, h), fill=(32, 24, 19))
        d.rectangle((0, 560, w, h), fill=(56, 35, 24))
        # warm storefront shelves
        for y in [170, 310, 450]:
            d.rectangle((70, y, 650, y+16), fill=(216, 166, 91))
            for x in range(105, 620, 105):
                d.rounded_rectangle((x, y-75, x+52, y-10), radius=8, fill=(114, 72, 45))
        # counter and cups
        d.rectangle((70, 620, 650, 720), fill=(95, 56, 35))
        for x in [180, 330, 480]:
            d.rounded_rectangle((x, 530, x+85, 620), radius=12, fill=(229, 220, 198))
    elif kind == "health":
        d.rectangle((0, 0, w, h), fill=(223, 242, 246))
        d.rectangle((0, 570, w, h), fill=(196, 228, 234))
        d.rounded_rectangle((105, 150, 615, 590), radius=35, fill=(247, 252, 253))
        d.rectangle((305, 245, 415, 495), fill=(44, 142, 158))
        d.rectangle((235, 315, 485, 425), fill=(44, 142, 158))
    else:
        # office / tech visual
        d.rectangle((0, 0, w, h), fill=(194, 222, 244))
        for x, bh in [(40, 360), (145, 470), (260, 390), (380, 530), (520, 430), (625, 500)]:
            d.rectangle((x, 560-bh, x+70, 560), fill=(85, 133, 176))
            for yy in range(120, 540, 55):
                if yy < 560-bh:
                    continue
                d.rectangle((x+15, yy, x+30, yy+20), fill=(210, 232, 247))
                d.rectangle((x+43, yy, x+58, yy+20), fill=(210, 232, 247))
        d.rectangle((0, 560, w, h), fill=(232, 239, 245))
        # desk, laptop, plant
        d.rectangle((65, 705, 650, 735), fill=(86, 101, 115))
        d.polygon([(175, 535), (455, 535), (420, 690), (210, 690)], fill=(43, 63, 82))
        d.rectangle((240, 565, 390, 650), fill=(83, 119, 151))
        d.rectangle((500, 610, 540, 705), fill=(81, 110, 62))
        d.ellipse((465, 560, 535, 640), fill=(90, 137, 76))
        d.ellipse((515, 545, 590, 630), fill=(80, 126, 67))
    return img


def trusted_photo(job: dict, title: str) -> Image.Image:
    """Use remote official imagery only where it has proven reliable; otherwise deterministic category art."""
    emp = display_employer(job.get("employer_name") or "")
    if "زين" in emp:
        try:
            photo = fetch_official_photo(job)
            if photo is not None and photo.width >= 650 and photo.height >= 380:
                return photo
        except Exception:
            pass
    return category_visual(category(job, title))


def crop_photo(photo: Image.Image, size=(610, 798)) -> Image.Image:
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    return ImageOps.fit(photo, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def icon(draw, cx, cy, kind):
    if kind == "pin":
        draw.ellipse((cx-15, cy-18, cx+15, cy+12), fill=INK)
        draw.polygon([(cx, cy+27), (cx-12, cy+7), (cx+12, cy+7)], fill=INK)
        draw.ellipse((cx-5, cy-7, cx+5, cy+3), fill=WHITE)
    elif kind == "briefcase":
        draw.rounded_rectangle((cx-23, cy-8, cx+23, cy+21), radius=5, fill=INK)
        draw.rectangle((cx-9, cy-17, cx+9, cy-8), fill=INK)
        draw.line((cx-23, cy+3, cx+23, cy+3), fill=WHITE, width=2)
    else:
        draw.ellipse((cx-19, cy-14, cx-3, cy+2), fill=INK)
        draw.ellipse((cx+3, cy-14, cx+19, cy+2), fill=INK)
        draw.rounded_rectangle((cx-25, cy+5, cx+25, cy+20), radius=7, fill=INK)


def card(draw, box, kind, label, value):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=PALE)
    cx = (x1+x2)//2
    icon(draw, cx, y1+34, kind)
    ar(draw, (cx, y1+82), label, afont(19, True), INK, "mm")
    value = clean(value)
    vf = fit(draw, value, 24, 17, x2-x1-24, True)
    lines = wrap(draw, value, vf, x2-x1-24, 2)
    if not lines:
        lines = ["غير مذكور"]
    start_y = y1 + 126 if len(lines) == 1 else y1 + 116
    for i, line in enumerate(lines):
        ar(draw, (cx, start_y + i*31), line, vf, INK, "mm")


def globe(draw, cx, cy):
    draw.ellipse((cx-21, cy-21, cx+21, cy+21), outline=WHITE, width=3)
    draw.ellipse((cx-9, cy-21, cx+9, cy+21), outline=WHITE, width=2)
    draw.line((cx-20, cy, cx+20, cy), fill=WHITE, width=2)


def count_value(title: str) -> str:
    t = clean(title)
    m = re.search(r"\b(\d{1,2})\s*(?:شاغر|شواغر|فرصة|وظيفة)", t)
    if m:
        return f"{m.group(1)} شاغر"
    if any(x in t for x in ["متنوعة", "عدة", "فرص", "وظائف", "شواغر"]):
        return "عدة وظائف"
    return "شاغر متاح"


def generate(job: dict, title: str):
    campaign_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job.get("campaign_id") or "job"))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{campaign_id}-{IMAGE_VERSION}.png"

    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    header_h, footer_h, left_w = 132, 94, 610
    content_bottom = HEIGHT - footer_h
    draw.rectangle((0, 0, WIDTH, header_h), fill=NAVY)
    draw.rectangle((0, content_bottom, WIDTH, HEIGHT), fill=NAVY)

    employer_raw = clean(job.get("employer_name") or "جهة توظيف")
    emp = display_employer(employer_raw)
    photo = crop_photo(trusted_photo(job, title), (left_w, content_bottom-header_h))
    img.paste(photo, (0, header_h))

    # Fixed clean divide: no gradient overlap and no text may cross x=650.
    draw.rectangle((left_w, header_h, WIDTH, content_bottom), fill=WHITE)

    # Header brand
    ar(draw, (470, 52), "وظائف الأردن", afont(38, True), WHITE)
    ar(draw, (470, 94), "أكبر منصة للوظائف في الأردن", afont(17), WHITE)
    fx, fy = 500, 31
    draw.rounded_rectangle((fx, fy, fx+62, fy+57), radius=6, fill=WHITE)
    draw.rectangle((fx+3, fy+3, fx+59, fy+20), fill=(0,0,0))
    draw.rectangle((fx+3, fy+20, fx+59, fy+38), fill=WHITE)
    draw.rectangle((fx+3, fy+38, fx+59, fy+54), fill=(0,122,61))
    draw.polygon([(fx+3,fy+3),(fx+3,fy+54),(fx+31,fy+28)], fill=(206,17,38))

    draw.rounded_rectangle((860, 18, 1485, 112), radius=24, fill=GOLD)
    ar(draw, (1380, 65), "إعلان توظيف جديد", afont(41, True), INK, "rm")
    draw.polygon([(1430,51),(1460,41),(1460,77),(1430,67)], fill=INK)

    # Right content uses strict safe zone x=650..1490.
    safe_right = 1470
    safe_width = 760
    emp_f = fit(draw, emp, 68, 42, safe_width, True)
    ar(draw, (safe_right, 208), emp, emp_f, INK)

    job_line = short_job_line(job, title, employer_raw)
    jf = fit(draw, job_line, 42, 27, safe_width, True)
    job_lines = wrap(draw, job_line, jf, safe_width, 2)
    y0 = 306
    for i, line in enumerate(job_lines):
        ar(draw, (safe_right, y0 + i*48), line, jf, INK)

    sal = salary_from(title, job.get("title") or "")
    sal_text = sal or "الراتب حسب الإعلان"
    draw.rounded_rectangle((650, 404, 1468, 484), radius=21, fill=GOLD)
    sf = fit(draw, sal_text, 38, 27, 760, True)
    ar(draw, (1058, 444), sal_text, sf, (0,0,0), "mm")

    sal_card = re.sub(r"^(?:رواتب متوقعة من|راتب متوقع)\s*", "", sal_text) if sal else "غير مذكور"
    employment = clean(job.get("employment_type") or "")
    if not employment or employment == "غير مذكور في الإعلان":
        employment = "حسب الإعلان"
    values = [
        ("people", "الراتب المتوقع", sal_card),
        ("briefcase", "نوع الوظيفة", employment),
        ("pin", "مكان العمل", location(job)),
        ("people", "عدد الشواغر", count_value(title)),
    ]
    starts = [1280, 1048, 816, 584]
    for sx, data in zip(starts, values):
        card(draw, (sx, 512, sx+214, 682), *data)

    dep = departments(job, title)
    draw.rounded_rectangle((530, 702, 1493, 766), radius=15, fill=PALE2)
    df = fit(draw, dep, 25, 18, 820, True)
    ar(draw, (1395, 734), dep, df, INK, "rm")
    draw.ellipse((1436, 716, 1472, 752), fill=INK)
    draw.ellipse((1448, 728, 1460, 740), fill=WHITE)

    draw.rounded_rectangle((500, 790, 1452, 890), radius=24, fill=RED)
    cta = "التفاصيل وطريقة التقديم داخل المقال"
    cf = fit(draw, cta, 38, 30, 760, True)
    ar(draw, (1245, 840), cta, cf, WHITE, "rm")
    draw.ellipse((1325, 810, 1385, 870), fill=WHITE)
    draw.line((1345,840,1364,840), fill=RED, width=6)
    draw.line((1354,831,1364,840), fill=RED, width=6)
    draw.line((1354,849,1364,840), fill=RED, width=6)

    # Footer: Latin URL + Arabic message, vector icons only.
    globe(draw, 70, 975)
    draw.text((110, 975), "jobsinjordan2026.blogspot.com", font=lfont(26, True), fill=WHITE, anchor="lm")
    draw.line((675, 947, 675, 1000), fill=(205,220,232), width=2)
    ar(draw, (1060, 975), "تابعنا لمزيد من فرص العمل في الأردن", afont(22), WHITE, "rm")
    for i, label in enumerate(["F", "IG", "IN", "TG"]):
        cx = 1255 + i*68
        draw.ellipse((cx, 951, cx+44, 995), fill=WHITE)
        draw.text((cx+22, 973), label, font=lfont(12 if len(label)>1 else 16, True), fill=INK, anchor="mm")

    img.save(path, format="PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"
