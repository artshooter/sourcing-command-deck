#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Initialize empty candidate pools for supplier discovery requests.')
    ap.add_argument('discovery_requests_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.discovery_requests_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    out = {'source_file': data.get('source_file'), 'candidate_pools': []}
    for req in data.get('discovery_requests', []):
        out['candidate_pools'].append({
            'item_index': req.get('item_index'),
            'market': req.get('market'),
            'theme': req.get('theme'),
            'brief_summary': req.get('brief_summary'),
            'queries': req.get('queries', []),
            'candidates': []
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
