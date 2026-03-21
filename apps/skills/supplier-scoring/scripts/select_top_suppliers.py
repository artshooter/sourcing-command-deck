#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Select top suppliers from scored supplier rows.')
    ap.add_argument('scored_json')
    ap.add_argument('--top-k', type=int, default=20)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.scored_json).read_text(encoding='utf-8'))
    rows = data.get('scored_rows', [])
    top = rows[: args.top_k]

    # fallback guard: if rows exist but top is empty for any reason, still expose a few best-effort rows
    if not top and rows:
        top = rows[: min(args.top_k, 5)]

    out = {
        'item_index': data.get('item_index'),
        'brief_summary': data.get('brief_summary'),
        'top_suppliers': top,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
