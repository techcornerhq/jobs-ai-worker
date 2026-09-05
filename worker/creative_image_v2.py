from __future__ import annotations

import copy
import hashlib
import io
import os
import random
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

import ai_job_image as base
import ai_job_image_runtime as runtime

WIDTH, HEIGHT = 1536, 1024
VERSION = "ai-v2"
UA = "JordanJobsCreativeImage/2.0"

# runtime import has already installed the resilient multi-model AI scene generator
_AI_SCENE = base.generate_scene
_BASE_OVERLAY = base.overlay_text
_BASE_VERSION = base.VERSION


def _role(job: dict, title: str) -> str:
    return base.first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة")


def _employer(job: dict) -> str:
    return base.first(job.get("employer_name"), default="")


def _location(job: dict) -> str:
    return base.first(job.get("location_text"), job.get("city"), job.get("governorate"), default="الأردن")


def _query_for_role(job: dict, title: str) -> str:
    role = _role(job, title)
    low = role.lower()
    cat, _ = base.visual_category(job, role)

    specific = [
        (("أشعة", "radiolog"), "radiologist doctor MRI CT hospital"),
        (("سائق باص", "bus driver"), "professional bus driver city bus"),
        (("أمين مستودع", "warehouse keeper", "storekeeper"), "warehouse worker inventory scanner logistics"),
        (("منسق بضائع", "merchandise coordinator"), "retail merchandise inventory worker shelves"),
        (("سكرت", "secretary"), "professional executive secretary modern office"),
        (("موارد بشرية", "human resources", "hr officer"), "human resources professional modern office interview"),
        (("باحث اجتماعي", "social worker"), "social worker counseling professional office"),
        (("حجوزات", "ticketing", "travel agent"), "travel agent airline reservations office"),
        (("مطور", "developer", "software"), "software developer coding modern office"),
        (("محاسب", "accountant"), "accountant finance professional office reports"),
        (("صيانة", "mechanic", "maintenance"), "maintenance technician industrial workshop safety gear"),
        (("مبيعات", "sales"), "sales professional helping customer modern retail"),
        (("خدمة عملاء", "customer service"), "customer service professional helping client office"),
        (("تمريض", "nurse"), "professional nurse hospital healthcare"),
        (("طبيب", "doctor"), "professional doctor hospital healthcare"),
    ]
    for needles, q in specific:
        if any(n in low for n in needles):
            return q

    by_cat = {
        "medical": "healthcare professional hospital working",
        "technology": "technology professional modern office laptop",
        "education": "education professional university campus office",
        "finance": "finance professional accounting modern office",
        "office": "administrative professional modern office working",
        "sales": "sales customer service professional workplace",
        "travel": "travel agent airline reservation office",
        "industrial": "engineer technician industrial workplace safety gear",
        "logistics": "warehouse logistics worker inventory professional",
        "hospitality": "hospitality professional hotel restaurant working",
        "field": "professional driver field worker urban workplace",
        "general": "professional employee modern workplace working",
    }
    return by_cat.get(cat, by_cat["general"])


def _download_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": UA})
        r.raise_for_status()
        if "image" not in (r.headers.get("content-type") or "").lower():
            return None
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        if im.width < 900 or im.height < 500:
            return None
        return im
    except Exception:
        return None


def _visual_score(im: Image.Image) -> float:
    probe = ImageOps.fit(im.convert("RGB"), (640, 426), method=Image.Resampling.LANCZOS)
    gray = probe.convert("L")
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0]
    variance = stat.var[0]
    edge = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    # Favor detailed, well-exposed photographs; heavily dark/washed-out images lose points.
    exposure = max(0.0, 100.0 - abs(mean - 125.0) * 0.9)
    detail = min(100.0, variance / 10.0 + edge * 2.2)
    return exposure * 0.45 + detail * 0.55


def _pexels_scene(job: dict, title: str, seed: int) -> Image.Image | None:
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return None
    query = _query_for_role(job, title)
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "orientation": "landscape", "size": "large", "per_page": 12},
            headers={"Authorization": key, "User-Agent": UA},
            timeout=35,
        )
        r.raise_for_status()
        photos = r.json().get("photos") or []
    except Exception as exc:
        print(f"Pexels unavailable; falling back to AI: {str(exc)[:180]}", flush=True)
        return None

    if not photos:
        return None

    # Evaluate several relevant results rather than blindly using result #1.
    candidates: list[tuple[float, Image.Image]] = []
    order = list(range(min(len(photos), 8)))
    random.Random(seed).shuffle(order)
    for idx in order[:6]:
        p = photos[idx]
        src = p.get("src") or {}
        url = src.get("large2x") or src.get("large") or src.get("landscape")
        if not url:
            continue
        im = _download_image(url)
        if im is None:
            continue
        score = _visual_score(im)
        # Slightly favor the API's relevance ordering while still selecting by quality.
        score += max(0, 10 - idx) * 1.2
        candidates.append((score, im))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"V2 source: Pexels query='{query}' score={candidates[0][0]:.1f}", flush=True)
    return candidates[0][1]


def _premium_prompt(job: dict, title: str) -> str:
    role = _role(job, title)
    cat, scene = base.visual_category(job, role)
    return (
        f"Premium editorial recruitment campaign photograph for the job role: {role}. "
        f"Role category: {cat}. Scene: {scene}. "
        "Show a clearly recognizable professional actively doing the job, not posing for a generic stock photo. "
        "Natural candid expression, realistic anatomy and hands, authentic workplace details, tasteful wardrobe, believable lighting, "
        "35mm editorial photography, shallow but realistic depth of field, strong subject separation, premium commercial composition. "
        "Avoid empty rooms, generic corporate handshakes, fake documents, exaggerated cinematic effects, plastic skin, malformed fingers, duplicated people, clutter. "
        "No readable text, no logos, no watermarks, no posters, no UI screens with text. "
        "Landscape 3:2, sophisticated, modern, trustworthy, visually striking but realistic."
    )


def _ai_scene(job: dict, title: str, seed: int) -> Image.Image:
    prompt = _premium_prompt(job, title)
    first = _AI_SCENE(prompt, seed)
    first_score = _visual_score(first)
    # Only spend a second generation when the first scene is objectively weak.
    if first_score >= 52:
        print(f"V2 source: AI score={first_score:.1f}", flush=True)
        return first
    try:
        second = _AI_SCENE(prompt + " Use a different camera angle and stronger human focal subject.", seed + 7919)
        second_score = _visual_score(second)
        print(f"V2 source: AI candidates={first_score:.1f}/{second_score:.1f}", flush=True)
        return second if second_score > first_score else first
    except Exception:
        return first


def _font(size: int, bold: bool = False):
    return base._font(size, bold)


def _draw_text(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, anchor="ra"):
    text = str(text or "")
    for token in ("•", "·", "▪", "▫", "|"):
        text = text.replace(token, " ")
    rendered, kwargs = base._display_text(text)
    draw.text(xy, rendered, font=font, fill=fill, anchor=anchor, **kwargs)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 2):
    return base._wrap(draw, text, font, max_width, max_lines)


def _fit_title(draw: ImageDraw.ImageDraw, text: str, max_width: int):
    for size in range(72, 43, -2):
        f = _font(size, True)
        lines = _wrap(draw, text, f, max_width, 2)
        if lines and all((base._text_bbox(draw, ln, f)[2] - base._text_bbox(draw, ln, f)[0]) <= max_width for ln in lines):
            return f, lines
    f = _font(44, True)
    return f, _wrap(draw, base.short(text, 60), f, max_width, 2)


def _bottom_gradient(size: tuple[int, int], top_y: int) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    px = layer.load()
    span = max(1, h - top_y)
    for y in range(top_y, h):
        t = (y - top_y) / span
        # Smooth cubic curve: nearly invisible at top, deep navy at bottom.
        a = int(235 * (t * t * (3 - 2 * t)))
        for x in range(w):
            px[x, y] = (3, 19, 35, a)
    return layer


def overlay_v2(scene: Image.Image, job: dict, title: str) -> Image.Image:
    canvas = ImageOps.fit(scene.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.48)).convert("RGBA")
    # Gentle clarity treatment instead of a box-heavy poster treatment.
    canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
    overlay = _bottom_gradient((WIDTH, HEIGHT), 410)
    d = ImageDraw.Draw(overlay)

    role = base.short(_role(job, title), 66)
    employer = base.short(_employer(job), 40)
    location = base.short(_location(job), 24)
    cat, _ = base.visual_category(job, role)

    # Small lightweight badge only; the photograph remains the dominant visual.
    badge_text = "فرصة عمل"
    badge_font = _font(24, True)
    badge_w = 180
    badge_box = (WIDTH - 64 - badge_w, 54, WIDTH - 64, 108)
    d.rounded_rectangle(badge_box, radius=27, fill=(7, 127, 117, 235))
    _draw_text(d, (WIDTH - 64 - badge_w / 2, 82), badge_text, badge_font, (255, 255, 255, 255), anchor="mm")

    # Category-specific micro-accent; this creates variation without becoming a fixed template.
    accents = {
        "medical": (30, 173, 183, 255), "technology": (68, 125, 220, 255),
        "education": (180, 133, 45, 255), "finance": (49, 150, 112, 255),
        "office": (111, 91, 180, 255), "sales": (220, 113, 54, 255),
        "travel": (37, 150, 190, 255), "industrial": (210, 139, 44, 255),
        "logistics": (75, 132, 157, 255), "hospitality": (185, 82, 120, 255),
        "field": (104, 132, 70, 255), "general": (7, 127, 117, 255),
    }
    accent = accents.get(cat, accents["general"])

    margin = 72
    right = WIDTH - margin
    max_width = 1120
    title_font, lines = _fit_title(d, role, max_width)
    y = HEIGHT - 335

    # Thin accent rule, not a card.
    d.rounded_rectangle((right - 120, y - 24, right, y - 14), radius=5, fill=accent)
    for line in lines:
        _draw_text(d, (right, y), line, title_font, (255, 255, 255, 255), "ra")
        bbox = base._text_bbox(d, line, title_font)
        y += (bbox[3] - bbox[1]) + 16

    meta = "، ".join([x for x in (employer, location) if x])
    if meta:
        y += 2
        meta_font = _font(29, True)
        _draw_text(d, (right, y), meta, meta_font, (226, 236, 242, 255), "ra")
        bbox = base._text_bbox(d, meta, meta_font)
        y += (bbox[3] - bbox[1]) + 25

    cta_font = _font(23, True)
    _draw_text(d, (right, min(y + 8, HEIGHT - 74)), "التفاصيل وطريقة التقديم داخل المقال", cta_font, (250, 205, 95, 255), "ra")

    result = Image.alpha_composite(canvas, overlay).convert("RGB")
    return result


def _scene(job: dict, title: str, prompt: str, seed: int) -> Image.Image:
    pexels = _pexels_scene(job, title, seed)
    if pexels is not None:
        return pexels
    return _ai_scene(job, title, seed)


def generate(job: dict, title: str):
    # Reuse the proven filename/validation path from v1 while replacing both creative source and overlay.
    original_scene = base.generate_scene
    original_overlay = base.overlay_text
    original_version = base.VERSION
    base.generate_scene = lambda prompt, seed: _scene(job, title, prompt, seed)
    base.overlay_text = overlay_v2
    base.VERSION = VERSION
    try:
        return runtime.generate(copy.deepcopy(job), title)
    finally:
        base.generate_scene = original_scene
        base.overlay_text = original_overlay
        base.VERSION = original_version


__all__ = ["generate"]
