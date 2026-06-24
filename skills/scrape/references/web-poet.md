# web-poet Reference

Concise reference for writing web-poet page objects. For full docs see
https://web-poet.readthedocs.io/

## Core concepts

**Page objects** separate extraction logic from crawling. A page object receives
inputs (HTTP response, browser HTML, etc.) and returns a structured item.

**Items** are data containers supported by the `itemadapter` library: `dict`,
`@dataclass` classes, or `@attrs.define` classes.

**Fields** are methods decorated with `@field` that extract one piece of data each.

## Dependency injection

web-poet uses `andi` for annotation-based DI. The framework reads `__init__` type
annotations to determine what to inject. `WebPage` is an attrs class — its subclasses
inherit attrs behavior and don't need `@attrs.define` unless adding new dependencies.
`ItemPage` is NOT attrs — subclasses that declare dependencies must use `@attrs.define`.

```python
import attrs
from web_poet import WebPage, HttpClient, Returns, field

@attrs.define  # needed because we're adding HttpClient
class MyPage(WebPage, Returns[dict]):
    http: HttpClient

    @field
    async def data(self) -> dict | None:
        resp = await self.http.get("https://api.example.com/data")
        return resp.json()
```

Common injectable dependencies:
- `HttpResponse` — raw HTTP response (provided by `WebPage` automatically)
- `BrowserResponse` — JavaScript-rendered HTML (requires `@attrs.define`)
- `HttpClient` — make additional HTTP requests (requires `@attrs.define`)
- `PageParams` — receive parameters from the spider

Limitation: a class cannot have two parameters of the same type.

## Base classes

| Class | Input provided | Use when |
|-------|---------------|----------|
| `WebPage` | `HttpResponse` | Raw HTTP response (most common) |
| `BrowserPage` | `BrowserResponse` | JavaScript-rendered pages |
| `ItemPage` | None built-in | Declare your own inputs with `@attrs.define` |

`WebPage` and `BrowserPage` both provide `self.css()`, `self.xpath()`, `self.url`,
`self.urljoin()`. They are attrs classes — subclasses inherit attrs behavior.

## Page object structure

```python
from web_poet import WebPage, Returns, field

class ProductPage(WebPage, Returns[dict]):
    @field
    def name(self) -> str | None:
        return self.css("h1::text").get()

    @field
    def price(self) -> str | None:
        return self.css("span.price::text").get()
```

### Item type declaration

```python
# Generic parameter (first declaration)
class MyPage(WebPage[MyItem]): ...

# Returns annotation (equivalent, also works for overrides)
class MyPage(WebPage, Returns[MyItem]): ...

# dict when there is no item class
class MyPage(WebPage, Returns[dict]): ...
```

## Fields

```python
@field
def name(self) -> str | None:
    return self.css("h1::text").get()

@field
async def reviews(self) -> list[dict] | None:
    # async fields can use HttpClient
    ...
```

- Each `@field` method = one key in the output item
- Return `None` when data is not found
- Only use `@field` for output fields; use `@cached_property` or `@cached_method`
  for internal helpers
- Fields can be sync or async

### url field

Many items have a `url` field. Inside `@field def url(self)`, `self.url` refers to
the field itself (infinite recursion). Use `str(self.response.url)` instead:

```python
@field
def url(self) -> str | None:
    return str(self.response.url)   # NOT self.url
```

### Caching

```python
from web_poet import cached_method

class MyPage(WebPage, Returns[dict]):
    @cached_method
    def _parsed_data(self):
        ...
```

Use `cached_method` for methods (especially async). Essential with `HttpClient` —
fetch a response once, reuse it across multiple fields:

```python
@cached_method
async def _api_response(self):
    return await self.http.get("https://api.example.com/product")

@field
async def name(self) -> str | None:
    data = (await self._api_response()).json()
    return data.get("name")

@field
async def price(self) -> str | None:
    data = (await self._api_response()).json()
    return data.get("price")
```

`functools.cached_property` is fine for sync property-like helpers.
Avoid `functools.lru_cache` (memory leaks).

## Selector API (Parsel)

Available on `WebPage` via `self.css()` and `self.xpath()`.
Also available on `BrowserResponse` objects (e.g. `self.browser.css()`).

### CSS selectors

```python
self.css("div.product")                  # SelectorList of elements
self.css("h1::text").get()               # first text match, or None
self.css("li::text").getall()            # all text matches as list[str]
self.css("a::attr(href)").get()          # attribute value
self.css("div.product").css("h2::text")  # chaining
```

### XPath

```python
self.xpath("//h1/text()").get()
self.xpath("//a/@href").getall()
```

### Iteration

```python
for product in self.css("div.product"):
    name = product.css("h2::text").get()
    price = product.css(".price::text").get()
```

## Response data

- `self.response.body` — raw bytes
- `self.response.text` — decoded string
- `self.url` — shortcut for `str(self.response.url)`
- `self.urljoin("/path")` — resolve relative URL to absolute

## HttpClient (additional requests)

For pages that need extra HTTP requests (AJAX, APIs). See the DI section for
how to declare it.

- Methods: `get()`, `post()`, `request()`, `execute()`, `batch_execute()`
- All methods are async — fields using HttpClient must be `async def`
- In tests, HttpClient responses are saved in fixtures and replayed

## Structured data extraction

### extruct

Use `extruct.extract()` to get all formats in one call. Pass
`self.selector.root` (lxml tree) to avoid re-parsing the HTML:

```python
import extruct
from functools import cached_property

class MyPage(WebPage, Returns[dict]):
    @cached_property
    def _metadata(self) -> dict:
        return extruct.extract(
            self.selector.root,
            base_url=self.url,
            syntaxes=["json-ld", "opengraph", "microdata"],
        )

    @cached_property
    def _jsonld(self) -> dict:
        for entry in self._metadata.get("json-ld", []):
            if entry.get("@type") == "Product":
                return entry
        return {}

    @field
    def name(self) -> str | None:
        return self._jsonld.get("name")
```

Supported syntaxes: `json-ld`, `opengraph`, `microdata`, `microformat`.

### JMESPath for JSON queries

```python
import jmespath
jmespath.search("offers.price", data)
```

### Price parsing

```python
from price_parser import Price
price = Price.fromstring("$29.99")
price.amount_float   # 29.99
price.currency       # '$'
```

## Input validation

Page objects can define `validate_input` to check the response before extraction:

```python
from web_poet.exceptions import Retry, UseFallback

class ProductPage(WebPage, Returns[dict]):
    def validate_input(self):
        if self.css(".error-503"):
            raise Retry()                      # temporary issue, try again
        if not self.css(".product"):
            raise UseFallback()                # can't handle this page
        if self.css(".product-list"):
            return dict(is_valid=False)        # wrong page type, return marker
```

- Return `None` — input is valid, proceed normally
- `raise Retry` — temporary issue, framework retries the request
- `raise UseFallback` — this PO can't handle the input, try another
- Return an item — override output (e.g., mark as invalid)

`validate_input` runs before any `@field` methods. Only sync fields work inside it.

## Testing

web-poet fixtures are directories with serialized inputs and expected outputs:

```
fixtures/
  my_project.pages.example_com.ProductPage/
    test-1/
      inputs/
        HttpResponse-body.html
        HttpResponse-info.json
      output.json
      meta.json
```

- Directory name = fully qualified page object class path
- `output.json` = expected result of `to_item()`
- `meta.json` = optional, can include `frozen_time` for time-dependent fields

```bash
uv run pytest FIXTURE_PATH                             # test against a specific fixture
uv run python -m web_poet.testing rerun FIXTURE_PATH   # re-run and print actual output
```
