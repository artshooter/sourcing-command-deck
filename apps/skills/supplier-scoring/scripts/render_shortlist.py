#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description='Render shortlist markdown from enriched scored suppliers.')
    ap.add_argument('enriched_scored_json')
    ap.add_argument('--top-k', type=int, default=20)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.enriched_scored_json).read_text(encoding='utf-8'))
    rows = data.get('scored_rows', [])[: args.top_k]

    lines = []
    lines.append(f"# 招商 shortlist\n")
    lines.append(f"**Brief**: {data.get('brief_summary', '')}\n")

    for i, row in enumerate(rows, 1):
        lines.append(f"## {i}. {row.get('supplier_name', '')}  |  {row.get('recommendation_level', '')}  |  {row.get('score_total', '')}")
        lines.append(f"- 标题：{row.get('product_title', '')}")
        lines.append(f"- 价格：{row.get('price_fit_guess', '')}")
        lines.append(f"- 商家画像：{row.get('supplier_profile_summary', '')}")
        lines.append(f"- 评分摘要：{json.dumps(row.get('score_breakdown', {}), ensure_ascii=False)}")
        if row.get('recommend_reasons'):
            lines.append(f"- 推荐理由：{'；'.join(row.get('recommend_reasons', [])[:4])}")
        if row.get('risk_warnings'):
            lines.append(f"- 风险提示：{'；'.join(row.get('risk_warnings', [])[:4])}")
        if row.get('shop_url'):
            lines.append(f"- 店铺：{row.get('shop_url')}")
        if row.get('source_url'):
            lines.append(f"- 商品：{row.get('source_url')}")
        lines.append('')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
