#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def load_tasks(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f).get('tasks', [])


def main():
    ap = argparse.ArgumentParser(description='Run 1688 mtop fetch + extract for multiple queries/pages.')
    ap.add_argument('tasks_json')
    ap.add_argument('--cookie-file', required=True)
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--queries', type=int, default=3, help='Max queries to run for this item')
    ap.add_argument('--pages', type=int, default=2, help='Pages per query')
    ap.add_argument('--page-size', type=int, default=60)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    tasks = load_tasks(args.tasks_json)
    task = next((t for t in tasks if t.get('item_index') == args.item_index), None)
    if not task:
        raise SystemExit(f'No task found for item_index={args.item_index}')

    skill_dir = Path(__file__).resolve().parent
    fetch_script = skill_dir / 'fetch_1688_mtop.py'
    extract_script = skill_dir / 'extract_1688_candidates.py'
    validate_script = skill_dir / 'validate_1688_result.py'
    fallback_script = skill_dir / 'generate_fallback_queries.py'

    all_rows = []
    queries = (task.get('queries_1688_native') or [])[: args.queries]

    _request_count = [0]

    def _is_cookie_blocked(mtop_out: Path) -> bool:
        try:
            obj = json.loads(mtop_out.read_text(encoding='utf-8'))
            ret = obj.get('ret') or []
            return any('FAIL_SYS_USER_VALIDATE' in r for r in ret)
        except Exception:
            return False

    def fetch_and_extract(query_list, start_rank=1):
        local_rows = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            for q_idx, query in enumerate(query_list, start_rank):
                for page in range(1, args.pages + 1):
                    # Throttle: 2s between requests to avoid triggering 1688 risk control
                    if _request_count[0] > 0:
                        time.sleep(2)
                    _request_count[0] += 1

                    mtop_out = tmpdir / f'mtop_q{q_idx}_p{page}.json'
                    rows_out = tmpdir / f'rows_q{q_idx}_p{page}.json'
                    cache_dir = str(Path('/root/.openclaw/workspace/outputs/1688-global-cache'))
                    cmd1 = [
                        sys.executable, str(fetch_script),
                        '--query', query,
                        '--cookie-file', args.cookie_file,
                        '--begin-page', str(page),
                        '--page-size', str(args.page_size),
                        '--retries', '2',
                        '--cache-dir', cache_dir,
                        '--out', str(mtop_out),
                    ]
                    r1 = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    if r1.returncode != 0:
                        continue

                    # Cookie blocked — abort immediately, no point sending more requests
                    if _is_cookie_blocked(mtop_out):
                        return local_rows

                    rv = subprocess.run([sys.executable, str(validate_script), str(mtop_out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    if rv.stdout.strip() != 'valid':
                        continue

                    cmd2 = [
                        sys.executable, str(extract_script), str(mtop_out),
                        '--item-index', str(args.item_index),
                        '--query', query,
                        '--out', str(rows_out),
                    ]
                    r2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    if r2.returncode != 0:
                        continue
                    data = json.loads(rows_out.read_text(encoding='utf-8'))
                    for row in data.get('candidate_rows', []):
                        row.setdefault('extra', {})['page'] = page
                        row['extra']['query_rank'] = q_idx
                        local_rows.append(row)
        return local_rows

    all_rows.extend(fetch_and_extract(queries, start_rank=1))

    # fallback: if nothing was recalled, switch to broader/lower-risk queries
    if not all_rows:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            fb_json = tmpdir / 'fallback.json'
            subprocess.run([
                sys.executable, str(fallback_script), args.tasks_json,
                '--item-index', str(args.item_index), '--out', str(fb_json)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if fb_json.exists():
                fallback_queries = json.loads(fb_json.read_text(encoding='utf-8')).get('fallback_queries', [])
                all_rows.extend(fetch_and_extract(fallback_queries[: args.queries], start_rank=100))

    out = {'candidate_rows': all_rows}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
