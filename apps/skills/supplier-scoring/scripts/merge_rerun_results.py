#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Merge second-pass rerun results back into batch summary.')
    ap.add_argument('batch_summary_json')
    ap.add_argument('rerun_summary_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    batch = json.loads(Path(args.batch_summary_json).read_text(encoding='utf-8'))
    rerun = json.loads(Path(args.rerun_summary_json).read_text(encoding='utf-8'))
    by_idx = {x['item_index']: x for x in rerun.get('rerun_results', [])}

    for item in batch.get('batch_results', []):
        rr = by_idx.get(item.get('item_index'))
        if not rr:
            continue
        item['second_pass'] = rr
        if rr.get('status') == 'ok' and int(rr.get('top_count', 0)) > int(item.get('top_count', 0)):
            item['top_count'] = rr.get('top_count', item.get('top_count', 0))
            item['top_json'] = rr.get('top_json', item.get('top_json', ''))
            item['shortlist_md'] = rr.get('shortlist_md', item.get('shortlist_md', ''))
            item['second_pass_promoted'] = True
        else:
            item['second_pass_promoted'] = False

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
