---
name: scrape-codegen
description: Generate web-poet page object code from an extraction spec
argument-hint: "[spec-path] [project-dir] [fields]"
allowed-tools: Skill, Agent, Bash, Read, Write
---

You are generating a web-poet page object from an extraction spec. The spec contains
a schema, saved HTML pages, and expected values. It may describe any data type —
product details, navigation links, article content, etc. Codegen doesn't need to
know the data type; it generates a PO that extracts according to the schema.

The spec was produced by `/scrape-spec` and the project by `/scrape-ensure-project`.

Read `python-environments.md` and `docs-access.md` from `${CLAUDE_SKILL_DIR}/../scrape/references`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into up to 3 whitespace-separated positional arguments:

1. **spec_path**: path to spec folder, e.g. `.scrape/books-toscrape`
2. **project_dir**: path to the Scrapy project
3. **fields**: optional, comma-separated field names to generate (empty = all fields)

## Process

### Step 1: Read the spec

Read `{spec_path}/spec.json` to get:
- `schema.properties` — the field definitions
- `html_variant` — which HTML to use (`raw` or `rendered`)
- `url` — the starting URL (used for domain name)
- `data_type` — what's being extracted (used for class naming); always singular (e.g. `product`, `book`)

Derive names from `data_type` using these conventions (never pluralize):
- `ClassName` = PascalCase + `Page` → `product` → `ProductPage`
- `ItemClass` = PascalCase + `Item` → `product` → `ProductItem`
- `module_name` = snake_case of `data_type` → `product` → `product`

If `fields` is provided, filter `schema.properties` to only include those fields.

List page directories in `{spec_path}/pages/` that have corresponding values in
`{spec_path}/values/`. Read expected values from each.

Derive `site_name` from the spec_path (parent directory name, e.g. `books-toscrape` from `.scrape/books-toscrape/products`).
Detect the project name from `{project_dir}`.

**List-type detection.** If `data_type` ends with `-list` (e.g., `products-list`):
- Set `is_list_type = true`
- Set `base_type` by stripping the `-list` suffix (e.g., `products`)
- Derive `ItemClass`: singularize `base_type` by dropping a trailing `s` if present
  (e.g., `products` → `product`), then TitleCase (e.g., `Product`). If the name
  already looks singular, just TitleCase it.
- `WrapperClass = {ItemClass}ListItems` (e.g., `ProductListItems`)
- `PageClass = {ItemClass}ListPage` (e.g., `ProductListPage`)
- Values are in array format: `{"url": ..., "values": [{...}, ...]}`

Otherwise, set `is_list_type = false` and derive `ClassName` as `TitleCase(data_type) + "Page"`.

### Step 2: Add item and page object stub

**For non-list types (`is_list_type = false`):**

Check `{project_name}/items.py` for an existing item class matching `data_type`.
If none exists, write one based on the schema (all fields optional, `| None = None`).

Add a page object stub in a sub-agent so the parent skill can continue afterward:

```
Agent(description="add page object stub", prompt="/scrape-add-page-object {project_dir}/{project_name}/pages/{module_name}.py {ClassName} {domain} web_poet.WebPage {project_name}.items.{ItemClass}")
```

Use `web_poet.BrowserPage` if `html_variant` is `rendered`.

**For list types (`is_list_type = true`):**

The `items.py` needs two classes. Check if they exist; write any that are missing.

1. **Base item class** (`ItemClass`, e.g., `Product`) — a `@dataclass` with fields
   typed to match the schema. Example:
   ```python
   @dataclass
   class Product:
       title: str
       price: str | None = None
   ```

2. **Wrapper class** (`WrapperClass`, e.g., `ProductListItems`) — a `@dataclass` with a
   single `items` field typed as `list[ItemClass] | None = None`. Example:
   ```python
   @dataclass
   class ProductListItems:
       items: list[Product] | None = None
   ```

Then add the page object stub in a sub-agent, explicitly passing `items` as arg 6
so the `@field` stub is generated even though all wrapper fields have defaults:

```
Agent(description="add page object stub", prompt="/scrape-add-page-object {project_dir}/{project_name}/pages/{module_name}.py {PageClass} {domain} web_poet.WebPage {project_name}.items.{WrapperClass} items")
```

### Step 3: Convert fixtures

Find the fixture class path from the project structure (e.g.,
`{project_name}.pages.{module_name}.{ClassName}`).

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/convert_fixtures.py \
    {spec_path} {project_dir} {fixture_class_path}
```

### Step 4: Analyze pages (parallel)

```bash
mkdir -p .scrape/.work/{site_name}/codegen-analyze
```

Launch one Agent per page with values, **all in a single message** for parallel
execution. Each agent runs `/scrape-codegen-analyze` with all 4 arguments:

```
/scrape-codegen-analyze {spec_path}/pages/{page_id}/{html_variant}.html .scrape/.work/{site_name} {spec_path}/spec.json {spec_path}/values/{page_id}.json
```

Skip pages whose HTML file doesn't exist.

For list-type specs, pages are named `list-*` and values contain arrays.
The `scrape-codegen-analyze` skill detects list pages automatically from
`meta.json` (where `page_type` is `list`) and produces container-based
extraction instructions.

### Step 5: Generate page object code

After all analysis agents complete, launch a single Agent running
`/scrape-codegen-generate` with all 3 arguments:

```
/scrape-codegen-generate .scrape/.work/{site_name} {project_dir}/{project_name}/pages/{module_name}.py {spec_path}/spec.json
```

### Step 6: Test

```bash
cd {project_dir} && uv run pytest fixtures/ -x -v
```

Report results. If tests fail, read errors and consider re-generating failed fields.

### Step 7: Report

```
Generated page object at {project_dir}/{project_name}/pages/{module_name}.py:
  Class: {ClassName} (N fields)
  Fixtures: N test cases
  Tests: N/N passing
```

## Codegen rules

Follow the web-poet reference at `${CLAUDE_SKILL_DIR}/../scrape/references/web-poet.md`, plus:

- Keep code simple and domain-general — not overfitted to example pages
- Return `None` for missing data — never empty string, `False`, or `[]`
- Use guard clauses, check for `None` before attribute access
- Don't add docstrings to field methods
- Don't catch generic `Exception` — only specific exceptions
- Prefer deterministic output — avoid sets (use list + dedup if needed)
- If analysis shows a field comes from structured data (JSON-LD, microdata), use
  `extruct` — the metadata format matches `extract_metadata.py` output from earlier
  stages, so the same access patterns work in the page object
- If a browser response is needed, use `BrowserPage` as the base class