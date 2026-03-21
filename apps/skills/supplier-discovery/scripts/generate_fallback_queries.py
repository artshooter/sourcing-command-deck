#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_task(path, item_index):
    tasks = json.loads(Path(path).read_text(encoding='utf-8')).get('tasks', [])
    for t in tasks:
        if t.get('item_index') == item_index:
            return t
    raise SystemExit(f'No task for item_index={item_index}')


def build_fallbacks(task):
    cat = (task.get('category_cn') or '女装').strip()
    theme = (task.get('theme') or '').strip()
    req = task.get('required_tags') or []
    queries = []
    # simpler, lower-risk, broader recall
    if theme:
        queries.append(theme)
        if cat and cat not in theme:
            queries.append(f'{theme} {cat}')
        queries.append(f'{theme} 女装')
    for r in req[:2]:
        r = (r or '').strip()
        if not r:
            continue
        if theme:
            queries.append(f'{r}{theme}')
        queries.append(f'{r} {cat}')
    queries += [
        f'{cat}',
        f'{cat} 女装',
        f'{cat} 新款',
        f'{cat} 源头厂',
    ]
    out = []
    seen = set()
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:6]


def main():
    ap = argparse.ArgumentParser(description='Generate lower-risk fallback queries for 1688 batch runs.')
    ap.add_argument('tasks_json')
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    task = load_task(args.tasks_json, args.item_index)
    out = {
        'item_index': args.item_index,
        'fallback_queries': build_fallbacks(task)
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
