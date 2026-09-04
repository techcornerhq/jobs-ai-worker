from __future__ import annotations

from PIL import Image, ImageDraw

import job_image_v6 as base
from company_visual import fetch_official_photo
from job_image_v8 import arabic_job_phrase, departments, headline, safe_text


def neutral_fallback(employer: str = '') -> Image.Image:
    """Clean text-free fallback so the CTA can never overlap baked-in labels."""
    w, h = 900, 1100
    img = Image.new('RGB', (w, h), (7, 24, 39))
    d = ImageDraw.Draw(img)
    # decorative architecture/network only; deliberately no text or glyphs
    for i in range(7):
        x1 = 80 + i * 105
        y1 = 225 + (i % 2) * 45
        x2 = x1 + 64
        y2 = 760 - (i % 3) * 35
        d.rounded_rectangle((x1, y1, x2, y2), radius=14, outline=(214, 170, 83), width=5)
        d.rectangle((x1 + 12, y1 + 55, x2 - 12, y2 - 70), fill=(138, 112, 69))
    d.rectangle((65, 145, 815, 172), fill=(238, 199, 112))
    # network nodes in lower area
    nodes = [(120, 900), (290, 835), (470, 930), (650, 840), (790, 940)]
    for a, b in zip(nodes, nodes[1:]):
        d.line((a[0], a[1], b[0], b[1]), fill=(66, 133, 166), width=5)
    for x, y in nodes:
        d.ellipse((x-18, y-18, x+18, y+18), fill=(238, 199, 112))
    return img


def generate(job: dict, title: str):
    original_fetch = base.fetch_company_photo
    original_fallback = base.fallback_photo
    original_clean = base.clean
    original_headline = base.headline
    original_departments = base.departments

    base.IMAGE_VERSION = 'v9'
    # Only use a verified official photo; otherwise use our clean text-free visual.
    base.fetch_company_photo = lambda j: fetch_official_photo(j)
    base.fallback_photo = neutral_fallback
    base.clean = safe_text
    base.headline = headline
    base.departments = departments
    try:
        return base.generate(job, arabic_job_phrase(title))
    finally:
        base.fetch_company_photo = original_fetch
        base.fallback_photo = original_fallback
        base.clean = original_clean
        base.headline = original_headline
        base.departments = original_departments
