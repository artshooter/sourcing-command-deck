#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from scoring_levels import classify_recommendation_level


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def text_blob(row):
    return ' '.join([
        row.get('product_title', '') or '',
        row.get('supplier_name', '') or '',
        ' '.join(row.get('evidence', []) or []),
    ]).lower()


def hits(text, tags):
    out = []
    for tag in tags or []:
        t = str(tag).strip().lower()
        if t and t in text:
            out.append(tag)
    return out


def score_price(price, price_min, price_max):
    p = safe_float(price)
    if p is None:
        return 0, '缺少价格'
    if price_min is None or price_max is None:
        return 2, '有价格可参考'
    if price_min <= p <= price_max:
        return 15, '价格在企划带内'
    if p < price_min:
        return 10, '价格低于企划带，需确认品质/复杂度'
    gap = p - price_max
    if gap <= 5:
        return 6, '价格略高于企划带'
    if gap <= 20:
        return 0, '价格高于企划带'
    return -8, '价格显著高于企划带'


def score_credibility(row):
    score = 0
    reasons = []
    if row.get('shop_url'):
        score += 4
        reasons.append('有店铺链接')
    if row.get('extra', {}).get('factory_inspection'):
        score += 6
        reasons.append('显示厂检')
    if row.get('extra', {}).get('quantity_prices'):
        score += 3
        reasons.append('有阶梯价')
    booked = row.get('extra', {}).get('booked_count')
    try:
        booked = int(booked)
    except Exception:
        booked = None
    if booked is not None:
        if booked >= 100:
            score += 3
            reasons.append('成交量较高')
        elif booked >= 10:
            score += 1
            reasons.append('有一定成交')
    return score, reasons


def score_row(row, brief):
    text = text_blob(row)
    theme = brief.get('theme', '') or ''
    style_tags = brief.get('merged_style_tags') or brief.get('style_tags') or []
    fabrics = brief.get('fabrics') or []
    elements = brief.get('elements') or []
    required_tags = brief.get('merged_required_tags') or brief.get('required_tags') or []
    forbidden_tags = brief.get('merged_forbidden_tags') or brief.get('forbidden_tags') or []
    price_min = brief.get('price_min')
    price_max = brief.get('price_max')

    breakdown = {}
    recommend_reasons = []
    risk_warnings = []

    # Theme/style
    style_score = 0
    if theme and theme.lower() in text:
        style_score += 18
        recommend_reasons.append(f'标题直接命中主题：{theme}')
    style_hits = hits(text, style_tags)
    style_score += min(len(style_hits), 5) * 3
    if style_hits:
        recommend_reasons.append('命中风格标签：' + '、'.join(map(str, style_hits[:5])))
    req_hits = hits(text, required_tags)
    style_score += len(req_hits) * 4
    if req_hits:
        recommend_reasons.append('命中必备要求：' + '、'.join(map(str, req_hits[:4])))
    breakdown['theme_style'] = style_score

    # Fabric/detail
    fd_score = 0
    fabric_hits = hits(text, fabrics)
    element_hits = hits(text, elements)
    fd_score += min(len(fabric_hits), 3) * 4
    fd_score += min(len(element_hits), 4) * 3
    if fabric_hits:
        recommend_reasons.append('命中面料关键词：' + '、'.join(map(str, fabric_hits[:3])))
    if element_hits:
        recommend_reasons.append('命中元素关键词：' + '、'.join(map(str, element_hits[:4])))
    breakdown['fabric_detail'] = fd_score

    # Price
    p_score, p_reason = score_price(row.get('price_fit_guess'), price_min, price_max)
    breakdown['price_fit'] = p_score
    if p_score >= 6:
        recommend_reasons.append(p_reason)
    else:
        risk_warnings.append(p_reason)

    # Credibility
    c_score, c_reasons = score_credibility(row)
    breakdown['credibility'] = c_score
    recommend_reasons.extend(c_reasons)

    # Risks
    risk_penalty = 0
    forbid_hits = hits(text, forbidden_tags)
    if forbid_hits:
        risk_penalty -= len(forbid_hits) * 8
        risk_warnings.append('命中禁忌标签：' + '、'.join(map(str, forbid_hits[:4])))

    bad_kw = ['万圣节', 'cos', '戏服', '家居服', '睡裙', '中世纪', '角色扮演']
    bad_hits = hits(text, bad_kw)
    if bad_hits:
        risk_penalty -= len(bad_hits) * 5
        risk_warnings.append('疑似风格漂移：' + '、'.join(map(str, bad_hits[:4])))

    if not row.get('shop_url'):
        risk_penalty -= 2
        risk_warnings.append('缺少店铺链接')
    if not row.get('supplier_name'):
        risk_penalty -= 3
        risk_warnings.append('缺少供应商名')
    breakdown['risk_penalty'] = risk_penalty

    total = sum(breakdown.values())
    level = classify_recommendation_level(total, breakdown)

    profile_bits = []
    if row.get('supplier_name'):
        profile_bits.append(row['supplier_name'])
    if row.get('product_title'):
        profile_bits.append(row['product_title'][:50])
    if row.get('price_fit_guess'):
        profile_bits.append(f"价格{row['price_fit_guess']}")
    if row.get('extra', {}).get('factory_inspection'):
        profile_bits.append('厂检')
    profile_summary = '｜'.join(profile_bits)

    out = dict(row)
    out['score_total'] = total
    out['score_breakdown'] = breakdown
    out['recommendation_level'] = level
    out['profile_summary'] = profile_summary
    out['recommend_reasons'] = recommend_reasons[:8]
    out['risk_warnings'] = risk_warnings[:8]
    return out


def main():
    ap = argparse.ArgumentParser(description='Score discovered supplier candidates against one planning brief item.')
    ap.add_argument('brief_json')
    ap.add_argument('candidate_json')
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    brief = load_json(args.brief_json).get('items', [])[args.item_index - 1]
    candidate_data = load_json(args.candidate_json)
    rows = candidate_data.get('kept_rows') or candidate_data.get('candidate_rows') or []

    scored = [score_row(row, brief) for row in rows]
    scored.sort(key=lambda x: x.get('score_total', 0), reverse=True)

    out = {
        'item_index': args.item_index,
        'brief_summary': brief.get('brief_summary'),
        'scored_rows': scored,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
