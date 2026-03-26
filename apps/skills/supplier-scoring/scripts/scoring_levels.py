#!/usr/bin/env python3

A_LEVEL_MIN_SCORE = 48
B_LEVEL_MIN_SCORE = 36
C_LEVEL_MIN_SCORE = 24

A_LEVEL_MIN_THEME_STYLE = 20
A_LEVEL_MIN_PRICE_FIT = 6
A_LEVEL_MIN_RISK_PENALTY = -7


def safe_float(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def classify_recommendation_level(total, breakdown=None):
    total = safe_float(total, 0)
    breakdown = breakdown or {}

    theme_style = safe_float(breakdown.get('theme_style', 0), 0)
    price_fit = safe_float(breakdown.get('price_fit', 0), 0)
    risk_penalty = safe_float(breakdown.get('risk_penalty', 0), 0)

    a_pass = (
        total >= A_LEVEL_MIN_SCORE
        and theme_style >= A_LEVEL_MIN_THEME_STYLE
        and price_fit >= A_LEVEL_MIN_PRICE_FIT
        and risk_penalty >= A_LEVEL_MIN_RISK_PENALTY
    )
    if a_pass:
        return 'A'
    if total >= B_LEVEL_MIN_SCORE:
        return 'B'
    if total >= C_LEVEL_MIN_SCORE:
        return 'C'
    return 'D'


def refresh_row_recommendation_level(row):
    row['recommendation_level'] = classify_recommendation_level(
        row.get('score_total', 0),
        row.get('score_breakdown', {}) or {},
    )
    return row


def refresh_rows_recommendation_levels(rows):
    for row in rows or []:
        refresh_row_recommendation_level(row)
    return rows
