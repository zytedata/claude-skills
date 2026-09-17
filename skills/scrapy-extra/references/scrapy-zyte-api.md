This file is 88 lines long; read all of them.

# Zyte API Reference (scrapy-zyte-api)

Concise reference for using Zyte API with Scrapy. For full docs see
https://scrapy-zyte-api.readthedocs.io/llms.txt

## What it does

Zyte API provides anti-ban protection and browser rendering for web scraping.
`scrapy-zyte-api` integrates it into Scrapy as a download handler.

## Setup

The addon configures middlewares, download handlers, and the provider for
scrapy-poet. It enables transparent mode by default, but this can be overridden:

```python
# settings.py
ADDONS = {
    "scrapy_poet.Addon": 300,
    "scrapy_zyte_api.Addon": 500,
}

# Disable transparent mode globally — enable per-spider when needed
ZYTE_API_TRANSPARENT_MODE = False
```

API key can be set via `ZYTE_API_KEY` setting or `ZYTE_API_KEY` environment variable.
No API key is needed if transparent mode is off and no requests use Zyte API.

## Transparent mode

When enabled, all requests are automatically routed through Zyte API. Page objects
don't need to change — the framework handles routing.

Enable per-spider:
```python
class MySpider(scrapy.Spider):
    custom_settings = {"ZYTE_API_TRANSPARENT_MODE": True}
```

A page object using `BrowserResponse` will automatically get browser-rendered
content via Zyte API.

If a page object needs rendered HTML, prefer declaring it as the page
object's input — `BrowserResponse` (subclass `BrowserPage`) — over requesting
`browserHtml` through automap params, `custom_settings`, or request meta.
Global or per-spider `browserHtml` automap params render every affected request,
including pages where raw HTML is sufficient. Per-request `browserHtml` avoids
that global cost, but still hides the rendering requirement from the page
object's declared dependencies.

To bypass Zyte API for a specific request:
```python
yield scrapy.Request(url, meta={"zyte_api_automap": False})
```

## Automap

When transparent mode is on (or `zyte_api_automap=True` in request meta), the
plugin automatically determines which Zyte API parameters to use. Requesting
`browserHtml` or `screenshot` switches from HTTP to browser mode automatically.

Override automap params per-request (for spider-level needs like geolocation —
not for enabling `browserHtml` for page-object extraction; see above):
```python
yield scrapy.Request(url, meta={"zyte_api_automap": {"geolocation": "US"}})
```

Prefer setting these per-spider via `custom_settings`, not in settings.py — different
spiders may need different Zyte API configurations:

```python
class MySpider(scrapy.Spider):
    custom_settings = {
        "ZYTE_API_TRANSPARENT_MODE": True,
        "ZYTE_API_AUTOMAP_PARAMS": {"geolocation": "US"},
    }
```

For scrapy-poet page objects, prefer using dependency annotations instead of
global settings (e.g., `Annotated[Geolocation, "US"]` on the page object).

## Debugging

`ZYTE_API_LOG_REQUESTS = True` logs the JSON payload sent to Zyte API for each
request. Useful for diagnosing issues with automap or transparent mode.
