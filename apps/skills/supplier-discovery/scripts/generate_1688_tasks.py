#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

CN_CATEGORY_MAP = {
    'Dress': '连衣裙',
    'Skirt': '半身裙',
    'Top': '上衣',
    'Shirt': '衬衫',
    'Tee': 'T恤',
    'Pants': '裤子',
    'Jeans': '牛仔裤',
    'Denim': '牛仔',
    'Jacket': '外套',
    'jumpsuits': '连体裤',
    'jumpsuit': '连体裤',
}

MARKET_HINT_MAP = {
    '中东': '中东风',
    '印度': '印度风',
}


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


def get_cn_category(item):
    cat = item.get('category_l3') or item.get('category_l2') or item.get('category_l1') or ''
    return CN_CATEGORY_MAP.get(cat, cat)


def pick_tags(item):
    tags = []
    for key in ['merged_style_tags', 'style_tags', 'fabrics', 'elements', 'required_tags']:
        for x in item.get(key, []) or []:
            if x and x not in tags:
                tags.append(x)
    return tags


def zh_only(text):
    text = (text or '').strip()
    if not text:
        return ''
    text = text.replace('\n', ' ')
    text = text.replace('/', ' ')
    text = text.replace('|', ' ')
    text = text.replace('  ', ' ')
    return text.strip()


def build_native_queries(item):
    cat_cn = zh_only(get_cn_category(item)) or '女装'
    theme = zh_only(item.get('theme', ''))
    market = zh_only(item.get('market', ''))
    style_raw = zh_only(item.get('style_raw', ''))
    tags = [zh_only(x) for x in pick_tags(item)]
    fabrics = [zh_only(x) for x in (item.get('fabrics', []) or [])]
    elements = [zh_only(x) for x in (item.get('elements', []) or [])]
    queries = []

    if theme:
        queries.append(theme)
        if cat_cn and cat_cn not in theme:
            queries.append(f'{theme} {cat_cn}')

    style_bits = [x for x in style_raw.split() if x][:2]
    for s in style_bits:
        if theme:
            queries.append(f'{s}{theme}')
        elif cat_cn:
            queries.append(f'{s}{cat_cn}')

    for fabric in fabrics[:2]:
        if theme:
            queries.append(f'{fabric}{theme}')
        elif cat_cn:
            queries.append(f'{fabric}{cat_cn}')

    for element in elements[:2]:
        if theme:
            queries.append(f'{element}{theme}')
        elif cat_cn:
            queries.append(f'{element}{cat_cn}')

    hint = MARKET_HINT_MAP.get(market)
    if hint and theme:
        queries.append(f'{hint} {theme}')
    elif hint and cat_cn:
        queries.append(f'{hint} {cat_cn}')

    if cat_cn:
        queries += [
            f'{cat_cn}',
            f'{cat_cn} 女装',
            f'{cat_cn} 厂家',
            f'{cat_cn} 源头厂',
        ]
    return dedupe_keep_order([q for q in queries if q])


def main():
    ap = argparse.ArgumentParser(description='Generate 1688-native discovery tasks from parsed planning brief items.')
    ap.add_argument('brief_json')
    ap.add_argument('--item-index', type=int, help='1-based item index; omit to generate for all items')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.brief_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    selected = enumerate(items, 1)
    if args.item_index:
        selected = [(args.item_index, items[args.item_index - 1])]

    tasks = []
    for idx, item in selected:
        tasks.append({
            'item_index': idx,
            'market': item.get('market'),
            'theme': item.get('theme'),
            'brief_summary': item.get('brief_summary'),
            'channel': '1688',
            'category_cn': get_cn_category(item),
            'queries_1688_native': build_native_queries(item),
            'required_tags': item.get('merged_required_tags') or item.get('required_tags', []),
            'forbidden_tags': item.get('merged_forbidden_tags') or item.get('forbidden_tags', []),
        })

    out = {'source_file': data.get('source_file'), 'tasks': tasks}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
