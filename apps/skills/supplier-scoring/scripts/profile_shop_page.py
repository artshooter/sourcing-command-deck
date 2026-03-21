#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
TAG_RE = re.compile(r'<[^>]+>')


def clean(s):
    if not s:
        return ''
    s = TAG_RE.sub(' ', s)
    return ' '.join(s.split())


def find_keywords(text, keywords):
    hits = []
    for kw in keywords:
        if kw in text:
            hits.append(kw)
    return hits


def main():
    ap = argparse.ArgumentParser(description='Infer shop-level profile from fetched shop page HTML.')
    ap.add_argument('shop_html_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.shop_html_json).read_text(encoding='utf-8'))
    html = data.get('html', '')
    text = clean(html)

    m = TITLE_RE.search(html)
    title = clean(m.group(1)) if m else ''

    main_style = find_keywords(text, ['晕染', '印花', '网纱', '拼接', '荷叶边', '绑带', '度假', '欧美', '连衣裙', '女装', '跨境', '外贸', '亚马逊'])
    cross = find_keywords(text, ['跨境', '外贸', '亚马逊', '欧美'])
    risk = []
    if '家居服' in text or '睡衣' in text or 'cos' in text.lower() or '戏服' in text:
        risk.append('店铺可能存在明显风格漂移')

    consistency = 'unknown'
    if len(main_style) >= 5:
        consistency = 'high'
    elif len(main_style) >= 3:
        consistency = 'medium'
    elif len(main_style) >= 1:
        consistency = 'low'

    platform_fit = 'medium'
    if '女装' in text and ('连衣裙' in text or '欧美' in text or '跨境' in text):
        platform_fit = 'high'
    if risk:
        platform_fit = 'low' if consistency == 'low' else 'medium'

    summary_parts = []
    if title:
        summary_parts.append(title)
    if main_style:
        summary_parts.append('风格信号:' + '、'.join(main_style[:6]))
    if cross:
        summary_parts.append('跨境信号:' + '、'.join(cross[:4]))
    summary_parts.append('一致性:' + consistency)
    summary_parts.append('平台适配:' + platform_fit)
    if risk:
        summary_parts.append('风险:' + '、'.join(risk[:3]))

    out = {
        'shop_profile': {
            'shop_url': data.get('shop_url', ''),
            'shop_title': title,
            'about_text': text[:800],
            'main_style_signals': main_style,
            'crossborder_signals': cross,
            'price_position_guess': 'unknown',
            'shop_consistency_guess': consistency,
            'platform_fit_guess': platform_fit,
            'risk_notes': risk,
        },
        'shop_profile_summary': '｜'.join(summary_parts),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
