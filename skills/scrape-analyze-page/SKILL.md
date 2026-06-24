---
name: scrape-analyze-page
description: Extract structured data (all available fields with values) from a page saved locally as an HTML file, optionally following a schema. Use this skill only to process already downloaded files. Do not invoke when the user provides a URL. When invoking, pass the user's full request verbatim as args — do not pre-parse file paths and don't rephrase it.
allowed-tools: Skill, Bash, Read, Write
---

You are extracting structured data from a page. Given saved HTML, identify all available fields and extract their values.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

This is the user prompt: `$ARGUMENTS`. You need to extract the following information from it:

1. Path to the saved HTML file, e.g. `product1.html`. This is what you need to analyze. Don't proceed if it's not provided.
2. Path to output file, e.g. `product1.json`. When provided, this is where you will save the structured analysis.
3. Path to data-type spec.json. When provided, guides extraction using schema field names, descriptions, and examples.
4. Whether to strictly extract only the fields listed in the schema, if the schema was provided. When asked for strict extraction, extract only schema fields — no extras.

## Process

### 1. Clean and read the page

**Only process this one page.** Do not read or compare with other pages' analysis files.

Clean the HTML and extract metadata, saving outputs to the work directory. Use `{page_id}.{html_variant}` as the filename base to avoid collisions:
```
mkdir -p .scrape/.work/analysis
uv run ${CLAUDE_SKILL_DIR}/scripts/clean_html.py PAGE.html -l1 -o .scrape/.work/analysis/{page_id}.{html_variant}.cleaned.html
uv run ${CLAUDE_SKILL_DIR}/scripts/extract_metadata.py PAGE.html -u PAGE_URL -o .scrape/.work/analysis/{page_id}.{html_variant}.metadata.json
```

Read **only** the cleaned HTML (never the original) and the metadata JSON. The metadata may be empty `{}` if the page has no structured data.

### 2. Extract fields

**IMPORTANT**: Never read the original HTML file (PAGE.html), even partially, even via tools such as Bash. Only use the cleaned HTML output from step 1 as your HTML source.

Use **both** the cleaned HTML and the metadata as data sources. Metadata (especially JSON-LD) often has cleaner, more complete values than what's visible in the HTML — e.g., structured `price`/`priceCurrency` vs rendered "$29.99", `aggregateRating` with review count, `brand` as a structured object. Some fields may only exist in metadata (e.g., `sku`, `gtin`, `@type`).

Examine both sources and extract all meaningful data fields. For each field, determine:
- **name**: descriptive snake_case field name
- **type**: str, float, int, list, or dict
- **value**: the extracted value

**Three modes** depending on arguments:

- **No schema** (Stage 1 — discovery): Extract all meaningful fields from the page. Invent descriptive snake_case names.
- **Schema** (Stage 2 — default): Extract schema fields using their exact names, descriptions, and `examples` for formatting. Also extract additional fields not in the schema — they may reveal data the user didn't know about.
- **Schema + strict** (Stage 2 — re-analysis): Extract only the schema fields. No extras.

### 3. Handle large values

For fields with large values (long text, HTML content, nested structures):
- Extract the full value for the saved output
- Prepare a truncated version (first 100 chars) for the summary

### 4. Save full output

If `output_path` is provided, save complete extraction to `output_path`, otherwise skip this step.
If the user has asked for a specific format and structure, use that.
Otherwise write a JSON file with the following structure:
```json
{
  "fields": {
    "name": {"type": "str", "value": "Widget X"},
    "price": {"type": "str", "value": "$29.99"},
    "description": {"type": "str", "value": "Full long description..."}
  }
}
```

### 5. Return summary

Return a concise summary, with field names, types and values.
Truncate large values, if the full output was saved into a file.
Example:
```
These fields were discovered:
  name (str): "Widget X"
  price (str): "$29.99"
  description (str): "Premium widget with advanced..." (2340 chars)
  rating (float): 4.5
The full report is saved to $output_path
```
