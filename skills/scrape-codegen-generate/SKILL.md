---
name: scrape-codegen-generate
description: Generate web-poet page object code from per-page extraction analyses
argument-hint: "[work-path] [output-path] [spec-path]"
allowed-tools: Skill, Bash, Read, Write
---

You are generating web-poet page object code. You receive per-page extraction analyses (from Stage 1) that describe WHERE and HOW each field can be extracted from pages on a given domain. Your job is to synthesize these analyses into a single page object class that works across the entire domain.

## Input

The raw argument string is `$ARGUMENTS`. Split it into 3 whitespace-separated positional arguments:

1. **work_path**: directory containing Stage 1 analysis files, e.g. `.scrape/.work/spec`
2. **output_path**: where to save the generated page object, e.g. `.scrape/spec/page_object.py`
3. **spec_path**: path to spec.json file, e.g. `.scrape/spec/spec.json`

Plus, taken from the surrounding prompt text (not from the argument string):

- **fields**: optional, specific fields to generate (provided in the prompt as "Only generate these fields: ..."). When set, only generate `@field` methods for those fields. When not set, generate all fields found in the analyses.

## Process

### 1. Read inputs

Read `web-poet.md` and `docs-access.md` from `${CLAUDE_SKILL_DIR}/../scrape/references/`.

Read the schema from `{spec_path}` — use the `properties` object inside `schema`.

Read all Stage 1 analysis files from `{work_path}/codegen-analyze/`:
```
{work_path}/codegen-analyze/detail-1.json
{work_path}/codegen-analyze/detail-2.json
...
```

### 2. Build consensus across pages

For each field in the schema, review all per-page analyses together:

- **Identify common patterns**: Do all pages use the same CSS selector / JSON-LD path? If so, that's a strong signal.
- **Resolve disagreements**: If analyses recommend different approaches for different pages, determine:
  - Is one approach more general? (e.g., a selector that works on all pages vs one that only works on some)
  - Should you combine approaches? (e.g., try JSON-LD first, fall back to CSS)
  - Are there structural differences between pages that require conditional logic?
- **Validate target values**: Check that the recommended extraction method would produce the target values across all pages.
- **Decide on data source**: For each field, decide whether to use HTML selectors, JSON-LD, microdata, URL, or a combination.

### 3. Generate page object code

**No content filtering — ever.** Even if the user's prompt asks to filter,
exclude, or limit results by value, do NOT implement that logic in the page
object. Page objects extract; spiders filter. Mention in your summary that
filtering belongs at the spider level.

Generate a complete, self-contained Python module following the web-poet reference. The code must:

- **Work across the domain**: not just for the analyzed pages. Avoid overfitting — no hardcoded product names, specific if/else for individual pages, etc.
- **Be simple**: prefer the simplest approach that works. Only add fallbacks when analyses show the data genuinely comes from different sources on different pages.
- Use BrowserPage as base class if a browser response is needed.
- **Handle missing data**: return `None` when a field is not present (never empty string or `[]`).
- **Match schema types**: return values matching the JSON schema types.
- **Use recommended libraries**: `extruct` for JSON-LD/microdata, `price_parser` for prices, `jmespath` for JSON queries.
- **Include all imports**: the module must be self-contained and runnable.

Structure:
```python
from web_poet import WebPage, field
# ... other imports as needed

class PageObject(WebPage[dict]):
    # shared helpers as @cached_property if multiple fields need them

    @field
    def field_name(self) -> type | None:
        # extraction logic
        ...
```

### 4. Save and report

Save the generated code to `{output_path}`.

Return a summary of what was generated:
```
Generated page object with N fields:
  name: CSS h1.product-title::text
  price: JSON-LD offers.price, fallback to CSS span.price
  description: CSS div.product-description (text join)
  rating: JSON-LD aggregateRating.ratingValue
  image_url: CSS img.product-image::attr(src) + urljoin
```

Include notes on any fields where consensus was difficult or where extraction may be fragile.
