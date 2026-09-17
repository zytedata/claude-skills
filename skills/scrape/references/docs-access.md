This file is 26 lines long; read all of them.

# Accessing Library Documentation

When you need information beyond the built-in reference files, fetch docs
online with `curl`. Markdown pages need no extraction, so reading one is a
3-second command; delegating it to a subagent costs a minute or more.

## Known llms.txt-compatible sites

The following documentation is LLM-friendly: `llms.txt` provides a table of
contents, and all pages are available in Markdown, just replace `.html` with `.md` in the URL.

https://docs.zyte.com: Zyte (Zyte API, Scrapy Cloud)
https://docs.scrapy.org: Scrapy
https://LIBRARY.readthedocs.io: python-scrapinghub, python-zyte-api, scrapy-poet, scrapy-zyte-api, shub, web-poet.

For example:

```
https://docs.scrapy.org/llms.txt
https://web-poet.readthedocs.io/en/stable/page-objects/fields.md
```

For these sites, fetch the Markdown URL directly instead of using web search,
which returns rendered HTML and stale summaries.
