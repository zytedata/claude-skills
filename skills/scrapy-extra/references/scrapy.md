This file is 205 lines long; read all of them.

# Scrapy Reference

Concise reference for writing Scrapy spiders. For full docs see
https://docs.scrapy.org/llms.txt

This covers plain Scrapy. For page objects layered on top, see
`web-poet.md` and `scrapy-poet.md`; for anti-ban / browser rendering see
`scrapy-zyte-api.md`.

## Project layout

A Scrapy project is a Python package with a `scrapy.cfg` at its root:

```
myproject/
  scrapy.cfg            # points at the settings module
  myproject/
    __init__.py
    settings.py         # project settings
    items.py            # item definitions (optional)
    spiders/            # one module per spider
```

Run commands from the directory containing `scrapy.cfg`.

## Spiders

Extraction is often isolated in web-poet page objects rather than written
inline (see `web-poet.md` / `scrapy-poet.md`, and the skill's guidance on when
to prefer them). The inline extraction below is the plain-Scrapy baseline.

```python
import scrapy


class BooksSpider(scrapy.Spider):
    name = "books"
    start_urls = ["https://books.toscrape.com/"]

    def parse(self, response):
        for book in response.css("article.product_pod"):
            yield {"title": book.css("h3 a::attr(title)").get()}
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
```

- `name` — unique spider name, used by `scrapy crawl <name>`.
- `start_urls` — requested with `parse` as the default callback. For custom
  headers/meta or non-GET requests, override the async `start()` method
  instead and `yield scrapy.Request(...)`:

  ```python
  async def start(self):
      yield scrapy.Request("https://books.toscrape.com/", headers={...})
  ```

- Callbacks `yield` either items (dicts / item objects) or further
  `Request`s.

`start()` is async and was added in Scrapy 2.13, replacing the old sync
`start_requests()` — which was deprecated in 2.13 and removed in 2.16. Use
`start_requests()` only when the project must run on Scrapy < 2.13.

### Requests and following links

Prefer, in order: `response.follow_all` (extracts links and resolves URLs),
then `response.follow` (resolves a single URL), then a plain `Request`.

```python
from scrapy import Request

# Best: extract and follow many links in one call.
yield from response.follow_all(css="a.product::attr(href)", callback=self.parse_detail)
# Good: follow a single link; resolves relative URLs against the response.
yield response.follow(relative_href, callback=self.parse_detail)
# Last resort: a plain Request, e.g. for an absolute URL built by hand.
yield Request(url, callback=self.parse_detail, meta={"key": "value"})
```

`response.meta` carries per-request state between callbacks. `cb_kwargs` is
the modern, explicit way to pass data to a callback:

```python
yield response.follow(href, self.parse_detail, cb_kwargs={"category": cat})

def parse_detail(self, response, category):
    ...
```

### Selectors (Parsel)

```python
response.css("h1::text").get()          # first match or None
response.css("li::text").getall()       # list[str]
response.css("a::attr(href)").get()     # attribute
response.xpath("//h1/text()").get()
response.css("div.product").css("h2::text")   # chaining
```

`response.json()` parses a JSON response body — useful for API endpoints.

## Built-in spider classes

Scrapy ships generic spider classes for common crawling patterns —
`CrawlSpider` (rule-based link following), `SitemapSpider`, `XMLFeedSpider`,
`CSVFeedSpider`. In most cases, however, a plain `Spider` with explicit
`response.follow` control flow is usually clearer. See
https://docs.scrapy.org/en/latest/topics/spiders.md for details.

## Items

Items are optional — yielding plain dicts is fine. Define items for a stable
schema, typed fields, and pipeline validation.
[`itemadapter`](https://raw.githubusercontent.com/scrapy/itemadapter/refs/heads/master/README.md)
lets Scrapy treat dicts, `scrapy.Item`, `@dataclass`, `attrs`, and
`pydantic` classes uniformly, and it can be extended with custom adapters to
support additional item types.

```python
from dataclasses import dataclass


@dataclass
class BookItem:
    title: str | None = None
    price: str | None = None
```

## Item pipelines

Post-process, validate, or store items. This layer (or the spider) is where
filtering, deduplication, and enrichment belong — the counterpart to keeping
them out of extraction code.

```python
# pipelines.py
from scrapy.exceptions import DropItem


class PriceRequiredPipeline:
    def process_item(self, item, spider):
        if not item.get("price"):
            raise DropItem("missing price")
        return item
```

```python
# settings.py
ITEM_PIPELINES = {"myproject.pipelines.PriceRequiredPipeline": 300}
```

## Output

Scrapy exports items to files (feed exports) and, via item pipelines, to
databases and other services. Zyte's
[export guide](https://docs.zyte.com/web-scraping/guides/export/index.md)
covers the destinations and when to use each — Scrapy Cloud, file storage
(local, S3, Azure, Google Cloud Storage, FTP/SFTP, Google Sheets, …), and
item storage (e.g. BigQuery, or a custom pipeline for any database or
message queue).

For a quick local run, feed exports on the command line are enough:

```bash
scrapy crawl books -o items.jsonl        # append
scrapy crawl books -O items.json         # overwrite
scrapy crawl books -o books.csv
```

Configure `FEEDS` in settings for scheduled/cloud runs.

## Common settings

```python
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1
FEED_EXPORT_ENCODING = "utf-8"
```

Prefer per-spider overrides via `custom_settings` when only one spider needs
them:

```python
class MySpider(scrapy.Spider):
    custom_settings = {"DOWNLOAD_DELAY": 0.5}
```

## Running and debugging

```bash
scrapy crawl <name>                                  # run a spider
scrapy crawl <name> -s CLOSESPIDER_ITEMCOUNT=5 -o items.jsonl   # bounded test run
scrapy list                                          # list spiders
scrapy parse "https://example.com" --spider <name> --callback parse   # test a callback
scrapy shell "https://example.com" -c "response.css('h1::text').get()"   # test a selector non-interactively
```

A clean exit is not proof of correct data — read the produced items and check
field values before declaring a spider done (a consistently `null` field
usually means a wrong selector, verifiable with the `scrapy shell -c` form
above).
