#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Extract same-shop multi-product samples from raw 1688 candidate rows.')
    ap.add_argument('candidate_rows_json')
    ap.add_argument('--min-samples', type=int, default=2)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    rows = json.loads(Path(args.candidate_rows_json).read_text(encoding='utf-8')).get('candidate_rows', [])
    grouped = defaultdict(list)
    for row in rows:
        key = row.get('shop_url') or row.get('supplier_name') or ''
        if not key:
            continue
        grouped[key].append(row)

    shops = []
    for key, items in grouped.items():
        if len(items) >= args.min_samples:
            shops.append({
                'shop_key': key,
                'shop_url': items[0].get('shop_url', ''),
                'supplier_name': items[0].get('supplier_name', ''),
                'sample_count': len(items),
                'samples': items,
            })

    shops.sort(key=lambda x: x['sample_count'], reverse=True)
    out = {'multi_sample_shops': shops}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
