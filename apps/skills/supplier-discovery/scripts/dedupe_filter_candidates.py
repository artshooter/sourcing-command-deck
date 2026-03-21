#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def score_row(row, required_tags, forbidden_tags):
    text = ' '.join([
        row.get('product_title', '') or '',
        row.get('supplier_name', '') or '',
        ' '.join(row.get('evidence', []) or [])
    ]).lower()
    score = 0
    matched_required = []
    hit_forbidden = []
    for tag in required_tags or []:
        if str(tag).lower() in text:
            score += 2
            matched_required.append(tag)
    for tag in forbidden_tags or []:
        if str(tag).lower() in text:
            score -= 3
            hit_forbidden.append(tag)
    if row.get('price_fit_guess'):
        score += 1
    if row.get('shop_url'):
        score += 1
    if row.get('extra', {}).get('factory_inspection'):
        score += 1
    return score, matched_required, hit_forbidden


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (
            row.get('shop_url') or '',
            row.get('source_url') or '',
            row.get('supplier_name') or '',
            row.get('product_title') or '',
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser(description='Dedupe and lightly filter supplier candidate rows.')
    ap.add_argument('candidate_rows_json')
    ap.add_argument('--required-tags-json', help='JSON array string, e.g. ["收腰"]')
    ap.add_argument('--forbidden-tags-json', help='JSON array string, e.g. ["前胸打揽"]')
    ap.add_argument('--min-score', type=int, default=0)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    required_tags = json.loads(args.required_tags_json) if args.required_tags_json else []
    forbidden_tags = json.loads(args.forbidden_tags_json) if args.forbidden_tags_json else []

    rows = json.loads(Path(args.candidate_rows_json).read_text(encoding='utf-8')).get('candidate_rows', [])
    rows = dedupe(rows)
    kept = []
    dropped = []
    for row in rows:
        score, matched_required, hit_forbidden = score_row(row, required_tags, forbidden_tags)
        row['light_score'] = score
        row['matched_required_tags'] = matched_required
        row['hit_forbidden_tags'] = hit_forbidden
        if score >= args.min_score:
            kept.append(row)
        else:
            dropped.append(row)

    out = {
        'candidate_rows': sorted(kept, key=lambda x: x.get('light_score', 0), reverse=True),
        'dropped_rows': sorted(dropped, key=lambda x: x.get('light_score', 0), reverse=True),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
