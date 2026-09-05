from __future__ import annotations

import io
import json
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageStat

UA = "Mozilla/5.0 (compatible; JordanJobsBrandBot/13.0; +https://jobsinjordan2026.blogspot.com/)"
TIMEOUT = (5, 10)

# Curated official homepages are seeds only. The resolver still discovers the
# actual logo/photo from the live official page at render time.
OFFICIAL_SEEDS = {
    "زين": ["https://www.jo.zain.com/arabic/pages/default.aspx?hl=ar"],
    "العميد": ["https://alameedcoffee.com/"],
    "المناصير": ["https://manaseergroup.com/Home/"],
    "جامعة عمان العربية": ["https://aau.edu.jo/"],
    "ابن الهيثم": ["https://ihh.com.jo/"],
    "سختيان": ["https://sukhtian.com/ar"],
    "حلاوة": ["https://www.halawatravel.com/"],
}

BLOCKED_HOST_BITS = (
    "facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "x.com", "twitter.com",
    "indeed.com", "jooble", "bayt.com", "akhtaboot", "tanqeeb", "wuzzuf", "blogspot.com",
    "jobsinjordan", "google.com", "bing.com", "youtube.com",
)

LOGO_HINTS = ("logo", "brand", "identity", "شعار")
PHOTO_HINTS = ("building", "office", "branch", "headquarter", "headquarters", "hq", "campus", "hospital", "store", "مبنى", "فرع", "مقر")


def clean_text(value: str) -> str:
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalized_employer(value: str) -> str:
    e = clean_text(value)
    replacements = [
        (r"العاديات السريعة.*", "مجموعة المناصير"),
        (r".*Alameed.*", "بن العميد"),
        (r".*\bZain\b.*", "زين الأردن"),
        (r".*جامعة\s+عمان\s+العربية.*", "جامعة عمان العربية"),
        (r".*ابن\s+الهيثم.*", "مستشفى ابن الهيثم"),
        (r".*Munir\s+Sukhtian.*", "مجموعة منير سختيان"),
        (r".*منير\s+سختيان.*", "مجموعة منير سختيان"),
        (r".*Halawa\s+Travel.*", "Halawa Travel & Tourism"),
        (r".*حلاوة.*(?:سياحة|سفر).*", "Halawa Travel & Tourism"),
    ]
    for pat, repl in replacements:
        if re.search(pat, e, re.I):
            return repl
    return e


def employer_key(value: str) -> str | None:
    e = normalized_employer(value).lower()
    tests = [
        ("جامعة عمان العربية", ("جامعة عمان العربية", "amman arab university")),
        ("ابن الهيثم", ("ابن الهيثم", "ibn al-haytham", "ibn alhaytham", "ihh")),
        ("سختيان", ("سختيان", "sukhtian")),
        ("حلاوة", ("halawa travel", "حلاوة")),
        ("زين", ("زين", "zain")),
        ("المناصير", ("المناصير", "manaseer")),
        ("العميد", ("العميد", "alameed", "al ameed")),
    ]
    for key, needles in tests:
        if any(n in e for n in needles):
            return key
    return None


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _blocked(url: str) -> bool:
    h = _host(url)
    return any(x in h for x in BLOCKED_HOST_BITS)


def candidate_pages(job: dict, employer: str) -> list[str]:
    key = employer_key(employer)
    pages: list[str] = []
    if key:
        pages.extend(OFFICIAL_SEEDS.get(key, []))
    for field in ("application_url", "source_original_url", "source_discovery_url"):
        value = clean_text(job.get(field) or "")
        if value and value.startswith(("http://", "https://")) and not _blocked(value):
            pages.append(value)
    out: list[str] = []
    seen: set[str] = set()
    for page in pages:
        if page not in seen:
            seen.add(page)
            out.append(page)
    return out[:8]


def _tokens(employer: str) -> list[str]:
    e = normalized_employer(employer).lower()
    raw = re.split(r"[^\u0621-\u064Aa-z0-9]+", e)
    stop = {"شركة", "مجموعة", "مؤسسة", "مستشفى", "جامعة", "الأردن", "الاردن", "jordan", "group", "company", "co", "ltd", "travel", "tourism"}
    return [x for x in raw if len(x) >= 3 and x not in stop][:8]


def _page_mentions_employer(soup: BeautifulSoup, employer: str) -> bool:
    tokens = _tokens(employer)
    if not tokens:
        return False
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "").lower()
    text = clean_text(soup.get_text(" ", strip=True)[:12000]).lower()
    hay = title + " " + text
    return any(t in hay for t in tokens)


def _jsonld_assets(soup: BeautifulSoup, base: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def walk(obj):
        if isinstance(obj, dict):
            typ = str(obj.get("@type") or "").lower()
            if "organization" in typ or "corporation" in typ or "educationalorganization" in typ or "hospital" in typ:
                logo = obj.get("logo")
                image = obj.get("image")
                for value, kind, score in ((logo, "logo", 320), (image, "photo", 210)):
                    if isinstance(value, dict):
                        value = value.get("url") or value.get("contentUrl")
                    if isinstance(value, list) and value:
                        value = value[0]
                    if isinstance(value, str) and value:
                        out.append((score, kind, urljoin(base, value)))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            walk(json.loads(tag.string or tag.get_text() or "{}"))
        except Exception:
            continue
    return out


def _candidate_assets(page: str, employer: str) -> list[tuple[int, str, str]]:
    try:
        r = requests.get(page, timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []

    trusted_page = _page_mentions_employer(soup, employer) or employer_key(employer) in OFFICIAL_SEEDS
    base_bonus = 35 if trusted_page else 0
    out: list[tuple[int, str, str]] = []
    out.extend(_jsonld_assets(soup, page))

    # Explicit social image: useful as a real institution photo when present.
    for selector, attr in [
        ("meta[property='og:image']", "content"),
        ("meta[name='twitter:image']", "content"),
    ]:
        el = soup.select_one(selector)
        if el and el.get(attr):
            out.append((165 + base_bonus, "photo", urljoin(page, el.get(attr))))

    # Explicit logo selectors and common logo-like images.
    for img in soup.find_all("img", src=True)[:220]:
        src = urljoin(page, img.get("src"))
        if not src.startswith(("http://", "https://")):
            continue
        attrs = " ".join([
            str(img.get("alt") or ""), str(img.get("title") or ""), str(img.get("class") or ""),
            str(img.get("id") or ""), src,
        ]).lower()
        score = base_bonus
        kind = "photo"
        if any(h in attrs for h in LOGO_HINTS):
            score += 230
            kind = "logo"
        if any(h in attrs for h in PHOTO_HINTS):
            score += 120
            kind = "photo"
        if any(t in attrs for t in _tokens(employer)):
            score += 120
        if score >= 150:
            out.append((score, kind, src))

    # Favicons are a last-resort brand mark, never treated as a photo.
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel:
            out.append((95 + base_bonus, "logo", urljoin(page, link.get("href"))))

    dedup: dict[tuple[str, str], int] = {}
    for score, kind, url in out:
        key = (kind, url)
        dedup[key] = max(score, dedup.get(key, 0))
    return sorted(((score, kind, url) for (kind, url), score in dedup.items()), reverse=True)


def _download(url: str, kind: str, referer: str | None = None) -> Image.Image | None:
    try:
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        r = requests.get(url, timeout=TIMEOUT, headers=headers)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if ctype and "image" not in ctype:
            return None
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

    w, h = im.size
    if kind == "logo":
        if w < 64 or h < 32:
            return None
        ratio = w / max(h, 1)
        if ratio < 0.18 or ratio > 10:
            return None
        return im

    if w < 600 or h < 300:
        return None
    ratio = w / max(h, 1)
    if ratio < 0.45 or ratio > 3.8:
        return None
    probe = im.convert("RGB").resize((96, 96))
    variance = sum(ImageStat.Stat(probe).var) / 3
    if variance < 110:
        return None
    return im


def fetch_brand_asset(job: dict) -> dict:
    employer = normalized_employer(job.get("employer_name") or job.get("employer") or "")
    best_logo = None
    best_photo = None

    for page in candidate_pages(job, employer):
        for score, kind, url in _candidate_assets(page, employer)[:14]:
            if kind == "logo" and best_logo is None:
                im = _download(url, "logo", page)
                if im is not None:
                    best_logo = {"kind": "logo", "image": im, "url": url, "page": page, "score": score}
            elif kind == "photo" and best_photo is None:
                im = _download(url, "photo", page)
                if im is not None:
                    best_photo = {"kind": "photo", "image": im, "url": url, "page": page, "score": score}
            if best_logo and best_photo:
                break
        if best_logo and best_photo:
            break

    # Prefer a real official photo when confidence is strong. Otherwise a logo
    # is safer and more faithful than an unrelated generic icon.
    if best_photo and best_photo["score"] >= 190:
        return best_photo
    if best_logo:
        return best_logo
    if best_photo:
        return best_photo
    return {"kind": "none", "image": None, "url": None, "page": None, "score": 0}
