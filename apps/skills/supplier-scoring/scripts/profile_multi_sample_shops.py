#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path

STYLE_KEYWORDS = ['晕染印花', '印花', '晕染', '网纱', '拼接', '荷叶边', '绑带', '系带', '度假', '欧美', '连衣裙', '女装', '跨境', '外贸', '亚马逊', '泡泡袖', '收腰', '吊带', '长裙', '碎花', '挂脖', '无袖']
BAD_KEYWORDS = ['万圣节', 'cos', '戏服', '家居服', '睡裙', '角色扮演', '中世纪']


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def profile(shop):
    rows = shop.get('samples', [])
    style_counter = Counter()
    cross_counter = Counter()
    bad_hits = []
    prices = []
    for row in rows:
        text = ' '.join([
            row.get('product_title', '') or '',
            row.get('supplier_name', '') or '',
            ' '.join(row.get('evidence', []) or [])
        ])
        for kw in STYLE_KEYWORDS:
            if kw in text:
                style_counter[kw] += 1
        for kw in ['跨境', '外贸', '亚马逊', '欧美']:
            if kw in text:
                cross_counter[kw] += 1
        for kw in BAD_KEYWORDS:
            if kw.lower() in text.lower():
                bad_hits.append(kw)
        p = safe_float(row.get('price_fit_guess'))
        if p is not None:
            prices.append(p)

    main_style = [k for k, _ in style_counter.most_common(10)]
    cross = [k for k, _ in cross_counter.most_common(4)]
    avg_price = round(sum(prices) / len(prices), 2) if prices else None
    if avg_price is None:
        price_guess = 'unknown'
    elif avg_price < 25:
        price_guess = 'low'
    elif avg_price < 50:
        price_guess = 'mid-low'
    elif avg_price < 80:
        price_guess = 'mid'
    else:
        price_guess = 'high'

    if len(rows) >= 4 and len(main_style) >= 4:
        consistency = 'high'
    elif len(rows) >= 2 and len(main_style) >= 3:
        consistency = 'medium'
    elif len(main_style) >= 1:
        consistency = 'low'
    else:
        consistency = 'unknown'

    platform_fit = 'medium'
    if ('连衣裙' in main_style or '女装' in main_style) and ('印花' in main_style or '晕染' in main_style or '度假' in main_style):
        platform_fit = 'high'
    if bad_hits and consistency in ('low', 'unknown'):
        platform_fit = 'low'

    risk = []
    if bad_hits:
        risk.append('样本出现风格漂移词:' + '、'.join(list(dict.fromkeys(bad_hits))[:5]))

    summary = []
    if shop.get('supplier_name'):
        summary.append(shop['supplier_name'])
    summary.append(f'样本数:{len(rows)}')
    if main_style:
        summary.append('主风格:' + '、'.join(main_style[:6]))
    if cross:
        summary.append('跨境信号:' + '、'.join(cross[:4]))
    if avg_price is not None:
        summary.append(f'均价:{avg_price}')
    summary.append('一致性:' + consistency)
    summary.append('平台适配:' + platform_fit)
    if risk:
        summary.append('风险:' + '；'.join(risk[:2]))

    return {
        'shop_key': shop.get('shop_key', ''),
        'shop_url': shop.get('shop_url', ''),
        'supplier_name': shop.get('supplier_name', ''),
        'sample_count': len(rows),
        'main_style_signals': main_style,
        'crossborder_signals': cross,
        'avg_price': avg_price,
        'price_position_guess': price_guess,
        'shop_consistency_guess': consistency,
        'platform_fit_guess': platform_fit,
        'risk_notes': risk,
        'sample_titles': [r.get('product_title', '') for r in rows[:12]],
        'summary': '｜'.join(summary),
    }


def main():
    ap = argparse.ArgumentParser(description='Profile same-shop multi-product samples extracted from raw recall.')
    ap.add_argument('multi_sample_shops_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    shops = json.loads(Path(args.multi_sample_shops_json).read_text(encoding='utf-8')).get('multi_sample_shops', [])
    out = {'shop_profiles': [profile(s) for s in shops]}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
