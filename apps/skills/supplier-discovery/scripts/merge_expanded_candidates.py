#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (
            row.get('shop_url') or '',
            row.get('product_title') or '',
            row.get('source_url') or '',
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser(description='Merge expanded shop-sample candidate rows into an existing candidate/scored pool.')
    ap.add_argument('base_json')
    ap.add_argument('expanded_rows_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    base = json.loads(Path(args.base_json).read_text(encoding='utf-8'))
    exp = json.loads(Path(args.expanded_rows_json).read_text(encoding='utf-8'))

    if 'candidate_rows' in base:
        rows = base.get('candidate_rows', []) + exp.get('candidate_rows', [])
        base['candidate_rows'] = dedupe(rows)
    elif 'kept_rows' in base:
        rows = base.get('kept_rows', []) + exp.get('candidate_rows', [])
        base['kept_rows'] = dedupe(rows)
    elif 'scored_rows' in base:
        # expansion should usually happen before scoring, but support this merge too
        rows = base.get('scored_rows', []) + exp.get('candidate_rows', [])
        base['scored_rows'] = dedupe(rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
