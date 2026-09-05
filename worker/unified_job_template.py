from __future__ import annotations

import base64
import hashlib
import io
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

# FINAL LOCKED MARSAD AL-WAZAAEF VISUAL SYSTEM
# Approved visual = the user-approved "إعلان توظيف" poster.
# Fixed: Petra, Amman skyline, Jordan flags, مرصد الوظائف identity, watermarks,
# "إعلان توظيف" headline and all decorative elements.
# Variable: vacancy title inside the maroon application bar only.
WIDTH, HEIGHT = 1280, 720
VERSION = "ai-v1"  # preserve existing Blogger/raw-GitHub URL contract
IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
ASSET_DIR = Path(__file__).with_name("exact_template_asset")
MASTER_SIZE = (720, 405)
MASTER_SHA256 = "456d02ba6411390c3415855732299b04ec5d8d9bcb333c5359418528da60bb52"
ASSET_PARTS = 6

# The approved artwork already contains the full red/gold bar and chevron.
# We repaint only its text-safe interior so the original sample title is removed,
# then draw the current vacancy title without altering any other design element.
BAR_BOX = (486, 375, 1018, 446)
BAR_RADIUS = 28
TITLE_CENTER = (752, 410)
TITLE_MAX_WIDTH = 485
TITLE_MAX_HEIGHT = 53
MAROON_LEFT = (122, 6, 19)
MAROON_RIGHT = (62, 1, 7)
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


def short(value: str, limit: int = 58) -> str:
    s = clean(value)
    if len(s) <= limit:
        return s
    cut = s[: limit + 1].rsplit(" ", 1)[0].strip()
    return (cut or s[:limit]).rstrip(" ،,؛:-") + "…"


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Black.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-ExtraBold.ttf",
        "/usr/share/opentype/noto/NotoSansArabic-Black.ttf",
        "/usr/share/opentype/noto/NotoSansArabic-ExtraBold.ttf",
        "/usr/share/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/opentype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
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


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    rendered, kwargs = _display(text)
    box = draw.textbbox((0, 0), rendered, font=font, **kwargs)
    return box[2] - box[0], box[3] - box[1]


def _draw_text(draw: ImageDraw.ImageDraw, xy, text: str, font, fill):
    rendered, kwargs = _display(text)
    draw.text(xy, rendered, font=font, fill=fill, anchor="mm", **kwargs)


def _fit_title_font(draw: ImageDraw.ImageDraw, role: str):
    for size in range(38, 20, -1):
        font = _font(size)
        w, h = _measure(draw, role, font)
        if w <= TITLE_MAX_WIDTH and h <= TITLE_MAX_HEIGHT:
            return font
    return _font(20)


def _paint_bar_text_area(image: Image.Image) -> None:
    x1, y1, x2, y2 = BAR_BOX
    w, h = x2 - x1, y2 - y1

    grad = Image.new("RGB", (w, 1))
    px = grad.load()
    for x in range(w):
        t = x / max(1, w - 1)
        px[x, 0] = tuple(
            round(MAROON_LEFT[i] * (1 - t) + MAROON_RIGHT[i] * t)
            for i in range(3)
        )
    grad = grad.resize((w, h))

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=BAR_RADIUS, fill=255)
    image.paste(grad, (x1, y1), mask)


@lru_cache(maxsize=1)
def _master() -> Image.Image:
    parts = sorted(ASSET_DIR.glob("*.b64"))
    expected = [f"{i:02d}.b64" for i in range(ASSET_PARTS)]
    if [p.name for p in parts] != expected:
        raise RuntimeError(f"Approved مرصد الوظائف template asset is incomplete: {[p.name for p in parts]}")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != MASTER_SHA256:
        raise RuntimeError(f"Approved مرصد الوظائف master checksum mismatch: {digest}")
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.size != MASTER_SIZE:
        raise RuntimeError(f"Unexpected approved master size: {image.size}")
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(job: dict, title: str) -> Image.Image:
    image = _master().copy()
    _paint_bar_text_area(image)
    draw = ImageDraw.Draw(image)

    role = short(first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة"), 58)
    role = re.sub(r"^(?:مطلوب(?:ة)?|إعلان\s+توظيف)\s*[:\-–—]?\s*", "", role).strip() or "فرصة عمل جديدة"
    font = _fit_title_font(draw, role)
    _draw_text(draw, TITLE_CENTER, role, font, WHITE)
    return image


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    role = first(job.get("job_title"), title, job.get("title"), default="job")
    employer = first(job.get("employer_name"), default="")
    digest = hashlib.sha1(f"{role}|{employer}".encode("utf-8")).hexdigest()[:24]
    path = IMAGE_DIR / f"{digest}-{VERSION}.png"
    render(job, title).save(path, "PNG", optimize=True)
    return str(path), f"{RAW_BASE}/{path.name}"


__all__ = [
    "generate", "render", "clean", "first", "short", "WIDTH", "HEIGHT",
    "VERSION", "IMAGE_DIR", "RAW_BASE", "MASTER_SHA256"
]
