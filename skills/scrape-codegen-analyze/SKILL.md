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

Read `meta.json` from the same directory for the source URL.

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

For each field in the schema, produce a detailed analysis. Consider **all** possible data sources in the HTML:

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

Save to `{work_path}/codegen-analyze/{page_id}.json`:

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

### 5. Return summary

Return a compact summary for the orchestrator:
```
detail-1 (https://...):
  name: "Widget X" — h1.product-title, also in JSON-LD
  price: "$29.99" — span.price::text, JSON-LD offers.price
  description: "A premium widget..." (2340 chars) — div.description
  rating: null — not found in HTML
```
