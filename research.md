# Research Notes

This document captures candidate sources, access notes, and selector/API hints for the Vietnam Gold Dashboard.

## SJC / Local Gold Prices
### Primary: SJC (official)
- URL: https://sjc.com.vn/gia-vang-online
- Notes: Page loads HTML; in this environment, detailed price rows were not surfaced via the content chunks. The legacy `textContent.php` endpoints appear unstable or blocked:
  - https://sjc.com.vn/giavang/textContent.php (404)
  - http://sjc.com.vn/giavang/textContent.php (timeout)
  - https://www.sjc.com.vn/giavang/textContent.php?target=popup (TLS mismatch)
- Action: test in code with strict headers + retry; if blocked, fallback to Mi Hồng source below.

### Secondary: Mi Hồng (local gold prices)
- URL: https://www.mihong.vn/en/vietnam-gold-pricings
- Notes: Page exposes sections for current price (Gold Type: SJC, 999, etc.) and time ranges. In code, parse the table structure (may require inspecting live HTML via requests).

## USD/VND (Black Market)
### Candidate Source: EGCurrency
- URL: https://egcurrency.com/en/currency/USD-to-VND/blackMarket
- Notes: Content includes "Sell Price" and "Live exchange rate" text. Likely simple HTML; parse for numeric values.

### Alternate Source: TygiaUSD (needs verification)
- URL: https://tygiausd.org/
- Notes: Site content is heavy; USD black-market data likely embedded in tables not captured in simple chunks. Consider as fallback after inspecting HTML directly.

## VN30 Index
- URL: https://banggia.vietstock.vn/bang-gia/vn30
- Notes: Page exposes index line for "VN30-INDEX" with value and delta in plain text. Parse the VN30 row or index line. If dynamic in production, may require finding the API behind the page.

## Bitcoin (BTC/VND)
- URL: https://coinmarketcap.com/currencies/bitcoin/btc/vnd/
- Notes: Page contains BTC to VND conversion text. Parsing may require targeting specific DOM nodes; consider using CMC only for crypto (allowed by domain rules).

## Anti-Bot / Headers
- Use strict browser-like headers for every request (User-Agent, Accept, Accept-Language, Referer when needed).
- Set timeouts and retry with backoff; if a scrape fails, return cached values.

## Next Research Actions
1. Confirm SJC HTML structure in live requests; if blocked, switch primary to Mi Hồng for local gold price.
2. Inspect EGCurrency and Vietstock HTML to pin exact CSS selectors.
3. Verify whether Vietstock exposes a JSON/CSV API for VN30 index.
