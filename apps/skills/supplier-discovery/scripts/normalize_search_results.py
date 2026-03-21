#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Normalize external search results into supplier candidate rows.')
    ap.add_argument('search_results_json')
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--channel', default='1688')
    ap.add_argument('--query-used', default='')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.search_results_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    results = data.get('results', []) or data.get('web', {}).get('results', []) or []
    for r in results:
        title = r.get('title', '')
        url = r.get('url', '')
        snippet = r.get('description', '') or r.get('snippet', '')
        rows.append({
            'item_index': args.item_index,
            'channel': args.channel,
            'query_used': args.query_used,
            'supplier_name': title,
            'source_channel': args.channel,
            'source_url': url,
            'market_fit_guess': '',
            'category_fit_guess': '',
            'style_fit_guess': '',
            'price_fit_guess': '',
            'evidence': [title, snippet] if snippet else [title],
            'risk_notes': [],
            'confidence': 'low'
        })

    out = {'candidate_rows': rows}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
