from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from job_dedupe import classify, register
from job_image_v10 import generate as generate_job_image
from qwen_enricher import run_qwen
from render_job import render
from resolve_source import resolve

MISSING = "غير مذكور في الإعلان"
DISCOVERY_PATH = Path("data/discovery/jo-jobs.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_candidate(index: int) -> dict:
    data = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not items:
        raise RuntimeError("No discovery candidates")
    if index < 0 or index >= len(items):
        raise RuntimeError(f"candidate index out of range: {index}; count={len(items)}")
    return items[index]


def feed_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def usable(value) -> bool:
    return value not in (None, "", MISSING)


def merge_ai_facts(job: dict, enriched: dict) -> dict:
    out = dict(job)
    official = enriched.get("official_details") or {}
    mappings = {
        "job_title": "job_title",
        "employer_name": "employer",
        "employment_type": "employment_type",
        "experience": "experience",
        "qualification": "qualification",
    }
    for target, source in mappings.items():
        value = official.get(source)
        if usable(value):
            out[target] = value
    if usable(official.get("location")):
        out["location_text"] = official["location"]
    if usable(official.get("application_method")):
        out["application_method"] = official["application_method"]
    out["date_posted"] = feed_date_to_iso(out.get("feed_published"))
    out["field_confidence"] = {
        "official_facts": "source_or_ai_extracted_under_no-invention-policy",
        "general_guidance": "editorial_general_not_official",
    }
    return out


def arabic_display_title(value: str) -> str:
    s = str(value or "").strip()
    replacements = [
        (r"Integration\s+Developer(?:\s+Team\s+Member)?", "مطور تكامل أنظمة"),
        (r"Integration\s+Developer", "مطور تكامل أنظمة"),
        (r"Team\s+Member", ""),
        (r"Software\s+Engineer", "مهندس برمجيات"),
    ]
    for pattern, repl in replacements:
        s = re.sub(pattern, repl, s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_editorial_display(enriched: dict) -> None:
    for key in ("seo_title", "social_title"):
        if enriched.get(key):
            enriched[key] = arabic_display_title(enriched[key])
    official = enriched.get("official_details") or {}
    if official.get("job_title"):
        official["job_title"] = arabic_display_title(official["job_title"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--output", default="data/results/latest.json")
    parser.add_argument("--no-register", action="store_true", help="Do not persist campaign state (useful for tests)")
    args = parser.parse_args()

    started = now_iso()
    candidate = load_candidate(args.index)
    resolved = resolve(candidate)
    enriched = run_qwen(resolved)
    normalize_editorial_display(enriched)

    if enriched.get("paid_api_used") is not False:
        raise RuntimeError("ZERO-PAID-AI guard failed: paid API usage detected")
    if enriched.get("paid_fallback_used") is not False:
        raise RuntimeError("ZERO-PAID-AI guard failed: paid fallback detected")
    if enriched.get("ai_provider") != "groq_free_plan":
        raise RuntimeError("ZERO-PAID-AI guard failed: unexpected AI provider")

    canonical = merge_ai_facts(resolved, enriched)
    dedupe = classify(canonical)
    canonical["campaign_id"] = dedupe.campaign_id
    canonical["repost_of"] = dedupe.matched_campaign_id if dedupe.action == "publish_genuine_repost" else None

    image_path = None
    image_url = None
    if dedupe.action == "merge_same_campaign":
        package = {
            "action": "do_not_republish",
            "reason": "Same job campaign detected across sources/current window. Merge source internally instead of creating another Blogger post.",
            "existing_campaign_id": dedupe.campaign_id,
        }
    else:
        image_title = enriched.get("social_title") or enriched.get("seo_title") or canonical.get("job_title") or candidate.get("title")
        image_path, image_url = generate_job_image(canonical, image_title)
        canonical["featured_image_url"] = image_url
        rendered = render(canonical, enriched)
        package = {
            "action": "publish_new_post" if dedupe.action == "publish_new_campaign" else "publish_genuine_repost",
            **rendered,
        }

    if not args.no_register:
        register(canonical, dedupe)

    result = {
        "worker_version": 10,
        "started_at": started,
        "completed_at": now_iso(),
        "policy": {
            "paid_ai_allowed": False,
            "paid_fallback_allowed": False,
            "missing_information_causes_rejection": False,
            "invent_official_facts": False,
            "cross_source_duplicates_create_new_posts": False,
            "genuine_employer_reposts_allowed": True,
            "competitor_discovery_links_publicly_exposed": False,
            "branded_featured_image_required": True,
            "poster_version_required": "v10",
            "poster_text_collision_guard": True,
            "poster_remote_image_fallback_required": True,
        },
        "candidate": candidate,
        "source_resolution": {
            "source_discovery_url": resolved.get("source_discovery_url"),
            "source_original_url": resolved.get("source_original_url"),
            "source_original_fetch_ok": resolved.get("source_original_fetch_ok"),
            "application_email": resolved.get("application_email"),
            "application_phone": resolved.get("application_phone"),
            "verified_at": resolved.get("verified_at"),
        },
        "canonical": {
            "campaign_id": canonical.get("campaign_id"),
            "repost_of": canonical.get("repost_of"),
            "job_title": canonical.get("job_title"),
            "employer_name": canonical.get("employer_name"),
            "location_text": canonical.get("location_text"),
            "application_method": canonical.get("application_method"),
            "application_url": canonical.get("application_url"),
            "application_email": canonical.get("application_email"),
            "application_phone": canonical.get("application_phone"),
            "date_posted": canonical.get("date_posted"),
            "source_discovery_url": canonical.get("source_discovery_url"),
            "source_original_url": canonical.get("source_original_url"),
            "country": canonical.get("country"),
            "featured_image_url": image_url,
            "featured_image_path": image_path,
        },
        "ai": {
            "provider": enriched.get("ai_provider"),
            "model": enriched.get("ai_model"),
            "paid_api_used": enriched.get("paid_api_used"),
            "paid_fallback_used": enriched.get("paid_fallback_used"),
            "usage": enriched.get("usage"),
            "seo_title": enriched.get("seo_title"),
            "meta_description": enriched.get("meta_description"),
            "official_details": enriched.get("official_details"),
            "missing_official_information": enriched.get("missing_official_information"),
            "verification_notes": enriched.get("verification_notes"),
        },
        "dedupe": asdict(dedupe),
        "publication_package": package,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "candidate": candidate.get("title"),
        "ai": result["ai"]["provider"],
        "model": result["ai"]["model"],
        "dedupe": dedupe.action,
        "publication_action": package["action"],
        "featured_image": image_url,
        "output": str(out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
