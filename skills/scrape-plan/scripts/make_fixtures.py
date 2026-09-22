# /// script
# dependencies = ["web-poet>=0.24.0"]
# ///
"""Generate web-poet test fixtures from a scrape extraction spec.

This is the offline counterpart to `scrapy savefixture`: instead of re-fetching
each page live, it reuses the HTML already captured under a spec data-type folder
and the expected values already verified during spec building. That keeps the
fixture input identical to the HTML the page object was written against (so a
passing fixture validates the page object, not "the live site hasn't changed"),
and costs no extra requests.

Fixtures are written with web-poet's own serializer (``Fixture.save``); this
script never hand-writes the ``inputs/`` files, whose on-disk layout is
web-poet's to define and has changed across versions.

Usage:
    uv run --python 3.14 make_fixtures.py SPEC_TYPE_DIR PROJECT_DIR CLASS_PATH [--variant auto|http|browser]

Where:
    SPEC_TYPE_DIR  a data-type folder of a spec, e.g. .scrape/books/product
                   (contains spec.json, pages/<id>/{raw,rendered}.html + meta.json,
                    and values/<id>.json)
    PROJECT_DIR    the Scrapy project root; fixtures land under PROJECT_DIR/fixtures/
    CLASS_PATH     the page object's import path, e.g.
                   books_project.pages.books_toscrape_com.ProductPage
    --variant      which captured HTML to serialize as the page object input:
                     http     raw.html as an HttpResponse    (web_poet.WebPage)
                     browser  rendered.html as a BrowserResponse (web_poet.BrowserPage)
                     auto     follow spec.json's html_variant (default), falling
                              back to whichever HTML is present

One fixture directory (named after the page id) is created per page that has
both the required HTML and expected values.
"""

import argparse
import json
import sys
from pathlib import Path

from web_poet import BrowserHtml, BrowserResponse, HttpResponse, HttpResponseHeaders
from web_poet.testing import Fixture


def _http_input(page_dir: Path, meta: dict) -> HttpResponse:
    body = (page_dir / "raw.html").read_bytes()
    return HttpResponse(
        url=meta.get("final_url") or meta["url"],
        body=body,
        status=meta.get("http_status", 200),
        headers=HttpResponseHeaders(meta.get("http_headers", {})),
    )


def _browser_input(page_dir: Path, meta: dict) -> BrowserResponse:
    html = (page_dir / "rendered.html").read_text(encoding="utf-8", errors="replace")
    return BrowserResponse(
        url=meta.get("final_url") or meta["url"],
        html=BrowserHtml(html),
        status=meta.get("http_status", 200),
    )


def _resolve_variant(spec_variant: str | None, requested: str) -> str:
    """Decide the input kind. ``auto`` follows the spec's html_variant."""
    if requested != "auto":
        return requested
    return "browser" if spec_variant == "rendered" else "http"


def _make_input(page_dir: Path, meta: dict, variant: str):
    """Return the page object input for this page, or None if its HTML is absent.

    Falls back to the other variant when the preferred one is missing, so a page
    captured with only rendered.html still yields a fixture.
    """
    have_http = (page_dir / "raw.html").exists()
    have_browser = (page_dir / "rendered.html").exists()
    if variant == "browser":
        if have_browser:
            return _browser_input(page_dir, meta)
        if have_http:
            return _http_input(page_dir, meta)
    else:
        if have_http:
            return _http_input(page_dir, meta)
        if have_browser:
            return _browser_input(page_dir, meta)
    return None


def build_fixtures(
    spec_type_dir: Path,
    project_dir: Path,
    class_path: str,
    variant: str = "auto",
) -> dict:
    pages_dir = spec_type_dir / "pages"
    values_dir = spec_type_dir / "values"
    if not pages_dir.is_dir():
        raise SystemExit(f"No pages directory at {pages_dir}")

    spec_variant = None
    spec_file = spec_type_dir / "spec.json"
    if spec_file.exists():
        spec_variant = json.loads(spec_file.read_text(encoding="utf-8")).get("html_variant")
    variant = _resolve_variant(spec_variant, variant)

    base_dir = project_dir / "fixtures" / class_path
    created, skipped = [], []

    for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
        page_id = page_dir.name

        meta_file = page_dir / "meta.json"
        values_file = values_dir / f"{page_id}.json"
        if not meta_file.exists():
            skipped.append({"page": page_id, "reason": "no meta.json"})
            continue
        if not values_file.exists():
            skipped.append({"page": page_id, "reason": "no expected values"})
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        page_input = _make_input(page_dir, meta, variant)
        if page_input is None:
            skipped.append({"page": page_id, "reason": "no HTML captured"})
            continue

        values_data = json.loads(values_file.read_text(encoding="utf-8"))
        item = values_data.get("values", values_data)

        fixture_meta = None
        captured_at = meta.get("captured_at")
        if captured_at:
            fixture_meta = {"frozen_time": captured_at}

        Fixture.save(
            base_dir,
            inputs=[page_input],
            item=item,
            meta=fixture_meta,
            fixture_name=page_id,
        )
        created.append(
            {
                "page": page_id,
                "fixture": str(base_dir / page_id),
                "input": type(page_input).__name__,
            }
        )

    return {
        "class_path": class_path,
        "variant": variant,
        "fixtures_created": len(created),
        "fixtures": created,
        "skipped": skipped,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Generate web-poet fixtures from a scrape extraction spec"
    )
    parser.add_argument("spec_type_dir", type=Path, help="Spec data-type folder")
    parser.add_argument("project_dir", type=Path, help="Scrapy project root")
    parser.add_argument("class_path", help="Page object import path")
    parser.add_argument(
        "--variant",
        choices=["auto", "http", "browser"],
        default="auto",
        help="Which captured HTML to use as the page object input (default: auto)",
    )
    args = parser.parse_args()

    result = build_fixtures(
        args.spec_type_dir, args.project_dir, args.class_path, args.variant
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if result["fixtures_created"] == 0:
        raise SystemExit("No fixtures were created")


if __name__ == "__main__":
    main()
