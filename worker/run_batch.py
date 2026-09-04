from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from run_worker import DISCOVERY_PATH, process_candidate

STATE_PATH = Path("data/state/auto_cursor.json")
DEFAULT_OUTPUT = Path("data/results/auto-batch.json")


def utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"date": utc_date(), "processed_today": 0, "seen_candidate_ids": []}
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    if state.get("date") != utc_date():
        state["date"] = utc_date()
        state["processed_today"] = 0
    state.setdefault("seen_candidate_ids", [])
    return state


def candidate_key(item: dict) -> str:
    raw = str(item.get("candidate_id") or item.get("discovery_url") or item.get("title") or "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-per-day", type=int, default=40)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    discovery = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    items = discovery.get("items") or []
    state = load_state()
    seen = set(state.get("seen_candidate_ids") or [])
    remaining = max(0, args.max_per_day - int(state.get("processed_today") or 0))
    limit = min(max(args.batch_size, 0), remaining)

    selected: list[tuple[int, dict, str]] = []
    for index, item in enumerate(items):
        key = candidate_key(item)
        if key in seen:
            continue
        selected.append((index, item, key))
        if len(selected) >= limit:
            break

    results: list[dict] = []
    failures: list[dict] = []
    for index, item, key in selected:
        try:
            result = process_candidate(index, register_state=False)
            results.append(result)
            seen.add(key)
            state["processed_today"] = int(state.get("processed_today") or 0) + 1
        except Exception as exc:
            failures.append({"index": index, "candidate": item.get("title"), "error": str(exc)})

    state["seen_candidate_ids"] = list(seen)[-1000:]
    state["updated_at"] = now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    publishable = [r for r in results if (r.get("publication_package") or {}).get("action") in {"publish_new_post", "publish_genuine_repost"}]
    batch = {
        "batch_version": 1,
        "generated_at": now_iso(),
        "source": "current_enabled_discovery_sources",
        "daily_cap": args.max_per_day,
        "processed_today": state.get("processed_today"),
        "selected_count": len(selected),
        "result_count": len(results),
        "publishable_count": len(publishable),
        "failure_count": len(failures),
        "failures": failures,
        "items": publishable,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: batch[k] for k in ["generated_at", "daily_cap", "processed_today", "selected_count", "publishable_count", "failure_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
