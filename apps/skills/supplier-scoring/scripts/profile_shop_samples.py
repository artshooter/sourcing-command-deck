#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path

STYLE_KEYWORDS = ['晕染印花', '印花', '晕染', '网纱', '拼接', '荷叶边', '绑带', '系带', '度假', '欧美', '连衣裙', '女装', '跨境', '外贸', '亚马逊', '泡泡袖', '收腰', '吊带', '长裙']
BAD_KEYWORDS = ['万圣节', 'cos', '戏服', '家居服', '睡裙', '角色扮演', '中世纪']


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def extract_profile(shop_sample):
    rows = shop_sample.get('samples', [])
    text_blobs = []
    prices = []
    bad_hits = []
    style_counter = Counter()
    cross_counter = Counter()
    for row in rows:
        text = ' '.join([
            row.get('product_title', '') or '',
            row.get('supplier_name', '') or '',
            ' '.join(row.get('evidence', []) or [])
        ])
        text_blobs.append(text)
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

    main_style = [k for k, _ in style_counter.most_common(8)]
    cross = [k for k, _ in cross_counter.most_common(4)]

    if len(rows) >= 5 and len(main_style) >= 4:
        consistency = 'high'
    elif len(rows) >= 3 and len(main_style) >= 3:
        consistency = 'medium'
    elif len(main_style) >= 1:
        consistency = 'low'
    else:
        consistency = 'unknown'

    price_guess = 'unknown'
    avg_price = None
    if prices:
        avg_price = round(sum(prices) / len(prices), 2)
        if avg_price < 25:
            price_guess = 'low'
        elif avg_price < 50:
            price_guess = 'mid-low'
        elif avg_price < 80:
            price_guess = 'mid'
        else:
            price_guess = 'high'

    platform_fit = 'medium'
    if ('连衣裙' in main_style or '女装' in main_style) and len(main_style) >= 3:
        platform_fit = 'high'
    if bad_hits and consistency in ('low', 'unknown'):
        platform_fit = 'low'

    risk_notes = []
    if bad_hits:
        risk_notes.append('样本中出现风格漂移词:' + '、'.join(list(dict.fromkeys(bad_hits))[:5]))
    if len(rows) < 2:
        risk_notes.append('同店铺样本不足，整体判断置信度低')

    summary = []
    if shop_sample.get('supplier_name'):
        summary.append(shop_sample['supplier_name'])
    summary.append(f'样本数:{len(rows)}')
    if main_style:
        summary.append('主风格:' + '、'.join(main_style[:6]))
    if cross:
        summary.append('跨境信号:' + '、'.join(cross[:4]))
    if avg_price is not None:
        summary.append(f'均价:{avg_price}')
    summary.append('一致性:' + consistency)
    summary.append('平台适配:' + platform_fit)
    if risk_notes:
        summary.append('风险:' + '；'.join(risk_notes[:2]))

    return {
        'shop_key': shop_sample.get('shop_key', ''),
        'shop_url': shop_sample.get('shop_url', ''),
        'supplier_name': shop_sample.get('supplier_name', ''),
        'sample_count': len(rows),
        'main_style_signals': main_style,
        'crossborder_signals': cross,
        'avg_price': avg_price,
        'price_position_guess': price_guess,
        'shop_consistency_guess': consistency,
        'platform_fit_guess': platform_fit,
        'risk_notes': risk_notes,
        'sample_titles': [r.get('product_title', '') for r in rows[:10]],
        'summary': '｜'.join(summary),
    }


def main():
    ap = argparse.ArgumentParser(description='Build shop-level profiles from grouped in-pool product samples.')
    ap.add_argument('shop_samples_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.shop_samples_json).read_text(encoding='utf-8'))
    profiles = [extract_profile(s) for s in data.get('shop_samples', [])]
    out = {
        'brief_summary': data.get('brief_summary', ''),
        'shop_profiles': sorted(profiles, key=lambda x: (x.get('sample_count', 0), x.get('platform_fit_guess', '')), reverse=True)
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
