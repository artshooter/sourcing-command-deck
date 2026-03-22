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
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description='Rerun empty items from a batch workflow with softer parameters.')
    ap.add_argument('batch_summary_json')
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--cookie-file', required=True)
    ap.add_argument('--queries', type=int, default=2)
    ap.add_argument('--pages', type=int, default=1)
    ap.add_argument('--top-k', type=int, default=8)
    ap.add_argument('--workdir', required=True)
    args = ap.parse_args()

    batch = json.loads(Path(args.batch_summary_json).read_text(encoding='utf-8'))
    empty_items = [x for x in batch.get('batch_results', []) if x.get('status') == 'ok' and int(x.get('top_count', 0)) == 0]

    ws = detect_workspace()
    runner = ws / 'skills/supplier-scoring/scripts/run_end_to_end_workflow.py'
    base = Path(args.workdir)
    base.mkdir(parents=True, exist_ok=True)

    results = []
    for item in empty_items:
        idx = item['item_index']
        item_dir = base / f'item-{idx:03d}'
        # second-pass: slightly broader but still controlled
        cmd = [
            sys.executable, str(runner),
            '--xlsx', args.xlsx,
            '--cookie-file', args.cookie_file,
            '--item-index', str(idx),
            '--queries', str(args.queries),
            '--pages', str(args.pages),
            '--top-k', str(args.top_k),
            '--workdir', str(item_dir),
            '--skip-images'
        ]
        try:
            summary_path = run(cmd)
            summary = json.loads(Path(summary_path).read_text(encoding='utf-8'))
            top = json.loads(Path(summary['top_json']).read_text(encoding='utf-8'))
            results.append({
                'item_index': idx,
                'status': 'ok',
                'brief_summary': top.get('brief_summary', ''),
                'top_count': len(top.get('top_suppliers', [])),
                'top_json': summary.get('top_json', ''),
                'shortlist_md': summary.get('shortlist_md', ''),
            })
        except Exception as e:
            results.append({
                'item_index': idx,
                'status': 'error',
                'error': str(e),
            })
        time.sleep(random.uniform(8, 15))

    out = {'rerun_results': results}
    out_path = base / 'rerun-summary.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
