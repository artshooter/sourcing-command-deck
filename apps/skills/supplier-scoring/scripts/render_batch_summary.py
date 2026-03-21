#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description='Render a human-readable summary for batch workflow outputs.')
    ap.add_argument('batch_summary_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    batch = load_json(args.batch_summary_json)
    lines = []
    lines.append('# 批量招商结果汇总')
    lines.append('')

    ok_count = sum(1 for x in batch.get('batch_results', []) if x.get('status') == 'ok')
    err_count = sum(1 for x in batch.get('batch_results', []) if x.get('status') != 'ok')
    lines.append(f'- 成功 item 数：{ok_count}')
    lines.append(f'- 失败 item 数：{err_count}')
    lines.append('')

    for item in batch.get('batch_results', []):
        idx = item.get('item_index')
        status = item.get('status')
        lines.append(f'## Item {idx} | {status}')
        if status != 'ok':
            lines.append(f"- 错误：{item.get('error', '')}")
            lines.append('')
            continue

        brief = item.get('brief_summary', '')
        lines.append(f'- Brief：{brief}')
        lines.append(f"- shortlist：{item.get('shortlist_md', '')}")
        lines.append(f"- top_json：{item.get('top_json', '')}")
        lines.append(f"- Top 数量：{item.get('top_count', 0)}")

        try:
            top = load_json(item.get('top_json', ''))
            rows = top.get('top_suppliers', [])[:5]
            if rows:
                lines.append('- Top 5 预览：')
                for i, row in enumerate(rows, 1):
                    lines.append(f"  {i}. {row.get('supplier_name', '')} | {row.get('recommendation_level', '')} | {row.get('score_total', '')} | 价格 {row.get('price_fit_guess', '')}")
                    title = row.get('product_title', '')
                    if title:
                        lines.append(f"     - {title}")
                    profile = row.get('shop_sample_profile_summary') or row.get('supplier_profile_summary') or ''
                    if profile:
                        lines.append(f"     - 画像：{profile}")
                    reasons = row.get('recommend_reasons', [])[:3]
                    if reasons:
                        lines.append(f"     - 推荐：{'；'.join(reasons)}")
                    risks = row.get('risk_warnings', [])[:2]
                    if risks:
                        lines.append(f"     - 风险：{'；'.join(risks)}")
            else:
                lines.append('- Top 5 预览：空')
        except Exception as e:
            lines.append(f'- 读取 top_json 失败：{e}')

        lines.append('')

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
