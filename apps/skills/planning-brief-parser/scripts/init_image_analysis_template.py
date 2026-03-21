#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Initialize a row-level image analysis template from item-image-sets JSON.')
    ap.add_argument('item_image_sets_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.item_image_sets_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    out = {'source_file': data.get('source_file'), 'item_image_sets': []}
    for item in data.get('item_image_sets', []):
        out['item_image_sets'].append({
            'item_index': item.get('item_index'),
            'market': item.get('market'),
            'theme': item.get('theme'),
            'brief_summary': item.get('brief_summary'),
            'forbidden_tags': item.get('forbidden_tags', []),
            'required_tags': item.get('required_tags', []),
            'image_count': item.get('image_count', 0),
            'image_paths': item.get('image_paths', []),
            'image_cells': item.get('image_cells', []),
            'status': 'pending',
            'image_summary': '',
            'image_consensus_tags': [],
            'image_unique_tags': [],
            'image_conflict_tags': [],
            'image_visual_fields': {
                'garment_type_tags': [],
                'silhouette_tags': [],
                'neckline_tags': [],
                'sleeve_tags': [],
                'length_tags': [],
                'fabric_visual_tags': [],
                'pattern_tags': [],
                'detail_tags': [],
                'mood_tags': []
            }
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
