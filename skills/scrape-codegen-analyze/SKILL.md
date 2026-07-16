---
name: scrape-codegen-analyze
description: Analyze an HTML page to produce field extraction instructions for code generation
argument-hint: "[page-html-path] [work-path] [spec-path] [values-path]"
allowed-tools: Skill, Bash, Read, Write
---

You are analyzing a detail page to produce extraction instructions for a code generation system. Given an HTML page, a schema, and expected values, you determine WHERE and HOW each field can be extracted from the page.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

Your analysis will be read by a separate code-generation agent that does **not** have access to the HTML. It must be detailed enough for that agent to write correct web-poet extraction code.

## Input

The raw argument string is `$ARGUMENTS`. Split it into 4 whitespace-separated positional arguments:

1. **page_html_path**: path to saved HTML file, e.g. `.scrape/spec/pages/detail-1/raw.html`
2. **work_path**: working directory for saving analysis output, e.g. `.scrape/.work/spec`
3. **spec_path**: path to spec.json file, e.g. `.scrape/spec/spec.json`
4. **values_path**: path to values JSON file for this page, e.g. `.scrape/spec/values/detail-1.json`

Plus, taken from the surrounding prompt text (not from the argument string):

- **fields**: optional, specific fields to analyze (provided in the prompt as "Only analyze these fields: ..."). When set, only analyze those fields from the schema — skip the rest. When not set, analyze all fields.

The page directory (parent of the HTML file) also contains `meta.json` with the source URL.

## Process

### 1. Read inputs and prepare HTML

Derive the **page_id** from the directory name (e.g. `detail-1` from `.../detail-1/raw.html`).

Read `meta.json` from the same directory for the source URL and `page_type`.

If `meta.json` has `"page_type": "list"`, or the page_id starts with `list-`,
set `is_list_page = true`. This changes how fields are analyzed (see step 2).

Read the schema from `{spec_path}` — use the `properties` object inside `schema`.
Read the expected values from `{values_path}` — use the `values` object (may be `{}`).

Clean the HTML and extract structured metadata. Use level 0 cleaning to preserve scripts (which may contain JSON-LD/embedded data):

```bash
mkdir -p {work_path}/codegen-analyze
uv run ${CLAUDE_SKILL_DIR}/../scrape-analyze-page/scripts/clean_html.py PAGE.html -l0 -o {work_path}/codegen-analyze/{page_id}.cleaned.html
uv run ${CLAUDE_SKILL_DIR}/../scrape-analyze-page/scripts/extract_metadata.py PAGE.html -u PAGE_URL -o {work_path}/codegen-analyze/{page_id}.metadata.json
```

Read **only** the cleaned HTML (not the original) and the metadata JSON.

### 2. Analyze each field

**For list pages (`is_list_page = true`):** The page contains multiple repeated
item elements. Instead of locating a single field value, you must identify:

1. **The container selector** — the CSS selector for the repeating element that
   wraps each item (e.g., `article.product_pod`, `li.col-xs-6 article`, `div.item`).
   Look for the smallest repeated element that contains ALL requested fields.
   Report this as `container_selector` in the analysis output (see step 4).

2. **Per-field selectors relative to the container** — for each field, note the
   CSS selector that works *inside* a single container element (e.g., if the
   container is `article.product_pod`, the title might be `h3 a::attr(title)`
   relative to it). Verify that this relative selector works consistently across
   multiple container instances on the page.

3. **Expected item count** — note how many container elements you find; this
   should match the number of items in the values array.

The analysis for a list page should describe the container-based extraction
pattern so `scrape-codegen-generate` can produce a `for container in self.css(...):`
loop.

**For detail pages:** For each field in the schema, produce a detailed analysis.
Consider **all** possible data sources in the HTML:

- **HTML elements**: tags, classes, IDs, attributes — note the CSS selectors or XPaths
- **JSON-LD**: `<script type="application/ld+json">` blocks — note the JSON path
- **Microdata**: `itemscope`/`itemprop` attributes
- **OpenGraph**: `<meta property="og:...">` tags
- **Other script tags**: embedded JSON in `<script>` tags (e.g. `window.__DATA__ = {...}`)
- **URL components**: data derivable from the page URL
- **Meta tags**: `<meta name="...">` tags
- **Hidden inputs** or `data-*` attributes

For each source found, describe:
- The **CSS selector or XPath** that reaches the data element
- The **post-processing** needed (text extraction, regex, JSON path, type conversion)
- **Reliability**: is the selector unique and stable, or fragile?
- A **small HTML snippet** showing the relevant element in context (use `...` to shorten long content)

Then recommend the best extraction method and explain why.

### 3. Determine target values

For each field, determine the correct target extraction value:
- If expected values are provided, verify them against what's actually in the HTML
- If they match, use them
- If they seem wrong or incomplete, note the discrepancy and provide the corrected value based on the HTML
- If a field has no data in this page, set to `null`

### 4. Save analysis

Save to `{work_path}/codegen-analyze/{page_id}.json`.

For **detail pages**:
```json
{
  "url": "https://example.com/product/widget-x",
  "page_id": "detail-1",
  "fields": {
    "name": {
      "target_value": "Widget X",
      "analysis": "The product name appears in two places:\n\n1. **HTML element** `<h1 class=\"product-title\">Widget X</h1>`\n   - Selector: `h1.product-title::text`\n   - Clean text, no post-processing needed\n   - Reliable: unique h1 on the page\n\n2. **JSON-LD** in `<script type=\"application/ld+json\">`:\n   ```json\n   {\"@type\": \"Product\", \"name\": \"Widget X\", ...}\n   ```\n   - Path: `name` on the Product object\n   - Also reliable\n\nRecommended: CSS selector `h1.product-title::text` — simplest, most direct."
    },
    "price": {
      "target_value": "$29.99",
      "analysis": "..."
    }
  }
}
```

For **list pages**, include `container_selector` and `item_count`, and
per-field analyses use relative selectors inside the container:
```json
{
  "url": "https://example.com/category/widgets/",
  "page_id": "list-1",
  "is_list_page": true,
  "container_selector": "article.product_pod",
  "item_count": 20,
  "fields": {
    "name": {
      "target_values": ["Widget X", "Widget Y", "..."],
      "analysis": "Container: article.product_pod\nRelative selector: h3 a::attr(title)\nFinds the full product title in the anchor's title attribute.\nVerified across 20 containers on the page."
    },
    "price": {
      "target_values": ["$29.99", "$14.99", "..."],
      "analysis": "Container: article.product_pod\nRelative selector: p.price_color::text\nFinds the price text directly. Verified across 20 containers."
    }
  }
}
```

### 5. Return summary

For detail pages, return a compact summary:
```
detail-1 (https://...):
  name: "Widget X" — h1.product-title, also in JSON-LD
  price: "$29.99" — span.price::text, JSON-LD offers.price
  description: "A premium widget..." (2340 chars) — div.description
  rating: null — not found in HTML
```

For list pages, include the container selector and item count:
```
list-1 (https://...): 20 items, container: article.product_pod
  name: h3 a::attr(title) — "Widget X", "Widget Y", ...
  price: p.price_color::text — "$29.99", "$14.99", ...
```
