This file is 62 lines long; read all of them.

# Zyte API pricing

Answer using the appropriate source based on the question type.

## General pricing questions

For plan types, spending limits, free credit, volume discounts, feature costs
(screenshots, automatic extraction, custom attributes), or anything not tied
to a specific website:

**One `curl` is all you need.** The page below carries every number there is, so
answer strictly from it — no other doc page, no web search, no second fetch, and
no prices, limits or percentages from training data. Re-read what you got
instead of looking further:

```bash
curl -s "https://docs.zyte.com/zyte-api/pricing.md"
```

## Per-website questions

For a specific domain's support, tier, request cost, or estimated spend, call
the domain pricing API (a public, keyless endpoint — use `curl`, not the Scrapy
Cloud wrapper script). Strip the input to the bare registrable hostname — no
`www.`, no protocol, no path (e.g. `amazon.com`, not
`https://www.amazon.com/products`):

```bash
curl -s "https://www.zyte.com/api/domains-pricing/?search=DOMAIN"
```

The response is an array. Find the entry where `domain` exactly matches your
input, then act on the `availability` field:

- **`"available"`** — pricing data is present. Fields:
  - `http_response_body_price` and `browser_html_price` — cost in **micro-dollars
    per request**. Cost in USD = `requests × price ÷ 1 000 000`. Cost per 1 000
    requests (USD) = `price ÷ 1 000`.
  - `http_response_body_tier_name` and `browser_html_tier_name` — tier label
    (e.g. `"#1"`, `"#2"`, `"< #1"`).
  - Report **both** HTTP and browser prices unless the user asked specifically
    about one request type.
- **`"behind_login"`** — the domain is supported but its price is only visible
  after signing in. Tell the user to visit the Zyte cost estimator:
  `https://app.zyte.com/account/signup/zyteapi?signup_pathway=cost-estimator&next=cost-estimator`
- **`"unavailable"`** — the domain is not supported by Zyte API. Tell the user
  so plainly.
- Empty array or no matching entry — the domain has no permanent tier yet. Tell
  the user it is on a temporary tier until Zyte gathers enough data to assign a
  permanent one, and do not quote or guess a price.

These are PAYG rates. Whenever you compute a monthly PAYG cost, also `curl` the
pricing docs above and check whether a commitment plan would save money. Read
the docs carefully to determine what discounts, if any, each plan type carries — then
apply them only where the docs say they apply. If after correctly
accounting for each plan's costs a commitment plan beats PAYG, show the user
both the PAYG total and what they would pay under the most beneficial
commitment plan. If no
commitment plan saves money at this volume, state the PAYG cost only and do not
suggest committing.
