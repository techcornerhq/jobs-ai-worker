from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from unified_job_template import IMAGE_DIR, RAW_BASE, VERSION, WIDTH, HEIGHT, first, render


def _production_filename(job: dict, title: str) -> str:
    role = first(job.get("job_title"), title, job.get("title"), default="job")
    employer = first(job.get("employer_name"), default="")
    location = first(job.get("location_text"), job.get("city"), job.get("governorate"), default="")
    # Preserve the exact digest contract used by ai_job_image_runtime so all existing
    # Blogger image URLs keep working when the artwork is replaced in-place.
    hash_employer = f"{employer}، {location}" if employer and location else employer
    digest = hashlib.sha1(f"{role}|{hash_employer}".encode("utf-8")).hexdigest()
    return f"job-{digest[:14]}-{VERSION}.png"


def generate(job: dict, title: str) -> tuple[str, str]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = _production_filename(job, title)
    path = IMAGE_DIR / filename
    final = render(job, title)
    final.save(path, "PNG", compress_level=6)

    with Image.open(path) as check:
        if check.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Unexpected unified template image size: {check.size}")
    if path.stat().st_size < 60_000:
        raise RuntimeError("Unified template image looks unexpectedly small or blank")
    return str(path), f"{RAW_BASE}/{filename}"


__all__ = ["generate", "_production_filename"]
