#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Merge a shop-level profile into one scored supplier row by rank index.')
    ap.add_argument('enriched_scored_json')
    ap.add_argument('shop_profile_json')
    ap.add_argument('--rank-index', type=int, required=True, help='1-based index in scored_rows')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.enriched_scored_json).read_text(encoding='utf-8'))
    shop = json.loads(Path(args.shop_profile_json).read_text(encoding='utf-8'))

    idx = args.rank_index - 1
    row = data['scored_rows'][idx]
    row['shop_profile'] = shop.get('shop_profile', {})
    row['shop_profile_summary'] = shop.get('shop_profile_summary', '')

    # small score adjustment
    fit = row['shop_profile'].get('platform_fit_guess')
    consistency = row['shop_profile'].get('shop_consistency_guess')
    delta = 0
    if fit == 'high':
        delta += 4
    elif fit == 'low':
        delta -= 4
    if consistency == 'high':
        delta += 3
    elif consistency == 'low':
        delta -= 2
    row['shop_profile_score_delta'] = delta
    row['score_total'] = row.get('score_total', 0) + delta
    row.setdefault('recommend_reasons', [])
    row.setdefault('risk_warnings', [])
    if delta > 0:
        row['recommend_reasons'].insert(0, '店铺整体风格与平台招商方向较一致')
    elif delta < 0:
        row['risk_warnings'].insert(0, '店铺整体风格一致性或平台适配存在疑点')

    data['scored_rows'].sort(key=lambda x: x.get('score_total', 0), reverse=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
