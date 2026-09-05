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

# FINAL LOCKED VISUAL SYSTEM
# The approved artwork is a fixed master image. Nothing in the background,
# composition, colors, flags, Petra, skyline, typography artwork or ornaments
# is regenerated. Only the vacancy title inside the existing burgundy strip changes.
WIDTH, HEIGHT = 1280, 720
VERSION = "ai-v1"  # keep the existing Blogger image URL contract unchanged
IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
ASSET_DIR = Path(__file__).with_name("exact_template_asset")
MASTER_SIZE = (960, 540)
MASTER_SHA256 = "ef48897a491f8b2aa0bc34420cafc311b6362cd8969c5021d24b51b50003c108"
TITLE_CENTER = (790, 397)
TITLE_MAX_WIDTH = 570
TITLE_MAX_HEIGHT = 66

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


def short(value: str, limit: int = 55) -> str:
    s = clean(value)
    if len(s) <= limit:
        return s
    cut = s[: limit + 1].rsplit(" ", 1)[0].strip()
    return (cut or s[:limit]).rstrip(" ،,؛:-") + "…"


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Black.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-ExtraBold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Black.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-ExtraBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/opentype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
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


def _bbox(draw: ImageDraw.ImageDraw, text: str, font):
    rendered, kwargs = _display(text)
    return draw.textbbox((0, 0), rendered, font=font, **kwargs)


def _draw_text(draw: ImageDraw.ImageDraw, xy, text: str, font):
    rendered, kwargs = _display(text)
    draw.text(xy, rendered, font=font, fill=(255, 255, 255), anchor="mm", **kwargs)


def _fit_title_font(draw: ImageDraw.ImageDraw, title: str):
    for size in range(48, 25, -1):
        font = _font(size)
        box = _bbox(draw, title, font)
        if (box[2] - box[0]) <= TITLE_MAX_WIDTH and (box[3] - box[1]) <= TITLE_MAX_HEIGHT:
            return font
    return _font(25)


@lru_cache(maxsize=1)
def _master() -> Image.Image:
    parts = sorted(ASSET_DIR.glob("*.b64"))
    if [p.name for p in parts] != [f"{i:02d}.b64" for i in range(9)]:
        raise RuntimeError("Exact approved template asset is incomplete")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != MASTER_SHA256:
        raise RuntimeError(f"Exact approved template checksum mismatch: {digest}")
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.size != MASTER_SIZE:
        raise RuntimeError(f"Unexpected exact master size: {image.size}")
    # Proportional upscale only. No crop, redraw, recolor or generative processing.
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(job: dict, title: str) -> Image.Image:
    image = _master().copy()
    draw = ImageDraw.Draw(image)
    role = short(first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة"), 55)
    font = _fit_title_font(draw, role)
    _draw_text(draw, TITLE_CENTER, role, font)
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
