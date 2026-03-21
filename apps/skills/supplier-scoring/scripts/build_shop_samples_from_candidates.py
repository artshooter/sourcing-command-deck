#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description='Group candidate/scored rows into shop-level sample sets using shop_url or supplier_name.')
    ap.add_argument('input_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = load_json(args.input_json)
    rows = data.get('scored_rows') or data.get('kept_rows') or data.get('candidate_rows') or data.get('top_suppliers') or []

    groups = defaultdict(list)
    for row in rows:
        key = row.get('shop_url') or row.get('supplier_name') or row.get('source_url') or ''
        if not key:
            continue
        groups[key].append(row)

    shop_samples = []
    for key, items in groups.items():
        shop_samples.append({
            'shop_key': key,
            'shop_url': items[0].get('shop_url', ''),
            'supplier_name': items[0].get('supplier_name', ''),
            'sample_count': len(items),
            'samples': items,
        })

    out = {
        'brief_summary': data.get('brief_summary', ''),
        'shop_samples': sorted(shop_samples, key=lambda x: x['sample_count'], reverse=True)
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
