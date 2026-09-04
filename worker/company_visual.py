from __future__ import annotations

import io
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

UA = 'Mozilla/5.0 (compatible; JordanJobsImageBot/3.0; +https://jobsinjordan2026.blogspot.com/)'

OFFICIAL_PAGES = {
    'زين': [
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


def image_urls(page: str) -> list[str]:
    try:
        r = requests.get(page, timeout=15, headers={'User-Agent': UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return []
    out = []
    for selector, attr in [
        ("meta[property='og:image']", 'content'),
        ("meta[name='twitter:image']", 'content'),
        ("link[rel='image_src']", 'href'),
    ]:
        el = soup.select_one(selector)
        if el and el.get(attr):
            out.append(urljoin(page, el.get(attr)))
    for img in soup.find_all('img', src=True)[:100]:
        src = urljoin(page, img.get('src'))
        low = src.lower()
        if any(x in low for x in ['icon', 'sprite', 'avatar', 'favicon', 'logo-small']):
            continue
        out.append(src)
    seen = set()
    return [u for u in out if not (u in seen or seen.add(u))]


def fetch_official_photo(job: dict) -> Image.Image | None:
    for page in pages_for(job):
        for url in image_urls(page)[:40]:
            try:
                r = requests.get(url, timeout=15, headers={'User-Agent': UA})
                r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert('RGB')
                ratio = im.width / max(im.height, 1)
                if im.width < 650 or im.height < 380 or ratio > 3.4 or ratio < 0.45:
                    continue
                return im
            except Exception:
                continue
    return None
