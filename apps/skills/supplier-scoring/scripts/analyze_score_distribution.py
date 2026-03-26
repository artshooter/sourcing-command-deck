#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from scoring_levels import (
    A_LEVEL_MIN_PRICE_FIT,
    A_LEVEL_MIN_RISK_PENALTY,
    A_LEVEL_MIN_SCORE,
    A_LEVEL_MIN_THEME_STYLE,
    B_LEVEL_MIN_SCORE,
    C_LEVEL_MIN_SCORE,
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def ratio(numerator, denominator):
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def build_warnings(total_rows, level_counts, gate_failures):
    warnings = []
    a_ratio = ratio(level_counts['A'], total_rows)
    b_ratio = ratio(level_counts['B'], total_rows)
    c_ratio = ratio(level_counts['C'], total_rows)

    if total_rows == 0:
        warnings.append('无候选商家，无法判断分层分布')
        return warnings
    if a_ratio > 0.2:
        warnings.append('A 类占比偏高，建议复核主题词或继续提高 A 类门槛')
    if level_counts['A'] == 0:
        warnings.append('A 类为空，建议检查 query、企划词或价格带是否过窄')
    if (b_ratio + c_ratio) < 0.3:
        warnings.append('B/C 缓冲层偏薄，分层可能过于陡峭')
    if gate_failures['theme_style'] > 0:
        warnings.append('有商家总分达标但被主题/风格硬门槛拦下，说明相关性不足')
    if gate_failures['price_fit'] > 0:
        warnings.append('有商家总分达标但被价格硬门槛拦下，说明价格适配仍需人工复核')
    if gate_failures['risk_penalty'] > 0:
        warnings.append('有商家总分达标但被风险硬门槛拦下，说明存在明显风格漂移或禁忌命中')
    if c_ratio > 0.5:
        warnings.append('C 类占比较高，说明当前候选多为弱匹配储备')
    return warnings


def summarize_rows(rows):
    level_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    score_bands = {
        'gte_48': 0,
        '36_47': 0,
        '24_35': 0,
        '0_23': 0,
        'lt_0': 0,
    }
    gate_failures = {
        'theme_style': 0,
        'price_fit': 0,
        'risk_penalty': 0,
    }
    totals = []

    for row in rows:
        total = safe_float(row.get('score_total', 0), 0.0)
        totals.append(total)

        level = row.get('recommendation_level') or 'D'
        if level not in level_counts:
            level = 'D'
        level_counts[level] += 1

        if total >= A_LEVEL_MIN_SCORE:
            score_bands['gte_48'] += 1
        elif total >= B_LEVEL_MIN_SCORE:
            score_bands['36_47'] += 1
        elif total >= C_LEVEL_MIN_SCORE:
            score_bands['24_35'] += 1
        elif total >= 0:
            score_bands['0_23'] += 1
        else:
            score_bands['lt_0'] += 1

        breakdown = row.get('score_breakdown', {}) or {}
        if total >= A_LEVEL_MIN_SCORE:
            if safe_float(breakdown.get('theme_style', 0), 0.0) < A_LEVEL_MIN_THEME_STYLE:
                gate_failures['theme_style'] += 1
            if safe_float(breakdown.get('price_fit', 0), 0.0) < A_LEVEL_MIN_PRICE_FIT:
                gate_failures['price_fit'] += 1
            if safe_float(breakdown.get('risk_penalty', 0), 0.0) < A_LEVEL_MIN_RISK_PENALTY:
                gate_failures['risk_penalty'] += 1

    total_rows = len(rows)
    avg_score = round(sum(totals) / total_rows, 2) if total_rows else 0
    min_score = round(min(totals), 2) if totals else 0
    max_score = round(max(totals), 2) if totals else 0

    return {
        'total_rows': total_rows,
        'score_stats': {
            'min': min_score,
            'max': max_score,
            'avg': avg_score,
        },
        'level_counts': level_counts,
        'level_ratios': {k: ratio(v, total_rows) for k, v in level_counts.items()},
        'score_bands': score_bands,
        'a_gate_failures': gate_failures,
        'warnings': build_warnings(total_rows, level_counts, gate_failures),
        'thresholds': {
            'A': {
                'min_score': A_LEVEL_MIN_SCORE,
                'min_theme_style': A_LEVEL_MIN_THEME_STYLE,
                'min_price_fit': A_LEVEL_MIN_PRICE_FIT,
                'min_risk_penalty': A_LEVEL_MIN_RISK_PENALTY,
            },
            'B': {'min_score': B_LEVEL_MIN_SCORE},
            'C': {'min_score': C_LEVEL_MIN_SCORE},
        },
    }


def main():
    ap = argparse.ArgumentParser(description='Analyze score distribution for one scored supplier output.')
    ap.add_argument('scored_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = load_json(args.scored_json)
    rows = data.get('scored_rows', []) or []
    summary = summarize_rows(rows)
    summary.update({
        'item_index': data.get('item_index'),
        'brief_summary': data.get('brief_summary', ''),
        'source_scored_json': str(Path(args.scored_json)),
    })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
