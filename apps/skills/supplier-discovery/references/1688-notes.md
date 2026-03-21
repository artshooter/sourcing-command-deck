# 1688 operational notes

## Reality check

Direct 1688 search often requires login or hits anti-bot / risk pages.

## Preferred automation path

If the user has a logged-in Chrome tab on 1688 and can attach it via OpenClaw Browser Relay, use browser automation on profile `chrome`.

## Fallback path

If a live 1688 tab is not available, use external web search with `site:1688.com` queries to discover candidate pages, then extract weak evidence from those pages.

## Discovery-stage evidence on 1688

Capture lightweight fields only:

- supplier/store name
- product title
- page URL
- shop URL
- visible category/theme clues
- visible price clues if present
- quantity-price ladder if present
- obvious risk notes

Do not overclaim factory status or deep style fit at discovery stage.

## Better-than-HTML path

When cookie mode works, prefer calling the page's underlying mtop interface for `getOfferList` and then normalize returned items into candidate rows. This is more reliable than scraping rendered HTML.
