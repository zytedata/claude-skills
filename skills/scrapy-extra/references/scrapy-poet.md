This file is 129 lines long; read all of them.

# scrapy-poet Reference

Concise reference for using web-poet page objects in Scrapy spiders. For full
docs see https://scrapy-poet.readthedocs.io/llms.txt

## Setup

```python
# settings.py
ADDONS = {
    "scrapy_poet.Addon": 300,
}
SCRAPY_POET_DISCOVER = ["my_project.pages"]
```

## Using page objects in spiders

The recommended way is to annotate a callback parameter with the **item class**
you want. scrapy-poet finds the page object registered for that URL and item
type (via `@handle_urls`) and injects the already-built item — you never call
`to_item()` yourself:

```python
import scrapy
from scrapy_poet import DummyResponse, callback_for

from my_project.items import Navigation, Product


class ExampleSpider(scrapy.Spider):
    name = "example"
    start_urls = ["https://example.com"]

    parse_product = callback_for(Product)

    async def parse(self, response: DummyResponse, nav: Navigation):
        for link in nav.items or []:
            yield scrapy.Request(link["url"], callback=self.parse_product)
```

When a callback would do nothing but yield the injected item, use
`callback_for(ItemClass)` to generate it instead of writing it out.
`callback_for` accepts an item class (as above) or a page object class, and the
generated callback handles both sync and async `to_item()`.

Annotate a parameter with the **page object class** instead only when you
actually need the page object itself (e.g. to call another method on it). Then
scrapy-poet injects the page object and you call `await po.to_item()` yourself —
so that callback must be `async def`.

### List-page extraction (item page object returns a list)

Sometimes the item page object extracts every item straight from the listing
page — it returns an item holding a list of items, so there are no detail pages
to request. Inject both the navigation item and the list item into the **same**
callback, yield the listed items directly, and follow navigation links:

```python
import scrapy
from scrapy_poet import DummyResponse

from my_project.items import Navigation, ProductList


class ExampleSpider(scrapy.Spider):
    name = "example"
    start_urls = ["https://example.com"]

    async def parse(
        self, response: DummyResponse, nav: Navigation, product_list: ProductList
    ):
        for item in product_list.items or []:
            yield item

        if nav.next_page:
            yield scrapy.Request(nav.next_page, callback=self.parse)
        for sub in nav.subcategories or []:
            yield scrapy.Request(sub["url"], callback=self.parse)
```

No `parse_item` callback and no `callback_for` — items come straight off the
list page. Pagination and subcategory links recurse back into `parse`.

### DummyResponse

When a callback only uses the injected page object and doesn't need the Scrapy
`response`, annotate the parameter as `response: DummyResponse`. This tells
scrapy-poet that no download is needed for the response object — the page object's
dependencies are provided separately (e.g., via Zyte API provider).

## handle_urls

`@handle_urls` registers a page object for a URL pattern. This serves two purposes:
- **Documentation** — declares which domain/path a page object is designed for
- **Generic spiders** — enables spiders that request an item class (e.g., `ProductItem`),
  and the framework automatically picks the right page object for the current URL

```python
from web_poet import handle_urls, WebPage, Returns

@handle_urls("example.com")
class ProductPage(WebPage, Returns[ProductItem]): ...
```

- `"example.com"` — matches domain and subdomains
- `"example.com/products/"` — matches specific path prefix

Without `@handle_urls`, page objects can still be injected directly by type
annotation in a callback; it's only required for the generic/multi-site case
above. Modules containing `@handle_urls` decorators must be listed in
`SCRAPY_POET_DISCOVER` for scrapy-poet to find them.

## Testing fixtures

Generate web-poet test fixtures with the `savefixture` command rather than
writing the `inputs/` files by hand:

```bash
cd PROJECT_DIR
uv run scrapy savefixture my_project.pages.example_com.ProductPage 'https://example.com/product/1'
```

It makes a live request, runs the page object's `to_item()`, and writes a fixture
under `fixtures/` (the `SCRAPY_POET_TESTS_DIR` setting, default `fixtures`). The
page object must be importable (a normal import path — it does not have to be in
`SCRAPY_POET_DISCOVER`). See `web-poet.md` → Testing for the fixture layout and
how to set the expected values in each `output.json`.
