from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from job_image import fetch_company_photo, crop_photo, fallback_photo

IMAGE_DIR = Path('data/images')
RAW_BASE = 'https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images'
WIDTH, HEIGHT = 1536, 1024
IMAGE_VERSION = 'v6'
HAS_RAQM = bool(features.check_feature('raqm'))

NAVY = (2, 31, 59)
INK = (2, 43, 82)
GOLD = (250, 186, 60)
RED = (226, 24, 48)
WHITE = (255, 255, 255)
PALE = (238, 244, 249)


def afont(size: int, bold: bool = False):
    names = [
        '/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for p in names:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def lfont(size: int, bold: bool = False):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size=size) if Path(p).exists() else ImageFont.load_default()


def kw():
    return {'direction': 'rtl', 'language': 'ar'} if HAS_RAQM else {}


def clean(s: str) -> str:
    s = str(s or '')
    s = s.replace('–', '-').replace('—', '-').replace('|', ' ')
    s = re.sub(r'[\u200b\u200e\u200f\u202a-\u202e]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def ar(draw, xy, text, font, fill, anchor='ra'):
    draw.text(xy, clean(text), font=font, fill=fill, anchor=anchor, **kw())


def measure(draw, text, font):
    b = draw.textbbox((0, 0), clean(text), font=font, **kw())
    return b[2] - b[0]


def fit(draw, text, start, minimum, width):
    for size in range(start, minimum - 1, -2):
        f = afont(size, True)
        if measure(draw, text, f) <= width:
            return f
    return afont(minimum, True)


def wrap(draw, text, font, width, max_lines=2):
    words = clean(text).split()
    lines, current = [], []
    for word in words:
        trial = ' '.join(current + [word])
        if not current or measure(draw, trial, font) <= width:
            current.append(word)
        else:
            lines.append(' '.join(current))
            current = [word]
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(' '.join(current))
    used = sum(len(x.split()) for x in lines)
    if used < len(words) and lines:
        lines[-1] = lines[-1].rstrip('،.- ') + '...'
    return lines


def salary_from(text: str):
    t = str(text or '')
    m = re.search(r'(\d{2,4})\s*(?:إلى|الى|-|–)\s*(\d{2,4})\s*دينار', t)
    if m:
        return f'رواتب متوقعة من {m.group(1)} إلى {m.group(2)} دينار'
    m = re.search(r'(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار', t)
    if m:
        return f'راتب متوقع حتى {m.group(1)} دينار'
    return None


def display_employer(e: str):
    e = clean(e)
    if 'المناصير' in e or 'العاديات السريعة' in e:
        return 'مجموعة المناصير'
    if 'زين' in e or 'Zain' in e:
        return 'زين الأردن'
    if 'العميد' in e or 'Alameed' in e:
        return 'بن العميد'
    return re.sub(r'\s*\([^)]*\)\s*', ' ', e).strip()[:42]


def headline(title: str, employer: str):
    t = clean(title)
    t = re.sub(r'\s*[-:]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?.*$', '', t).strip(' :-')
    emp = display_employer(employer)
    for token in [emp, employer]:
        if token and token in t:
            t = t.replace(token, '', 1).strip(' :-')
            break
    t = re.sub(r'^(?:تعلن عن|تعلن|تفتح باب التوظيف|تطلب موظفين|توظف)\s*', '', t).strip()
    if not t:
        t = 'فرص عمل جديدة'
    if not t.startswith(('فرص', 'وظائف', 'شواغر', 'مطلوب', 'فرصة')):
        t = 'فرص عمل ' + t
    return emp or 'جهة توظيف', t


def location(job):
    x = clean(job.get('location_text') or 'الأردن')
    return x.replace('الأردن - ', '').replace('- الأردن', '').strip() or 'الأردن'


def departments(title):
    t = str(title or '')
    if any(x in t for x in ['Developer', 'تقنية', 'برمج', 'IT', 'تكامل']):
        return 'في عدة أقسام: تقنية، تطوير، دعم، عمليات وغيرها'
    if any(x in t for x in ['صيانة', 'ميكاني', 'كهرب', 'حدادة', 'دهان', 'بودي']):
        return 'في عدة تخصصات: صيانة، ميكانيك، كهرباء، حدادة وغيرها'
    return 'في عدة أقسام: إدارية، تقنية، تشغيلية، مبيعات وخدمة عملاء'


def icon(draw, cx, cy, kind):
    if kind == 'pin':
        draw.ellipse((cx-15, cy-18, cx+15, cy+12), fill=INK)
        draw.polygon([(cx, cy+27), (cx-12, cy+7), (cx+12, cy+7)], fill=INK)
        draw.ellipse((cx-5, cy-7, cx+5, cy+3), fill=WHITE)
    elif kind == 'briefcase':
        draw.rounded_rectangle((cx-23, cy-8, cx+23, cy+21), radius=5, fill=INK)
        draw.rectangle((cx-9, cy-17, cx+9, cy-8), fill=INK)
    else:
        draw.ellipse((cx-20, cy-14, cx-3, cy+3), fill=INK)
        draw.ellipse((cx+3, cy-14, cx+20, cy+3), fill=INK)
        draw.rounded_rectangle((cx-26, cy+5, cx+26, cy+20), radius=7, fill=INK)


def card(draw, box, kind, label, value):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=20, fill=PALE)
    cx = (x1 + x2) // 2
    icon(draw, cx, y1+37, kind)
    ar(draw, (cx, y1+88), label, afont(22, True), INK, 'mm')
    f = fit(draw, value, 27, 20, x2-x1-30)
    yy = y1 + 136
    for line in wrap(draw, value, f, x2-x1-30, 2):
        ar(draw, (cx, yy), line, f, INK, 'mm')
        yy += 33


def globe(draw, cx, cy):
    draw.ellipse((cx-22, cy-22, cx+22, cy+22), outline=WHITE, width=3)
    draw.ellipse((cx-10, cy-22, cx+10, cy+22), outline=WHITE, width=2)
    draw.line((cx-21, cy, cx+21, cy), fill=WHITE, width=2)


def generate(job: dict, title: str):
    campaign_id = re.sub(r'[^a-zA-Z0-9_-]', '', str(job.get('campaign_id') or 'job'))
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f'{campaign_id}-{IMAGE_VERSION}.png'

    img = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    header_h, footer_h, left_w = 132, 94, 610
    draw.rectangle((0, 0, WIDTH, header_h), fill=NAVY)
    draw.rectangle((0, HEIGHT-footer_h, WIDTH, HEIGHT), fill=NAVY)

    photo = fetch_company_photo(job) or fallback_photo()
    photo = crop_photo(photo, (left_w, HEIGHT-header_h-footer_h))
    img.paste(photo, (0, header_h))
    fade = Image.new('L', (170, HEIGHT-header_h-footer_h), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(170):
        fd.line((x, 0, x, fade.height), fill=int(255*x/169))
    img.paste(Image.new('RGB', fade.size, WHITE), (left_w-85, header_h), fade)
    draw = ImageDraw.Draw(img)

    ar(draw, (465, 52), 'وظائف الأردن', afont(38, True), WHITE)
    ar(draw, (465, 94), 'أكبر منصة للوظائف في الأردن', afont(17), WHITE)
    fx, fy = 495, 30
    draw.rounded_rectangle((fx, fy, fx+62, fy+57), radius=6, fill=WHITE)
    draw.rectangle((fx+3, fy+3, fx+59, fy+20), fill=(0,0,0))
    draw.rectangle((fx+3, fy+20, fx+59, fy+38), fill=WHITE)
    draw.rectangle((fx+3, fy+38, fx+59, fy+54), fill=(0,122,61))
    draw.polygon([(fx+3,fy+3),(fx+3,fy+54),(fx+31,fy+28)], fill=(206,17,38))

    draw.rounded_rectangle((846, 16, 1485, 116), radius=26, fill=GOLD)
    ar(draw, (1385, 66), 'إعلان توظيف جديد', afont(44, True), INK, 'rm')
    draw.polygon([(1430,52),(1460,42),(1460,78),(1430,68)], fill=INK)

    emp, rest = headline(title, str(job.get('employer_name') or 'جهة توظيف'))
    ar(draw, (1470, 210), emp, fit(draw, emp, 78, 50, 790), INK)
    rf = fit(draw, rest, 51, 35, 790)
    y = 326
    for line in wrap(draw, rest, rf, 790, 2):
        ar(draw, (1470, y), line, rf, INK)
        y += 59

    sal = salary_from(title) or salary_from(str(job.get('title') or ''))
    sal_text = sal or 'الراتب يحدد حسب الوظيفة والخبرة'
    draw.rounded_rectangle((640, 414, 1468, 498), radius=24, fill=GOLD)
    ar(draw, (1055, 456), sal_text, fit(draw, sal_text, 40, 29, 760), (0,0,0), 'mm')

    sal_card = re.sub(r'^(?:رواتب متوقعة من|راتب متوقع)\s*', '', sal_text) if sal else 'حسب الوظيفة والخبرة'
    values = [
        ('people', 'الراتب المتوقع', sal_card),
        ('briefcase', 'نوع الوظيفة', 'حسب الإعلان'),
        ('pin', 'مكان العمل', location(job)),
        ('people', 'عدد الشواغر', 'عدة وظائف' if any(x in title for x in ['متنوعة','فرص','وظائف','شواغر','عدة']) else 'شاغر متاح'),
    ]
    for sx, data in zip([1280,1048,816,584], values):
        card(draw, (sx,528,sx+214,710), *data)

    draw.rounded_rectangle((505,726,1493,794), radius=16, fill=PALE)
    dep = departments(title)
    ar(draw, (1395,760), dep, fit(draw, dep, 26, 20, 850), INK, 'rm')
    draw.ellipse((1432,742,1470,780), fill=INK)
    draw.ellipse((1444,754,1458,768), fill=WHITE)

    draw.rounded_rectangle((468,812,1452,914), radius=25, fill=RED)
    ar(draw, (1248,863), 'التفاصيل وطريقة التقديم داخل المقال', afont(39, True), WHITE, 'rm')
    draw.ellipse((1320,831,1384,895), fill=WHITE)
    draw.line((1343,862,1363,862), fill=RED, width=6)
    draw.line((1353,852,1363,862), fill=RED, width=6)
    draw.line((1353,872,1363,862), fill=RED, width=6)

    globe(draw, 72, 974)
    draw.text((112,974), 'jobsinjordan2026.blogspot.com', font=lfont(27, True), fill=WHITE, anchor='lm')
    draw.line((670,946,670,1000), fill=(205,220,232), width=2)
    ar(draw, (1060,974), 'تابعنا لمزيد من فرص العمل في الأردن', afont(24), WHITE, 'rm')
    for i, label in enumerate(['F','IG','IN','TG']):
        cx = 1260 + i*65
        draw.ellipse((cx,948,cx+45,993), fill=WHITE)
        draw.text((cx+22,970), label, font=lfont(13 if len(label)>1 else 17, True), fill=INK, anchor='mm')

    img.save(path, format='PNG', optimize=True)
    return str(path), f'{RAW_BASE}/{path.name}'
