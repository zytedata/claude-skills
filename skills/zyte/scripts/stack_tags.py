# /// script
# requires-python = ">=3.11"
# ///
"""Pick the `scrapinghub/scrapinghub-stack-scrapy` Docker tag for the
`scrapinghub.yml` `stack` key.

Run it with the Scrapy version named in the requirements file, e.g.:

    uv run stack_tags.py 2.14

Omit the version to get the newest tag overall:

    uv run stack_tags.py
"""

import json
import re
import sys
from urllib.request import urlopen

TAGS_URL = "https://hub.docker.com/v2/repositories/scrapinghub/scrapinghub-stack-scrapy/tags?page_size=100"
TAG_RE = re.compile(r"^(\d+)\.(\d+)-(\d{8})$")


def _tag_key(name: str) -> tuple[int, int, str] | None:
    """Return the `(major, minor, date)` sort key of a tag matching
    `{VERSION}-{YYYYMMDD}`, or `None` if it doesn't match."""
    match = TAG_RE.match(name)
    if not match:
        return None
    major, minor, date = match.groups()
    return int(major), int(minor), date


def sorted_tags(tag_names: list[str]) -> list[str]:
    """Return the tags matching `{VERSION}-{YYYYMMDD}`, highest Scrapy version
    first and, among equal versions, latest frozen date first."""
    keyed = [(key, name) for name in tag_names if (key := _tag_key(name)) is not None]
    keyed.sort(reverse=True)
    return [name for _, name in keyed]


def _best_match(sorted_tag_names: list[str], major_minor: str) -> str | None:
    """Return the newest of *sorted_tag_names* (as returned by `sorted_tags`)
    for *major_minor*, if any."""
    for tag in sorted_tag_names:
        if tag.split("-", 1)[0] == major_minor:
            return tag
    return None


def select_tag(tag_names: list[str], scrapy_version: str | None = None) -> str | None:
    """Return the newest tag for *scrapy_version* (e.g. `"2.14"` or `"2.14.0"`,
    only the major.minor part is matched), falling back to the newest tag
    overall when it is `None` or none match."""
    tags = sorted_tags(tag_names)
    if scrapy_version:
        major_minor = ".".join(scrapy_version.split(".")[:2])
        match = _best_match(tags, major_minor)
        if match:
            return match
    return tags[0] if tags else None


def _iter_tag_names(url: str = TAGS_URL):
    """Yield tag names, fetching pages from Docker Hub lazily as needed."""
    while url:
        with urlopen(url, timeout=10) as response:
            payload = json.load(response)
        yield from (result["name"] for result in payload["results"])
        url = payload.get("next")


def find_tag(scrapy_version: str | None = None, url: str = TAGS_URL) -> str | None:
    """Like `select_tag`, fetching tags from Docker Hub lazily and stopping
    as soon as a match for *scrapy_version* is found, instead of fetching
    and holding onto every tag upfront. Tags are listed newest-first, so the
    first match is already the newest one."""
    target = tuple(int(part) for part in scrapy_version.split(".")[:2]) if scrapy_version else None
    best = None
    for name in _iter_tag_names(url):
        key = _tag_key(name)
        if key is None:
            continue
        if target and key[:2] == target:
            return name
        if best is None or key > best[0]:
            best = (key, name)
    return best[1] if best else None


if __name__ == "__main__":
    scrapy_version = sys.argv[1] if len(sys.argv) > 1 else None
    tag = find_tag(scrapy_version)
    if tag:
        print(tag)
