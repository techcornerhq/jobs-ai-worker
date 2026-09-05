from __future__ import annotations

import base64
import hashlib
import html
import io
import re
import unicodedata
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from company_visual_v13 import fetch_brand_asset, normalized_employer

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH, HEIGHT = 1536, 1024
IMAGE_VERSION = "v13"

_ALLOWED = re.compile(r"[^\u0621-\u064A\u0660-\u0669A-Za-z0-9\s.,:؛،()/%+\-&#@']", re.UNICODE)


def clean(value: str, limit: int | None = None) -> str:
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = s.replace("–", "-").replace("—", "-").replace("ـ", "").replace("|", " - ")
    s = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    s = _ALLOWED.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def safe(value: str, limit: int | None = None) -> str:
    return html.escape(clean(value, limit), quote=True)


def first(*values, default="غير مذكور") -> str:
    for v in values:
        s = clean(v)
        if s and s not in {"غير مذكور", "غير مذكور في الإعلان", "None"}:
            return s
    return default


def _title(job: dict, title: str) -> str:
    return first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة")


def _employer(job: dict) -> str:
    return normalized_employer(first(job.get("employer_name"), job.get("employer"), default="جهة التوظيف"))


def _salary(job: dict, title: str) -> str:
    direct = first(job.get("salary_text"), job.get("salary"), default="")
    if direct:
        return direct
    t = clean(title)
    m = re.search(r"(\d{2,4})\s*(?:إلى|الى|-)\s*(\d{2,4})\s*دينار", t)
    if m:
        return f"{m.group(1)} - {m.group(2)} دينار"
    m = re.search(r"(?:حتى|تصل إلى|تصل الى)\s*(\d{2,4})\s*دينار", t)
    if m:
        return f"حتى {m.group(1)} دينار"
    return "حسب الإعلان"


def _vacancies(job: dict, title: str) -> str:
    direct = clean(job.get("vacancy_count") or "")
    if direct:
        if direct.isdigit():
            return f"{direct} شاغر"
        return direct
    t = clean(title)
    m = re.search(r"(?<!\d)(\d{1,3})\s*(?:شاغر|شواغر|وظيفة|فرصة)", t)
    if m:
        return f"{m.group(1)} شاغر"
    if any(x in t for x in ("وظائف", "شواغر", "فرص عمل متنوعة")):
        return "عدة شواغر"
    return "حسب الإعلان"


def _location(job: dict) -> str:
    return first(job.get("location_text"), job.get("city"), job.get("governorate"), default="الأردن")


def _employment(job: dict) -> str:
    return first(job.get("employment_type"), default="حسب الإعلان")


def _specialty(job: dict, title: str) -> str:
    value = first(job.get("specialty_text"), job.get("category_text"), default="")
    if value:
        return value
    job_title = _title(job, title)
    if len(job_title) <= 65:
        return f"التخصص: {job_title}"
    return "التخصص والتفاصيل موضحة داخل الإعلان"


def _image_data_uri(image: Image.Image | None) -> str | None:
    if image is None:
        return None
    im = image.copy()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    bio = io.BytesIO()
    im.save(bio, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(bio.getvalue()).decode("ascii")


def _svg_icon(kind: str) -> str:
    # Inline SVGs only: no icon-font/emoji dependency, so no missing-glyph boxes.
    paths = {
        "people": "<circle cx='8' cy='7' r='3'/><circle cx='16' cy='7' r='3'/><path d='M2 19c0-4 2-6 6-6s6 2 6 6M11 19c.5-3.2 2.2-5 5-5 3.6 0 5.5 1.8 6 5'/>",
        "pin": "<path d='M12 22s7-6.2 7-13a7 7 0 1 0-14 0c0 6.8 7 13 7 13z'/><circle cx='12' cy='9' r='2.3'/>",
        "briefcase": "<rect x='3' y='7' width='18' height='13' rx='2'/><path d='M8 7V4h8v3M3 12h18'/>",
        "money": "<rect x='2.5' y='5' width='19' height='14' rx='2'/><circle cx='12' cy='12' r='3'/><path d='M6 8H5v1M18 8h1v1M6 16H5v-1M18 16h1v-1'/>",
    }
    return f"<svg viewBox='0 0 24 24' aria-hidden='true'><g fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{paths[kind]}</g></svg>"


def _html(job: dict, title: str, asset: dict) -> str:
    employer = _employer(job)
    role = _title(job, title)
    salary = _salary(job, title)
    location = _location(job)
    employment = _employment(job)
    vacancies = _vacancies(job, title)
    specialty = _specialty(job, title)
    asset_kind = asset.get("kind") or "none"
    uri = _image_data_uri(asset.get("image"))

    if uri and asset_kind == "photo":
        visual = f"<img class='institution-photo' src='{uri}' alt=''/>"
        visual_class = "has-photo"
    elif uri and asset_kind == "logo":
        visual = f"<div class='logo-card'><img class='institution-logo' src='{uri}' alt=''/></div>"
        visual_class = "has-logo"
    else:
        visual = f"<div class='name-card'><div class='name-mark'>{safe(employer, 54)}</div><div class='name-sub'>هوية جهة التوظيف</div></div>"
        visual_class = "no-asset"

    return f"""<!doctype html>
<html lang='ar' dir='rtl'>
<head>
<meta charset='utf-8'/>
<style>
*{{box-sizing:border-box}}
html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden;background:#f5f8fc}}
body{{font-family:'Noto Kufi Arabic','Noto Sans Arabic',Arial,sans-serif;color:#082c51}}
.poster{{position:relative;width:{WIDTH}px;height:{HEIGHT}px;background:#f7f9fc;display:grid;grid-template-columns:610px 1fr;direction:ltr}}
.visual{{position:relative;background:#031f3b;overflow:hidden;direction:rtl}}
.visual:before{{content:'';position:absolute;inset:0;background:radial-gradient(circle at 50% 35%,rgba(26,92,145,.26),transparent 44%),linear-gradient(145deg,#021a31,#073b68);z-index:0}}
.brand-strip{{position:absolute;z-index:4;top:38px;left:38px;right:38px;display:flex;align-items:center;justify-content:space-between;color:#fff}}
.brand-title{{font-weight:900;font-size:26px;line-height:1.2}} .brand-small{{font-size:12px;opacity:.74;margin-top:4px}}
.flag{{width:58px;height:38px;border-radius:5px;overflow:hidden;border:2px solid rgba(255,255,255,.75);background:linear-gradient(#111 0 33%,#fff 33% 66%,#087a3d 66%)}}
.flag:after{{content:'';display:block;width:0;height:0;border-top:17px solid transparent;border-bottom:17px solid transparent;border-right:31px solid #ce1634;transform:translateY(0)}}
.media{{position:absolute;z-index:2;left:34px;right:34px;top:118px;bottom:112px;border-radius:26px;overflow:hidden;border:1px solid rgba(255,255,255,.13);box-shadow:0 20px 55px rgba(0,0,0,.22);background:#062a4d;display:grid;place-items:center}}
.institution-photo{{width:100%;height:100%;object-fit:cover;display:block}} .has-photo .media:after{{content:'';position:absolute;inset:auto 0 0;height:38%;background:linear-gradient(transparent,rgba(2,31,59,.82))}}
.logo-card{{width:82%;height:70%;border-radius:28px;background:#fff;display:grid;place-items:center;padding:44px;box-shadow:0 18px 45px rgba(0,0,0,.18)}} .institution-logo{{max-width:100%;max-height:100%;object-fit:contain}}
.name-card{{width:82%;min-height:310px;border:2px solid rgba(250,186,60,.64);border-radius:28px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;text-align:center;background:rgba(2,31,59,.58)}}
.name-mark{{color:#faba3c;font-size:40px;font-weight:900;line-height:1.55}} .name-sub{{margin-top:18px;color:#fff;font-size:16px;font-weight:700;opacity:.84}}
.visual-label{{position:absolute;z-index:5;left:55px;right:55px;bottom:128px;text-align:center;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.38)}} .visual-label b{{display:block;font-size:31px;line-height:1.45}} .visual-label span{{font-size:14px;opacity:.84}}
.has-logo .visual-label,.no-asset .visual-label{{display:none}}
.visual-footer{{position:absolute;z-index:5;bottom:33px;left:38px;right:38px;color:#fff;display:flex;justify-content:space-between;align-items:center;font-size:14px}} .visual-footer small{{opacity:.7}}
.content{{direction:rtl;padding:50px 52px 92px 48px;display:flex;flex-direction:column;background:#fff}}
.topline{{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px}} .site-chip{{font-size:15px;font-weight:900;color:#087f75}} .new-badge{{background:#faba3c;color:#082c51;padding:13px 27px;border-radius:14px;font-size:20px;font-weight:900}}
.role{{margin:10px 0 8px;font-size:48px;line-height:1.38;font-weight:900;color:#061f3b;letter-spacing:-.3px;max-height:200px;overflow:hidden}}
.employer{{font-size:24px;font-weight:800;color:#50657a;margin-bottom:22px;min-height:38px}}
.salary{{background:#faba3c;border-radius:14px;min-height:62px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;color:#082c51;margin-bottom:20px;padding:8px 20px}}
.facts{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:15px}}
.fact{{min-height:128px;border:1px solid #d7e2ec;border-radius:14px;background:#eef5fb;padding:15px 10px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px}}
.fact svg{{width:31px;height:31px;color:#063d70}} .fact-label{{font-size:13px;font-weight:800;color:#46617a}} .fact-value{{font-size:14px;font-weight:900;color:#082c51;line-height:1.45}}
.specialty{{min-height:48px;border:1px solid #d7e2ec;border-radius:12px;background:#f8fbfd;display:flex;align-items:center;padding:8px 18px;font-size:14px;font-weight:800;color:#274b6e;margin-bottom:16px}}
.cta{{margin-top:auto;background:#eb1838;color:#fff;border-radius:14px;min-height:72px;display:flex;align-items:center;justify-content:center;font-size:23px;font-weight:900;box-shadow:0 10px 24px rgba(235,24,56,.14)}}
.page-footer{{position:absolute;right:0;left:610px;bottom:0;height:62px;background:#031f3b;color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;opacity:.98}}
</style>
</head>
<body>
<div class='poster'>
  <section class='visual {visual_class}'>
    <div class='brand-strip'><div><div class='brand-title'>وظائف الأردن</div><div class='brand-small'>فرص عمل موثقة في الأردن</div></div><div class='flag'></div></div>
    <div class='media'>{visual}</div>
    <div class='visual-label'><b dir='auto'>{safe(employer, 52)}</b><span>صورة أو هوية جهة التوظيف</span></div>
    <div class='visual-footer'><b>jobsinjordan2026.blogspot.com</b><small>تابعنا لمزيد من فرص العمل في الأردن</small></div>
  </section>
  <section class='content'>
    <div class='topline'><div class='site-chip'>فرصة عمل في الأردن</div><div class='new-badge'>إعلان توظيف جديد</div></div>
    <h1 class='role' dir='auto'>{safe(role, 105)}</h1>
    <div class='employer' dir='auto'>{safe(employer, 68)}</div>
    <div class='salary'>الراتب: {safe(salary, 54)}</div>
    <div class='facts'>
      <div class='fact'>{_svg_icon('people')}<div class='fact-label'>عدد الشواغر</div><div class='fact-value'>{safe(vacancies, 25)}</div></div>
      <div class='fact'>{_svg_icon('pin')}<div class='fact-label'>مكان العمل</div><div class='fact-value'>{safe(location, 30)}</div></div>
      <div class='fact'>{_svg_icon('briefcase')}<div class='fact-label'>نوع الوظيفة</div><div class='fact-value'>{safe(employment, 28)}</div></div>
      <div class='fact'>{_svg_icon('money')}<div class='fact-label'>الراتب</div><div class='fact-value'>{safe(salary, 28)}</div></div>
    </div>
    <div class='specialty'>{safe(specialty, 92)}</div>
    <div class='cta'>التفاصيل وطريقة التقديم داخل المقال</div>
  </section>
  <div class='page-footer'>وظائف الأردن — تفاصيل موثقة ومنظمة للباحثين عن عمل</div>
</div>
</body>
</html>"""


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    employer = _employer(job)
    role = _title(job, title)
    key = hashlib.sha1(f"{employer}|{role}".encode("utf-8")).hexdigest()[:14]
    filename = f"job-{key}-{IMAGE_VERSION}.png"
    path = IMAGE_DIR / filename

    asset = fetch_brand_asset({**job, "employer_name": employer})
    markup = _html(job, title, asset)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.set_content(markup, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(path), full_page=False, type="png")
        browser.close()

    # Hard validation: exact expected canvas size and a non-trivial file.
    with Image.open(path) as im:
        if im.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Poster size mismatch: {im.size}")
    if path.stat().st_size < 35_000:
        raise RuntimeError("Poster render appears unexpectedly small/blank")

    return str(path), f"{RAW_BASE}/{filename}"
