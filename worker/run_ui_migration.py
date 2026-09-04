from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from run_worker import process_candidate

OUT = Path('data/results/ui-migration.json')
DEFAULT_INDICES = [0, 1, 2, 6, 7, 8, 9]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    raw = os.environ.get('UI_MIGRATION_INDICES', '').strip()
    indices = [int(x.strip()) for x in raw.split(',') if x.strip()] if raw else DEFAULT_INDICES
    delay = int(os.environ.get('UI_MIGRATION_DELAY_SECONDS', '68'))
    results = []
    failures = []
    for pos, idx in enumerate(indices):
        print(f'Processing current live candidate index {idx} ({pos+1}/{len(indices)})')
        try:
            result = process_candidate(idx, register_state=False)
            package = result.get('publication_package') or {}
            content = package.get('content') or ''
            if not result.get('quality_gate', {}).get('passed'):
                raise RuntimeError('quality gate failed')
            if "class='job-page-hero'" not in content or "id='job-apply'" not in content:
                raise RuntimeError('new article UX markers missing')
            results.append(result)
        except Exception as exc:
            failures.append({'index': idx, 'error': str(exc)})
        if pos < len(indices) - 1:
            print(f'Waiting {delay}s for Groq Free Plan output-token window...')
            time.sleep(delay)
    payload = {
        'started_indices': indices,
        'completed_at': now_iso(),
        'count': len(results),
        'failure_count': len(failures),
        'failures': failures,
        'items': results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'count': len(results), 'failures': failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(f'UI migration failed for {len(failures)} candidate(s)')


if __name__ == '__main__':
    main()
