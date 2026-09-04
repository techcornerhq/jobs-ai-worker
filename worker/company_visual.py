from __future__ import annotations

import io
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

UA = 'Mozilla/5.0 (compatible; JordanJobsImageBot/4.0; +https://jobsinjordan2026.blogspot.com/)'

OFFICIAL_PAGES = {
    'زين': [
        'https://www.zain.com/en/media-center',
        'https://www.zain.com/ar/media-center',
        'https://eshop.jo.zain.com/en/press-releases?release=zain-opens-its-brand-new-store-in-irbid-239',
        'https://www.jo.zain.com/arabic/pages/default.aspx?hl=ar',
    ],
    'المناصير': [
        'https://manaseergroup.com/Home/',
        'https://manaseergroup.com/Home/about.php?language=2',
    ],
    'العميد': ['https://careers.alameedcoffee.com/jobs.php'],
}


def pages_for(job: dict) -> list[str]:
    pages = [job.get('source_original_url'), job.get('application_url')]
    emp = str(job.get('employer_name') or '')
    for key, vals in OFFICIAL_PAGES.items():
        if key in emp:
            pages.extend(vals)
    seen = set()
    return [str(x) for x in pages if x and not (str(x) in seen or seen.add(str(x)))]


def image_candidates(page: str, employer: str = '') -> list[tuple[int, str]]:
    try:
        r = requests.get(page, timeout=18, headers={'User-Agent': UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return []

    out: list[tuple[int, str]] = []
    for selector, attr in [
        ("meta[property='og:image']", 'content'),
        ("meta[name='twitter:image']", 'content'),
        ("link[rel='image_src']", 'href'),
    ]:
        el = soup.select_one(selector)
        if el and el.get(attr):
            out.append((40, urljoin(page, el.get(attr))))

    emp = employer.lower()
    for img in soup.find_all('img', src=True)[:180]:
        src = urljoin(page, img.get('src'))
        low = src.lower()
        alt = ' '.join([str(img.get('alt') or ''), str(img.get('title') or '')]).lower()
        if any(x in low for x in ['icon', 'sprite', 'avatar', 'favicon', 'logo-small', 'loader', 'pixel']):
            continue
        score = 10
        if 'زين' in employer or 'zain' in emp:
            if 'zain jordan' in alt or 'jordan headquarters' in alt or 'jordan hq' in alt or 'مقر زين الأردن' in alt:
                score += 200
            elif 'jordan' in alt and 'zain' in (alt + low):
                score += 120
            elif 'zain' in alt or 'zain' in low:
                score += 35
        if 'العميد' in employer and ('alameed' in alt or 'coffee' in alt or 'alameed' in low):
            score += 80
        if 'المناصير' in employer and ('manaseer' in alt or 'manaseer' in low):
            score += 80
        out.append((score, src))

    best: dict[str, int] = {}
    for score, url in out:
        best[url] = max(score, best.get(url, -1))
    return sorted(((s, u) for u, s in best.items()), reverse=True)


def fetch_official_photo(job: dict) -> Image.Image | None:
    employer = str(job.get('employer_name') or '')
    for page in pages_for(job):
        for _score, url in image_candidates(page, employer)[:70]:
            try:
                r = requests.get(url, timeout=18, headers={'User-Agent': UA, 'Referer': page})
                r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert('RGB')
                ratio = im.width / max(im.height, 1)
                if im.width < 650 or im.height < 380 or ratio > 3.8 or ratio < 0.42:
                    continue
                return im
            except Exception:
                continue
    return None
