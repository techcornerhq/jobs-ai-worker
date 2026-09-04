from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

SOURCES_PATH = Path("config/sources.json")
OUTPUT_DIR = Path("data/discovery")
OUTPUT_PATH = OUTPUT_DIR / "jo-jobs.json"
MAX_ITEMS = 250


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def fingerprint(source_id: str, url: str, title: str) -> str:
    material = f"{source_id}|{normalize_url(url)}|{title.strip().lower()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def load_source() -> dict:
    cfg = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    for source in cfg.get("sources", []):
        if source.get("id") == "jo-jobs":
            return source
    raise RuntimeError("Source jo-jobs not found in config/sources.json")


def fetch_feed(url: str) -> bytes:
    response = requests.get(
        url,
        headers={"User-Agent": "JordanJobsDiscoveryBot/2.0 (+https://jobsinjordan2026.blogspot.com/)"},
        timeout=45,
    )
    response.raise_for_status()
    return response.content


def parse_published(entry):
    return entry.get("published") or entry.get("updated") or None


def load_previous() -> dict:
    if not OUTPUT_PATH.exists():
        return {"items": []}
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def main() -> None:
    source = load_source()
    if source.get("role") != "discovery_only":
        raise RuntimeError("jo-jobs must remain discovery_only")

    raw = fetch_feed(source["feed_url"])
    parsed = feedparser.parse(raw)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"RSS parse failed: {getattr(parsed, 'bozo_exception', 'unknown error')}")

    previous = load_previous()
    previous_by_url = {
        normalize_url(x.get("discovery_url", "")): x
        for x in previous.get("items", [])
        if x.get("discovery_url")
    }

    discovered_at = now_iso()
    seen = set()
    items = []
    for entry in parsed.entries:
        title = re.sub(r"\s+", " ", (entry.get("title") or "").strip())
        url = normalize_url(entry.get("link") or "")
        if not title or not url or url in seen:
            continue
        seen.add(url)
        old = previous_by_url.get(url, {})
        items.append({
            "candidate_id": old.get("candidate_id") or fingerprint(source["id"], url, title),
            "source_id": source["id"],
            "source_name": source["name"],
            "source_tier": source["tier"],
            "source_role": source["role"],
            "title": title,
            "discovery_url": url,
            "feed_published": parse_published(entry),
            "first_discovered_at": old.get("first_discovered_at") or discovered_at,
            "last_seen_at": discovered_at,
            "status": old.get("status") or "discovered",
            "requires_original_source_resolution": bool(source.get("resolve_original_source", True)),
            "copy_article_text": False,
        })
        if len(items) >= MAX_ITEMS:
            break

    if not items:
        raise RuntimeError("RSS returned no usable entries")

    old_urls = set(previous_by_url)
    payload = {
        "source": {
            "id": source["id"],
            "name": source["name"],
            "tier": source["tier"],
            "role": source["role"],
            "feed_url": source["feed_url"],
        },
        "generated_at": discovered_at,
        "count": len(items),
        "new_since_previous_run": sum(1 for x in items if x["discovery_url"] not in old_urls),
        "policy": {
            "publish_directly": False,
            "copy_source_article": False,
            "resolve_original_source_before_publish": True,
            "estimated_claims_are_not_official": True,
        },
        "items": items,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovered {len(items)} candidates -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
