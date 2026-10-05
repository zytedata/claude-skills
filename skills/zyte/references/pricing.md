This file is 35 lines long; read all of them.

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

A specific website's support, tier and pay-as-you-go price per request come
from the `zyte_api_domain_pricing` tool of the Zyte MCP, not from this skill.

The volume discounts in the pricing docs are taken off those pay-as-you-go
rates. Whenever a monthly pay-as-you-go cost is computed, also `curl` the
pricing docs above and check whether a commitment plan would save money. Read
the docs carefully to determine what discounts, if any, each plan type carries
— then apply them only where the docs say they apply. If after correctly
accounting for each plan's costs a commitment plan beats pay-as-you-go, show
the user both the pay-as-you-go total and what they would pay under the most
beneficial commitment plan. If no commitment plan saves money at this volume,
state the pay-as-you-go cost only and do not suggest committing.
