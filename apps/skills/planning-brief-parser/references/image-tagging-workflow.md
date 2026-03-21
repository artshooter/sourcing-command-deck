# Image tagging workflow

Use this when embedded planning images need semantic understanding.

## Goal

Produce row-level visual tags that strengthen supplier search and scoring.

## Minimal workflow

1. Extract images from the workbook.
2. Parse the workbook with image manifest attached.
3. Build row-level image sets.
4. Initialize an image analysis template.
5. Fill the template with visual tags.
6. Merge image analysis back into parsed brief JSON.

## Commands

```bash
python3 scripts/extract_xlsx_images.py <file.xlsx> --outdir ./outputs/brief-images
python3 scripts/parse_planning_xlsx.py <file.xlsx> --image-manifest ./outputs/brief-images/image-manifest.json --pretty > ./outputs/planning-brief.json
python3 scripts/build_item_image_sets.py ./outputs/planning-brief.json --out ./outputs/item-image-sets.json
python3 scripts/init_image_analysis_template.py ./outputs/item-image-sets.json --out ./outputs/image-analysis-template.json
python3 scripts/merge_image_analysis.py ./outputs/planning-brief.json ./outputs/image-analysis-template.json --out ./outputs/planning-brief-enriched.json
```

## How to fill visual tags

For each row-level image set, inspect a few representative images and fill:

- `image_summary`
- `image_consensus_tags`
- `image_unique_tags`
- `image_conflict_tags`
- `image_visual_fields`

Prefer stable, supplier-relevant tags:

- silhouette
- neckline
- sleeve
- length
- fabric feel
- pattern
- visible details
- mood

## Conflict handling

If images visibly contradict the text brief, record that in:

- `image_conflict_tags`
- `image_summary`

Examples:
- notes require `收腰`, but most images look straight and loose
- theme says `晕染印花`, but images are mainly floral
- low price band but images show high-complexity embellishment

## Quality bar

A good image analysis helps answer:

- What does this theme actually look like visually?
- What supplier capabilities are visually implied?
- Which textual tags were confirmed by images?
- Which hidden details appear only in images, not in text?
