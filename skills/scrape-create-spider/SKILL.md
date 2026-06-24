---
name: scrape-create-spider
description: Generate a Scrapy spider that wires page objects together
argument-hint: "[project-dir] [item-page] [nav-page]"
allowed-tools: Bash, Read, Write, Edit
---

You are generating a Scrapy spider that wires together web-poet page objects (item
extraction + navigation) into a working crawler.

Read `python-environments.md` and `docs-access.md` from `${CLAUDE_SKILL_DIR}/../scrape/references`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into 3 whitespace-separated positional arguments:

1. **project_dir**: path to the Scrapy project
2. **item_page**: import path of the item extraction PO (e.g. `books_project.pages.books_toscrape_com.ProductPage`)
3. **nav_page**: import path of the navigation PO (e.g. `books_project.pages.books_toscrape_com.NavigationPage`)

Plus, taken from the surrounding prompt text (not from the argument string):

- **start_urls**: provided in the prompt text (e.g. "Start URLs: https://example.com https://example.com/category/shoes")

## Process

### 1. Read the project and spec

Detect the project name from `{project_dir}`.

Use the provided PO import paths to determine the module and class names for imports.
Parse start URLs to derive the spider name from the domain.

Read `references/scrapy-poet-reference.md` for spider patterns.

### 2. Generate the spider

Write a spider to `{project_name}/spiders/{spider_name}.py`.

The spider uses the navigation PO to discover links and the item extraction PO to
extract data. Pattern:

```python
import scrapy
from scrapy_poet import DummyResponse

from {project_name}.pages.{module} import {ItemPage}, {NavPage}


class {SpiderClass}(scrapy.Spider):
    name = "{spider_name}"
    start_urls = ["{start_url}"]

    async def parse(self, response: DummyResponse, nav: {NavPage}):
        """Parse list/category pages — extract navigation links."""
        nav_item = await nav.to_item()

        # Follow item links → item extraction PO
        for link in nav_item.items or []:
            yield scrapy.Request(link["url"], callback=self.parse_item)

        # Follow pagination
        if nav_item.next_page:
            yield scrapy.Request(nav_item.next_page, callback=self.parse)

        # Follow subcategories
        for link in nav_item.subcategories or []:
            yield scrapy.Request(link["url"], callback=self.parse)

    async def parse_item(self, response: DummyResponse, page: {ItemPage}):
        """Extract item data."""
        yield await page.to_item()
```

Key points:
- `parse` is the default callback for `start_urls`
- POs are injected via type annotations on callbacks
- `response: DummyResponse` since we only need the PO, not raw response
- Pagination and subcategory links recurse back to `parse`

### 3. Naming

- **spider_name**: derive from domain (e.g., `books_toscrape_com`)
- **SpiderClass**: PascalCase version (e.g., `BooksToscrapeCom`)
- **module**: the page objects module file (same domain-based name)

### 4. Custom settings (if needed)

If the site requires Zyte API (e.g., detected during spec building), add:
```python
    custom_settings = {
        "ZYTE_API_TRANSPARENT_MODE": True,
    }
```

Read the scrapy-zyte-api reference:

```
references/scrapy-zyte-api-reference.md
```

### 5. Test the spider and validate items

Run a test crawl that saves items to a file so you can inspect them:

```bash
cd {project_dir} && uv run scrapy crawl {spider_name} -s CLOSESPIDER_ITEMCOUNT=5 -o items.jsonl 2>&1
```

**If the crawl fails** (non-zero exit, exceptions in output):
- Check error messages
- Verify page object imports are correct
- Verify `SCRAPY_POET_DISCOVER` includes the pages module
- Try with `ZYTE_API_LOG_REQUESTS=True` if using Zyte API

If the crawl succeeds, read `items.jsonl` and check for obvious data-quality issues. If you find any, read the relevant page object, diagnose and fix the root cause, delete `items.jsonl`, and re-run. Repeat up to 2 more times (3 total). If items still look wrong after 3 attempts, stop and report what you found.

Only declare the spider complete once items look correct.

### 6. Report

```
Created spider at {project_name}/spiders/{spider_name}.py:
  Start URL: {start_url}
  Navigation: {NavPage} → follows items, pagination, subcategories
  Extraction: {ItemPage} via callback_for

Run: cd {project_dir} && uv run scrapy crawl {spider_name}
```
