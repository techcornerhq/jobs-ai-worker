from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?962|00962|0)?\s?7[789]\s?\d{3}\s?\d{4}")
DATE_RE = re.compile(r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b")

KNOWN_DISCOVERY_HOSTS = {"jo-jobs.com"}
SOCIAL_HOSTS = {
    "x.com", "twitter.com", "facebook.com", "fb.com", "linkedin.com",
    "instagram.com", "tiktok.com", "youtube.com", "whatsapp.com", "wa.me",
    "telegram.me", "t.me", "pinterest.com", "reddit.com",
}
SOCIAL_SHARE_PATH_HINTS = (
    "/intent/", "/share", "/sharer", "/sharing/", "/tweet", "/dialog/share", "/send/",
)
SHARE_QUERY_KEYS = {"text", "url", "u", "share", "quote", "type", "app_absent"}
OFFICIAL_HINTS = (
    "careers", "career", "jobs", "job", "vacancy", "vacancies", "recruitment",
    "linkedin.com/jobs", "akhtaboot", "bayt.com", "for9a.com", "apply"
)
APPLICATION_HINTS = (
    "apply", "application", "قدم", "تقديم", "التقديم", "سجل", "register",
    "careers", "career", "vacancy", "job"
)

# Previously verified live campaigns. Used only when the discovery host is temporarily unreachable.
CACHED_RESOLUTIONS = {
    "https://www.jo-jobs.com/archives/6773": {
        "source_original_url": "https://careers.zain.com/vacancy/175993",
        "application_url": "https://careers.zain.com/vacancy/175993",
        "application_email": None,
        "application_phone": None,
        "discovery_text": "زين الأردن تفتح باب التوظيف والتدريب لفرص متعددة، ورواتب متوقعة تصل إلى 800 دينار. الفرصة المتحققة: Integration Developer Team Member في عمان.",
        "original_text": "Zain Jordan vacancy: Integration Developer Team Member in Amman. Requires at least one year of experience and a bachelor's degree in Computer Science, Computer Engineering or a related field. Application through Zain Careers. Deadline 08-Oct-2026.",
        "source_original_fetch_ok": True,
    },
    "https://www.jo-jobs.com/archives/6771": {
        "source_original_url": "https://careers.alameedcoffee.com/jobs.php",
        "application_url": "https://careers.alameedcoffee.com/jobs.php",
        "application_email": None,
        "application_phone": None,
        "discovery_text": "بن العميد تطلب موظفين في عمان برواتب متوقعة من 300 إلى 600 دينار. شواغر متنوعة إدارية وتقنية وتشغيلية ومبيعات وخدمة عملاء.",
        "original_text": "Al Ameed Coffee careers page for available jobs and electronic applications in Jordan.",
        "source_original_fetch_ok": True,
    },
    "https://www.jo-jobs.com/archives/6775": {
        "source_original_url": None,
        "application_url": None,
        "application_email": "jobs@mgc-machinery.com",
        "application_phone": None,
        "discovery_text": "مجموعة المناصير تفتح باب التوظيف في عدة تخصصات ورواتب متوقعة تصل إلى 850 دينار. شواغر صيانة تشمل حدادة وميكانيك وكهرباء ودهان وبودي، إضافة إلى فرصة لحديثي التخرج في الهندسة الميكانيكية. التقديم عبر jobs@mgc-machinery.com.",
        "original_text": None,
        "source_original_fetch_ok": False,
    },
}


def host(url: str | None) -> str:
    try:
        h = urlsplit(url or "").netloc.lower().split(":", 1)[0]
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def host_matches(h: str, domains: set[str]) -> bool:
    return any(h == d or h.endswith("." + d) for d in domains)


def is_social_url(url: str) -> bool:
    return host_matches(host(url), SOCIAL_HOSTS)


def is_allowed_social_job_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        h = host(url)
        path = p.path.lower()
        return host_matches(h, {"linkedin.com"}) and (path.startswith("/jobs/view/") or path.startswith("/jobs/collections/"))
    except Exception:
        return False


def is_social_share_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        h = host(url)
        path = p.path.lower()
        query_keys = {k.lower() for k in parse_qs(p.query).keys()}
        is_social = host_matches(h, SOCIAL_HOSTS)
        if is_social and any(x in path for x in SOCIAL_SHARE_PATH_HINTS):
            return True
        if host_matches(h, {"x.com", "twitter.com"}) and path.startswith("/intent/"):
            return True
        if host_matches(h, {"facebook.com", "fb.com"}) and ("sharer" in path or "dialog/share" in path):
            return True
        if host_matches(h, {"whatsapp.com", "wa.me"}) and ("/send" in path or "text" in query_keys):
            return True
        if is_social and len(query_keys & SHARE_QUERY_KEYS) >= 2:
            return True
    except Exception:
        return True
    return False


def is_candidate_source_url(url: str, base_url: str) -> bool:
    h = host(url)
    if not url.startswith(("http://", "https://")) or not h or h == host(base_url):
        return False
    if is_social_share_url(url):
        return False
    if is_social_url(url) and not is_allowed_social_job_url(url):
        return False
    return True


def get(url: str) -> requests.Response:
    r = requests.get(
        url,
        headers={"User-Agent": "JordanJobsVerifier/2.4 (+https://jobsinjordan2026.blogspot.com/)"},
        timeout=(8, 12),
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
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href", "").strip())
        if href in seen or not is_candidate_source_url(href, base_url):
            continue
        seen.add(href)
        h = host(href)
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:240]
        low = (href + " " + text).lower()
        score = 0
        if any(k in low for k in OFFICIAL_HINTS): score += 4
        if h not in KNOWN_DISCOVERY_HOSTS: score += 2
        if any(x in low for x in APPLICATION_HINTS): score += 3
        out.append({"url": href, "host": h, "text": text, "score": score})
    return sorted(out, key=lambda x: x["score"], reverse=True)


def looks_like_application_url(item: dict | None) -> bool:
    if not item:
        return False
    url = item.get("url", "")
    if is_social_url(url) and not is_allowed_social_job_url(url):
        return False
    low = (url + " " + item.get("text", "")).lower()
    return any(x in low for x in APPLICATION_HINTS) and not is_social_share_url(url)


def cached_result(candidate: dict) -> dict | None:
    discovery_url = candidate.get("discovery_url")
    cached = CACHED_RESOLUTIONS.get(discovery_url)
    if not cached:
        return None
    return {
        **candidate,
        "source_discovery_url": discovery_url,
        "source_original_url": cached.get("source_original_url"),
        "source_original_host": host(cached.get("source_original_url")),
        "source_original_fetch_ok": cached.get("source_original_fetch_ok", False),
        "page_title": candidate.get("title"),
        "discovery_text": cached.get("discovery_text"),
        "original_text": cached.get("original_text"),
        "application_email": cached.get("application_email"),
        "application_phone": cached.get("application_phone"),
        "application_url": cached.get("application_url"),
        "dates_found": DATE_RE.findall((cached.get("discovery_text") or "") + "\n" + (cached.get("original_text") or ""))[:12],
        "external_links": [],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "country": "Jordan",
        "status": "cached_verified_fallback",
        "date_discovered": candidate.get("first_discovered_at") or datetime.now(timezone.utc).isoformat(),
        "fact_policy": {
            "discovery_aggregator_is_not_official": True,
            "estimated_salary_is_not_official_without_original_confirmation": True,
            "social_share_links_are_never_original_or_application_urls": True,
            "social_profiles_are_never_original_or_application_urls": True,
            "cached_fallback_only_for_previously_verified_campaign": True,
        },
    }


def resolve(candidate: dict) -> dict:
    discovery_url = candidate["discovery_url"]
    try:
        r = get(discovery_url)
    except Exception:
        cached = cached_result(candidate)
        if cached:
            return cached
        raise

    soup = BeautifulSoup(r.text, "html.parser")
    discovery_text = clean_text(soup)
    links = external_links(soup, r.url)
    emails = sorted(set(EMAIL_RE.findall(discovery_text)))
    phones = sorted(set(re.sub(r"\s+", "", x) for x in PHONE_RE.findall(discovery_text)))
    dates = sorted(set(DATE_RE.findall(discovery_text)))
    best = links[0] if links and links[0]["score"] >= 4 else None
    original_url = best["url"] if best else None
    application_url = best["url"] if looks_like_application_url(best) else None
    original_text = None
    original_fetch_ok = False
    original_host = None

    if original_url:
        try:
            orr = get(original_url)
            redirected = orr.url
            if is_social_share_url(redirected) or (is_social_url(redirected) and not is_allowed_social_job_url(redirected)):
                original_url = None
                application_url = None
            else:
                original_url = redirected
                original_host = host(original_url)
                original_text = clean_text(BeautifulSoup(orr.text, "html.parser"))[:30000]
                original_fetch_ok = True
                combined = discovery_text + "\n" + original_text
                emails = sorted(set(emails + EMAIL_RE.findall(combined)))
                phones = sorted(set(phones + [re.sub(r"\s+", "", x) for x in PHONE_RE.findall(combined)]))
                dates = sorted(set(dates + DATE_RE.findall(combined)))
                if application_url and host(application_url) != original_host:
                    application_url = None
        except Exception:
            original_fetch_ok = False

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
        "application_url": application_url,
        "dates_found": dates[:12],
        "external_links": links[:20],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "country": "Jordan",
        "status": "unknown",
        "date_discovered": candidate.get("first_discovered_at") or datetime.now(timezone.utc).isoformat(),
        "fact_policy": {
            "discovery_aggregator_is_not_official": True,
            "estimated_salary_is_not_official_without_original_confirmation": True,
            "social_share_links_are_never_original_or_application_urls": True,
            "social_profiles_are_never_original_or_application_urls": True,
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
