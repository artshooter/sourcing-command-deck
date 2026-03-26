#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def detect_workspace():
    env_ws = os.environ.get('OPENCLAW_WORKSPACE')
    if env_ws:
        return Path(env_ws).resolve()
    return Path(__file__).resolve().parents[3]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, cwd=cwd)
    if r.stderr:
        sys.stderr.write(r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description='Run planning parse -> 1688 discovery -> shop-sample profiling -> scoring workflow for one brief item.')
    ap.add_argument('--xlsx', required=True, help='Path to planning xlsx')
    ap.add_argument('--cookie-file', required=True, help='Local 1688 cookie file')
    ap.add_argument('--item-index', type=int, required=True, help='1-based brief item index')
    ap.add_argument('--queries', type=int, default=3)
    ap.add_argument('--pages', type=int, default=2)
    ap.add_argument('--top-k', type=int, default=20)
    ap.add_argument('--workdir', help='Output directory (defaults to <workspace>/outputs/workflow-run)')
    ap.add_argument('--image-manifest', help='Optional prebuilt image manifest path')
    ap.add_argument('--skip-images', action='store_true')
    args = ap.parse_args()

    ws = detect_workspace()
    base = Path(args.workdir) if args.workdir else (ws / 'outputs/workflow-run')
    base.mkdir(parents=True, exist_ok=True)

    s1 = ws / 'skills/planning-brief-parser/scripts'
    s2 = ws / 'skills/supplier-discovery/scripts'
    s3 = ws / 'skills/supplier-scoring/scripts'

    image_manifest = args.image_manifest
    if not args.skip_images and not image_manifest:
        image_dir = base / 'brief-images'
        run([sys.executable, str(s1 / 'extract_xlsx_images.py'), args.xlsx, '--outdir', str(image_dir)])
        image_manifest = str(image_dir / 'image-manifest.json')

    brief_json = base / 'planning-brief.json'
    cmd = [sys.executable, str(s1 / 'parse_planning_xlsx.py'), args.xlsx, '--pretty']
    if image_manifest:
        cmd += ['--image-manifest', image_manifest]
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr)
    brief_json.write_text(out.stdout, encoding='utf-8')

    tasks_json = base / '1688-tasks.json'
    run([sys.executable, str(s2 / 'generate_1688_tasks.py'), str(brief_json), '--item-index', str(args.item_index), '--out', str(tasks_json)])

    batch_json = base / '1688-batch.json'
    run([
        sys.executable, str(s2 / 'run_1688_batch.py'), str(tasks_json),
        '--cookie-file', args.cookie_file,
        '--item-index', str(args.item_index),
        '--queries', str(args.queries),
        '--pages', str(args.pages),
        '--out', str(batch_json)
    ])

    reranked_json = base / '1688-reranked.json'
    run([
        sys.executable, str(s2 / 'rerank_1688_candidates.py'), str(brief_json), str(batch_json),
        '--item-index', str(args.item_index), '--min-score', '3', '--top-k', '80', '--out', str(reranked_json)
    ])

    multi_shops_json = base / 'multi-sample-shops.json'
    run([sys.executable, str(s2 / 'extract_multi_sample_shops.py'), str(batch_json), '--min-samples', '2', '--out', str(multi_shops_json)])

    scored_json = base / 'scored.json'
    run([sys.executable, str(s3 / 'score_suppliers.py'), str(brief_json), str(reranked_json), '--item-index', str(args.item_index), '--out', str(scored_json)])

    enriched_json = base / 'scored-enriched.json'
    run([sys.executable, str(s3 / 'enrich_supplier_profiles.py'), str(scored_json), '--out', str(enriched_json)])

    multi_profiles_json = base / 'multi-sample-shop-profiles.json'
    run([sys.executable, str(s3 / 'profile_multi_sample_shops.py'), str(multi_shops_json), '--out', str(multi_profiles_json)])

    final_scored_json = base / 'scored-final.json'
    run([sys.executable, str(s3 / 'merge_shop_sample_profiles.py'), str(enriched_json), str(multi_profiles_json), '--out', str(final_scored_json)])

    score_distribution_json = base / 'score-distribution.json'
    run([sys.executable, str(s3 / 'analyze_score_distribution.py'), str(final_scored_json), '--out', str(score_distribution_json)])

    top_json = base / 'top-suppliers.json'
    shortlist_md = base / 'shortlist.md'
    run([sys.executable, str(s3 / 'select_top_suppliers.py'), str(final_scored_json), '--top-k', str(args.top_k), '--out', str(top_json)])
    run([sys.executable, str(s3 / 'render_shortlist.py'), str(final_scored_json), '--top-k', str(args.top_k), '--out', str(shortlist_md)])
    score_distribution = json.loads(score_distribution_json.read_text(encoding='utf-8'))

    summary = {
        'brief_json': str(brief_json),
        'tasks_json': str(tasks_json),
        'batch_json': str(batch_json),
        'reranked_json': str(reranked_json),
        'multi_shops_json': str(multi_shops_json),
        'scored_json': str(scored_json),
        'final_scored_json': str(final_scored_json),
        'score_distribution_json': str(score_distribution_json),
        'score_distribution': score_distribution,
        'top_json': str(top_json),
        'shortlist_md': str(shortlist_md),
    }
    summary_path = base / 'workflow-summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(summary_path))


if __name__ == '__main__':
    main()
