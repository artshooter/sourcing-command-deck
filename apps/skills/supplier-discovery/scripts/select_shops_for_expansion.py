#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_rows(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return data.get('kept_rows') or data.get('candidate_rows') or []


def main():
    ap = argparse.ArgumentParser(description='Select top shops from candidate rows for shop expansion.')
    ap.add_argument('candidate_json')
    ap.add_argument('--top-shops', type=int, default=10)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    rows = load_rows(args.candidate_json)
    grouped = {}
    for row in rows:
        key = row.get('shop_url') or row.get('supplier_name') or ''
        if not key:
            continue
        cur = grouped.get(key)
        score = row.get('coarse_score', row.get('score_total', 0))
        if not cur or score > cur['best_score']:
            grouped[key] = {
                'shop_url': row.get('shop_url', ''),
                'supplier_name': row.get('supplier_name', ''),
                'best_score': score,
                'representative_title': row.get('product_title', ''),
                'representative_price': row.get('price_fit_guess', ''),
            }

    shops = sorted(grouped.values(), key=lambda x: x['best_score'], reverse=True)[: args.top_shops]
    out = {'shops_for_expansion': shops}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
