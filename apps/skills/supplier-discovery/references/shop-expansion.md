# Shop expansion for 1688 discovery

Use this after the first-pass product recall has identified promising candidate shops.

## Goal

Expand from one matched product to multiple product samples from the same shop, so downstream scoring can judge shop-level consistency.

## Workflow

1. Start from recalled candidate rows.
2. Group by `shop_url`.
3. Select top shops for expansion.
4. Fetch additional products for each selected shop.
5. Merge expanded product samples back into the candidate pool.

## Why

Without shop expansion, downstream scoring often sees only one product per shop and cannot reliably judge whether the matched product is representative of the shop's overall style.
