# Planning brief item schema

Use one normalized `brief_item` per row/theme after parsing a planning Excel.

## Core fields

- `market`: target market or region, usually sheet name
- `category_l1`, `category_l2`, `category_l3`: category hierarchy
- `theme`: planning topic or key style direction
- `demand_raw`: original quantity cell text
- `demand_by_month`: normalized month-to-quantity map
- `colors`: normalized color tokens
- `fabrics`: normalized fabric tokens
- `elements`: normalized detail / craft / design tokens
- `price_min`, `price_max`: parsed numeric price band
- `notes`: explicit constraints and exclusions
- `anchored_image_count`: number of embedded images anchored to the planning row in columns F-M
- `anchored_images`: extracted image metadata with sheet/cell/path when image extraction is enabled

## Matching guidance

When using parsed brief items for supplier matching, prioritize these buckets:

1. Category fit
2. Theme/style fit
3. Fabric/craft fit
4. Price-band fit
5. Market-specific constraints
6. Exclusion handling from `notes`

## Recommended downstream derived tags

Derive these after parsing if needed:

- `style_tags`
- `forbidden_tags`
- `required_tags`
- `silhouette_tags`
- `occasion_tags`
- `market_tags`
- `price_tier`
- `brief_summary`

Keep raw fields; do not overwrite them with inferred tags.

## Current parser output additions

The current parser also emits:

- `style_tags`: normalized theme/style/fabric/detail tags
- `forbidden_tags`: exclusions inferred from notes such as `避免X` / `不要X`
- `required_tags`: mandatory cues inferred from notes such as `款式要X`
- `silhouette_tags`: shape and length cues like `A摆`, `收腰`, `及踝长裙`
- `occasion_tags`: context tags like `度假`, `礼服`
- `market_tags`: market tags such as `印度市场`, `中东市场`
- `brief_summary`: compact summary string for downstream search or display
