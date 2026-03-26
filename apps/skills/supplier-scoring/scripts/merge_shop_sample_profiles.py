#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from scoring_levels import refresh_rows_recommendation_levels


def main():
    ap = argparse.ArgumentParser(description='Merge shop sample profiles into scored supplier rows by shop_url or supplier_name.')
    ap.add_argument('scored_json')
    ap.add_argument('shop_profiles_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    scored = json.loads(Path(args.scored_json).read_text(encoding='utf-8'))
    profs = json.loads(Path(args.shop_profiles_json).read_text(encoding='utf-8')).get('shop_profiles', [])

    by_key = {}
    for p in profs:
        if p.get('shop_url'):
            by_key[p['shop_url']] = p
        if p.get('supplier_name'):
            by_key[p['supplier_name']] = p

    for row in scored.get('scored_rows', []):
        key = row.get('shop_url') or row.get('supplier_name')
        p = by_key.get(key)
        if not p:
            continue
        row['shop_sample_profile'] = p
        row['shop_sample_profile_summary'] = p.get('summary', '')
        delta = 0
        fit = p.get('platform_fit_guess')
        consistency = p.get('shop_consistency_guess')
        if fit == 'high':
            delta += 6
        elif fit == 'low':
            delta -= 6
        if consistency == 'high':
            delta += 4
        elif consistency == 'medium':
            delta += 2
        elif consistency == 'low':
            delta -= 1
        if p.get('sample_count', 0) >= 3:
            delta += 2
        if p.get('risk_notes'):
            delta -= min(4, len(p.get('risk_notes', [])) * 2)
        row['shop_sample_score_delta'] = delta
        row['score_total'] = row.get('score_total', 0) + delta
        row.setdefault('recommend_reasons', [])
        row.setdefault('risk_warnings', [])
        if delta > 0:
            row['recommend_reasons'].insert(0, '同店铺多个商品样本与企划方向一致')
        elif delta < 0:
            row['risk_warnings'].insert(0, '同店铺样本显示整体风格一致性不足或存在漂移')

    refresh_rows_recommendation_levels(scored.get('scored_rows', []))

    scored['scored_rows'].sort(key=lambda x: x.get('score_total', 0), reverse=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
