#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def price_tier(price):
    p = safe_float(price)
    if p is None:
        return 'unknown'
    if p < 25:
        return 'low'
    if p < 50:
        return 'mid-low'
    if p < 80:
        return 'mid'
    return 'high'


def infer_business_type(row):
    name = (row.get('supplier_name') or '')
    if '服装厂' in name or '制衣厂' in name or '工厂' in name:
        return 'factory-like'
    if '有限公司' in name or '经营部' in name or '商贸' in name:
        return 'company-like'
    return 'unknown'


def infer_crossborder_signal(row):
    text = ' '.join([
        row.get('product_title', '') or '',
        row.get('supplier_name', '') or '',
        ' '.join(row.get('evidence', []) or [])
    ])
    hits = []
    for kw in ['跨境', '外贸', '亚马逊', '欧美']:
        if kw in text:
            hits.append(kw)
    return hits


def infer_style_summary(row):
    matched = row.get('matched_style_tags') or []
    if matched:
        return '、'.join(map(str, matched[:5]))
    title = row.get('product_title', '') or ''
    guesses = []
    for kw in ['晕染印花', '印花', '网纱', '吊带', '收腰', '荷叶边', '绑带', '度假', '泡泡袖']:
        if kw in title:
            guesses.append(kw)
    return '、'.join(guesses[:5]) if guesses else 'unknown'


def build_profile(row):
    extra = row.get('extra', {}) or {}
    cross = infer_crossborder_signal(row)
    business_type = infer_business_type(row)
    price_band = price_tier(row.get('price_fit_guess'))
    province = extra.get('province') or ''
    booked = extra.get('booked_count')
    style_summary = infer_style_summary(row)

    structured = {
        'business_type_guess': business_type,
        'price_tier_guess': price_band,
        'province': province,
        'factory_inspection': bool(extra.get('factory_inspection')),
        'crossborder_signals': cross,
        'style_summary': style_summary,
        'has_shop_url': bool(row.get('shop_url')),
        'booked_count': booked,
        'shop_url': row.get('shop_url') or '',
    }

    summary_parts = []
    if province:
        summary_parts.append(province)
    summary_parts.append(business_type)
    if style_summary and style_summary != 'unknown':
        summary_parts.append('风格:' + style_summary)
    if price_band != 'unknown':
        summary_parts.append('价格层级:' + price_band)
    if cross:
        summary_parts.append('跨境信号:' + '、'.join(cross[:4]))
    if structured['factory_inspection']:
        summary_parts.append('厂检')
    if booked not in [None, '']:
        summary_parts.append(f'成交:{booked}')

    row['supplier_profile'] = structured
    row['supplier_profile_summary'] = '｜'.join(summary_parts)
    return row


def main():
    ap = argparse.ArgumentParser(description='Enrich scored supplier rows with structured supplier profiles.')
    ap.add_argument('scored_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = load_json(args.scored_json)
    rows = data.get('scored_rows', [])
    enriched = [build_profile(dict(r)) for r in rows]
    data['scored_rows'] = enriched

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
