from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

STATE_PATH = Path("data/state/job_campaigns.json")
AR_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
NON_WORD = re.compile(r"[^0-9A-Za-z\u0600-\u06FF]+")
SPACE = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = AR_DIACRITICS.sub("", value.replace("ـ", "")).lower().strip()
    return SPACE.sub(" ", NON_WORD.sub(" ", value)).strip()


def normalize_ar(value: str | None) -> str:
    return (
        normalize_text(value)
        .replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ى", "ي").replace("ة", "ه")
    )


def host(url: str | None) -> str:
    try:
        h = urlsplit(url or "").netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def similarity(a: str, b: str) -> float:
    a, b = normalize_ar(a), normalize_ar(b)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    return seq * 0.55 + jac * 0.45


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass
class MatchResult:
    action: str
    campaign_id: str
    matched_campaign_id: str | None
    score: float
    reason: str


def canonical_keys(job: dict) -> dict:
    application = job.get("application_email") or job.get("application_phone") or job.get("application_url") or ""
    return {
        "employer": normalize_ar(job.get("employer_name")),
        "title": normalize_ar(job.get("job_title") or job.get("title")),
        "location": normalize_ar(" ".join(filter(None, [job.get("governorate"), job.get("city"), job.get("area"), job.get("location_text")]))) ,
        "application": normalize_ar(application),
        "application_host": host(job.get("application_url")),
        "original_host": host(job.get("source_original_url")),
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"campaigns": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"campaigns": []}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def score_against(job: dict, campaign: dict) -> tuple[float, list[str]]:
    a, b = canonical_keys(job), campaign.get("keys", {})
    reasons: list[str] = []
    title_score = similarity(a["title"], b.get("title", ""))
    employer_score = similarity(a["employer"], b.get("employer", ""))
    location_score = similarity(a["location"], b.get("location", ""))

    score = title_score * 0.40 + employer_score * 0.30 + location_score * 0.10
    if a["application"] and a["application"] == b.get("application"):
        score += 0.12
        reasons.append("same application contact")
    elif a["application_host"] and a["application_host"] == b.get("application_host"):
        score += 0.06
        reasons.append("same application domain")
    if a["original_host"] and a["original_host"] == b.get("original_host"):
        score += 0.08
        reasons.append("same original source domain")

    if title_score >= 0.88:
        reasons.append("very similar title")
    if employer_score >= 0.88:
        reasons.append("same/similar employer")
    if location_score >= 0.85 and a["location"]:
        reasons.append("same/similar location")

    # Strong same-origin + nearly identical title is enough even when sparse ads omit location/contact.
    if title_score >= 0.94 and a["original_host"] and a["original_host"] == b.get("original_host"):
        score = max(score, 0.82)
    return min(score, 1.0), reasons


def classify(job: dict, *, same_window_days: int = 21, repost_min_days: int = 18) -> MatchResult:
    campaigns = load_state().get("campaigns", [])
    source_date = parse_date(job.get("date_posted") or job.get("date_discovered")) or datetime.now(timezone.utc)

    best, best_score, best_reasons = None, 0.0, []
    for campaign in campaigns:
        score, reasons = score_against(job, campaign)
        if score > best_score:
            best, best_score, best_reasons = campaign, score, reasons

    if best and best_score >= 0.76:
        last_seen = parse_date(best.get("last_seen_at")) or source_date
        gap_days = abs((source_date - last_seen).days)
        keys = canonical_keys(job)
        changed_deadline = bool(job.get("valid_through") and job.get("valid_through") != best.get("valid_through"))
        changed_app = bool(keys["application"] and best.get("keys", {}).get("application") and keys["application"] != best.get("keys", {}).get("application"))

        if gap_days <= same_window_days and not (changed_deadline or changed_app):
            return MatchResult("merge_same_campaign", best["campaign_id"], best["campaign_id"], best_score, ", ".join(best_reasons) or "strong cross-source match")

        if gap_days >= repost_min_days or changed_deadline or changed_app:
            new_id = stable_hash(best["campaign_id"], source_date.date().isoformat(), job.get("source_discovery_url", ""))
            reason = "genuine repost/new campaign window"
            if changed_deadline or changed_app:
                reason += "; material application details changed"
            return MatchResult("publish_genuine_repost", new_id, best["campaign_id"], best_score, reason)

    keys = canonical_keys(job)
    new_id = stable_hash(keys["employer"], keys["title"], keys["location"], keys["original_host"], job.get("source_discovery_url", ""))
    return MatchResult("publish_new_campaign", new_id, None, best_score, "no strong existing campaign match")


def register(job: dict, result: MatchResult) -> None:
    state = load_state()
    campaigns = state.setdefault("campaigns", [])
    seen_at = job.get("date_discovered") or now_iso()

    if result.action == "merge_same_campaign":
        for campaign in campaigns:
            if campaign.get("campaign_id") == result.campaign_id:
                campaign["last_seen_at"] = seen_at
                campaign.setdefault("source_urls", [])
                for url in [job.get("source_discovery_url"), job.get("source_original_url")]:
                    if url and url not in campaign["source_urls"]:
                        campaign["source_urls"].append(url)
                if job.get("valid_through"):
                    campaign["valid_through"] = job["valid_through"]
                save_state(state)
                return

    campaigns.append({
        "campaign_id": result.campaign_id,
        "repost_of": result.matched_campaign_id,
        "keys": canonical_keys(job),
        "job_title": job.get("job_title") or job.get("title"),
        "employer_name": job.get("employer_name"),
        "first_seen_at": seen_at,
        "last_seen_at": seen_at,
        "valid_through": job.get("valid_through"),
        "source_urls": [u for u in [job.get("source_discovery_url"), job.get("source_original_url")] if u],
    })
    save_state(state)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("job_json")
    args = parser.parse_args()
    job = json.loads(Path(args.job_json).read_text(encoding="utf-8"))
    print(json.dumps(asdict(classify(job)), ensure_ascii=False, indent=2))
