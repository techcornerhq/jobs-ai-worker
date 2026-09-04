from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from company_visual import fetch_official_photo, normalized_employer

IMAGE_DIR = Path('data/images')
RAW_BASE = 'https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images'
WIDTH, HEIGHT = 1536, 1024
IMAGE_VERSION = 'v11'
HAS_RAQM = bool(features.check_feature('raqm'))

NAVY = (2, 31, 59)
NAVY2 = (7, 48, 86)
INK = (5, 45, 82)
GOLD = (250, 186, 60)
RED = (229, 27, 51)
WHITE = (255, 255, 255)
PALE = (237, 244, 250)
PALE2 = (247, 250, 253)
MUTED = (82, 102, 121)
LINE = (218, 228, 237)

_ALLOWED = re.compile(r'[^\u0600-\u06FFA-Za-z0-9\s.,:؛،()/%+\-]', re.UNICODE)


def clean(value: str) -> str:
    s = str(value or '')
    s = s.replace('–', '-').replace('—', '-').replace('|', ' - ')
    s = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]', '', s)
    s = _ALLOWED.sub(' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def afont(size: int, bold: bool = False):
    candidates = [
        '/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf' if bold else '/usr/share/opentype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def lfont(size: int, bold: bool = False):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size=size) if Path(p).exists() else ImageFont.load_default()


def ar_kwargs():
    return {'direction': 'rtl', 'language': 'ar'} if HAS_RAQM else {}


def draw_ar(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, anchor='ra'):
    draw.text(xy, clean(text), font=font, fill=fill, anchor=anchor, **ar_kwargs())


def width_of(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    b = draw.textbbox((0, 0), clean(text), font=font, **ar_kwargs())
    return max(0, b[2] - b[0])


def fit_font(draw, text: str, start: int, minimum: int, max_width: int, bold=True):
    for size in range(start, minimum - 1, -2):
        f = afont(size, bold)
        if width_of(draw, text, f) <= max_width:
            return f
    return afont(minimum, bold)


def fit_lines(draw, text: str, max_width: int, max_lines: int, start: int, minimum: int, bold=True):
    text = clean(text)
    if not text:
        return afont(minimum, bold), []
    for size in range(start, minimum - 1, -2):
        font = afont(size, bold)
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            trial = ' '.join(current + [word])
            if not current or width_of(draw, trial, font) <= max_width:
                current.append(word)
            else:
                lines.append(' '.join(current))
                current = [word]
                if len(lines) >= max_lines:
                    break
        if len(lines) < max_lines and current:
            lines.append(' '.join(current))
        consumed = sum(len(x.split()) for x in lines)
        if len(lines) <= max_lines and consumed >= len(words) and all(width_of(draw, x, font) <= max_width for x in lines):
            return font, lines
    font = afont(minimum, bold)
    words = text.split()
    lines, current = [], []
    for word in words:
        trial = ' '.join(current + [word])
        if not current or width_of(draw, trial, font) <= max_width:
            current.append(word)
        else:
            if len(lines) >= max_lines - 1:
                break
            lines.append(' '.join(current))
            current = [word]
    if current and len(lines) < max_lines:
        lines.append(' '.join(current))
    return font, lines[:max_lines]


def employer_name(job: dict) -> str:
    e = normalized_employer(job.get('employer_name') or '')
    e = re.sub(r'\s*\([^)]*\)\s*', ' ', e)
    e = re.sub(r'^(?:شركة|مؤسسة)\s+', '', e).strip()
    return clean(e)[:46] or 'جهة توظيف'


def arabic_role(value: str) -> str:
    s = clean(value)
    replacements = [
        (r'Integration\s+Developer(?:\s+Team\s+Member)?', 'مطور تكامل أنظمة'),
        (r'Software\s+Engineer', 'مهندس برمجيات'),
        (r'Data\s+Analyst', 'محلل بيانات'),
        (r'Accountant', 'محاسب'),
        (r'Customer\s+Service', 'خدمة عملاء'),
        (r'Team\s+Member', ''),
        (r'Developer', 'مطور برمجيات'),
        (r'Engineer', 'مهندس'),
    ]
    for pat, repl in replacements:
        s = re.sub(pat, repl, s, flags=re.I)
    return clean(s)


def short_role(job: dict, title: str, employer: str) -> str:
    emp = clean(employer)
    jt = arabic_role(job.get('job_title') or '')
    if 'زين' in emp:
        return 'مطور تكامل أنظمة في عمّان'
    if 'العميد' in emp:
        return 'فرص عمل متنوعة في عمّان'
    if 'المناصير' in emp:
        return 'فرص صيانة وهندسة ميكانيكية'
    if jt and jt != 'غير مذكور في الإعلان':
        return jt[:72]
    source = arabic_role(title)
    source = re.sub(r'\s*[-:]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?.*$', '', source).strip(' :-')
    if emp and emp in source:
        source = source.replace(emp, '', 1).strip(' :-')
    return (source or 'فرصة عمل جديدة')[:76]


def salary_line(job: dict, title: str) -> str:
    candidates = [title, job.get('title') or '', job.get('salary_text') or '']
    for raw in candidates:
        t = clean(raw)
        m = re.search(r'(\d{2,4})\s*(?:إلى|الى|-)\s*(\d{2,4})\s*دينار', t)
        if m:
            return f'رواتب متوقعة من {m.group(1)} إلى {m.group(2)} دينار'
        m = re.search(r'(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار', t)
        if m:
            return f'راتب متوقع حتى {m.group(1)} دينار'
    official = clean(job.get('salary') or '')
    if official and official != 'غير مذكور في الإعلان':
        return official[:52]
    return 'الراتب يحدد حسب الوظيفة والخبرة'


def loc_line(job: dict) -> str:
    x = clean(job.get('location_text') or 'الأردن')
    x = x.replace('الأردن - ', '').replace('- الأردن', '').strip()
    return x or 'الأردن'


def count_line(job: dict, title: str) -> str:
    for raw in [job.get('vacancy_count'), title, job.get('title')]:
        t = clean(raw or '')
        if t.isdigit():
            return f'{t} شاغر'
        m = re.search(r'(?<!\d)(\d{1,3})\s*(?:شاغر|شواغر|فرصة|وظيفة)', t)
        if m:
            return f'{m.group(1)} شاغر'
    return 'عدة وظائف' if any(x in clean(title) for x in ['وظائف', 'شواغر', 'فرص']) else 'شاغر متاح'


def employment_line(job: dict) -> str:
    x = clean(job.get('employment_type') or '')
    return x if x and x != 'غير مذكور في الإعلان' else 'حسب الإعلان'


def specialty_line(job: dict, title: str) -> str:
    t = ' '.join([arabic_role(title), arabic_role(job.get('job_title') or '')])
    if any(x in t for x in ['تكامل', 'مطور', 'برمج', 'تقنية']):
        return 'التخصص: تطوير وتكامل الأنظمة التقنية'
    if any(x in t for x in ['صيانة', 'ميكاني', 'كهرب', 'حدادة', 'دهان', 'آليات']):
        return 'التخصصات: صيانة، ميكانيك، كهرباء، حدادة، هندسة ميكانيكية'
    if any(x in t for x in ['مبيعات', 'خدمة عملاء', 'إدارية', 'تشغيلية', 'متنوعة']):
        return 'الأقسام: إدارية، تقنية، تشغيلية، مبيعات، خدمة عملاء'
    return 'التخصصات والتفاصيل موضحة داخل الإعلان'


def category(job: dict, title: str) -> str:
    t = ' '.join([clean(title), clean(job.get('job_title') or ''), employer_name(job)]).lower()
    if any(x in t for x in ['قهوة', 'coffee', 'العميد', 'barista', 'مطعم', 'مبيعات', 'متجر']):
        return 'retail'
    if any(x in t for x in ['صيانة', 'ميكاني', 'كهرب', 'حدادة', 'دهان', 'آليات', 'mechanic']):
        return 'mechanical'
    if any(x in t for x in ['مطور', 'برمج', 'تكامل', 'developer', 'software', 'تقنية', ' it ']):
        return 'tech'
    if any(x in t for x in ['تمريض', 'طبيب', 'صيدل', 'medical', 'health']):
        return 'health'
    return 'office'


def _monogram(employer: str) -> str:
    words = [w for w in clean(employer).split() if w not in {'شركة', 'مجموعة', 'مؤسسة'}]
    if not words:
        return 'و'
    return ''.join(w[0] for w in words[:2])


def fallback_visual(kind: str, employer: str) -> Image.Image:
    w, h = 610, 786
    img = Image.new('RGB', (w, h), NAVY)
    d = ImageDraw.Draw(img)
    # Layered geometric background: deliberately graphic, never pretending to be a photo.
    d.rectangle((0, 0, w, h), fill=NAVY)
    for i in range(7):
        pad = 32 + i * 18
        tone = (7 + i * 3, 48 + i * 4, 86 + i * 5)
        d.rounded_rectangle((pad, 70 + i * 18, w - pad, h - 70 - i * 12), radius=34, outline=tone, width=3)
    d.ellipse((120, 118, 490, 488), fill=(10, 58, 99), outline=GOLD, width=7)

    # Category icon made only from shapes so fonts/emoji can never break.
    cx, cy = 305, 305
    if kind == 'tech':
        d.rounded_rectangle((190, 205, 420, 385), radius=22, outline=WHITE, width=12)
        d.line((250, 410, 360, 410), fill=WHITE, width=12)
        d.line((305, 385, 305, 410), fill=WHITE, width=12)
        d.line((245, 275, 205, 315, 245, 355), fill=GOLD, width=12, joint='curve')
        d.line((365, 275, 405, 315, 365, 355), fill=GOLD, width=12, joint='curve')
    elif kind == 'mechanical':
        d.ellipse((215, 215, 395, 395), outline=WHITE, width=14)
        d.ellipse((268, 268, 342, 342), outline=GOLD, width=13)
        for ang in range(0, 360, 45):
            x1 = cx + int(math.cos(math.radians(ang)) * 92)
            y1 = cy + int(math.sin(math.radians(ang)) * 92)
            x2 = cx + int(math.cos(math.radians(ang)) * 125)
            y2 = cy + int(math.sin(math.radians(ang)) * 125)
            d.line((x1, y1, x2, y2), fill=WHITE, width=14)
    elif kind == 'health':
        d.rounded_rectangle((260, 190, 350, 420), radius=14, fill=WHITE)
        d.rounded_rectangle((190, 260, 420, 350), radius=14, fill=WHITE)
        d.rounded_rectangle((278, 208, 332, 402), radius=8, fill=GOLD)
        d.rounded_rectangle((208, 278, 402, 332), radius=8, fill=GOLD)
    elif kind == 'retail':
        d.rounded_rectangle((205, 235, 405, 395), radius=24, outline=WHITE, width=12)
        d.line((235, 235, 250, 190, 360, 190, 375, 235), fill=GOLD, width=12)
        d.line((240, 285, 370, 285), fill=WHITE, width=10)
        d.line((240, 335, 370, 335), fill=WHITE, width=10)
    else:
        d.rounded_rectangle((205, 235, 405, 390), radius=20, outline=WHITE, width=12)
        d.rectangle((260, 195, 350, 245), outline=GOLD, width=12)
        d.line((205, 300, 405, 300), fill=GOLD, width=10)

    mono = _monogram(employer)
    mf = fit_font(d, mono, 82, 50, 300, True)
    draw_ar(d, (305, 575), mono, mf, GOLD, anchor='mm')
    sf = afont(24, True)
    draw_ar(d, (305, 652), 'هوية بصرية بديلة موثوقة', sf, WHITE, anchor='mm')
    df = afont(18, False)
    draw_ar(d, (305, 704), 'تستخدم عند تعذر صورة رسمية مناسبة', df, (196, 213, 228), anchor='mm')
    return img


def visual(job: dict, title: str, employer: str) -> tuple[Image.Image, str]:
    photo = fetch_official_photo({**job, 'employer_name': employer})
    if photo is not None:
        return ImageOps.fit(photo.convert('RGB'), (610, 786), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)), 'official_photo'
    return fallback_visual(category(job, title), employer), 'designed_fallback'


def draw_flag(d: ImageDraw.ImageDraw, x: int, y: int):
    d.rounded_rectangle((x, y, x + 60, y + 42), radius=5, fill=WHITE)
    d.rectangle((x + 3, y + 3, x + 57, y + 15), fill=(0, 122, 61))
    d.rectangle((x + 3, y + 15, x + 57, y + 28), fill=WHITE)
    d.rectangle((x + 3, y + 28, x + 57, y + 39), fill=(0, 0, 0))
    d.polygon([(x + 3, y + 3), (x + 30, y + 21), (x + 3, y + 39)], fill=(206, 17, 38))


def draw_info_card(d, box, label: str, value: str):
    x1, y1, x2, y2 = box
    d.rounded_rectangle(box, radius=22, fill=PALE, outline=LINE, width=2)
    # icon: three simple dots + base, guaranteed to render.
    cx = (x1 + x2) // 2
    d.ellipse((cx - 9, y1 + 22, cx + 9, y1 + 40), fill=INK)
    d.ellipse((cx - 28, y1 + 31, cx - 12, y1 + 47), fill=INK)
    d.ellipse((cx + 12, y1 + 31, cx + 28, y1 + 47), fill=INK)
    d.rounded_rectangle((cx - 38, y1 + 48, cx + 38, y1 + 62), radius=7, fill=INK)
    lf = fit_font(d, label, 22, 16, x2 - x1 - 20, True)
    draw_ar(d, (cx, y1 + 92), label, lf, INK, anchor='mm')
    vf, lines = fit_lines(d, value, x2 - x1 - 22, 2, 24, 17, True)
    if not lines:
        lines = ['غير مذكور']
    y = y1 + 135
    for line in lines[:2]:
        draw_ar(d, (cx, y), line, vf, INK, anchor='mm')
        y += int(vf.size * 1.45)


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    campaign_id = clean(job.get('campaign_id') or 'job').replace(' ', '-')[:48]
    filename = f'{campaign_id}-{IMAGE_VERSION}.png'
    path = IMAGE_DIR / filename

    img = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    d = ImageDraw.Draw(img)

    # Header, body and footer are strict non-overlapping bands.
    header_h, footer_h = 132, 106
    body_top, body_bottom = header_h, HEIGHT - footer_h
    left_w = 610
    d.rectangle((0, 0, WIDTH, header_h), fill=NAVY)
    d.rectangle((0, body_top, WIDTH, body_bottom), fill=WHITE)
    d.rectangle((0, body_bottom, WIDTH, HEIGHT), fill=NAVY)

    employer = employer_name(job)
    role = short_role(job, title, employer)
    salary = salary_line(job, title)
    loc = loc_line(job)
    visual_img, visual_kind = visual(job, title, employer)
    img.paste(visual_img, (0, body_top))
    d = ImageDraw.Draw(img)

    # Header brand
    draw_flag(d, 520, 45)
    bf = afont(31, True)
    draw_ar(d, (455, 58), 'وظائف الأردن', bf, WHITE, anchor='ra')
    sf = afont(14, False)
    draw_ar(d, (455, 95), 'فرص عمل يومية في الأردن', sf, (202, 217, 230), anchor='ra')
    d.rounded_rectangle((905, 26, 1504, 108), radius=24, fill=GOLD)
    af = afont(34, True)
    draw_ar(d, (1455, 66), 'إعلان توظيف جديد', af, NAVY, anchor='ra')
    d.polygon([(936, 50), (970, 66), (936, 82)], fill=NAVY)

    # Right content region
    rx1, rx2 = 650, 1490
    maxw = rx2 - rx1 - 35

    ef = fit_font(d, employer, 62, 38, maxw, True)
    draw_ar(d, (rx2, 210), employer, ef, INK, anchor='ra')

    rf, rlines = fit_lines(d, role, maxw, 2, 34, 24, True)
    y = 278
    for line in rlines[:2]:
        draw_ar(d, (rx2, y), line, rf, INK, anchor='ra')
        y += int(rf.size * 1.45)

    # Salary banner is fixed and cannot collide with title.
    d.rounded_rectangle((rx1, 370, rx2, 448), radius=22, fill=GOLD)
    salf = fit_font(d, salary, 34, 23, maxw - 40, True)
    draw_ar(d, ((rx1 + rx2) // 2, 409), salary, salf, (15, 25, 32), anchor='mm')

    # Four fixed info cards.
    gap = 12
    card_w = (rx2 - rx1 - gap * 3) // 4
    cards = [
        ('الراتب', salary.replace('رواتب متوقعة ', '').replace('راتب متوقع ', '')),
        ('نوع الوظيفة', employment_line(job)),
        ('مكان العمل', loc),
        ('عدد الشواغر', count_line(job, title)),
    ]
    for i, (label, value) in enumerate(cards):
        x1 = rx1 + i * (card_w + gap)
        draw_info_card(d, (x1, 470, x1 + card_w, 655), label, value)

    # Specialty strip.
    d.rounded_rectangle((rx1, 680, rx2, 738), radius=18, fill=PALE2, outline=LINE, width=2)
    dep = specialty_line(job, title)
    depf = fit_font(d, dep, 24, 17, maxw - 55, True)
    draw_ar(d, (rx2 - 24, 709), dep, depf, INK, anchor='ra')
    d.ellipse((rx1 + 18, 694, rx1 + 48, 724), fill=INK)
    d.ellipse((rx1 + 29, 705, rx1 + 37, 713), fill=WHITE)

    # CTA is always above footer and separated from every other band.
    d.rounded_rectangle((rx1, 764, rx2, 858), radius=25, fill=RED)
    ctaf = fit_font(d, 'التفاصيل وطريقة التقديم داخل المقال', 34, 25, maxw - 120, True)
    draw_ar(d, ((rx1 + rx2) // 2 + 30, 811), 'التفاصيل وطريقة التقديم داخل المقال', ctaf, WHITE, anchor='mm')
    d.ellipse((rx2 - 90, 782, rx2 - 34, 838), fill=WHITE)
    d.line((rx2 - 68, 810, rx2 - 51, 810), fill=RED, width=7)
    d.line((rx2 - 58, 800, rx2 - 48, 810, rx2 - 58, 820), fill=RED, width=7, joint='curve')

    # Footer: Latin URL uses Latin font, no Arabic shaping.
    d.ellipse((42, body_bottom + 27, 78, body_bottom + 63), outline=WHITE, width=3)
    d.line((60, body_bottom + 29, 60, body_bottom + 61), fill=WHITE, width=2)
    d.line((45, body_bottom + 45, 75, body_bottom + 45), fill=WHITE, width=2)
    d.text((90, body_bottom + 49), 'jobsinjordan2026.blogspot.com', font=lfont(25, True), fill=WHITE, anchor='lm')
    draw_ar(d, (1010, body_bottom + 49), 'تابعنا لمزيد من فرص العمل في الأردن', afont(18, False), (208, 222, 233), anchor='mm')
    for i, label in enumerate(['F', 'IG', 'IN', 'TG']):
        cx = 1280 + i * 68
        d.ellipse((cx - 21, body_bottom + 28, cx + 21, body_bottom + 70), fill=WHITE)
        d.text((cx, body_bottom + 49), label, font=lfont(10, True), fill=NAVY, anchor='mm')

    # Tiny internal provenance marker outside visible content semantics; helps automated QA.
    d.text((1495, 1005), visual_kind, font=lfont(5, False), fill=NAVY, anchor='rb')

    img.save(path, format='PNG', optimize=True)
    return str(path), f'{RAW_BASE}/{filename}'
