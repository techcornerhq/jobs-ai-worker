from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from company_visual import PREFERRED_IMAGES, normalized_employer, _download_image

IMAGE_DIR = Path('data/images')
RAW_BASE = 'https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images'
WIDTH, HEIGHT = 1536, 1024
IMAGE_VERSION = 'v12'
HAS_RAQM = bool(features.check_feature('raqm'))

NAVY=(2,31,59); NAVY2=(7,48,86); INK=(5,45,82); GOLD=(250,186,60); RED=(229,27,51)
WHITE=(255,255,255); PALE=(237,244,250); PALE2=(247,250,253); MUTED=(82,102,121); LINE=(218,228,237)

_ALLOWED = re.compile(r'[^\u0621-\u064A\u0660-\u0669A-Za-z0-9\s.,:؛،()/%+\-]', re.UNICODE)


def clean(value: str) -> str:
    s = unicodedata.normalize('NFKC', str(value or ''))
    for bad in ('□','�','■','▪','▫','●','○','◆','◇','•','·','■','□'):
        s = s.replace(bad, ' ')
    s = s.replace('–','-').replace('—','-').replace('ـ','').replace('|',' - ')
    s = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]', '', s)
    s = _ALLOWED.sub(' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def afont(size:int,bold:bool=False):
    names = [
        '/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf' if bold else '/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf' if bold else '/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for p in names:
        if Path(p).exists(): return ImageFont.truetype(p,size=size)
    return ImageFont.load_default()


def lfont(size:int,bold:bool=False):
    p='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p,size=size) if Path(p).exists() else ImageFont.load_default()


def akw(): return {'direction':'rtl','language':'ar'} if HAS_RAQM else {}

def width_of(d,text,font):
    b=d.textbbox((0,0),clean(text),font=font,**akw()); return max(0,b[2]-b[0])

def height_of(d,text,font):
    b=d.textbbox((0,0),clean(text),font=font,**akw()); return max(1,b[3]-b[1])

def fit_font(d,text,start,minimum,max_width,bold=True):
    for size in range(start,minimum-1,-2):
        f=afont(size,bold)
        if width_of(d,text,f)<=max_width: return f
    return afont(minimum,bold)

def fit_lines(d,text,max_width,max_lines,start,minimum,bold=True):
    text=clean(text)
    if not text: return afont(minimum,bold),[]
    words=text.split()
    for size in range(start,minimum-1,-2):
        f=afont(size,bold); lines=[]; cur=[]
        for w in words:
            trial=' '.join(cur+[w])
            if not cur or width_of(d,trial,f)<=max_width: cur.append(w)
            else: lines.append(' '.join(cur)); cur=[w]
        if cur: lines.append(' '.join(cur))
        if len(lines)<=max_lines: return f,lines
    f=afont(minimum,bold); lines=[]; cur=[]
    for w in words:
        trial=' '.join(cur+[w])
        if not cur or width_of(d,trial,f)<=max_width: cur.append(w)
        else:
            if len(lines)>=max_lines-1: break
            lines.append(' '.join(cur)); cur=[w]
    if cur and len(lines)<max_lines: lines.append(' '.join(cur))
    return f,lines[:max_lines]

def draw_ar(d,xy,text,font,fill,anchor='ra'):
    d.text(xy,clean(text),font=font,fill=fill,anchor=anchor,**akw())

def draw_center_ar(d,box,text,font,fill):
    x1,y1,x2,y2=box
    draw_ar(d,((x1+x2)//2,(y1+y2)//2),text,font,fill,anchor='mm')


def employer_name(job):
    e=normalized_employer(job.get('employer_name') or '')
    e=re.sub(r'\s*\([^)]*\)\s*',' ',e)
    e=re.sub(r'^(?:شركة|مؤسسة)\s+','',e).strip()
    return clean(e)[:42] or 'جهة توظيف'

def arabic_role(v):
    s=clean(v)
    for p,r in [(r'Integration\s+Developer(?:\s+Team\s+Member)?','مطور تكامل أنظمة'),(r'Software\s+Engineer','مهندس برمجيات'),(r'Data\s+Analyst','محلل بيانات'),(r'Accountant','محاسب'),(r'Customer\s+Service','خدمة عملاء'),(r'Team\s+Member',''),(r'Developer','مطور برمجيات'),(r'Engineer','مهندس')]:
        s=re.sub(p,r,s,flags=re.I)
    return clean(s)
def short_role(job,title,emp):
    if 'زين' in emp: return 'مطور تكامل أنظمة في عمان'
    if 'العميد' in emp: return 'فرص عمل متنوعة في عمان'
    if 'المناصير' in emp: return 'فرص صيانة وهندسة ميكانيكية'
    jt=arabic_role(job.get('job_title') or '')
    if jt and jt!='غير مذكور في الإعلان': return jt[:64]
    s=arabic_role(title); s=re.sub(r'\s*[-:]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?.*$','',s).strip(' :-')
    return (s or 'فرصة عمل جديدة')[:68]
def salary_line(job,title):
    for raw in [title,job.get('title') or '',job.get('salary_text') or '']:
        t=clean(raw)
        m=re.search(r'(\d{2,4})\s*(?:إلى|الى|-)\s*(\d{2,4})\s*دينار',t)
        if m:return f'رواتب متوقعة من {m.group(1)} إلى {m.group(2)} دينار'
        m=re.search(r'(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار',t)
        if m:return f'راتب متوقع حتى {m.group(1)} دينار'
    off=clean(job.get('salary') or '')
    return off[:48] if off and off!='غير مذكور في الإعلان' else 'الراتب يحدد حسب الوظيفة والخبرة'
def loc_line(job):
    x=clean(job.get('location_text') or 'الأردن').replace('الأردن - ','').replace('- الأردن','').strip()
    return x or 'الأردن'
def count_line(job,title):
    for raw in [job.get('vacancy_count'),title,job.get('title')]:
        t=clean(raw or '')
        if t.isdigit():return f'{t} شاغر'
        m=re.search(r'(?<!\d)(\d{1,3})\s*(?:شاغر|شواغر|فرصة|وظيفة)',t)
        if m:return f'{m.group(1)} شاغر'
    return 'عدة وظائف' if any(x in clean(title) for x in ['وظائف','شواغر','فرص']) else 'شاغر متاح'
def employment_line(job):
    x=clean(job.get('employment_type') or '')
    return x if x and x!='غير مذكور في الإعلان' else 'حسب الإعلان'
def specialty_line(job,title):
    t=' '.join([arabic_role(title),arabic_role(job.get('job_title') or '')])
    if any(x in t for x in ['تكامل','مطور','برمج','تقنية']): return 'التخصص: تطوير وتكامل الأنظمة التقنية'
    if any(x in t for x in ['صيانة','ميكاني','كهرب','حدادة','دهان','آليات']): return 'التخصصات: صيانة، ميكانيك، كهرباء، حدادة وهندسة ميكانيكية'
    if any(x in t for x in ['مبيعات','خدمة عملاء','إدارية','تشغيلية','متنوعة']): return 'الأقسام: إدارية، تقنية، تشغيلية، مبيعات وخدمة عملاء'
    return 'التخصصات والتفاصيل موضحة داخل الإعلان'
def category(job,title):
    t=' '.join([clean(title),clean(job.get('job_title') or ''),employer_name(job)]).lower()
    if any(x in t for x in ['صيانة','ميكاني','كهرب','حدادة','دهان','آليات','mechanic']): return 'mechanical'
    if any(x in t for x in ['مطور','برمج','تكامل','developer','software','تقنية',' it ']): return 'tech'
    if any(x in t for x in ['قهوة','coffee','العميد','barista','مطعم','مبيعات','متجر']): return 'retail'
    if any(x in t for x in ['تمريض','طبيب','صيدل','medical','health']): return 'health'
    return 'office'


def trusted_photo(job,emp):
    key='زين' if 'زين' in emp else ('العميد' if 'العميد' in emp else None)
    # Only explicitly curated company photos are allowed. No arbitrary page image scraping.
    if key:
        for url,referer in PREFERRED_IMAGES.get(key,[]):
            im=_download_image(url,referer)
            if im is not None:return im
    return None

def fallback_visual(kind,emp):
    w,h=610,786; im=Image.new('RGB',(w,h),NAVY); d=ImageDraw.Draw(im)
    d.rectangle((0,0,w,h),fill=NAVY)
    for i in range(8):
        pad=30+i*16; tone=(8+i*3,48+i*4,84+i*5)
        d.rounded_rectangle((pad,60+i*16,w-pad,h-60-i*10),radius=30,outline=tone,width=3)
    d.ellipse((125,120,485,480),fill=(10,58,99),outline=GOLD,width=7)
    cx,cy=305,300
    if kind=='mechanical':
        d.ellipse((210,205,400,395),outline=WHITE,width=14); d.ellipse((265,260,345,340),outline=GOLD,width=13)
        for a in range(0,360,45):
            x1=cx+int(math.cos(math.radians(a))*98); y1=cy+int(math.sin(math.radians(a))*98)
            x2=cx+int(math.cos(math.radians(a))*132); y2=cy+int(math.sin(math.radians(a))*132)
            d.line((x1,y1,x2,y2),fill=WHITE,width=15)
        # wrench cue
        d.line((205,420,395,230),fill=GOLD,width=18)
    elif kind=='tech':
        d.rounded_rectangle((185,205,425,385),radius=20,outline=WHITE,width=12); d.line((245,410,365,410),fill=WHITE,width=12); d.line((305,385,305,410),fill=WHITE,width=12)
        d.line((245,270,205,315,245,355),fill=GOLD,width=12); d.line((365,270,405,315,365,355),fill=GOLD,width=12)
    elif kind=='retail':
        d.rounded_rectangle((195,230,415,400),radius=24,outline=WHITE,width=12); d.line((225,230,245,185,365,185,385,230),fill=GOLD,width=12)
        d.line((235,285,375,285),fill=WHITE,width=10); d.line((235,340,375,340),fill=WHITE,width=10)
    elif kind=='health':
        d.rounded_rectangle((260,185,350,420),radius=14,fill=WHITE); d.rounded_rectangle((190,260,420,350),radius=14,fill=WHITE)
        d.rounded_rectangle((278,205,332,400),radius=8,fill=GOLD); d.rounded_rectangle((210,278,400,332),radius=8,fill=GOLD)
    else:
        d.rounded_rectangle((195,230,415,400),radius=20,outline=WHITE,width=12); d.rectangle((260,190,350,240),outline=GOLD,width=12); d.line((195,300,415,300),fill=GOLD,width=10)
    mf=afont(46,True); draw_center_ar(d,(85,520,525,590),emp[:24],mf,GOLD)
    draw_center_ar(d,(85,600,525,650),'تصميم مرتبط بمجال الوظيفة',afont(23,True),WHITE)
    return im

def visual(job,title,emp):
    photo=trusted_photo(job,emp)
    if photo is not None:return ImageOps.fit(photo.convert('RGB'),(610,786),method=Image.Resampling.LANCZOS,centering=(0.5,0.5)),'curated_official_photo'
    return fallback_visual(category(job,title),emp),'sector_fallback'


def draw_flag(d,x,y):
    d.rounded_rectangle((x,y,x+60,y+42),radius=5,fill=WHITE); d.rectangle((x+3,y+3,x+57,y+15),fill=(0,122,61)); d.rectangle((x+3,y+15,x+57,y+28),fill=WHITE); d.rectangle((x+3,y+28,x+57,y+39),fill=(0,0,0)); d.polygon([(x+3,y+3),(x+30,y+21),(x+3,y+39)],fill=(206,17,38))

def icon_people(d,cx,y):
    d.ellipse((cx-8,y,cx+8,y+16),fill=INK); d.ellipse((cx-27,y+9,cx-13,y+23),fill=INK); d.ellipse((cx+13,y+9,cx+27,y+23),fill=INK); d.rounded_rectangle((cx-36,y+25,cx+36,y+38),radius=6,fill=INK)
def icon_pin(d,cx,y):
    d.ellipse((cx-18,y,cx+18,y+36),fill=INK); d.polygon([(cx-15,y+24),(cx+15,y+24),(cx,y+50)],fill=INK); d.ellipse((cx-6,y+10,cx+6,y+22),fill=WHITE)
def icon_bag(d,cx,y):
    d.rounded_rectangle((cx-28,y+12,cx+28,y+43),radius=5,fill=INK); d.rectangle((cx-12,y+4,cx+12,y+14),outline=INK,width=5)
def icon_money(d,cx,y):
    d.rounded_rectangle((cx-34,y+4,cx+34,y+42),radius=6,outline=INK,width=5); d.ellipse((cx-8,y+13,cx+8,y+29),fill=INK); d.line((cx-27,y+12,cx-20,y+12),fill=INK,width=4); d.line((cx+20,y+34,cx+27,y+34),fill=INK,width=4)
def draw_info_card(d,box,label,value,kind):
    x1,y1,x2,y2=box; d.rounded_rectangle(box,radius=20,fill=PALE,outline=LINE,width=2); cx=(x1+x2)//2
    {'salary':icon_money,'type':icon_bag,'location':icon_pin,'count':icon_people}[kind](d,cx,y1+18)
    draw_center_ar(d,(x1+8,y1+76,x2-8,y1+112),label,fit_font(d,label,20,15,x2-x1-20,True),INK)
    vf,lines=fit_lines(d,value,x2-x1-22,2,22,16,True); lines=lines or ['غير مذكور']
    total=sum(height_of(d,ln,vf) for ln in lines)+(len(lines)-1)*9; yy=y1+133+(52-total)//2
    for ln in lines:
        h=height_of(d,ln,vf); draw_ar(d,(cx,yy+h//2),ln,vf,INK,anchor='mm'); yy+=h+9


def generate(job,title):
    IMAGE_DIR.mkdir(parents=True,exist_ok=True); cid=clean(job.get('campaign_id') or 'job').replace(' ','-')[:48]; filename=f'{cid}-{IMAGE_VERSION}.png'; path=IMAGE_DIR/filename
    img=Image.new('RGB',(WIDTH,HEIGHT),WHITE); d=ImageDraw.Draw(img); header_h=132; footer_h=106; body_bottom=HEIGHT-footer_h
    d.rectangle((0,0,WIDTH,header_h),fill=NAVY); d.rectangle((0,header_h,WIDTH,body_bottom),fill=WHITE); d.rectangle((0,body_bottom,WIDTH,HEIGHT),fill=NAVY)
    emp=employer_name(job); role=short_role(job,title,emp); salary=salary_line(job,title); loc=loc_line(job); vis,viskind=visual(job,title,emp); img.paste(vis,(0,header_h)); d=ImageDraw.Draw(img)

    # Header: true vertical centering; nothing can clip.
    draw_flag(d,520,44); draw_center_ar(d,(150,24,475,82),'وظائف الأردن',afont(31,True),WHITE); draw_center_ar(d,(160,78,470,112),'فرص عمل يومية في الأردن',afont(14,False),(202,217,230))
    badge=(905,22,1505,110); d.rounded_rectangle(badge,radius=24,fill=GOLD); draw_center_ar(d,(990,27,1470,106),'إعلان توظيف جديد',afont(32,True),NAVY); d.polygon([(935,50),(970,66),(935,82)],fill=NAVY)

    rx1,rx2=650,1490; maxw=rx2-rx1-35
    # Dynamic title block between y=160 and y=330.
    ef=fit_font(d,emp,58,34,maxw,True); rf,rlines=fit_lines(d,role,maxw,2,32,21,True)
    eh=height_of(d,emp,ef); rhs=[height_of(d,x,rf) for x in rlines]; needed=eh+18+sum(rhs)+max(0,len(rhs)-1)*8
    while needed>155 and ef.size>34:
        ef=afont(ef.size-2,True); rf,rlines=fit_lines(d,role,maxw,2,max(21,rf.size-2),19,True); eh=height_of(d,emp,ef); rhs=[height_of(d,x,rf) for x in rlines]; needed=eh+16+sum(rhs)+max(0,len(rhs)-1)*7
    top=160+(155-needed)//2; draw_ar(d,(rx2,top),emp,ef,INK,anchor='rt'); y=top+eh+16
    for i,ln in enumerate(rlines):
        draw_ar(d,(rx2,y),ln,rf,INK,anchor='rt'); y+=rhs[i]+7

    d.rounded_rectangle((rx1,340,rx2,416),radius=21,fill=GOLD); draw_center_ar(d,(rx1+20,343,rx2-20,413),salary,fit_font(d,salary,32,21,maxw-40,True),(15,25,32))
    gap=12; cw=(rx2-rx1-gap*3)//4
    cards=[('الراتب',salary.replace('رواتب متوقعة ','').replace('راتب متوقع ',''),'salary'),('نوع الوظيفة',employment_line(job),'type'),('مكان العمل',loc,'location'),('عدد الشواغر',count_line(job,title),'count')]
    for i,(lab,val,kind) in enumerate(cards):
        x1=rx1+i*(cw+gap); draw_info_card(d,(x1,438,x1+cw,638),lab,val,kind)
    d.rounded_rectangle((rx1,657,rx2,715),radius=17,fill=PALE2,outline=LINE,width=2); dep=specialty_line(job,title); draw_ar(d,(rx2-24,686),dep,fit_font(d,dep,23,16,maxw-60,True),INK,anchor='ra'); d.ellipse((rx1+18,671,rx1+48,701),fill=INK); d.ellipse((rx1+29,682,rx1+37,690),fill=WHITE)
    d.rounded_rectangle((rx1,735,rx2,838),radius=25,fill=RED); cta='التفاصيل وطريقة التقديم داخل المقال'; draw_center_ar(d,(rx1+40,742,rx2-110,832),cta,fit_font(d,cta,32,23,maxw-145,True),WHITE); d.ellipse((rx2-88,758,rx2-32,814),fill=WHITE); d.line((rx2-66,786,rx2-49,786),fill=RED,width=7); d.line((rx2-56,776,rx2-46,786,rx2-56,796),fill=RED,width=7)

    d.ellipse((42,body_bottom+27,78,body_bottom+63),outline=WHITE,width=3); d.line((60,body_bottom+29,60,body_bottom+61),fill=WHITE,width=2); d.line((45,body_bottom+45,75,body_bottom+45),fill=WHITE,width=2); d.text((90,body_bottom+49),'jobsinjordan2026.blogspot.com',font=lfont(25,True),fill=WHITE,anchor='lm')
    draw_center_ar(d,(800,body_bottom+20,1170,body_bottom+78),'تابعنا لمزيد من فرص العمل في الأردن',afont(17,False),(208,222,233))
    for i,label in enumerate(['F','IG','IN','TG']):
        cx=1280+i*68; d.ellipse((cx-21,body_bottom+28,cx+21,body_bottom+70),fill=WHITE); d.text((cx,body_bottom+49),label,font=lfont(10,True),fill=NAVY,anchor='mm')
    d.text((1495,1005),viskind,font=lfont(5,False),fill=NAVY,anchor='rb')
    img.save(path,format='PNG',optimize=True)
    return str(path),f'{RAW_BASE}/{filename}'
