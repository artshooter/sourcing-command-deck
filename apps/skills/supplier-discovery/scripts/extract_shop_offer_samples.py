#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

TITLE_PAT = re.compile(r'(?:title|subject)["\']?\s*[:=]\s*["\']([^"\']{6,120})["\']', re.I)
PRICE_PAT = re.compile(r'(?<!\d)(\d+(?:\.\d+)?)(?!\d)')
OFFER_ID_PAT = re.compile(r'offerId[=:\"]+(\d{6,})|/offer/(\d{6,})\.html', re.I)
IMG_PAT = re.compile(r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)', re.I)

BAD_TOKENS = {'window.g_config', 'jstracker', 'aplus', 'collection_url', 'whiteScreen'}


def unique_keep(items):
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser(description='Extract weak product samples from a 1688 shop page HTML.')
    ap.add_argument('shop_page_json')
    ap.add_argument('--supplier-name', default='')
    ap.add_argument('--item-index', type=int, default=0)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.shop_page_json).read_text(encoding='utf-8'))
    html = data.get('html', '')
    shop_url = data.get('shop_url', '')

    titles = []
    for m in TITLE_PAT.finditer(html):
        title = m.group(1).strip()
        if len(title) < 6:
            continue
        if any(tok in title for tok in BAD_TOKENS):
            continue
        titles.append(title)
    titles = unique_keep(titles)[:30]

    offer_ids = []
    for m in OFFER_ID_PAT.finditer(html):
        offer_ids.append(m.group(1) or m.group(2))
    offer_ids = unique_keep([x for x in offer_ids if x])[:30]

    imgs = unique_keep(IMG_PAT.findall(html))[:30]

    prices = []
    for m in PRICE_PAT.finditer(html[:20000]):
        try:
            v = float(m.group(1))
        except Exception:
            continue
        if 5 <= v <= 1000:
            prices.append(v)
    prices = prices[:100]

    rows = []
    for i, title in enumerate(titles[:12], 1):
        price = ''
        if i-1 < len(prices):
            price = str(prices[i-1])
        offer_id = offer_ids[i-1] if i-1 < len(offer_ids) else ''
        source_url = f'https://detail.1688.com/offer/{offer_id}.html' if offer_id else shop_url
        img = imgs[i-1] if i-1 < len(imgs) else ''
        rows.append({
            'item_index': args.item_index,
            'channel': '1688-shop-expansion',
            'query_used': 'shop_expansion',
            'supplier_name': args.supplier_name,
            'source_channel': '1688',
            'source_url': source_url,
            'shop_url': shop_url,
            'product_title': title,
            'product_image': img,
            'market_fit_guess': '',
            'category_fit_guess': '',
            'style_fit_guess': '',
            'price_fit_guess': price,
            'evidence': [title, 'shop_expansion'],
            'risk_notes': ['来自店铺扩样，需进一步校验'],
            'confidence': 'low',
            'extra': {
                'offer_id': offer_id,
                'expansion_source': 'shop_homepage',
            }
        })

    out = {'candidate_rows': rows, 'offer_ids': offer_ids, 'sample_titles': titles, 'sample_prices': prices[:20]}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
