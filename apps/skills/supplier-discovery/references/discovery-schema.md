# Supplier discovery schema

Use this skill after planning brief parsing. The input is one normalized `brief_item`, not the raw planning file.

## Input

A discovery request should contain at least:

- `market`
- `category_l1`, `category_l2`, `category_l3`
- `theme`
- `style_tags`
- `merged_style_tags` if image-enriched
- `fabrics`
- `elements`
- `required_tags`
- `forbidden_tags`
- `price_min`, `price_max`
- `brief_summary`

## Output candidate fields

Each candidate supplier record should aim to include:

- `supplier_name`
- `source_channel`
- `source_url`
- `market_fit_guess`
- `category_fit_guess`
- `style_fit_guess`
- `price_fit_guess`
- `evidence`
- `risk_notes`
- `confidence`

## Discovery principles

1. Discover broadly, judge lightly.
2. Preserve evidence and source links.
3. Separate hard filters from soft guesses.
4. Do not overclaim supplier capabilities from weak evidence.
5. Use the brief's exclusions to avoid obviously bad candidates early.
