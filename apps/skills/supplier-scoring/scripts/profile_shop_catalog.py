#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path

TAG_RE = re.compile(r'<[^>]+>')
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
URL_RE = re.compile(r'https?://[^\s"\']+')

STYLE_KEYWORDS = ['晕染印花', '印花', '晕染', '网纱', '拼接', '荷叶边', '绑带', '系带', '度假', '欧美', '连衣裙', '女装', '跨境', '外贸', '亚马逊', '泡泡袖', '收腰']
BAD_KEYWORDS = ['万圣节', 'cos', '戏服', '家居服', '睡裙', '角色扮演', '中世纪']
PRICE_RE = re.compile(r'(?<!\d)(\d+(?:\.\d+)?)(?!\d)')


def clean_text(html):
    text = TAG_RE.sub(' ', html or '')
    return ' '.join(text.split())


def extract_title(html):
    m = TITLE_RE.search(html or '')
    return clean_text(m.group(1)) if m else ''


def keyword_hits(text, keywords):
    hits = []
    for kw in keywords:
        if kw in text:
            hits.append(kw)
    return hits


def extract_offer_ids(text):
    # weak extraction from shop page links / embedded data
    ids = re.findall(r'offerId[=:\"]+(\d{6,})', text)
    ids += re.findall(r'/offer/(\d{6,})\.html', text)
    ids += re.findall(r'offerId%3D(\d{6,})', text)
    seen = set()
    out = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:30]


def infer_price_band(text):
    vals = []
    for m in PRICE_RE.finditer(text[:8000]):
        try:
            v = float(m.group(1))
        except Exception:
            continue
        if 1 <= v <= 5000:
            vals.append(v)
    if not vals:
        return {'guess': 'unknown', 'samples': []}
    vals = vals[:80]
    avg = sum(vals) / len(vals)
    if avg < 25:
        guess = 'low'
    elif avg < 50:
        guess = 'mid-low'
    elif avg < 80:
        guess = 'mid'
    else:
        guess = 'high'
    return {'guess': guess, 'samples': vals[:12], 'avg': round(avg, 2)}


def main():
    ap = argparse.ArgumentParser(description='Infer shop catalog profile from fetched shop HTML.')
    ap.add_argument('shop_html_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.shop_html_json).read_text(encoding='utf-8'))
    html = data.get('html', '')
    text = clean_text(html)
    title = extract_title(html)

    style_hits = keyword_hits(text, STYLE_KEYWORDS)
    bad_hits = keyword_hits(text.lower(), [x.lower() for x in BAD_KEYWORDS])
    offer_ids = extract_offer_ids(html)
    price_band = infer_price_band(text)

    counter = Counter(style_hits)
    main_style = [k for k, _ in counter.most_common(8)]

    if len(main_style) >= 6:
        consistency = 'high'
    elif len(main_style) >= 3:
        consistency = 'medium'
    elif len(main_style) >= 1:
        consistency = 'low'
    else:
        consistency = 'unknown'

    platform_fit = 'medium'
    if ('女装' in main_style or '连衣裙' in main_style) and len(main_style) >= 3:
        platform_fit = 'high'
    if bad_hits and consistency in ('low', 'unknown'):
        platform_fit = 'low'

    risk_notes = []
    if bad_hits:
        risk_notes.append('店铺出现风格漂移词:' + '、'.join(bad_hits[:5]))
    if not offer_ids:
        risk_notes.append('未能从店铺页提取到足够商品线索')

    summary = []
    if title:
        summary.append(title)
    if main_style:
        summary.append('店铺主风格:' + '、'.join(main_style[:6]))
    summary.append('一致性:' + consistency)
    summary.append('平台适配:' + platform_fit)
    if price_band.get('guess') != 'unknown':
        summary.append('价格层级:' + price_band['guess'])
    if offer_ids:
        summary.append(f'商品线索数:{len(offer_ids)}')
    if risk_notes:
        summary.append('风险:' + '；'.join(risk_notes[:2]))

    out = {
        'shop_catalog_profile': {
            'shop_url': data.get('shop_url', ''),
            'shop_title': title,
            'main_style_signals': main_style,
            'crossborder_signals': [x for x in main_style if x in ['跨境', '外贸', '亚马逊', '欧美']],
            'price_position_guess': price_band.get('guess', 'unknown'),
            'price_samples': price_band.get('samples', []),
            'shop_consistency_guess': consistency,
            'platform_fit_guess': platform_fit,
            'offer_id_samples': offer_ids[:10],
            'risk_notes': risk_notes,
        },
        'shop_catalog_profile_summary': '｜'.join(summary),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
