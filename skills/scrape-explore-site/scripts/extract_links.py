# /// script
# dependencies = ["parsel", "html-text"]
# ///
"""Extract links from an HTML file with structural context.

Usage:
    uv run extract_links.py PAGE.html [--css SELECTOR] [--base-url URL] [--link-limit LIMIT]
    uv run extract_links.py PAGE.html --group          # group by path
    uv run extract_links.py *.html --group             # multiple files, adds "file" key

    # Multiple files with per-file base URLs from meta.json:
    uv run extract_links.py pages/list-1/rendered.html pages/list-2/rendered.html --group --base-url-from-meta

Outputs JSON lines to stdout. With --group, outputs one numbered object per path group:
    0: {"path": "article.product_pod > h3 > a", "count": 20, "links": [...]}
    1: {"path": "aside.sidebar > ul.nav > li > a", "count": 12, "links": [...]}

Without --group, outputs one object per link:
    {"href": "/product/123", "text": "Widget X", "path": "div.products > div.card > h3 > a"}

--link-limit can be used to limit the number of links per path group.

Timing info is printed to stderr.
"""

import argparse
import json
import os
import sys
import time
from collections import OrderedDict
from urllib.parse import urljoin

import html_text
from parsel import Selector


GENERIC_TAGS = {"div", "span", "center", "table", "tr", "td", "tbody", "thead"}
MAX_CLASSES = 2


def _element_part(tag, class_attr):
    """Return CSS path segment for an element: tag.class1.class2 or just tag."""
    classes = class_attr.split()[:MAX_CLASSES] if class_attr else []
    if classes:
        return tag + "." + ".".join(classes)
    return tag


def css_path_parts(el):
    """Build a list of CSS path parts for an element.

    Keeps only structurally meaningful ancestors: those with a class attribute
    or a semantic tag. Skips generic wrappers (div, span, table, etc.).
    """
    parts = []
    for ancestor in el.xpath("ancestor::*"):
        tag = ancestor.xpath("local-name()").get()
        cls = ancestor.attrib.get("class", "").strip()
        if cls:
            parts.append(_element_part(tag, cls))
        elif tag not in GENERIC_TAGS:
            parts.append(tag)
    # Add the element itself
    tag = el.xpath("local-name()").get()
    cls = el.attrib.get("class", "").strip()
    if cls:
        parts.append(_element_part(tag, cls))
    else:
        parts.append(tag)
    return parts


def format_path(parts, max_parts=None):
    if max_parts and len(parts) > max_parts + 1:
        parts = parts[-(max_parts + 1):]
    return " > ".join(parts)


def extract_links(html, css_selector="a", base_url=None):
    sel = Selector(text=html)
    seen_hrefs = set()
    for a in sel.css(css_selector):
        href = a.attrib.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        if base_url:
            href = urljoin(base_url, href)
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        text = html_text.selector_to_text(a)
        parts = css_path_parts(a)
        yield {"href": href, "text": text, "path_parts": parts}


def group_by_path(links, max_parts=None, max_links=None):
    groups = OrderedDict()
    for link in links:
        path = format_path(link["path_parts"], max_parts=max_parts)
        if path not in groups:
            groups[path] = []
        groups[path].append({"href": link["href"], "text": link["text"]})

    for path, group_links in groups.items():
        total = len(group_links)
        if max_links is not None:
            group_links = group_links[:max_links]
        yield {
            "path": path,
            "count": total,
            "links": group_links,
        }


def read_html(path):
    """Read an HTML file, handling gzip-compressed responses."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip

        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def file_label(html_file):
    """Derive a label from the file path: use parent directory name if the
    file is inside a page directory (e.g. 'list-1' from 'list-1/rendered.html'),
    otherwise use the filename."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(html_file)))
    if parent and parent != ".":
        return parent
    return os.path.basename(html_file)


def base_url_from_meta(html_file):
    """Read base URL from meta.json in the same directory as the HTML file."""
    meta_path = os.path.join(os.path.dirname(html_file), "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        return meta.get("final_url") or meta.get("url")
    return None


def process_file(html_file, args, prefix=None, base_url_override=None, link_limit=None):
    """Extract and print links from a single HTML file.

    Returns list of group dicts when --group is used.
    """
    t0 = time.monotonic()
    html = read_html(html_file)
    base_url = base_url_override or args.base_url
    links = extract_links(html, args.css, base_url)
    file_groups = []

    if args.group:
        for group in group_by_path(links, max_parts=args.depth, max_links=link_limit):
            if prefix:
                group["file"] = prefix
            file_groups.append(group)
    else:
        for link in links:
            out = {
                "href": link["href"],
                "text": link["text"],
                "path": format_path(link["path_parts"], max_parts=args.depth),
            }
            if prefix:
                out["file"] = prefix
            print(json.dumps(out, ensure_ascii=False))

    elapsed = time.monotonic() - t0
    label = prefix or os.path.basename(html_file)
    print(f"[extract_links] {label}: {elapsed:.2f}s", file=sys.stderr)
    return file_groups


def main():
    t_start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_files", nargs="+", help="Path(s) to HTML file(s)")
    parser.add_argument("--css", default="a", help="CSS selector (default: a)")
    parser.add_argument("--base-url", help="Base URL for resolving relative hrefs")
    parser.add_argument(
        "--base-url-from-meta",
        action="store_true",
        help="Read base URL from meta.json in each file's directory",
    )
    parser.add_argument(
        "--group", action="store_true", help="Group links by path"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=4,
        help="Max path depth (default: 4)",
    )
    parser.add_argument("--link-limit", type=int, default=100, help="")
    args = parser.parse_args()

    multi = len(args.html_files) > 1
    all_groups = []
    for html_file in args.html_files:
        label = file_label(html_file)
        prefix = label if multi else None
        per_file_url = None
        if args.base_url_from_meta:
            per_file_url = base_url_from_meta(html_file)
        groups = process_file(html_file, args, prefix, base_url_override=per_file_url, link_limit=args.link_limit)
        all_groups.extend(groups)

    if args.group:
        for i, group in enumerate(all_groups):
            print(f"{i}: {json.dumps(group, ensure_ascii=False)}")

    elapsed = time.monotonic() - t_start
    print(f"[extract_links] total: {elapsed:.2f}s ({len(args.html_files)} files)", file=sys.stderr)


if __name__ == "__main__":
    main()
