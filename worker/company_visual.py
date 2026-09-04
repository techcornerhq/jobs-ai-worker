from __future__ import annotations

import io
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageStat

UA = 'Mozilla/5.0 (compatible; JordanJobsImageBot/5.0; +https://jobsinjordan2026.blogspot.com/)'

PREFERRED_IMAGES = {
    'زين': [
        ('https://d30ezutk4plts9.cloudfront.net/media/original_images/ZainJordan_HQ.jpg', 'https://www.zain.com/en/media-center'),
    ],
    'العميد': [
        ('https://alameedcoffee.com/uploads/2024/09/5592611f-07da-66eaa438bd73-861x565.jpg', 'https://alameedcoffee.com/en/news/Weibdeh-Branch-Opening'),
    ],
}

OFFICIAL_PAGES = {
    'زين': [
        'https://www.zain.com/en/media-center',
        'https://www.zain.com/ar/media-center',
        'https://www.jo.zain.com/arabic/pages/default.aspx?hl=ar',
    ],
    'المناصير': [
        'https://manaseergroup.com/Home/',
        'https://manaseergroup.com/Home/about.php?language=2',
        'https://manaseer-ic.com/',
    ],
    'العميد': [
        'https://careers.alameedcoffee.com/jobs.php',
        'https://alameedcoffee.com/en/news/Weibdeh-Branch-Opening',
    ],
}


def normalized_employer(value: str) -> str:
    e = str(value or '').strip()
    if 'العاديات السريعة' in e:
        return 'مجموعة المناصير'
    if 'Alameed' in e or 'العميد' in e:
        return 'بن العميد'
    if re.search(r'\bZain\b', e, re.I) or 'زين' in e:
        return 'زين الأردن'
    return e


def employer_key(value: str) -> str | None:
    e = normalized_employer(value)
    for key in ('زين', 'المناصير', 'العميد'):
        if key in e:
            return key
    return None


def pages_for(job: dict) -> list[str]:
    pages = [job.get('source_original_url'), job.get('application_url')]
    key = employer_key(job.get('employer_name') or '')
    if key:
        pages.extend(OFFICIAL_PAGES.get(key, []))
    seen: set[str] = set()
    out: list[str] = []
    for x in pages:
        if not x:
            continue
        s = str(x)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _same_host_or_subdomain(page: str, image_url: str) -> bool:
    try:
        p = urlparse(page).hostname or ''
        i = urlparse(image_url).hostname or ''
        return i == p or i.endswith('.' + p) or p.endswith('.' + i)
    except Exception:
        return False


def image_candidates(page: str, employer: str = '') -> list[tuple[int, str]]:
    try:
        r = requests.get(page, timeout=(5, 8), headers={'User-Agent': UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return []

    norm = normalized_employer(employer).lower()
    key = employer_key(employer)
    out: list[tuple[int, str]] = []

    for selector, attr in [
        ("meta[property='og:image']", 'content'),
        ("meta[name='twitter:image']", 'content'),
        ("link[rel='image_src']", 'href'),
    ]:
        el = soup.select_one(selector)
        if el and el.get(attr):
            url = urljoin(page, el.get(attr))
            score = 55 if _same_host_or_subdomain(page, url) else 25
            out.append((score, url))

    for img in soup.find_all('img', src=True)[:140]:
        src = urljoin(page, img.get('src'))
        low = src.lower()
        alt = ' '.join([str(img.get('alt') or ''), str(img.get('title') or '')]).lower()
        if any(x in low for x in ['icon', 'sprite', 'avatar', 'favicon', 'logo-small', 'loader', 'pixel', 'captcha']):
            continue
        score = 0
        if _same_host_or_subdomain(page, src):
            score += 15
        if key == 'زين':
            if 'zain jordan' in alt or 'jordan headquarters' in alt or 'jordan hq' in alt or 'مقر زين الأردن' in alt:
                score += 220
            elif 'jordan' in alt and 'zain' in (alt + low):
                score += 140
            elif 'zain' in (alt + low):
                score += 75
        elif key == 'العميد':
            if any(x in (alt + ' ' + low) for x in ['alameed', 'al ameed', 'العميد']):
                score += 120
            elif any(x in (alt + ' ' + low) for x in ['coffee', 'branch', 'cafe']):
                score += 70
        elif key == 'المناصير':
            if any(x in (alt + ' ' + low) for x in ['manaseer', 'مناصير']):
                score += 140
            elif any(x in (alt + ' ' + low) for x in ['building', 'headquarter', 'showroom', 'machinery']):
                score += 75
        else:
            tokens = [t for t in re.split(r'\W+', norm) if len(t) >= 4][:4]
            if tokens and any(t in (alt + ' ' + low) for t in tokens):
                score += 80

        if score >= 60:
            out.append((score, src))

    best: dict[str, int] = {}
    for score, url in out:
        best[url] = max(score, best.get(url, -1))
    return sorted(((s, u) for u, s in best.items()), reverse=True)


def _looks_like_real_photo(im: Image.Image) -> bool:
    if im.width < 650 or im.height < 380:
        return False
    ratio = im.width / max(im.height, 1)
    if ratio > 3.8 or ratio < 0.42:
        return False
    probe = im.resize((96, 96)).convert('RGB')
    stat = ImageStat.Stat(probe)
    # Reject nearly blank/flat banners while accepting normal photography.
    if sum(stat.var) / 3 < 160:
        return False
    return True


def _download_image(url: str, referer: str | None = None) -> Image.Image | None:
    try:
        headers = {'User-Agent': UA}
        if referer:
            headers['Referer'] = referer
        r = requests.get(url, timeout=(5, 10), headers=headers)
        r.raise_for_status()
        ctype = (r.headers.get('content-type') or '').lower()
        if ctype and 'image' not in ctype:
            return None
        im = Image.open(io.BytesIO(r.content)).convert('RGB')
        return im if _looks_like_real_photo(im) else None
    except Exception:
        return None


def fetch_official_photo(job: dict) -> Image.Image | None:
    employer = normalized_employer(job.get('employer_name') or '')
    key = employer_key(employer)

    if key:
        for url, referer in PREFERRED_IMAGES.get(key, []):
            im = _download_image(url, referer)
            if im is not None:
                return im

    for page in pages_for({**job, 'employer_name': employer}):
        for score, url in image_candidates(page, employer)[:10]:
            if score < 60:
                continue
            im = _download_image(url, page)
            if im is not None:
                return im
    return None
