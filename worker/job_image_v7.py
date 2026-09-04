from __future__ import annotations

import job_image_v6 as base
from company_visual import fetch_official_photo


def generate(job: dict, title: str):
    original_fetch = base.fetch_company_photo
    base.IMAGE_VERSION = 'v7'
    base.fetch_company_photo = lambda j: fetch_official_photo(j) or original_fetch(j)
    try:
        return base.generate(job, title)
    finally:
        base.fetch_company_photo = original_fetch
