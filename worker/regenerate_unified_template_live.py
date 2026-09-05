from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from unified_job_template import WIDTH, HEIGHT, MASTER_SHA256
from unified_template_runtime import generate

SOURCE = Path("data/migration/live-blogger-posts-2026-09-05.json")
CURRENT_MAP = Path("data/results/live-blogger-ai-images.json")
OUTPUT = Path("data/results/live-blogger-ai-images.json")
EXPECTED = 16
IMAGE_SYSTEM = "marsad-approved-poster-v3"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def basename(url: str) -> str:
    return Path(urlparse(str(url or "")).path).name


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = source.get("items") or []
    if int(source.get("count") or 0) != EXPECTED or len(items) != EXPECTED:
        raise RuntimeError(f"Expected {EXPECTED} live posts, got {len(items)}")

    current = json.loads(CURRENT_MAP.read_text(encoding="utf-8")) if CURRENT_MAP.exists() else {"items": []}
    current_by_id = {str(x.get("post_id")): x for x in current.get("items") or []}

    results = []
    for idx, item in enumerate(items, 1):
        post_id = str(item.get("post_id") or "")
        job = {
            "job_title": item.get("job_title"),
            "employer_name": item.get("employer_name"),
            "location_text": item.get("location_text"),
            "category_text": item.get("category_text"),
            "title": item.get("title"),
        }
        path, url = generate(job, item.get("job_title") or item.get("title") or "فرصة عمل جديدة")
        p = Path(path)
        if not p.exists() or p.stat().st_size < 60_000:
            raise RuntimeError(f"Invalid generated image for {post_id}: {p}")
        with Image.open(p) as im:
            if im.size != (WIDTH, HEIGHT):
                raise RuntimeError(f"Invalid dimensions for {post_id}: {im.size}")

        old = current_by_id.get(post_id) or {}
        old_name = basename(old.get("featured_image_url"))
        new_name = basename(url)
        if old_name and old_name != new_name:
            raise RuntimeError(
                f"Production URL contract changed for {post_id}: old={old_name}, new={new_name}"
            )

        results.append({
            **item,
            "featured_image_path": path,
            "featured_image_url": url,
            "image_version": IMAGE_SYSTEM,
            "brand": "مرصد الوظائف",
            "master_sha256": MASTER_SHA256,
            "background_variation_allowed": False,
            "only_variable": "job_title",
            "fixed_headline": "إعلان توظيف",
            "generated_at": now_iso(),
        })
        print(f"MARSAD {idx}/{EXPECTED}: {post_id} | {item.get('job_title')} -> {new_name}", flush=True)

    payload = {
        "source": str(SOURCE),
        "generated_at": now_iso(),
        "count": len(results),
        "failure_count": 0,
        "failures": [],
        "image_system": IMAGE_SYSTEM,
        "brand": "مرصد الوظائف",
        "master_sha256": MASTER_SHA256,
        "background_variation_allowed": False,
        "only_variable": "job_title",
        "fixed_headline": "إعلان توظيف",
        "items": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(results), "complete": len(results) == EXPECTED, "brand": "مرصد الوظائف"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
