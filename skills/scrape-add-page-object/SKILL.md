---
name: scrape-add-page-object
description: Add an empty web-poet page object to a Scrapy project
argument-hint: "[file-path] [class-name] [domain] [base-class] [item-class]"
allowed-tools: Bash, Read, Write
---

You are adding an empty web-poet page object to a Scrapy project.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into up to 6 whitespace-separated positional arguments:

1. **file_path**: path to the .py file to create or append to (e.g. `books_project/pages/books_toscrape_com.py`)
2. **class_name**: page object class name (e.g. `ProductPage`)
3. **domain**: domain for `@handle_urls` (e.g. `books.toscrape.com`)
4. **base_class**: base class import path (e.g. `web_poet.WebPage`)
5. **item_class**: item class import path (e.g. `books_project.items.ProductItem`)
6. **fields**: optional, comma-separated field names (e.g. `name,price,rating`)

## Process

Run from the **project root** (the directory containing `pyproject.toml`) so the item
class is importable for auto-detecting required fields:

```bash
uv run --project . --with libcst ${CLAUDE_SKILL_DIR}/scripts/add_page_object.py \
    FILE_PATH CLASS_NAME DOMAIN BASE_CLASS ITEM_CLASS
```

Required fields (those with no default in the item class) are detected automatically
via itemadapter and get `@field` stubs. If all fields have defaults the class body is
`pass`. Pass `--fields name,price` to override auto-detection.

The script uses libcst for correct AST manipulation:
- Creates the file if it doesn't exist
- Appends to existing files with proper import merging
- Multiple page objects can share a module (e.g., `ProductPage` and `CategoryPage`)

Common base classes:
- `web_poet.WebPage` — for pages using HTTP responses (most common)
