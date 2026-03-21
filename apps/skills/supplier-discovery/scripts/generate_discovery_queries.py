#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        item = (item or '').strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def pick_tags(item):
    tags = []
    for key in ['merged_style_tags', 'style_tags', 'fabrics', 'elements', 'required_tags']:
        for x in item.get(key, []) or []:
            if x and x not in tags:
                tags.append(x)
    return tags


def generate_queries(item):
    market = item.get('market', '')
    cat = item.get('category_l3') or item.get('category_l2') or item.get('category_l1') or 'fashion'
    theme = item.get('theme', '')
    tags = pick_tags(item)
    fabrics = item.get('fabrics', []) or []
    elements = item.get('elements', []) or []

    queries = []

    # core
    queries += [
        f'{cat} supplier',
        f'{cat} manufacturer',
        f'{cat} factory',
    ]
    if theme:
        queries += [
            f'{theme} {cat}',
            f'{theme} {cat} supplier',
            f'{theme} {cat} manufacturer',
        ]

    # tags
    for tag in tags[:6]:
        queries += [
            f'{tag} {cat} supplier',
            f'{tag} {cat} manufacturer',
        ]

    # fabrics / elements
    for fabric in fabrics[:3]:
        queries.append(f'{fabric} {cat} supplier')
    for element in elements[:3]:
        queries.append(f'{element} {cat} factory')

    # market
    if market:
        queries += [
            f'{market} {cat} supplier',
            f'{market} fashion {cat} manufacturer',
        ]
        if market == '中东':
            queries += [
                f'middle east {cat} supplier',
                f'middle east fashion {cat} manufacturer',
            ]
        if market == '印度':
            queries += [
                f'india {cat} supplier',
                f'india fashion {cat} manufacturer',
            ]

    # price/value
    queries += [
        f'low price {cat} wholesale',
        f'{cat} budget supplier',
        f'{cat} cheap wholesale',
    ]

    # channel specific
    if theme:
        queries += [
            f'site:1688.com {theme} {cat}',
            f'site:aliexpress.com {theme} {cat}',
            f'site:amazon.com {theme} {cat}',
        ]

    return dedupe_keep_order(queries)


def main():
    ap = argparse.ArgumentParser(description='Generate supplier discovery queries from parsed planning brief items.')
    ap.add_argument('brief_json')
    ap.add_argument('--item-index', type=int, help='1-based item index; omit to generate for all items')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.brief_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    out_items = []
    selected = enumerate(items, 1)
    if args.item_index:
        selected = [(args.item_index, items[args.item_index - 1])]

    for idx, item in selected:
        out_items.append({
            'item_index': idx,
            'market': item.get('market'),
            'theme': item.get('theme'),
            'brief_summary': item.get('brief_summary'),
            'queries': generate_queries(item),
            'forbidden_tags': item.get('merged_forbidden_tags') or item.get('forbidden_tags', []),
            'required_tags': item.get('merged_required_tags') or item.get('required_tags', []),
        })

    output = {'source_file': data.get('source_file'), 'discovery_requests': out_items}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
