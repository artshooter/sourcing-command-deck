---
name: supplier-scoring
description: Profile and score discovered supplier candidates against one parsed planning brief item. Use after supplier-discovery has produced a candidate pool and coarse reranking. This skill turns candidate rows into explainable scores, recommendation levels, profile summaries, reasons, risks, and shortlist outputs for sourcing or 招商 review.
---

# Supplier Scoring

Use this skill after candidate suppliers have already been discovered.

## Workflow

1. Load one parsed `brief_item` from the planning parser.
2. Load candidate rows from supplier discovery.
3. Score each row with explainable rules.
4. Produce recommendation levels and profile summaries.
5. Select top suppliers for review.

## Scripts

Core scoring:

```bash
python3 scripts/score_suppliers.py <brief.json> <candidate.json> --item-index 1 --out ./outputs/scored-item1.json
python3 scripts/enrich_supplier_profiles.py ./outputs/scored-item1.json --out ./outputs/scored-item1-enriched.json
python3 scripts/select_top_suppliers.py ./outputs/scored-item1-enriched.json --top-k 20 --out ./outputs/top-item1.json
python3 scripts/render_shortlist.py ./outputs/scored-item1-enriched.json --top-k 20 --out ./outputs/top-item1.md
```

Shop-level enhancement:

```bash
python3 scripts/build_shop_samples_from_candidates.py ./outputs/scored-item1-enriched.json --out ./outputs/shop-samples.json
python3 scripts/profile_shop_samples.py ./outputs/shop-samples.json --out ./outputs/shop-sample-profiles.json
python3 scripts/merge_shop_sample_profiles.py ./outputs/scored-item1-enriched.json ./outputs/shop-sample-profiles.json --out ./outputs/scored-item1-sample-enriched.json
```

End-to-end workflow:

```bash
python3 scripts/run_end_to_end_workflow.py --xlsx <planning.xlsx> --cookie-file ./secrets/1688-cookie.txt --item-index 1 --queries 3 --pages 2 --top-k 20
python3 scripts/run_batch_workflow.py --xlsx <planning.xlsx> --cookie-file ./secrets/1688-cookie.txt --items 1,2,3 --queries 2 --pages 1 --top-k 10
python3 scripts/run_auto_batch_workflow.py --xlsx <planning.xlsx> --cookie-file ./secrets/1688-cookie.txt --max-items 5 --queries 2 --pages 1 --top-k 10
python3 scripts/render_batch_summary.py ./outputs/workflow-batch/batch-summary.json --out ./outputs/workflow-batch/batch-summary.md
python3 scripts/render_batch_summary_v2.py ./outputs/workflow-batch/batch-summary.json --out ./outputs/workflow-batch/batch-summary-v2.md
```

## Scoring quality bar

A good scoring result should:

- keep the score explainable
- separate positive reasons from risk warnings
- reflect the planning brief's theme, fabric, element, and price band
- avoid pretending discovery-stage evidence is verified truth

## References

- `references/scoring-schema.md`
- `references/scoring-rules.md`
