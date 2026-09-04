from __future__ import annotations

import json

MISSING = "غير مذكور في الإعلان"


def usable(value) -> bool:
    return value not in (None, "", MISSING)


def build(job: dict, enriched: dict) -> dict:
    official = enriched.get("official_details") or {}
    title = official.get("job_title") or job.get("job_title")
    employer = official.get("employer") or job.get("employer_name")
    if not usable(title) or not usable(employer):
        return {}

    schema: dict = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": title,
        "hiringOrganization": {"@type": "Organization", "name": employer},
    }
    if enriched.get("summary"):
        schema["description"] = enriched["summary"]
    if job.get("date_posted"):
        schema["datePosted"] = job["date_posted"]
    if job.get("valid_through"):
        schema["validThrough"] = job["valid_through"]
    if usable(official.get("employment_type")):
        schema["employmentType"] = official["employment_type"]

    location = official.get("location") or job.get("location_text")
    if usable(location):
        schema["jobLocation"] = {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "JO",
                "addressLocality": location,
            },
        }

    # Only confirmed official salary belongs in JobPosting structured data.
    salary = str(official.get("salary") or "").strip()
    if usable(salary) and "متوقع" not in salary and "تقدير" not in salary:
        # We do not attempt to parse arbitrary salary prose into baseSalary; leaving it out
        # is safer than emitting a misleading numeric schema.
        pass

    if job.get("application_url"):
        schema["directApply"] = True
    return schema


def ensure(rendered: dict, job: dict, enriched: dict) -> dict:
    content = str(rendered.get("content") or "")
    if "application/ld+json" in content:
        return rendered
    schema = build(job, enriched)
    if schema:
        rendered = dict(rendered)
        rendered["schema"] = schema
        rendered["content"] = content + "\n<script type='application/ld+json'>" + json.dumps(schema, ensure_ascii=False) + "</script>"
    return rendered
