from __future__ import annotations

import re

MISSING = "غير مذكور في الإعلان"


def validate(job: dict, enriched: dict, rendered: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    title = str(rendered.get("title") or "").strip()
    content = str(rendered.get("content") or "")
    labels = rendered.get("labels") or []
    image = str(rendered.get("featured_image_url") or job.get("featured_image_url") or "")
    official = enriched.get("official_details") or {}
    summary = str(enriched.get("summary") or "").strip()

    if len(title) < 12:
        errors.append("title_too_short")
    if len(title) > 115:
        warnings.append("title_long_for_mobile")
    if len(summary) < 70:
        errors.append("summary_too_thin")
    if len(content) < 2200:
        errors.append("article_too_thin")
    if "-v10.png" not in image:
        errors.append("poster_v10_required")
    if image and image not in content:
        errors.append("poster_not_embedded")
    if "jo-jobs.com" in content.lower():
        errors.append("competitor_url_exposed")
    if "□" in content or "\ufffd" in content:
        errors.append("broken_character_detected")
    if len(labels) < 2:
        errors.append("insufficient_taxonomy_labels")
    if "job-related-box" not in content:
        errors.append("internal_link_block_missing")
    if "application/ld+json" not in content:
        warnings.append("jobposting_schema_not_emitted")

    required_sections = [
        "ملخص الوظيفة", "طريقة التقديم", "تنبيه مهم للباحثين عن عمل", "التحقق من الإعلان"
    ]
    for section in required_sections:
        if section not in content:
            errors.append("missing_section:" + section)

    salary = str(official.get("salary") or "").strip()
    if salary and salary != MISSING and re.search(r"متوقع|تقدير", salary):
        errors.append("estimated_salary_promoted_to_official")

    if job.get("application_url") and official.get("application_method") in (None, "", MISSING):
        warnings.append("application_method_missing_despite_url")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "title_chars": len(title),
            "summary_chars": len(summary),
            "content_chars": len(content),
            "labels": len(labels),
        },
    }


def enforce(job: dict, enriched: dict, rendered: dict) -> dict:
    result = validate(job, enriched, rendered)
    if not result["passed"]:
        raise RuntimeError("QUALITY_GATE_FAILED: " + ", ".join(result["errors"]))
    return result
