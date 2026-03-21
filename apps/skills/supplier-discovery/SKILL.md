---
name: supplier-discovery
description: Discover candidate suppliers or merchants from parsed planning brief items for sourcing and 招商 workflows. Use when a user wants to go from a structured buying/planning brief to search queries, candidate supplier pools, source evidence, and lightweight fit guesses across channels like 1688, AliExpress, Amazon, historical supplier tables, or referral lists. This is the second stage after planning brief parsing and before supplier profiling/scoring.
---

# Supplier Discovery

Use this skill only after the planning brief has already been parsed into row-level `brief_item` records.

## Workflow

1. Start from one normalized `brief_item`.
   - Do not search from the raw Excel directly.
   - Prefer enriched fields like `merged_style_tags` when available.

2. Generate a focused query set.
   - Use category, theme, style tags, fabrics, elements, market, and price intent.
   - Use several short query buckets instead of one overloaded query.

3. Create a candidate pool shell.
   - One `candidate_pool` per `brief_item`.
   - Preserve the original queries used for traceability.

4. Search channels and collect weak evidence.
   - Examples: 1688, AliExpress, Amazon seller pages, internal tables, referral lists.
   - For 1688, prefer short native Chinese query phrases over only site-search patterns.
   - If browser relay is unavailable, cookie mode can be used for a short-lived PoC.
   - At discovery stage, preserve links and observations rather than making strong judgments.

5. Record lightweight fit guesses only.
   - `market_fit_guess`
   - `category_fit_guess`
   - `style_fit_guess`
   - `price_fit_guess`
   - `confidence`

6. Hand the resulting candidate pool to the next skill for deep profiling and scoring.

## Scripts

Generic discovery:

```bash
python3 scripts/generate_discovery_queries.py <brief.json> --out ./outputs/discovery-requests.json
python3 scripts/init_candidate_pool.py ./outputs/discovery-requests.json --out ./outputs/candidate-pools.json
```

1688-focused discovery:

```bash
python3 scripts/generate_1688_tasks.py <brief.json> --out ./outputs/1688-tasks.json
python3 scripts/init_1688_candidate_rows.py ./outputs/1688-tasks.json --out ./outputs/1688-candidate-rows.json
python3 scripts/fetch_1688_with_cookie.py --query "晕染印花 连衣裙" --cookie-file ./secrets/1688-cookie.txt --out ./outputs/1688-cookie-test.json
python3 scripts/fetch_1688_mtop.py --query "晕染印花 连衣裙" --cookie-file ./secrets/1688-cookie.txt --out ./outputs/1688-mtop.json
python3 scripts/extract_1688_candidates.py ./outputs/1688-mtop.json --item-index 1 --query "晕染印花 连衣裙" --out ./outputs/1688-candidate-rows-item1.json
python3 scripts/run_1688_batch.py ./outputs/1688-tasks.json --cookie-file ./secrets/1688-cookie.txt --item-index 1 --queries 3 --pages 2 --out ./outputs/1688-batch-item1.json
python3 scripts/dedupe_filter_candidates.py ./outputs/1688-batch-item1.json --required-tags-json '["收腰"]' --forbidden-tags-json '["前胸打揽"]' --min-score 1 --out ./outputs/1688-batch-item1-filtered.json
python3 scripts/rerank_1688_candidates.py <brief.json> ./outputs/1688-batch-item1.json --item-index 1 --min-score 3 --top-k 50 --out ./outputs/1688-batch-item1-reranked.json
python3 scripts/select_shops_for_expansion.py ./outputs/1688-batch-item1-reranked.json --top-shops 5 --out ./outputs/shops-for-expansion.json
python3 scripts/fetch_shop_home_search.py --shop-url 'https://example.1688.com' --cookie-file ./secrets/1688-cookie.txt --out ./outputs/shop-home.json
python3 scripts/extract_shop_offer_samples.py ./outputs/shop-home.json --supplier-name '示例商家' --item-index 1 --out ./outputs/shop-expanded-rows.json
python3 scripts/merge_expanded_candidates.py ./outputs/1688-batch-item1-reranked.json ./outputs/shop-expanded-rows.json --out ./outputs/1688-batch-item1-expanded.json
```

If candidate rows are collected separately, merge them with:

```bash
python3 scripts/merge_candidate_rows.py ./outputs/candidate-pools.json ./outputs/candidate-rows.json --out ./outputs/candidate-pools-merged.json
```

## Discovery quality bar

A good discovery result should:

- produce search queries that reflect the brief item, not generic category spam
- preserve evidence and source links
- keep weak guesses separate from verified facts
- avoid obviously conflicting suppliers using forbidden tags and market cues

## References

- `references/discovery-schema.md`
- `references/query-patterns.md`
- `references/1688-notes.md`
- `references/cookie-mode.md`
