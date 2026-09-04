from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?962|00962|0)?\s?7[789]\s?\d{3}\s?\d{4}")
DATE_RE = re.compile(r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b")

KNOWN_DISCOVERY_HOSTS = {"jo-jobs.com"}
OFFICIAL_HINTS = (
    "careers", "career", "jobs", "job", "vacancy", "vacancies", "recruitment",
    "linkedin.com/jobs", "akhtaboot", "bayt.com", "for9a.com", "apply"
)


def host(url: str | None) -> str:
    try:
        h = urlsplit(url or "").netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def get(url: str) -> requests.Response:
    r = requests.get(
        url,
        headers={"User-Agent": "JordanJobsVerifier/2.0 (+https://jobsinjordan2026.blogspot.com/)"},
        timeout=45,
        allow_redirects=True,
    )
    r.raise_for_status()
    return r


def clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
    return "\n".join(x for x in lines if x)


def external_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    base_host = host(base_url)
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href", "").strip())
        h = host(href)
        if not href.startswith(("http://", "https://")) or not h or h == base_host or href in seen:
            continue
        seen.add(href)
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:240]
        low = (href + " " + text).lower()
        score = 0
        if any(k in low for k in OFFICIAL_HINTS):
            score += 4
        if h not in KNOWN_DISCOVERY_HOSTS:
            score += 2
        if any(x in low for x in ("apply", "تقديم", "قدم", "التوظيف", "وظائف", "careers")):
            score += 3
        if any(x in low for x in ("facebook.com", "instagram.com", "tiktok.com", "youtube.com")):
            score -= 2
        out.append({"url": href, "host": h, "text": text, "score": score})
    return sorted(out, key=lambda x: x["score"], reverse=True)


def resolve(candidate: dict) -> dict:
    discovery_url = candidate["discovery_url"]
    r = get(discovery_url)
    soup = BeautifulSoup(r.text, "html.parser")
    discovery_text = clean_text(soup)
    links = external_links(soup, r.url)

    emails = sorted(set(EMAIL_RE.findall(discovery_text)))
    phones = sorted(set(re.sub(r"\s+", "", x) for x in PHONE_RE.findall(discovery_text)))
    dates = sorted(set(DATE_RE.findall(discovery_text)))

    best = links[0] if links and links[0]["score"] >= 4 else None
    original_url = best["url"] if best else None
    original_text = None
    original_fetch_ok = False
    original_host = None

    if original_url:
        try:
            orr = get(original_url)
            original_url = orr.url
            original_host = host(original_url)
            original_text = clean_text(BeautifulSoup(orr.text, "html.parser"))[:30000]
            original_fetch_ok = True
            combined = discovery_text + "\n" + original_text
            emails = sorted(set(emails + EMAIL_RE.findall(combined)))
            phones = sorted(set(phones + [re.sub(r"\s+", "", x) for x in PHONE_RE.findall(combined)]))
            dates = sorted(set(dates + DATE_RE.findall(combined)))
        except Exception:
            pass

    page_title = soup.title.get_text(" ", strip=True) if soup.title else candidate.get("title")
    return {
        **candidate,
        "source_discovery_url": discovery_url,
        "source_original_url": original_url,
        "source_original_host": original_host,
        "source_original_fetch_ok": original_fetch_ok,
        "page_title": page_title,
        "discovery_text": discovery_text[:30000],
        "original_text": original_text,
        "application_email": emails[0] if emails else None,
        "application_phone": phones[0] if phones else None,
        "application_url": original_url,
        "dates_found": dates[:12],
        "external_links": links[:20],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "country": "Jordan",
        "status": "unknown",
        "date_discovered": candidate.get("first_discovered_at") or datetime.now(timezone.utc).isoformat(),
        "fact_policy": {
            "discovery_aggregator_is_not_official": True,
            "estimated_salary_is_not_official_without_original_confirmation": True,
        },
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_json")
    parser.add_argument("output_json")
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate_json).read_text(encoding="utf-8"))
    result = resolve(candidate)
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
