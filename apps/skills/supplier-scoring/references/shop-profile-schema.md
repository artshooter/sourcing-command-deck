# Shop-level profile schema

Use this after discovery/scoring has already identified promising product-level candidates.

## Goal

Move from single-product matching to seller/shop-level judgment.

## Inputs

- scored supplier row
- `shop_url` when available
- optional cookie/session for authenticated access

## Output fields

### shop-level page profile
- `shop_profile.shop_url`
- `shop_profile.shop_title`
- `shop_profile.about_text`
- `shop_profile.main_style_signals`
- `shop_profile.crossborder_signals`
- `shop_profile.price_position_guess`
- `shop_profile.shop_consistency_guess`
- `shop_profile.platform_fit_guess`
- `shop_profile.risk_notes`
- `shop_profile_summary`

### shop catalog profile
- `shop_catalog_profile.shop_url`
- `shop_catalog_profile.shop_title`
- `shop_catalog_profile.main_style_signals`
- `shop_catalog_profile.crossborder_signals`
- `shop_catalog_profile.price_position_guess`
- `shop_catalog_profile.shop_consistency_guess`
- `shop_catalog_profile.platform_fit_guess`
- `shop_catalog_profile.offer_id_samples`
- `shop_catalog_profile.risk_notes`
- `shop_catalog_profile_summary`

## Judgment principle

A seller is better when:
- the matched product is not an isolated outlier
- the shop language/style keeps repeating the same direction
- cross-border/platform signals are visible when relevant
- the shop looks like an operating supplier rather than a random one-off listing source
