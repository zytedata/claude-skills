# Changelog

## 0.2.0 (2026-06-24)

### Action recommended: update your marketplace URL

The plugin repository moved from `zyte-ai/claude-skills` to
`zytedata/claude-skills`. The old URL continues to work for now, but we
recommend switching to the new one:

```bash
claude plugin marketplace remove zyte-ai
claude plugin marketplace add zytedata/claude-skills
```

Then reload plugins in any active Claude Code session:

```bash
/reload-plugins
```

### Added

- New `/scrape-zyte-api-stats` skill: query historical Zyte API usage —
  cost, request volume, response times, status codes — with grouping and
  filtering options.
- `/scrape-analyze-page` is now independently usable: pass any locally saved
  HTML file to extract structured data without running the full pipeline.

### Improved

- `/scrape`: single-page extraction requests are now correctly routed to
  `/scrape-analyze-page` instead of triggering the full workflow.
- `/scrape-review-schema`: review page redesigned — cleaner layout, better
  spacing, and improved field display.
- `/scrape-create-spider`: after the smoke-test crawl the spider now inspects
  extracted items for data-quality issues and self-corrects (up to 3 attempts)
  before reporting completion.
- `/scrape-spec`: navigation HTML variant is now chosen independently of the
  detail-page variant, improving navigation coverage on JS-rendered sites.
- `/scrape-explore-site`: improved accuracy when classifying navigation links —
  link groups that mix on-topic and off-topic URLs are now skipped instead of
  being followed, preventing the crawler from wandering out of scope.
- `/scrape-scrapy-cloud`: `shub` is now invoked via `uvx` — no separate
  install step required.
- `/scrape-add-page-object`: required fields are now auto-detected from the
  item class via itemadapter, reducing LLM calls and context usage.
- `/scrape-codegen`: generated page objects now return all available data
  without filtering, leaving content filtering to the spider.
- `/scrape-codegen`: generated page objects now use `BrowserPage` as the base
  class when a browser response is needed.
- Most skills now carry explicit `uv run` / `uvx` guidance, reducing failures
  caused by the model falling back on bare `python` or `pip` calls and the
  extra turns those failures produce.
- Code-generation and Scrapy Cloud skills can now look up live library
  documentation (docs.zyte.com, docs.scrapy.org, ReadTheDocs) when the
  built-in references do not cover a topic.
- Generated project directories and class names now use the singular form of
  the data type (e.g. `product/`, `ProductPage`) for consistency.

### Fixed

- `/scrape-review-schema`: submitting feedback from the review page no longer
  fails with `ERR_CONNECTION_REFUSED`.
- `/scrape-explore-site`: link group counts now correctly reflect the total
  number of links found, not just the number returned after applying the limit.
- `/scrape-analyze-page`: no longer triggered when the user's request contains
  a URL — the skill is now correctly limited to locally saved HTML files.

## 0.1.0 — 2026-05-12

Initial release.
