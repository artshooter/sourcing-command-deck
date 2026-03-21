#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Build row-level image sets from parsed planning brief JSON.')
    ap.add_argument('parsed_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    with open(args.parsed_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sets = []
    for i, item in enumerate(data.get('items', []), 1):
        images = item.get('anchored_images', []) or []
        sets.append({
            'item_index': i,
            'market': item.get('market'),
            'theme': item.get('theme'),
            'brief_summary': item.get('brief_summary'),
            'forbidden_tags': item.get('forbidden_tags', []),
            'required_tags': item.get('required_tags', []),
            'image_count': len(images),
            'image_paths': [img.get('image_path') for img in images],
            'image_cells': [img.get('cell_ref') for img in images],
        })

    out = {'source_file': data.get('source_file'), 'item_image_sets': sets}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == '__main__':
    main()
