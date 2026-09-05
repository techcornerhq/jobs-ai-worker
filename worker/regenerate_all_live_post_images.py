from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from ai_job_image_runtime import generate

SOURCE = Path("data/migration/live-blogger-posts-2026-09-05.json")
OUTPUT = Path("data/results/live-blogger-ai-images.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_one(index: int, item: dict) -> tuple[int, dict]:
    job = {
        "job_title": item.get("job_title"),
        "employer_name": item.get("employer_name"),
        "location_text": item.get("location_text"),
        "category_text": item.get("category_text"),
        "title": item.get("title"),
    }
    path, url = generate(job, item.get("job_title") or item.get("title") or "فرصة عمل جديدة")
    return index, {
        **item,
        "featured_image_path": path,
        "featured_image_url": url,
        "image_version": "ai-v1",
        "generated_at": now_iso(),
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = source.get("items") or []
    expected = int(source.get("count") or 0)
    if expected != 16 or len(items) != expected:
        raise RuntimeError(f"Expected complete 16-post snapshot; metadata={expected}, items={len(items)}")

    results_by_index: dict[int, dict] = {}
    failures = []
    # Keep concurrency intentionally low because the public image endpoint rate-limits bursts.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(render_one, idx, item): (idx, item) for idx, item in enumerate(items)}
        for future in as_completed(futures):
            idx, item = futures[future]
            try:
                out_idx, record = future.result()
                results_by_index[out_idx] = record
                print(f"DONE {len(results_by_index)}/{expected}: {item.get('post_id')} | {item.get('job_title')} -> {record.get('featured_image_url')}", flush=True)
            except Exception as exc:
                failures.append({"index": idx, "post_id": item.get("post_id"), "title": item.get("title"), "error": str(exc)})
                print(f"FAILED {item.get('post_id')}: {exc}", flush=True)

    results = [results_by_index[i] for i in range(expected) if i in results_by_index]
    payload = {
        "source": str(SOURCE),
        "generated_at": now_iso(),
        "count": len(results),
        "failure_count": len(failures),
        "failures": failures,
        "items": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures or len(results) != expected:
        raise RuntimeError(f"Live post image generation incomplete: {len(results)}/{expected}; failures={len(failures)}")
    print(json.dumps({"count": len(results), "failure_count": 0, "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
