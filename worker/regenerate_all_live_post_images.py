from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ai_job_image_runtime import generate

SOURCE = Path("data/migration/live-blogger-posts-2026-09-05.json")
OUTPUT = Path("data/results/live-blogger-ai-images.json")
EXPECTED = 16


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_cached(record: dict) -> bool:
    try:
        path = Path(record.get("featured_image_path") or "")
        url = str(record.get("featured_image_url") or "")
        if "-ai-v1.png" not in url or not path.exists() or path.stat().st_size <= 80_000:
            return False
        with Image.open(path) as im:
            return im.size == (1536, 1024)
    except Exception:
        return False


def save_payload(items: list[dict], failures: list[dict]) -> None:
    payload = {
        "source": str(SOURCE),
        "generated_at": now_iso(),
        "count": len(items),
        "failure_count": len(failures),
        "failures": failures,
        "items": items,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = source.get("items") or []
    expected = int(source.get("count") or 0)
    if expected != EXPECTED or len(items) != EXPECTED:
        raise RuntimeError(f"Expected complete {EXPECTED}-post snapshot; metadata={expected}, items={len(items)}")

    cached_by_post: dict[str, dict] = {}
    if OUTPUT.exists():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
            for record in old.get("items") or []:
                pid = str(record.get("post_id") or "")
                if pid and valid_cached(record):
                    cached_by_post[pid] = record
        except Exception as exc:
            print(f"Ignoring unreadable previous checkpoint: {exc}", flush=True)

    results: list[dict] = []
    failures: list[dict] = []

    for idx, item in enumerate(items, 1):
        post_id = str(item.get("post_id") or "")
        cached = cached_by_post.get(post_id)
        if cached:
            results.append(cached)
            print(f"CACHED {idx}/{expected}: {post_id} | {item.get('job_title')}", flush=True)
            continue

        try:
            job = {
                "job_title": item.get("job_title"),
                "employer_name": item.get("employer_name"),
                "location_text": item.get("location_text"),
                "category_text": item.get("category_text"),
                "title": item.get("title"),
            }
            path, url = generate(job, item.get("job_title") or item.get("title") or "فرصة عمل جديدة")
            record = {
                **item,
                "featured_image_path": path,
                "featured_image_url": url,
                "image_version": "ai-v1",
                "generated_at": now_iso(),
            }
            if not valid_cached(record):
                raise RuntimeError("Generated image failed local validation")
            results.append(record)
            print(f"DONE {idx}/{expected}: {post_id} | {item.get('job_title')} -> {url}", flush=True)
        except Exception as exc:
            failures.append({"post_id": post_id, "title": item.get("title"), "error": str(exc)})
            print(f"FAILED {idx}/{expected}: {post_id}: {exc}", flush=True)

        # Persist a local checkpoint after each job. The workflow commits this even if
        # one provider queue fails, so a retry only needs to generate the missing post.
        save_payload(results, failures)

        # Deliberately pace the public image endpoint to reduce rate-limit bursts.
        if idx < expected:
            time.sleep(10)

    save_payload(results, failures)
    print(json.dumps({
        "count": len(results),
        "failure_count": len(failures),
        "complete": len(results) == expected and not failures,
        "output": str(OUTPUT),
    }, ensure_ascii=False), flush=True)

    # Do not fail this generation step on a partial provider outage. The workflow
    # commits the checkpoint first, then the validation step marks the run incomplete.


if __name__ == "__main__":
    main()
