#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from scoring_levels import refresh_rows_recommendation_levels


def main():
    ap = argparse.ArgumentParser(description='Merge shop catalog profile into one scored supplier row by rank index.')
    ap.add_argument('scored_json')
    ap.add_argument('shop_catalog_profile_json')
    ap.add_argument('--rank-index', type=int, required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.scored_json).read_text(encoding='utf-8'))
    catalog = json.loads(Path(args.shop_catalog_profile_json).read_text(encoding='utf-8'))

    idx = args.rank_index - 1
    row = data['scored_rows'][idx]
    prof = catalog.get('shop_catalog_profile', {})
    row['shop_catalog_profile'] = prof
    row['shop_catalog_profile_summary'] = catalog.get('shop_catalog_profile_summary', '')

    delta = 0
    fit = prof.get('platform_fit_guess')
    consistency = prof.get('shop_consistency_guess')
    price_guess = prof.get('price_position_guess')
    if fit == 'high':
        delta += 5
    elif fit == 'low':
        delta -= 5
    if consistency == 'high':
        delta += 4
    elif consistency == 'medium':
        delta += 2
    elif consistency == 'low':
        delta -= 2
    if price_guess in ('low', 'mid-low', 'mid'):
        delta += 1
    if prof.get('risk_notes'):
        delta -= min(4, len(prof.get('risk_notes', [])) * 2)

    row['shop_catalog_score_delta'] = delta
    row['score_total'] = row.get('score_total', 0) + delta
    row.setdefault('recommend_reasons', [])
    row.setdefault('risk_warnings', [])
    if delta > 0:
        row['recommend_reasons'].insert(0, '店铺整体商品结构与企划方向较一致')
    elif delta < 0:
        row['risk_warnings'].insert(0, '店铺整体商品结构存在风格漂移或一致性不足')

    refresh_rows_recommendation_levels(data.get('scored_rows', []))

    data['scored_rows'].sort(key=lambda x: x.get('score_total', 0), reverse=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
