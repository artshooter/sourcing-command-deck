#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def text_blob(row):
    parts = [
        row.get('product_title', '') or '',
        row.get('supplier_name', '') or '',
        ' '.join(row.get('evidence', []) or []),
    ]
    return ' '.join(parts).lower()


def match_count(text, tags):
    hits = []
    for tag in tags or []:
        t = str(tag).strip().lower()
        if t and t in text:
            hits.append(tag)
    return hits


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def price_score(row, price_min, price_max):
    p = safe_float(row.get('price_fit_guess'))
    if p is None:
        return 0, 'no_price'
    if price_min is None or price_max is None:
        return 1, 'has_price'
    if price_min <= p <= price_max:
        return 4, 'in_range'
    if p < price_min:
        # cheaper may still be useful but with caution
        return 2, 'below_range'
    # above range: the further, the worse
    gap = p - price_max
    if gap <= 5:
        return 1, 'slightly_above'
    if gap <= 20:
        return -1, 'above_range'
    return -3, 'far_above'


def factory_score(row):
    if row.get('extra', {}).get('factory_inspection'):
        return 2
    return 0


def keyword_penalty(text, bad_keywords):
    hits = []
    for kw in bad_keywords or []:
        kw2 = str(kw).strip().lower()
        if kw2 and kw2 in text:
            hits.append(kw)
    return (-3 * len(hits), hits)


def keyword_bonus(text, good_keywords, unit=2):
    hits = []
    for kw in good_keywords or []:
        kw2 = str(kw).strip().lower()
        if kw2 and kw2 in text:
            hits.append(kw)
    return (unit * len(hits), hits)


def rerank_row(row, brief):
    text = text_blob(row)
    theme = brief.get('theme', '') or ''
    style_tags = brief.get('merged_style_tags') or brief.get('style_tags') or []
    fabrics = brief.get('fabrics') or []
    elements = brief.get('elements') or []
    required_tags = brief.get('merged_required_tags') or brief.get('required_tags') or []
    forbidden_tags = brief.get('merged_forbidden_tags') or brief.get('forbidden_tags') or []
    price_min = brief.get('price_min')
    price_max = brief.get('price_max')

    score = 0
    reasons = []

    if theme and theme.lower() in text:
        score += 6
        reasons.append(f'theme_hit:{theme}')

    style_hits = match_count(text, style_tags)
    score += min(len(style_hits), 5) * 2
    if style_hits:
        reasons.append('style_hits:' + ','.join(map(str, style_hits[:5])))

    fabric_hits = match_count(text, fabrics)
    score += min(len(fabric_hits), 3) * 2
    if fabric_hits:
        reasons.append('fabric_hits:' + ','.join(map(str, fabric_hits[:3])))

    element_hits = match_count(text, elements)
    score += min(len(element_hits), 4) * 2
    if element_hits:
        reasons.append('element_hits:' + ','.join(map(str, element_hits[:4])))

    required_hits = match_count(text, required_tags)
    score += len(required_hits) * 3
    if required_hits:
        reasons.append('required_hits:' + ','.join(map(str, required_hits[:4])))

    forbidden_hits = match_count(text, forbidden_tags)
    score -= len(forbidden_hits) * 5
    if forbidden_hits:
        reasons.append('forbidden_hits:' + ','.join(map(str, forbidden_hits[:4])))

    p_score, p_reason = price_score(row, price_min, price_max)
    score += p_score
    reasons.append('price:' + p_reason)

    f_score = factory_score(row)
    score += f_score
    if f_score:
        reasons.append('factory_inspection')

    # generic negative theme drift keywords for dresses/fashion sourcing
    bad_kw = ['万圣节', 'cos', '戏服', '家居服', '睡裙', '中世纪', '角色扮演']
    pen, bad_hits = keyword_penalty(text, bad_kw)
    score += pen
    if bad_hits:
        reasons.append('bad_kw:' + ','.join(map(str, bad_hits[:4])))

    # generic positive signals
    good_kw = ['跨境', '外贸', '亚马逊', '度假', '印花', '连衣裙']
    bon, good_hits = keyword_bonus(text, good_kw, unit=1)
    score += bon
    if good_hits:
        reasons.append('good_kw:' + ','.join(map(str, good_hits[:6])))

    row['coarse_score'] = score
    row['coarse_reasons'] = reasons
    row['theme_hit'] = bool(theme and theme.lower() in text)
    row['matched_style_tags'] = style_hits
    row['matched_fabrics'] = fabric_hits
    row['matched_elements'] = element_hits
    row['matched_required_tags'] = required_hits
    row['hit_forbidden_tags'] = forbidden_hits
    return row


def main():
    ap = argparse.ArgumentParser(description='Coarse reranker / filter for 1688 candidate rows against one brief item.')
    ap.add_argument('brief_json')
    ap.add_argument('candidate_rows_json')
    ap.add_argument('--item-index', type=int, required=True)
    ap.add_argument('--min-score', type=int, default=3)
    ap.add_argument('--top-k', type=int, default=50)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    brief_data = load_json(args.brief_json)
    brief = brief_data.get('items', [])[args.item_index - 1]
    rows = load_json(args.candidate_rows_json).get('candidate_rows', [])

    ranked = [rerank_row(dict(r), brief) for r in rows if (r.get('supplier_name') or r.get('product_title'))]
    ranked.sort(key=lambda x: x.get('coarse_score', 0), reverse=True)

    kept = [r for r in ranked if r.get('coarse_score', 0) >= args.min_score][: args.top_k]
    dropped = [r for r in ranked if r.get('coarse_score', 0) < args.min_score]

    out = {
        'item_index': args.item_index,
        'brief_summary': brief.get('brief_summary'),
        'kept_rows': kept,
        'dropped_rows': dropped,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
