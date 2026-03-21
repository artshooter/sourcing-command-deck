# Image analysis schema for planning brief items

Use this schema when analyzing extracted planning reference images.

## Goal

Turn reference images into structured visual signals that can be merged back into each `brief_item`.

## Per-image fields

- `image_path`
- `sheet`
- `cell_ref`
- `visual_summary`: one-sentence summary
- `garment_type_tags`: e.g. `连衣裙`, `衬衫裙`, `长裙`
- `silhouette_tags`: e.g. `收腰`, `A摆`, `直筒`, `及踝`
- `neckline_tags`: e.g. `方领`, `V领`, `圆领`, `一字肩`
- `sleeve_tags`: e.g. `泡泡袖`, `喇叭袖`, `长袖`, `无袖`
- `length_tags`: e.g. `短款`, `中长`, `及踝`
- `fabric_visual_tags`: e.g. `轻透`, `雪纺感`, `网纱感`, `针织感`
- `pattern_tags`: e.g. `晕染印花`, `小碎花`, `条纹`, `格子`
- `detail_tags`: e.g. `系带`, `荷叶边`, `立体花`, `拼接`, `金属装饰`
- `mood_tags`: e.g. `浪漫`, `度假`, `轻礼服`, `复古`
- `fit_for_theme`: high / medium / low
- `conflicts`: list of visible conflicts with notes or forbidden tags
- `confidence`: high / medium / low

## Row-level aggregation

After analyzing multiple images for one brief item, aggregate into:

- `image_consensus_tags`: tags repeated across multiple images
- `image_unique_tags`: less frequent but still useful tags
- `image_conflict_tags`: tags conflicting with notes or intended theme
- `image_summary`: 1-2 sentence summary of the visual direction

## Usage in downstream matching

Use image-derived tags to strengthen or correct text-derived parsing.

Typical cases:
- notes say `收腰`, and images confirm `收腰` -> increase confidence
- theme says `晕染印花`, images show floral instead -> flag mismatch
- price band is low but images show heavy detail/high-complexity styling -> note potential cost tension
