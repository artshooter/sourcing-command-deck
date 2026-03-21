---
name: planning-brief-parser
description: Parse buying plans, planning spreadsheets, product planning Excel files, buyer planning docs, and merchandising brief tables into normalized brief items for downstream supplier discovery and matching. Use when a user provides an Excel/Feishu planning file and wants to extract structured fields like market, category, theme, quantity, colors, fabrics, elements, price band, notes, or when building the first stage of a sourcing or招商 agent.
---

# Planning Brief Parser

Parse planning documents into reusable `brief_item` records before doing supplier search or scoring.

## Workflow

1. Identify the planning source.
   - Prefer the original `.xlsx` when available.
   - Treat each sheet as a market or business segment unless the file clearly uses another convention.

2. If the workbook contains embedded reference images, extract them first with `scripts/extract_xlsx_images.py`.
   - This creates an `image-manifest.json` plus extracted image files.
   - It maps each image to a sheet and anchored cell.

3. Parse the file with `scripts/parse_planning_xlsx.py`.
   - This script uses only Python standard library.
   - It works in environments without `openpyxl`.
   - If image extraction was run, pass `--image-manifest` so parsed brief items inherit anchored image metadata.

4. Normalize one `brief_item` per planning theme row.
   - Fill down category columns when the sheet uses grouped rows.
   - Preserve raw text for quantity, colors, fabrics, elements, price, and notes.
   - Also keep normalized token lists for downstream matching.
   - Attach any extracted images anchored to the same planning row in the reference-image columns.

5. Validate the result before handing off downstream.
   - Check whether `market`, `category`, `theme`, and `price_band` look reasonable.
   - Check whether exclusions in `notes` became `forbidden_tags`.
   - Check whether hard requirements in `notes` became `required_tags`.
   - Flag ambiguous rows instead of pretending certainty.

6. If the brief contains embedded reference images, analyze them at the row level.
   - Build row-level image sets from parsed output.
   - Extract visual tags such as silhouette, neckline, sleeve, fabric feel, pattern, details, and mood.
   - Merge image-derived signals back into the same `brief_item` instead of storing them separately.

7. Use the parsed output as the only upstream input for supplier search and scoring.
   - Supplier discovery should search against `brief_item`, not the entire source file.
   - Supplier scoring should compare supplier profiles against `brief_item` fields.
   - If images exist, image understanding should be attached to the row-level `brief_item`, not handled as a disconnected asset list.

## Script

Run:

```bash
python3 scripts/extract_xlsx_images.py <file.xlsx> --outdir ./outputs/brief-images
python3 scripts/parse_planning_xlsx.py <file.xlsx> --image-manifest ./outputs/brief-images/image-manifest.json --summary
python3 scripts/parse_planning_xlsx.py <file.xlsx> --image-manifest ./outputs/brief-images/image-manifest.json --pretty > ./outputs/planning-brief.json
python3 scripts/build_item_image_sets.py ./outputs/planning-brief.json --out ./outputs/item-image-sets.json
python3 scripts/init_image_analysis_template.py ./outputs/item-image-sets.json --out ./outputs/image-analysis-template.json
python3 scripts/merge_image_analysis.py ./outputs/planning-brief.json ./outputs/image-analysis-template.json --out ./outputs/planning-brief-enriched.json
```

Output fields are documented in `references/brief-schema.md`. Tag inference heuristics live in `references/tagging-rules.md`. Visual tagging targets live in `references/image-analysis-schema.md`. The row-level image workflow lives in `references/image-tagging-workflow.md`.

## Parsing rules

- Treat sheet name as `market` by default.
- Treat column E / theme column as the trigger for a new `brief_item`.
- Fill down category columns from previous non-empty rows.
- Parse month quantity text like `4月：20\n5月：15` into `demand_by_month`.
- Parse price bands like `32-48` into `price_min` and `price_max`.
- Split colors, fabrics, and elements on common Chinese and English separators.
- Preserve `notes` exactly; they often contain critical exclusions.

## Output quality bar

A good parse lets the next skill answer questions like:

- Which planning themes belong to which market?
- What price band is expected for this theme?
- What fabrics, elements, and exclusions define this brief item?
- Which supplier attributes must be matched later?

If the source file contains images, links, or merged-cell quirks not captured by the parser, keep the parsed rows and note the missing pieces explicitly instead of blocking the workflow.
