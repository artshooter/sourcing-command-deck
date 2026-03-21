#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def grade_item(top_rows):
    if not top_rows:
        return 'empty'
    top1 = top_rows[0].get('score_total', 0)
    count = len(top_rows)
    if top1 >= 45 and count >= 5:
        return 'strong'
    if top1 >= 30 and count >= 3:
        return 'usable'
    return 'weak'


def main():
    ap = argparse.ArgumentParser(description='Render upgraded batch summary with quality signals and repeated shops.')
    ap.add_argument('batch_summary_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    batch = load_json(args.batch_summary_json)
    items = batch.get('batch_results', [])

    lines = []
    lines.append('# 批量招商结果汇总 V2')
    lines.append('')

    ok_items = [x for x in items if x.get('status') == 'ok']
    err_items = [x for x in items if x.get('status') != 'ok']
    lines.append(f'- 成功 item 数：{len(ok_items)}')
    lines.append(f'- 失败 item 数：{len(err_items)}')
    lines.append('')

    repeated = defaultdict(list)
    item_summaries = []

    for item in ok_items:
        top_rows = []
        try:
            top = load_json(item.get('top_json', ''))
            top_rows = top.get('top_suppliers', [])
        except Exception:
            top_rows = []

        quality = grade_item(top_rows)
        top1 = top_rows[0].get('score_total', 0) if top_rows else 0
        item_summaries.append({
            'item_index': item.get('item_index'),
            'brief_summary': item.get('brief_summary', ''),
            'quality': quality,
            'top_count': len(top_rows),
            'top1_score': top1,
            'shortlist_md': item.get('shortlist_md', ''),
            'top_rows': top_rows,
        })

        for row in top_rows[:10]:
            key = row.get('shop_url') or row.get('supplier_name') or ''
            if not key:
                continue
            repeated[key].append({
                'item_index': item.get('item_index'),
                'supplier_name': row.get('supplier_name', ''),
                'score_total': row.get('score_total', 0),
                'brief_summary': item.get('brief_summary', ''),
            })

    # section 1: item quality dashboard
    lines.append('## 1. Item 质量看板')
    lines.append('')
    for s in sorted(item_summaries, key=lambda x: (x['quality'], x['top1_score']), reverse=True):
        lines.append(f"- Item {s['item_index']} | 质量：{s['quality']} | Top数：{s['top_count']} | Top1分数：{s['top1_score']}")
        lines.append(f"  - Brief：{s['brief_summary']}")
        lines.append(f"  - shortlist：{s['shortlist_md']}")
    lines.append('')

    # section 2: strongest items
    lines.append('## 2. 最值得先看的 Item')
    lines.append('')
    best_items = sorted(item_summaries, key=lambda x: (x['top1_score'], x['top_count']), reverse=True)[:5]
    for s in best_items:
        lines.append(f"### Item {s['item_index']} | {s['quality']} | Top1 {s['top1_score']}")
        lines.append(f"- Brief：{s['brief_summary']}")
        if s['top_rows']:
            row = s['top_rows'][0]
            lines.append(f"- 最优商家：{row.get('supplier_name', '')} | {row.get('recommendation_level', '')} | {row.get('score_total', '')} | 价格 {row.get('price_fit_guess', '')}")
            lines.append(f"- 标题：{row.get('product_title', '')}")
            profile = row.get('shop_sample_profile_summary') or row.get('supplier_profile_summary') or ''
            if profile:
                lines.append(f"- 画像：{profile}")
            reasons = row.get('recommend_reasons', [])[:3]
            if reasons:
                lines.append(f"- 推荐：{'；'.join(reasons)}")
            risks = row.get('risk_warnings', [])[:2]
            if risks:
                lines.append(f"- 风险：{'；'.join(risks)}")
        else:
            lines.append('- 最优商家：空')
        lines.append('')

    # section 3: repeated shops
    lines.append('## 3. 多个 Item 重复命中的店铺')
    lines.append('')
    repeated_items = [(k, v) for k, v in repeated.items() if len(v) >= 2]
    if not repeated_items:
        lines.append('- 暂无重复命中的店铺')
    else:
        repeated_items.sort(key=lambda kv: len(kv[1]), reverse=True)
        for key, hits in repeated_items[:20]:
            supplier_name = hits[0].get('supplier_name', '')
            item_list = ', '.join([f"item {x['item_index']}({x['score_total']})" for x in hits])
            lines.append(f"- {supplier_name}")
            lines.append(f"  - 命中次数：{len(hits)}")
            lines.append(f"  - 命中 item：{item_list}")
            lines.append(f"  - 店铺：{key}")
    lines.append('')

    # section 4: items needing attention
    lines.append('## 4. 需要人工重点补看的 Item')
    lines.append('')
    weak_items = [x for x in item_summaries if x['quality'] in ('weak', 'empty')]
    if not weak_items:
        lines.append('- 暂无')
    else:
        for s in weak_items:
            lines.append(f"- Item {s['item_index']} | 质量：{s['quality']} | Top数：{s['top_count']}")
            lines.append(f"  - Brief：{s['brief_summary']}")
            if not s['top_rows']:
                lines.append('  - 问题：当前未产出 shortlist，建议放宽 query 或补更多渠道')
            else:
                lines.append('  - 问题：有结果但整体偏弱，建议人工复核或补扩样')
    lines.append('')

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
