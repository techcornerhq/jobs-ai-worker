from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_job_image_runtime import generate

SOURCE = Path("data/results/ui-migration.json")
OUTPUT = Path("data/results/ui-migration-ai-images.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if len(items) != 7:
        raise RuntimeError(f"Expected 7 published migration items, got {len(items)}")

    out_items, failures = [], []
    for idx, source_item in enumerate(items):
        item = copy.deepcopy(source_item)
        try:
            canonical = item.get("canonical") or {}
            package = item.get("publication_package") or {}
            ai = item.get("ai") or {}
            old_url = str(canonical.get("featured_image_url") or "")
            image_title = ai.get("seo_title") or canonical.get("job_title") or package.get("title") or "فرصة عمل جديدة"
            path, new_url = generate(canonical, image_title)
            content = str(package.get("content") or "")
            if old_url and old_url in content:
                content = content.replace(old_url, new_url)
            else:
                raise RuntimeError("Existing featured image URL not found in article content")
            canonical["featured_image_url"] = new_url
            canonical["featured_image_path"] = path
            package["content"] = content
            package["featured_image_url"] = new_url
            item["canonical"] = canonical
            item["publication_package"] = package
            item["image_migration"] = {
                "version": "ai-v1",
                "generated_at": now_iso(),
                "old_url": old_url,
                "new_url": new_url,
                "path": path,
                "style": "dynamic_ai_scene_with_adaptive_short_text_overlay",
            }
            out_items.append(item)
            print(f"[{idx+1}/{len(items)}] {image_title} -> {new_url}")
        except Exception as exc:
            failures.append({"index": idx, "title": (source_item.get("publication_package") or {}).get("title"), "error": str(exc)})
            print(f"FAILED [{idx+1}/{len(items)}]: {exc}")

    result = {
        "source": str(SOURCE),
        "generated_at": now_iso(),
        "count": len(out_items),
        "failure_count": len(failures),
        "failures": failures,
        "items": out_items,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures or len(out_items) != 7:
        raise RuntimeError("Bulk image regeneration did not complete for all 7 published posts")
    print(json.dumps({"count": len(out_items), "failure_count": len(failures), "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
