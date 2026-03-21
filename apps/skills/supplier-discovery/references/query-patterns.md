# Discovery query patterns

Build search queries from one `brief_item`.

## Query buckets

Use several buckets instead of one long query.

### 1. Core category query
- `{category_l3} supplier`
- `{category_l3} manufacturer`
- `{category_l3} factory`
- `{theme} {category_l3}`

### 2. Style/theme query
- `{theme} {category_l3} supplier`
- `{style_tag} {category_l3} manufacturer`
- `{style_tag} {category_l3} wholesale`

### 3. Fabric/detail query
- `{fabric} {category_l3} supplier`
- `{element} {category_l3} factory`

### 4. Market query
- `{market} {category_l3} supplier`
- `{market} fashion {category_l3} manufacturer`
- `middle east {category_l3} supplier`
- `india {category_l3} supplier`

### 5. Price/value query
- `low price {category_l3} wholesale`
- `{category_l3} budget supplier`
- `{category_l3} cheap wholesale`

### 6. Channel-specific query
- `site:1688.com {theme} {category_l3}`
- `site:1688.com {style_tag} {category_l3}`
- `site:1688.com {fabric} {category_l3}`
- `site:aliexpress.com {theme} {category_l3}`
- `site:amazon.com {theme} {category_l3}`

### 7. Native 1688 query phrases
For actual 1688 search, also build short Chinese phrases instead of only site-search queries.

Examples:
- `{theme} {category_l3_cn}`
- `{style_tag} {category_l3_cn}`
- `{fabric} {category_l3_cn}`
- `{element} {category_l3_cn}`
- `{market_hint} {category_l3_cn}` only if it makes sense for export/region style

## Query composition rules

- Keep each query short and purposeful.
- Mix Chinese and English when source channels differ.
- Prefer 8-20 queries per brief item, not hundreds.
- Use required tags as boosters.
- Use forbidden tags as exclusion hints during human review.

## Notes

This skill generates discovery queries and candidate structures. It does not score suppliers deeply; that belongs in the next skill.
