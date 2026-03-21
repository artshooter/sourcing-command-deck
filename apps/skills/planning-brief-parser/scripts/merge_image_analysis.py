#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def normalize_list(v):
    if not v:
        return []
    if isinstance(v, list):
        return [x for x in v if x]
    return [v]


def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description='Merge row-level image analysis back into parsed planning brief JSON.')
    ap.add_argument('parsed_json')
    ap.add_argument('image_analysis_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.parsed_json, 'r', encoding='utf-8') as f:
        parsed = json.load(f)
    with open(args.image_analysis_json, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    idx_map = {item.get('item_index'): item for item in analysis.get('item_image_sets', [])}

    for i, item in enumerate(parsed.get('items', []), 1):
        ann = idx_map.get(i)
        if not ann:
            item['image_analysis_status'] = 'missing'
            continue

        item['image_analysis_status'] = ann.get('status', 'done')
        item['image_summary'] = ann.get('image_summary', '')
        item['image_consensus_tags'] = dedupe_keep_order(normalize_list(ann.get('image_consensus_tags')))
        item['image_unique_tags'] = dedupe_keep_order(normalize_list(ann.get('image_unique_tags')))
        item['image_conflict_tags'] = dedupe_keep_order(normalize_list(ann.get('image_conflict_tags')))
        item['image_visual_fields'] = ann.get('image_visual_fields', {})

        merged_style = normalize_list(item.get('style_tags')) + item['image_consensus_tags']
        merged_silhouette = normalize_list(item.get('silhouette_tags')) + normalize_list(ann.get('image_visual_fields', {}).get('silhouette_tags'))
        merged_required = normalize_list(item.get('required_tags'))
        merged_forbidden = normalize_list(item.get('forbidden_tags')) + item['image_conflict_tags']

        item['merged_style_tags'] = dedupe_keep_order(merged_style)
        item['merged_silhouette_tags'] = dedupe_keep_order(merged_silhouette)
        item['merged_required_tags'] = dedupe_keep_order(merged_required)
        item['merged_forbidden_tags'] = dedupe_keep_order(merged_forbidden)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
