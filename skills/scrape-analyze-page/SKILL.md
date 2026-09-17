---
name: scrape-analyze-page
description: Extract structured data (all available fields with values) from a page saved locally as an HTML file, optionally following a schema. Do not invoke when the user provides a URL. When invoking, pass the user's full request verbatim as args — do not pre-parse file paths and don't rephrase it.
allowed-tools: Skill, Bash, Read, Write
---

This file is 133 lines long; read all of them.

You are extracting structured data from a page. Given saved HTML, identify all available fields and extract their values.

## Input

This is the user prompt: `$ARGUMENTS`. You need to extract the following information from it:

1. Path to the saved HTML file, e.g. `product1.html`. This is what you need to analyze. Don't proceed if it's not provided.
2. Path to output file, e.g. `product1.json`. When provided, this is where you will save the structured analysis.
3. Path to data-type spec.json. When provided, guides extraction using schema field names, descriptions, and examples.
4. Whether to strictly extract only the fields listed in the schema, if the schema was provided. When asked for strict extraction, extract only schema fields — no extras.
5. `--list-mode`: when present, the page is a listing page. Extract ALL repeated item instances (e.g., every product card) as an array rather than a single-item object.

## Process

### 1. Clean and read the page

**Only process this one page.** Do not read or compare with other pages' analysis files.

`.scrape/.work/` is shared with the orchestrator and other concurrently
running agents. Never delete or "clean up" anything under it, at any point —
leave your intermediate files in place when you finish.

Clean the HTML and extract metadata, saving outputs to the work directory. Use `{page_id}.{html_variant}` as the filename base to avoid collisions:
```
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/clean_html.py PAGE.html -l1 -o .scrape/.work/analysis/{page_id}.{html_variant}.cleaned.html
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/extract_metadata.py PAGE.html -u PAGE_URL -o .scrape/.work/analysis/{page_id}.{html_variant}.metadata.json
```

Read **only** the cleaned HTML (never the original) and the metadata JSON. The metadata may be empty `{}` if the page has no structured data.

### 2. Extract fields

**IMPORTANT**: Never read the original HTML file (PAGE.html), even partially, even via tools such as Bash. Only use the cleaned HTML output from step 1 as your HTML source.

Use **both** the cleaned HTML and the metadata as data sources. Metadata (especially JSON-LD) often has cleaner, more complete values than what's visible in the HTML — e.g., structured `price`/`priceCurrency` vs rendered "$29.99", `aggregateRating` with review count, `brand` as a structured object. Some fields may only exist in metadata (e.g., `sku`, `gtin`, `@type`).

Examine both sources and extract all meaningful data fields. Meaningful means describing the page's own subject: leave out the surrounding site, such as navigation, ads, and other items listed as related, recommended, or recently viewed. For each field, determine:
- **name**: descriptive snake_case field name
- **type**: JSON Schema type name — string, number, integer, boolean, array, or object
- **value**: the extracted value

**Four modes** depending on arguments:

- **No schema** (Stage 1 — discovery): Extract all meaningful fields from the page. Invent descriptive snake_case names.
- **Schema** (Stage 2 — default): Extract schema fields using their exact names, descriptions, and `examples` for formatting. Also extract additional fields not in the schema — they may reveal data the user didn't know about.
- **Schema + strict** (Stage 2 — re-analysis): Extract only the schema fields. No extras.
- **List mode** (`--list-mode`): Identify the repeating container element on the page (e.g., `article.product_pod`, `.search-result`). Extract ALL item instances using schema field names. No extras — schema fields only. Produce an array.

In schema mode:

- Extract every schema property that has a value and save it with the schema's exact field name.
- For schema fields, follow the schema descriptions and examples first, preserve full values in the output file, and use the schema's JSON Schema type label (`string`, `number`, `integer`, `array`, `object`) when the schema provides one.
- If a schema field has no value in the cleaned HTML or metadata, omit it without calling attention to the missing field in the final response.
- Unless strict extraction was requested, also extract meaningful extra fields that are clearly present in metadata or cleaned content.
- For extras that do not have schema types, use `string`, `number`, `integer`, `boolean`, `array`, or `object`.
- For product media fields, prefer the displayed URL that matches the schema/example shape over canonical, thumbnail, zoom, or resized alternatives.
- Meaningful extras include product breadcrumbs, complete variant/offer lists, and obvious derived counts such as `tool_count` from an extracted `tools_included` list.
- If both a singular product image and an image list are available, save the singular best image field as well as the list when it is relevant.

### 3. Handle large values

For fields with large values (long text, HTML content, nested structures), extract the full value for the saved output and prepare a truncated version for the summary.

Truncating a value means keeping the beginning of it verbatim and stating how much was left out:

- Long text: the first 100 characters exactly as saved, plus the total character count.
- List or dict: the first entries exactly as saved, plus the total item count.

### 4. Save full output

If `output_path` is provided, save complete extraction to `output_path`, otherwise skip this step.
If the user has asked for a specific format and structure, use that.
Otherwise write a JSON file with the following structure.

**Standard format** (detail pages, no `--list-mode`):
```json
{
  "fields": {
    "name": {"type": "string", "value": "Widget X"},
    "price": {"type": "string", "value": "$29.99"},
    "description": {"type": "string", "value": "Full long description..."}
  }
}
```

**List mode format** (`--list-mode`): an array of all extracted item instances:
```json
{
  "url": "https://...",
  "values": [
    {"title": "A Light in the Attic", "price": "£51.77"},
    {"title": "Tipping the Velvet", "price": "£53.74"}
  ]
}
```

### 5. Return summary

Summarize the file you saved with:
```
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/summarize.py OUTPUT_PATH
```

It reads the saved JSON or YAML and prints every field with its name, type, and value, truncating the long ones as described in step 3. Use its output as your final message, unchanged.

Only when no `output_path` was provided, write that summary yourself: every extracted field with its field name, type, and value, no field omitted or renamed, and no value described instead of quoted, as in "8 offers" or "24 spec values".

Example:
```
These fields were discovered:
  name (string): "Widget X"
  price (string): "$29.99"
  description (string): "Premium widget with advanced..." (2340 chars)
  rating (number): 4.5
The full report is saved to $output_path
```

**List mode**: report count and a sample:
```
list-1 (https://...), saved to $output_path:
  20 items extracted
  sample: title="A Light in the Attic", price="£51.77"
```

Truncating long values is what keeps the summary compact enough to load into the orchestrator's main context alongside summaries from other pages.
