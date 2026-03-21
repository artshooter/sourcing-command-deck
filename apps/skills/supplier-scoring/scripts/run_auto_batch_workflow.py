#!/usr/bin/env python3
import argparse
import json
import os
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
    ap = argparse.ArgumentParser(description='Auto-plan, prioritize, and batch-run the sourcing workflow from one planning file.')
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--cookie-file', required=True)
    ap.add_argument('--max-items', type=int, default=5, help='How many prioritized items to run in this batch')
    ap.add_argument('--queries', type=int, default=2)
    ap.add_argument('--pages', type=int, default=1)
    ap.add_argument('--top-k', type=int, default=10)
    ap.add_argument('--workdir', help='Output directory (defaults to <workspace>/outputs/workflow-auto-batch)')
    args = ap.parse_args()

    ws = detect_workspace()
    s1 = ws / 'skills/planning-brief-parser/scripts'
    s3 = ws / 'skills/supplier-scoring/scripts'
    base = Path(args.workdir) if args.workdir else (ws / 'outputs/workflow-auto-batch')
    base.mkdir(parents=True, exist_ok=True)

    # 1) parse once
    brief_json = base / 'planning-brief.json'
    parse_proc = subprocess.run([
        sys.executable, str(s1 / 'parse_planning_xlsx.py'), args.xlsx, '--pretty'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if parse_proc.returncode != 0:
        raise RuntimeError(parse_proc.stderr)
    brief_json.write_text(parse_proc.stdout, encoding='utf-8')

    # 2) plan priority
    planned_json = base / 'planned-items.json'
    run([sys.executable, str(s3 / 'plan_item_priority.py'), str(brief_json), '--out', str(planned_json)])
    planned = json.loads(planned_json.read_text(encoding='utf-8')).get('planned_items', [])
    selected = planned[: args.max_items]
    item_indexes = [str(x['item_index']) for x in selected]

    # 3) batch run selected items
    batch_runner = s3 / 'run_batch_workflow.py'
    batch_summary = run([
        sys.executable, str(batch_runner),
        '--xlsx', args.xlsx,
        '--cookie-file', args.cookie_file,
        '--items', ','.join(item_indexes),
        '--queries', str(args.queries),
        '--pages', str(args.pages),
        '--top-k', str(args.top_k),
        '--workdir', str(base / 'batch-run')
    ])

    # second pass for empty items
    rerun_runner = s3 / 'rerun_empty_items.py'
    rerun_summary = run([
        sys.executable, str(rerun_runner), str(batch_summary),
        '--xlsx', args.xlsx,
        '--cookie-file', args.cookie_file,
        '--queries', str(max(2, args.queries)),
        '--pages', str(max(1, args.pages)),
        '--top-k', str(args.top_k),
        '--workdir', str(base / 'rerun-pass')
    ])

    merge_runner = s3 / 'merge_rerun_results.py'
    merged_batch_summary = run([
        sys.executable, str(merge_runner), str(batch_summary), str(rerun_summary),
        '--out', str(base / 'batch-run' / 'batch-summary-merged.json')
    ])

    # regenerate summaries on merged batch summary
    subprocess.run([
        sys.executable, str(s3 / 'render_batch_summary.py'), merged_batch_summary,
        '--out', str(base / 'batch-run' / 'batch-summary.md')
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    subprocess.run([
        sys.executable, str(s3 / 'render_batch_summary_v2.py'), merged_batch_summary,
        '--out', str(base / 'batch-run' / 'batch-summary-v2.md')
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    out = {
        'planned_items_json': str(planned_json),
        'selected_items': selected,
        'batch_summary_json': merged_batch_summary,
        'rerun_summary_json': rerun_summary,
        'batch_summary_md': str(base / 'batch-run' / 'batch-summary.md'),
        'batch_summary_v2_md': str(base / 'batch-run' / 'batch-summary-v2.md'),
    }
    out_path = base / 'auto-batch-summary.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
