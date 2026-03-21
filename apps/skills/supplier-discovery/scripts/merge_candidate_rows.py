#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        key = (item.get('supplier_name'), item.get('source_channel'), item.get('source_url'))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description='Merge supplier candidate rows into candidate pools.')
    ap.add_argument('candidate_pool_json')
    ap.add_argument('candidate_rows_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.candidate_pool_json, 'r', encoding='utf-8') as f:
        pools = json.load(f)
    with open(args.candidate_rows_json, 'r', encoding='utf-8') as f:
        rows = json.load(f)

    idx_map = {p.get('item_index'): p for p in pools.get('candidate_pools', [])}
    for row in rows.get('candidate_rows', []):
        idx = row.get('item_index')
        if idx in idx_map:
            idx_map[idx].setdefault('candidates', []).append(row)

    for pool in pools.get('candidate_pools', []):
        pool['candidates'] = dedupe_keep_order(pool.get('candidates', []))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(pools, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
