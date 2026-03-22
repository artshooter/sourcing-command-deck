#!/usr/bin/env python3
import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path


def detect_workspace():
    env_ws = os.environ.get('OPENCLAW_WORKSPACE')
    if env_ws:
        return Path(env_ws).resolve()
    return Path(__file__).resolve().parents[3]


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if r.stderr:
        sys.stderr.write(r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description='Run end-to-end sourcing workflow for multiple brief items from one planning file.')
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--cookie-file', required=True)
    ap.add_argument('--items', help='Comma-separated 1-based item indexes, e.g. 1,2,5. Omit to use 1..limit')
    ap.add_argument('--limit', type=int, default=5, help='How many items to run when --items is omitted')
    ap.add_argument('--queries', type=int, default=2)
    ap.add_argument('--pages', type=int, default=1)
    ap.add_argument('--top-k', type=int, default=10)
    ap.add_argument('--workdir', help='Output directory (defaults to <workspace>/outputs/workflow-batch)')
    args = ap.parse_args()

    ws = detect_workspace()
    base = Path(args.workdir) if args.workdir else (ws / 'outputs/workflow-batch')
    base.mkdir(parents=True, exist_ok=True)

    runner = ws / 'skills/supplier-scoring/scripts/run_end_to_end_workflow.py'

    if args.items:
        item_indexes = [int(x.strip()) for x in args.items.split(',') if x.strip()]
    else:
        item_indexes = list(range(1, args.limit + 1))

    results = []
    for idx in item_indexes:
        item_dir = base / f'item-{idx:03d}'
        cmd = [
            sys.executable, str(runner),
            '--xlsx', args.xlsx,
            '--cookie-file', args.cookie_file,
            '--item-index', str(idx),
            '--queries', str(args.queries),
            '--pages', str(args.pages),
            '--top-k', str(args.top_k),
            '--workdir', str(item_dir),
        ]
        try:
            summary_path = run(cmd)
            summary = json.loads(Path(summary_path).read_text(encoding='utf-8'))
            top_json = json.loads(Path(summary['top_json']).read_text(encoding='utf-8'))
            results.append({
                'item_index': idx,
                'status': 'ok',
                'brief_summary': top_json.get('brief_summary', ''),
                'top_json': summary.get('top_json', ''),
                'shortlist_md': summary.get('shortlist_md', ''),
                'top_count': len(top_json.get('top_suppliers', [])),
            })
        except Exception as e:
            results.append({
                'item_index': idx,
                'status': 'error',
                'error': str(e),
            })
        time.sleep(random.uniform(8, 15))

    out = {'batch_results': results}
    out_path = base / 'batch-summary.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    # best-effort markdown summaries
    try:
        renderer = ws / 'skills/supplier-scoring/scripts/render_batch_summary.py'
        subprocess.run([
            sys.executable, str(renderer), str(out_path), '--out', str(base / 'batch-summary.md')
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except Exception:
        pass
    try:
        renderer2 = ws / 'skills/supplier-scoring/scripts/render_batch_summary_v2.py'
        subprocess.run([
            sys.executable, str(renderer2), str(out_path), '--out', str(base / 'batch-summary-v2.md')
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except Exception:
        pass

    print(str(out_path))


if __name__ == '__main__':
    main()
