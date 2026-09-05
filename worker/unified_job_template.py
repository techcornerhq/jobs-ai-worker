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
# Variable: vacancy title inside the original maroon application bar only.
WIDTH, HEIGHT = 1280, 720
VERSION = "ai-v1"  # preserve existing Blogger/raw-GitHub URL contract
IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
ASSET_DIR = Path(__file__).with_name("exact_template_asset")
MASTER_SIZE = (720, 405)
MASTER_SHA256 = "456d02ba6411390c3415855732299b04ec5d8d9bcb333c5359418528da60bb52"
# 03.b64 is an obsolete interrupted-upload fragment and is intentionally ignored.
ASSET_FILES = ("00.b64", "01.b64", "02.b64", "03a.b64", "03b.b64", "04.b64", "05.b64")

# Coordinates on the final 1280x720 render. Only the original title pixels are
# reconstructed from clean pixels immediately above/below them. The original
# pill, gold border and chevron remain untouched.
ERASE_X1, ERASE_X2 = 485, 1065
ERASE_Y1, ERASE_Y2 = 390, 438
SAMPLE_TOP_Y, SAMPLE_BOTTOM_Y = 385, 445
EDGE_FEATHER = 20
TITLE_CENTER = (775, 413)
TITLE_MAX_WIDTH = 535
TITLE_MAX_HEIGHT = 50
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
    for size in range(36, 19, -1):
        font = _font(size)
        w, h = _measure(draw, role, font)
        if w <= TITLE_MAX_WIDTH and h <= TITLE_MAX_HEIGHT:
            return font
    return _font(19)


def _erase_original_bar_title(image: Image.Image) -> None:
    """Remove only the sample vacancy text while retaining the approved bar artwork."""
    px = image.load()
    for x in range(ERASE_X1, ERASE_X2 + 1):
        top = px[x, SAMPLE_TOP_Y]
        bottom = px[x, SAMPLE_BOTTOM_Y]
        edge_alpha = min(1.0, (x - ERASE_X1) / EDGE_FEATHER, (ERASE_X2 - x) / EDGE_FEATHER)
        edge_alpha = max(0.0, edge_alpha)
        for y in range(ERASE_Y1, ERASE_Y2 + 1):
            t = (y - ERASE_Y1) / max(1, ERASE_Y2 - ERASE_Y1)
            reconstructed = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            original = px[x, y]
            px[x, y] = tuple(round(original[i] * (1 - edge_alpha) + reconstructed[i] * edge_alpha) for i in range(3))


@lru_cache(maxsize=1)
def _master() -> Image.Image:
    parts = [ASSET_DIR / name for name in ASSET_FILES]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise RuntimeError(f"Approved مرصد الوظائف template asset is incomplete: {missing}")
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
    _erase_original_bar_title(image)
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
