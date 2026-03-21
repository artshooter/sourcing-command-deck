#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Initialize empty candidate rows for 1688 tasks.')
    ap.add_argument('tasks_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.tasks_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    for task in data.get('tasks', []):
        rows.append({
            'item_index': task.get('item_index'),
            'channel': '1688',
            'theme': task.get('theme'),
            'brief_summary': task.get('brief_summary'),
            'query_used': '',
            'supplier_name': '',
            'source_channel': '1688',
            'source_url': '',
            'market_fit_guess': '',
            'category_fit_guess': '',
            'style_fit_guess': '',
            'price_fit_guess': '',
            'evidence': [],
            'risk_notes': [],
            'confidence': ''
        })

    out = {'candidate_rows': rows}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
