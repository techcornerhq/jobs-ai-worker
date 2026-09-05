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
# The approved artwork is a fixed Jordan-themed master: Petra, Amman skyline,
# Jordan flags, مرصد الوظائف identity and subtle watermarks are baked into the asset.
# No AI/background variation is allowed. Only the vacancy title changes.
WIDTH, HEIGHT = 1280, 720
VERSION = "ai-v1"  # preserve existing Blogger/raw-GitHub image URL contract
IMAGE_DIR = Path("data/images")
RAW_BASE = "https://raw.githubusercontent.com/techcornerhq/jobs-ai-worker/main/data/images"
ASSET_DIR = Path(__file__).with_name("exact_template_asset")
MASTER_SIZE = (960, 540)
MASTER_SHA256 = "93c65e5def577fe64ef5e64b345121b5f9436662ed7e4b0007df917da3493f20"
ASSET_PARTS = 3

# Coordinates are for the final 1280x720 render. The central navy panel and icon
# are already part of the locked master. We render a gold "مطلوب" + white role.
TITLE_CENTER = (675, 350)
TITLE_MAX_WIDTH = 600
TITLE_MAX_HEIGHT = 78
TITLE_GAP = 12
PREFIX = "مطلوب"
WHITE = (255, 255, 255)
GOLD = (235, 178, 75)

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
        "/usr/share/opentype/noto/NotoSansArabic-ExtraBold.ttf",
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


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = _bbox(draw, text, font)
    return box[2] - box[0], box[3] - box[1]


def _draw_text(draw: ImageDraw.ImageDraw, xy, text: str, font, fill):
    rendered, kwargs = _display(text)
    draw.text(xy, rendered, font=font, fill=fill, anchor="mm", **kwargs)


def _fit_title_font(draw: ImageDraw.ImageDraw, role: str):
    for size in range(52, 24, -1):
        font = _font(size)
        role_w, role_h = _measure(draw, role, font)
        prefix_w, prefix_h = _measure(draw, PREFIX, font)
        if role_w + TITLE_GAP + prefix_w <= TITLE_MAX_WIDTH and max(role_h, prefix_h) <= TITLE_MAX_HEIGHT:
            return font
    return _font(24)


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
        raise RuntimeError(f"Approved مرصد الوظائف template checksum mismatch: {digest}")
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if image.size != MASTER_SIZE:
        raise RuntimeError(f"Unexpected approved master size: {image.size}")
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(job: dict, title: str) -> Image.Image:
    image = _master().copy()
    draw = ImageDraw.Draw(image)
    role = short(first(job.get("job_title"), title, job.get("title"), default="فرصة عمل جديدة"), 55)
    # Avoid a duplicated prefix if a source already writes "مطلوب ...".
    role = re.sub(r"^مطلوب(?:ة)?\s+", "", role).strip() or "فرصة عمل جديدة"
    font = _fit_title_font(draw, role)

    role_w, _ = _measure(draw, role, font)
    prefix_w, _ = _measure(draw, PREFIX, font)
    total_w = role_w + TITLE_GAP + prefix_w
    left = TITLE_CENTER[0] - total_w / 2
    role_x = left + role_w / 2
    prefix_x = left + role_w + TITLE_GAP + prefix_w / 2

    _draw_text(draw, (role_x, TITLE_CENTER[1]), role, font, WHITE)
    _draw_text(draw, (prefix_x, TITLE_CENTER[1]), PREFIX, font, GOLD)
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
    "VERSION", "IMAGE_DIR", "RAW_BASE", "MASTER_SHA256", "PREFIX"
]
