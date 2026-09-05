from __future__ import annotations

import hashlib
import io
import math
import os
import re
import textwrap
import unicodedata
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat, features

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
WIDTH, HEIGHT = 1536, 1024
VERSION = "ai-v1"
UA = "JordanJobsDynamicImage/1.0"

ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
BAD_CHARS = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff□■▪▫�]")


def clean(value: str) -> str:
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = BAD_CHARS.sub("", s)
    s = s.replace("–", "-").replace("—", "-").replace("ـ", "")
    return re.sub(r"\s+", " ", s).strip()


def short(value: str, limit: int) -> str:
    s = clean(value)
    if len(s) <= limit:
        return s
    cut = s[: limit + 1].rsplit(" ", 1)[0].strip()
    return (cut or s[:limit]).rstrip("-,:؛، ") + "…"


def first(*values, default="") -> str:
    for v in values:
        s = clean(v)
        if s and s not in {"غير مذكور", "غير مذكور في الإعلان", "None"}:
            return s
    return default


def visual_category(job: dict, title: str) -> tuple[str, str]:
    t = " ".join([
        clean(title), clean(job.get("job_title")), clean(job.get("employer_name")),
        clean(job.get("category_text")), clean(job.get("industry")), clean(job.get("location_text")),
    ]).lower()
    rules = [
        (("طبيب", "تمريض", "صيدل", "مستشفى", "medical", "nurse", "doctor", "health"), "medical", "a modern hospital or healthcare workplace with professional medical staff, clean clinical atmosphere"),
        (("مطور", "برمج", "software", "developer", "programmer", "تقنية", " it ", "data", "cyber"), "technology", "a contemporary technology workspace with laptop screens, coding and collaboration, premium modern office"),
        (("جامعة", "مدرس", "معلم", "تعليم", "محاضر", "school", "teacher", "education", "training"), "education", "a modern university or training environment, professional academic atmosphere, students or staff in a tasteful campus setting"),
        (("محاسب", "مالية", "بنك", "finance", "account", "audit"), "finance", "a refined finance and accounting office, professional desk work, reports and business analytics"),
        (("سكرت", "موارد بشرية", "hr ", "اداري", "إداري", "office", "coordinator", "secretary"), "office", "an elegant professional office with organized desk, meeting environment and administrative work"),
        (("مبيعات", "خدمة عملاء", "customer", "sales", "retail", "متجر"), "sales", "a polished customer service or sales workplace with friendly professional staff and modern retail or service environment"),
        (("سياح", "سفر", "حجوزات", "طيران", "travel", "ticket", "airline", "tourism"), "travel", "a premium travel agency or airline reservations environment, subtle airport and travel cues, professional service desk"),
        (("صيانة", "ميكاني", "كهرب", "هندس", "engineer", "mechanic", "maintenance", "factory", "industrial"), "industrial", "a professional engineering or industrial workplace with safety gear, tools or modern machinery, realistic and clean"),
        (("مخزن", "مستودع", "لوجست", "warehouse", "logistics", "inventory", "بضائع"), "logistics", "a clean modern warehouse or logistics environment with organized inventory and professional staff"),
        (("مطعم", "فندق", "ضيافة", "coffee", "barista", "hotel", "restaurant", "hospitality"), "hospitality", "a stylish hospitality workplace such as a cafe, hotel or restaurant service setting, realistic and welcoming"),
        (("سائق", "توصيل", "driver", "delivery", "مندوب"), "field", "a professional field-work or delivery scene in Jordan with vehicle and urban context, safe and realistic"),
    ]
    for needles, name, scene in rules:
        if any(x in t for x in needles):
            return name, scene
    return "general", "a modern professional workplace in Jordan appropriate for the role, realistic people and authentic business atmosphere"


def build_prompt(job: dict, title: str) -> str:
    role = first(job.get("job_title"), title, job.get("title"), default="professional job")
    employer = first(job.get("employer_name"), default="")
    location = first(job.get("location_text"), job.get("city"), job.get("governorate"), default="Jordan")
    cat, scene = visual_category(job, role)
    employer_context = f" The employer is {employer}." if employer else ""
    return (
        f"Create a highly attractive photorealistic editorial recruitment image for the role: {role}. "
        f"Category: {cat}. Workplace context: {scene}. Location context: {location}.{employer_context} "
        "Make it look like a premium real-world advertising photograph, cinematic but believable, strong focal subject, natural professional people when appropriate, clean composition, modern lighting, subtle Jordan context when relevant. "
        "Do not show any readable text, letters, logos, brand marks, watermarks, UI screenshots, fake documents, or poster graphics. "
        "Leave some calm negative space somewhere in the composition so short Arabic text can be added later. "
        "Landscape 3:2 composition, social-media friendly, sharp, realistic, elegant, visually engaging."
    )


def _legacy_request(prompt: str, seed: int, model: str) -> Image.Image:
    url = "https://image.pollinations.ai/prompt/" + quote(prompt, safe="")
    params = {"model": model, "seed": seed, "width": 1024, "height": 682, "safe": "true", "enhance": "false"}
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=240)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if "image" not in ctype:
        raise RuntimeError(f"Legacy image endpoint returned {ctype or 'unknown content type'}")
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _authenticated_request(prompt: str, seed: int, model: str, key: str) -> Image.Image:
    url = "https://gen.pollinations.ai/image/" + quote(prompt, safe="")
    r = requests.get(
        url,
        params={"model": model, "seed": seed},
        headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
        timeout=240,
    )
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if "image" not in ctype:
        raise RuntimeError(f"Authenticated image endpoint returned {ctype or 'unknown content type'}")
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def generate_scene(prompt: str, seed: int) -> Image.Image:
    model = os.getenv("JOB_IMAGE_MODEL", "flux")
    key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    errors = []
    if key:
        try:
            return _authenticated_request(prompt, seed, model, key)
        except Exception as exc:
            errors.append(f"authenticated: {exc}")
    try:
        return _legacy_request(prompt, seed, model)
    except Exception as exc:
        errors.append(f"legacy: {exc}")
    raise RuntimeError("AI image generation failed: " + " | ".join(errors))


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoKufiArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoKufiArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _has_arabic(s: str) -> bool:
    return bool(ARABIC_RE.search(s))


def _display_text(text: str) -> tuple[str, dict]:
    text = clean(text)
    if not _has_arabic(text):
        return text, {}
    if features.check_feature("raqm"):
        return text, {"direction": "rtl", "language": "ar"}
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text)), {}
    return text, {}


def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int, int, int]:
    rendered, kwargs = _display_text(text)
    return draw.textbbox((0, 0), rendered, font=font, **kwargs)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    words = clean(text).split()
    if not words:
        return []
    lines, current = [], []
    for word in words:
        trial = " ".join(current + [word])
        b = _text_bbox(draw, trial, font)
        if not current or (b[2] - b[0]) <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines[:max_lines]


def _fit_title(draw: ImageDraw.ImageDraw, title: str, max_width: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(66, 37, -2):
        font = _font(size, True)
        lines = _wrap(draw, title, font, max_width, 2)
        if lines and len(lines) <= 2 and all((_text_bbox(draw, line, font)[2] - _text_bbox(draw, line, font)[0]) <= max_width for line in lines):
            return font, lines
    font = _font(38, True)
    return font, _wrap(draw, short(title, 62), font, max_width, 2)


def _region_score(im: Image.Image, box: tuple[int, int, int, int]) -> float:
    crop = im.crop(box).convert("L").resize((128, 96))
    stat = ImageStat.Stat(crop)
    variance = stat.var[0]
    # Edge/detail estimate; flatter regions are better for text.
    edge = crop.filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edge).mean[0]
    return variance * 0.65 + edge_mean * 8.0


def _choose_region(im: Image.Image) -> tuple[int, int, int, int]:
    margin = 54
    w, h = 660, 420
    candidates = [
        (WIDTH - w - margin, margin, WIDTH - margin, margin + h),
        (margin, margin, margin + w, margin + h),
        (WIDTH - w - margin, HEIGHT - h - margin, WIDTH - margin, HEIGHT - margin),
        (margin, HEIGHT - h - margin, margin + w, HEIGHT - margin),
    ]
    return min(candidates, key=lambda b: _region_score(im, b))


def _draw_line(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, anchor: str):
    rendered, kwargs = _display_text(text)
    draw.text(xy, rendered, font=font, fill=fill, anchor=anchor, **kwargs)


def overlay_text(scene: Image.Image, job: dict, title: str) -> Image.Image:
    canvas = ImageOps.fit(scene.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).convert("RGBA")
    region = _choose_region(canvas.convert("RGB"))
    x1, y1, x2, y2 = region
    pad = 34
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    brightness = ImageStat.Stat(canvas.crop(region).convert("L")).mean[0]
    panel = (6, 18, 32, 205) if brightness > 105 else (255, 255, 255, 218)
    primary = (255, 255, 255, 255) if brightness > 105 else (12, 36, 58, 255)
    secondary = (231, 238, 244, 255) if brightness > 105 else (64, 88, 110, 255)
    accent = (250, 186, 60, 255)
    od.rounded_rectangle(region, radius=30, fill=panel)

    d = ImageDraw.Draw(overlay)
    role = short(first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة"), 68)
    employer = short(first(job.get("employer_name"), default=""), 42)
    location = short(first(job.get("location_text"), job.get("city"), job.get("governorate"), default="الأردن"), 28)
    subtitle = " • ".join([x for x in (employer, location) if x])

    max_width = (x2 - x1) - pad * 2
    title_font, title_lines = _fit_title(d, role, max_width)
    sub_font = _font(28, True)
    cta_font = _font(24, True)

    rtl = _has_arabic(role)
    tx = x2 - pad if rtl else x1 + pad
    anchor = "ra" if rtl else "la"
    y = y1 + 52
    for line in title_lines:
        _draw_line(d, (tx, y), line, title_font, primary, anchor)
        b = _text_bbox(d, line, title_font)
        y += (b[3] - b[1]) + 17

    if subtitle:
        y += 5
        sub_rtl = _has_arabic(subtitle)
        sx = x2 - pad if sub_rtl else x1 + pad
        _draw_line(d, (sx, y), subtitle, sub_font, secondary, "ra" if sub_rtl else "la")
        b = _text_bbox(d, subtitle, sub_font)
        y += (b[3] - b[1]) + 28

    # Accent rule and a single concise CTA. No icons or decorative glyph fonts.
    line_y = min(y, y2 - 100)
    od.rounded_rectangle((x1 + pad, line_y, x1 + pad + 120, line_y + 8), radius=4, fill=accent)
    cta = "التفاصيل وطريقة التقديم داخل المقال"
    _draw_line(d, (x2 - pad, min(line_y + 42, y2 - 34)), cta, cta_font, primary, "ra")

    return Image.alpha_composite(canvas, overlay).convert("RGB")


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    role = first(job.get("job_title"), title, job.get("title"), default="job")
    employer = first(job.get("employer_name"), default="")
    digest = hashlib.sha1(f"{role}|{employer}".encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16) % 2_000_000_000
    filename = f"job-{digest[:14]}-{VERSION}.png"
    path = IMAGE_DIR / filename

    scene = generate_scene(build_prompt(job, title), seed)
    final = overlay_text(scene, job, title)
    final.save(path, "PNG", optimize=True)

    with Image.open(path) as check:
        if check.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Unexpected image size: {check.size}")
    if path.stat().st_size < 80_000:
        raise RuntimeError("Generated image looks unexpectedly small or blank")
    return str(path), f"{RAW_BASE}/{filename}"
