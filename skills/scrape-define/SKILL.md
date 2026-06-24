---
name: scrape-define
description: Quick schema definition — explore 1 detail page, discover fields, fast approval loop
argument-hint: "[url] [what to extract]"
allowed-tools: Agent, Skill, Bash, Read, Write, AskUserQuestion
---

You are helping the user quickly define what to extract from a website. Download 1 detail page, discover fields, and iterate on the schema in the terminal until approved.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

The output is a draft spec folder with an approved schema and values (no stored pages — those are Stage 2's job). It can be expanded with `/scrape-spec` (more pages, variant comparison, navigation).

**Hard constraints — never violate these:**
- You MUST NOT fetch, read, grep, or parse any HTML file yourself. Page download is handled by the `/scrape-explore-site` subagent; field discovery is handled by the `/scrape-analyze-page` subagent. The main agent only orchestrates and consumes their outputs.
- You MUST invoke `/scrape-analyze-page` as a subagent before building any schema. Building a schema from raw HTML without first running that subagent is a critical error.

## Parse intent

From $ARGUMENTS, determine:
- **target_url**: the starting URL
- **data_type**: what is being extracted, **always singular** — whether the user names it or you infer it from the URL/page. If the user says "books" use "book", "products" → "product", "articles" → "article". If inferring, use the singular item noun (e.g. "product" not "products", "book" not "books"). Singularize before using anywhere.
- **field_hints**: any specific fields the user mentioned (may be empty)
- **site_name**: a short identifier (e.g. "books-toscrape", "realestate-listings") — derive from the site and data type

## Step 1: Set up folders

Ensure site_name is unique:
```bash
BASE="books-toscrape"  # your derived site_name
NAME="$BASE"
N=2
while [ -d ".scrape/$NAME" ]; do NAME="${BASE}-${N}"; N=$((N+1)); done
echo "$NAME"
```

Create the folder structure (`{data_type}` must be singular, e.g. `book` not `books`):
```
.scrape/{site_name}/
  {data_type}/
.scrape/.work/{site_name}/
  explore/
  analyze-page/
```

## Step 2: Get a detail page

Ask the user how to obtain a detail page via `AskUserQuestion`:

- **question**: "How should I get a detail page to analyze?"
- **header**: "Detail page"
- **options**:
  - `Provide a URL` — "I'll paste a detail page URL (e.g. a product page)."
  - `Explore the site` — "Find one automatically from the target URL."

**If the user picks "Provide a URL"**: follow up with a plain-text prompt — "Paste the detail page URL." — and wait for their next message. Then download that page using `download.py`:
```bash
uv run ${CLAUDE_SKILL_DIR}/../scrape-explore-site/scripts/download.py --skill scrape-define --log-file .scrape/.work/{site_name}/explore/download.log <<'EOF'
[{"url": "USER_URL", "output_dir": ".scrape/.work/{site_name}/explore/pages/detail-1", "page_type": "detail"}]
EOF
```

**If the user picks "Explore the site"**: Use a subagent to run the `/scrape-explore-site` skill with minimal counts. The subagent prompt should be:

> Run /scrape-explore-site {target_url} .scrape/.work/{site_name}/explore 1 0

This downloads the homepage + 1 detail page into `.scrape/.work/{site_name}/explore/pages/`.

If the site is blocked, suggest Zyte. Only invoke `/scrape-zyte-login` if the user agrees. After it returns, re-run the `scrape-explore-site` subagent above.

## Step 3: Analyze the detail page

Use `rendered.html` for analysis. If it doesn't exist, fall back to `raw.html`.

Run a subagent with the analysis skill:
```
Agent(description="analyze detail-1 rendered", prompt="/scrape-analyze-page Extract data from .scrape/.work/{site_name}/explore/pages/detail-1/rendered.html and save it into .scrape/.work/{site_name}/analyze-page/detail-1.rendered.json")
```

Read the analysis result from `.scrape/.work/{site_name}/analyze-page/detail-1.rendered.json`.

## Step 4: Build schema

From the analysis result, build a JSON Schema:
- Collect all field names and their types
- Map types: `str` → `string`, `float` → `number`, `int` → `integer`, `list` → `array`, `dict` → `object`
- Add `description` for each field (infer from context)
- Mark fields matching field_hints as `"source": "requested"`, others as `"source": "discovered"`

## Step 5: Quick schema check

Present the schema with values in the terminal. Group by requested/discovered:

```
Found {N} fields on {detail_page_url}:

Requested:
  title (string): "A Light in the Attic"
  price (string): "£51.77"

Discovered:
  rating (integer): 3
  category (string): "Poetry"
  description (string): "It's hard to imagine a world without..." (2340 chars)
  upc (string): "a897fe39b1053632"
  image_url (string): "https://books.toscrape.com/media/cache/fe/72/..."
```

Wait for user response. The user can:
- **Approve**: "looks good", "ok", "approve", etc. → go to step 6
- **Drop fields**: "drop description, image_url" → remove from schema, show updated
- **Keep discovered fields**: "keep rating" → change source to "requested"
- **Rename**: "rename upc to product_code" → rename in schema
- **Edit descriptions**: "price should be without currency symbol" → update description and value
- **Other instructions**: apply and show updated schema

Loop until the user approves. Re-display the schema after each change.

## Step 6: Save spec

### Data type spec

Write `.scrape/{site_name}/{data_type}/spec.json`. The output MUST be valid JSON Schema (draft/2020-12) — use exactly the structure shown below. Do NOT invent a custom format (e.g. a plain array of field objects). Include `examples` in each schema field — the user-approved value (with any corrections). This tells Stage 2 the expected format. Include `examples` for all fields. Truncate values longer than 200 chars with "..." — keep enough to show the format.

```json
{
  "url": "https://books.toscrape.com",
  "data_type": "product",
  "html_variant": "rendered",
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "Book title as displayed on the detail page",
        "source": "requested",
        "examples": ["A Light in the Attic"]
      },
      "price": {
        "type": "string",
        "description": "Book price without currency symbol",
        "source": "requested",
        "examples": ["51.77"]
      }
    }
  }
}
```

### Site-level spec

Write `.scrape/{site_name}/spec.json`:
```json
{
  "url": "https://books.toscrape.com",
  "data_types": ["{data_type}"]
}
```

Note: `data_types` only lists the primary data type. `/scrape-spec` adds "navigation" later.

## Done

```
Spec draft saved to .scrape/{site_name}/:
  {data_type}: {N} fields

Run /scrape-spec .scrape/{site_name} to explore more pages and validate.
```
