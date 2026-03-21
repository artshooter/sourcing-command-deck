#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

TAG_RE = re.compile(r'<[^>]+>')


def clean_html_text(text):
    if not text:
        return ''
    return TAG_RE.sub('', str(text)).strip()


def extract_rows(obj, item_index, query):
    offer = (((obj.get('data') or {}).get('data') or {}).get('OFFER') or {})
    items = offer.get('items') or []
    rows = []
    for item in items:
        d = item.get('data') or {}
        shop = d.get('shop') or {}
        shop_add = d.get('shopAddition') or {}
        price_info = d.get('priceInfo') or {}
        trade_service = shop_add.get('tradeService') or {}
        evidence = []
        if d.get('title'):
            evidence.append(clean_html_text(d.get('title')))
        if shop.get('text'):
            evidence.append(shop.get('text'))
        if d.get('province'):
            evidence.append(f"地区:{d.get('province')}")
        if price_info.get('price'):
            evidence.append(f"价格:{price_info.get('price')}")
        if shop_add.get('quantityPrices'):
            evidence.append('阶梯价:' + '; '.join([f"{x.get('quantity')}={x.get('value')}" for x in shop_add.get('quantityPrices', [])[:3]]))
        if d.get('factoryInspection'):
            evidence.append('厂检:true')
        if trade_service.get('compositeNewScore'):
            evidence.append(f"综合分:{trade_service.get('compositeNewScore')}")

        risk_notes = []
        if not d.get('factoryInspection'):
            risk_notes.append('未显示厂检')
        if not shop_add.get('shopLinkUrl'):
            risk_notes.append('缺少店铺链接')

        rows.append({
            'item_index': item_index,
            'channel': '1688',
            'query_used': query,
            'supplier_name': shop.get('text') or d.get('loginId') or '',
            'source_channel': '1688',
            'source_url': d.get('linkUrl') or '',
            'shop_url': shop_add.get('shopLinkUrl') or '',
            'product_title': clean_html_text(d.get('title') or ''),
            'product_image': d.get('offerPicUrl') or '',
            'market_fit_guess': '',
            'category_fit_guess': '',
            'style_fit_guess': '',
            'price_fit_guess': price_info.get('price') or '',
            'evidence': evidence,
            'risk_notes': risk_notes,
            'confidence': 'medium',
            'extra': {
                'province': d.get('province') or '',
                'booked_count': d.get('bookedCount'),
                'factory_inspection': d.get('factoryInspection'),
                'member_id': d.get('memberId') or '',
                'login_id': d.get('loginId') or '',
                'composite_score': trade_service.get('compositeNewScore'),
                'quantity_prices': shop_add.get('quantityPrices') or [],
            }
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description='Extract candidate rows from 1688 mtop result JSON.')
    ap.add_argument('mtop_json')
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--query', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    obj = json.loads(Path(args.mtop_json).read_text(encoding='utf-8'))
    rows = extract_rows(obj, args.item_index, args.query)
    out = {'candidate_rows': rows}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
