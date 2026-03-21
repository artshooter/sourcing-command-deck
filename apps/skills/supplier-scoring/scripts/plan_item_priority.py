#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def score_item(item, idx):
    score = 0
    reasons = []

    # clearer business constraints = higher priority
    if item.get('price_min') is not None or item.get('price_max') is not None:
        score += 3
        reasons.append('有价格带')
    if item.get('fabrics'):
        score += min(2, len(item.get('fabrics', [])))
        reasons.append('有面料约束')
    if item.get('elements'):
        score += min(2, len(item.get('elements', [])))
        reasons.append('有元素约束')
    if item.get('required_tags'):
        score += 2
        reasons.append('有必备要求')
    if item.get('forbidden_tags'):
        score += 1
        reasons.append('有禁忌项')
    if item.get('anchored_image_count', 0) > 0:
        score += 1
        reasons.append('有参考图')
    if item.get('theme'):
        theme_len = len(item.get('theme', ''))
        if theme_len <= 8:
            score += 2
            reasons.append('主题较聚焦')
        else:
            score += 1
    if item.get('market'):
        score += 1
    # mild front-loading for earlier items if otherwise similar
    score += max(0, 1 - (idx // 20))

    return score, reasons


def main():
    ap = argparse.ArgumentParser(description='Plan item priority from parsed planning brief JSON.')
    ap.add_argument('brief_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = load_json(args.brief_json)
    planned = []
    for idx, item in enumerate(data.get('items', []), 1):
        score, reasons = score_item(item, idx)
        planned.append({
            'item_index': idx,
            'brief_summary': item.get('brief_summary', ''),
            'theme': item.get('theme', ''),
            'market': item.get('market', ''),
            'priority_score': score,
            'priority_reasons': reasons,
        })

    planned.sort(key=lambda x: x['priority_score'], reverse=True)
    out = {'planned_items': planned}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
