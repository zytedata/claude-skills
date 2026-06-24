# Extraction Spec Format

IMPORTANT: this spec is not stable.

An extraction spec describes what to extract from a website. It is organized by
site, with separate data type folders for each extraction target (e.g., product,
navigation). Each data type folder is self-contained and can be passed to codegen
independently.

## Folder structure

```
.scrape/{site-name}/
  spec.json                    # site-level metadata
  {data-type}/                 # one folder per extraction target
    spec.json                  # schema + data type metadata
    pages/                     # saved pages for this data type
      detail-1/
        raw.html
        rendered.html
        screenshot.png
        meta.json
      detail-2/
        ...
    values/                    # expected values per page
      detail-1.json
      detail-2.json
```

`{site-name}` is a short identifier (e.g., "books-toscrape"). `{data-type}` is
the extraction target in singular form (e.g., "product", "navigation").

Example with two data types:

```
.scrape/books-toscrape/
  spec.json
  product/
    spec.json
    pages/detail-1/, detail-2/, detail-3/
    values/detail-1.json, detail-2.json, detail-3.json
  navigation/
    spec.json
    pages/list-1/, list-2/, start-1/
    values/list-1.json, list-2.json, start-1.json
```

Pages are copied into each data type folder to keep them self-contained. The same
HTML may appear in multiple data types (e.g., list pages used by both navigation
and future category-level extraction).

Working state (analysis results, intermediate data) is kept separately in
`.scrape/.work/{site-name}/` and is not part of the spec.

## Site-level spec.json

```json
{
  "url": "https://books.toscrape.com",
  "data_types": ["product", "navigation"]
}
```

## Data type spec.json

```json
{
  "url": "https://books.toscrape.com",
  "data_type": "product",
  "html_variant": "raw",
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "Full product name as shown on the page",
        "source": "requested",
        "examples": ["A Light in the Attic"]
      },
      "price": {
        "type": "string",
        "description": "Current sale price including currency symbol",
        "examples": ["£51.77"]
      }
    }
  }
}
```

### Schema subset

Use a minimal JSON Schema subset:
- **Types:** `string`, `number`, `integer`, `boolean`, `array`, `object`
- **Keywords:** `type`, `description`, `properties` (for objects), `items` (for arrays)
- **Extension:** `source` — either `"requested"` (user asked for this field) or `"discovered"` (AI found it during analysis). Used by the review UI.
- **Standard:** `examples` — array of example values showing the expected format. Set during Stage 1 from user-approved (possibly corrected) values. Used by Stage 2's analysis as extraction context. Truncate values longer than 200 chars with "..." — keep enough to show the format.
- **Not used:** `oneOf`, `allOf`, `anyOf`, `if/then/else`, `$ref`, `pattern`, `format`, `enum`, validation constraints

Every field must have `type` and `description`.

### Navigation schema

Navigation is a standard data type with a fixed schema:

```json
{
  "url": "https://books.toscrape.com",
  "data_type": "navigation",
  "html_variant": "raw",
  "schema": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {"type": "object", "properties": {"url": {"type": "string"}, "text": {"type": "string"}}},
        "description": "Links to detail/item pages"
      },
      "next_page": {
        "type": "string",
        "description": "URL of the next page, or null"
      },
      "subcategories": {
        "type": "array",
        "items": {"type": "object", "properties": {"url": {"type": "string"}, "text": {"type": "string"}}},
        "description": "Links to subcategory/sublisting pages"
      }
    }
  }
}
```

## Page directories

Each page is stored in its own directory: `pages/{type}-{n}/`. The directory contains:

- **raw.html** — HTTP response body
- **rendered.html** — Playwright-rendered HTML (may be absent if Playwright failed)
- **screenshot.png** — full-page screenshot (may be absent)
- **meta.json** — capture metadata:

```json
{
  "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "captured_at": "2026-03-18T14:30:00Z",
  "page_type": "detail",
  "http_status": 200,
  "http_headers": {"content-type": "text/html; charset=utf-8"}
}
```

Page types: `start`, `list`, `detail`.

## values/{page-id}.json

Expected values for one page, conforming to the schema:

```json
{
  "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "values": {
    "name": "A Light in the Attic",
    "price": "£51.77"
  }
}
```

For navigation:

```json
{
  "url": "https://books.toscrape.com/catalogue/category/books_1/index.html",
  "values": {
    "items": [
      {"url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html", "text": "A Light in the Attic"},
      {"url": "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html", "text": "Tipping the Velvet"}
    ],
    "next_page": "https://books.toscrape.com/catalogue/page-2.html",
    "subcategories": [
      {"url": "https://books.toscrape.com/catalogue/category/books/travel_2/index.html", "text": "Travel"}
    ]
  }
}
```

## What makes a spec complete

A data type spec is ready for codegen when:
1. `spec.json` exists with a schema
2. At least one page in `pages/` with its HTML and metadata
3. Corresponding values in `values/` for each page
