# Supplier scoring schema

Use this skill after supplier discovery has produced candidate rows.

## Inputs

1. One parsed `brief_item` from the planning-brief-parser skill
2. Candidate rows from supplier-discovery

## Outputs

Each scored supplier row should include:

- `supplier_name`
- `product_title`
- `score_total`
- `score_breakdown`
- `recommendation_level`
- `profile_summary`
- `supplier_profile`
- `supplier_profile_summary`
- `recommend_reasons`
- `risk_warnings`
- `evidence`

## Score buckets

Recommended first-pass buckets:

1. Theme/style match
2. Fabric/detail match
3. Price-band fit
4. Supplier credibility signals
5. Risk penalties

## Recommendation levels

- `A`: high priority
- `B`: strong backup
- `C`: watchlist / conditional
- `D`: not recommended
