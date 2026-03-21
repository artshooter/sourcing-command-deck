# Tagging rules for planning brief parsing

Use these heuristics after raw parsing. Keep all inferred tags separate from raw source fields.

## style_tags

Build from `theme`, `colors`, `fabrics`, and `elements`.

Examples:
- `晕染印花` -> `印花`, `晕染`, `柔和色调` if present
- `小碎花` -> `印花`, `小碎花`
- `条纹/格子/衬衫裙` -> `条纹`, `格子`, `衬衫裙`
- `蝴蝶结/立体花` -> `蝴蝶结`, `立体花`
- `雪纺/欧根纱` -> `雪纺`, `欧根纱`, `轻盈`
- `基础` -> `基础款`
- `轻礼服` -> `轻礼服`, `场合感`
- `Hijab` -> `中东`, `保守覆盖`, `长款偏好`

## forbidden_tags

Infer from `notes` when it contains explicit exclusions or negative constraints.

Patterns:
- `避免X` -> forbidden tag `X`
- `不要X` -> forbidden tag `X`
- `款式要Y` -> required tag `Y`
- `注意X不要过深` -> forbidden tag `过深X`

Examples:
- `避免前胸打揽的款式` -> forbidden: `前胸打揽`
- `避免美式乡村风` -> forbidden: `美式乡村风`
- `款式要收腰` -> required: `收腰`
- `提花面料注意颜色不要过深` -> forbidden: `深色提花`

## silhouette_tags

Infer from theme or notes when shape cues are explicit.

Examples:
- `大A摆` -> `A摆`
- `衬衫裙` -> `衬衫裙`
- `裙长到脚踝` -> `及踝长裙`
- `收腰` -> `收腰`

## occasion_tags

Use when the theme implies use context.

Examples:
- `度假印花` -> `度假`
- `轻礼服` -> `礼服`, `宴会`
- `POLO` -> `休闲运动`

## market_tags

Base on sheet/market name and explicit regional cues.

Examples:
- `印度` -> `印度市场`
- `中东` -> `中东市场`
- `Hijab` -> `中东风格`
