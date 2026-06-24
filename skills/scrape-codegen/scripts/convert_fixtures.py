# /// script
# dependencies = []
# ///
"""Convert extraction spec snapshots to web-poet test fixtures.

Usage:
    uv run convert_fixtures.py SPEC_PATH PROJECT_DIR FIXTURE_CLASS_PATH

Example:
    python convert_fixtures.py .scrape/books-toscrape ./books-project project.pages.books_toscrape_com.ProductPage

Reads pages and values from SPEC_PATH, creates web-poet fixtures at:
    PROJECT_DIR/fixtures/FIXTURE_CLASS_PATH/test-N/
        inputs/HttpResponse-body.html         (if raw.html exists)
        inputs/HttpResponse-info.json         (if raw.html exists)
        inputs/BrowserResponse-body.html      (if rendered.html exists)
        inputs/BrowserResponse-info.json      (if rendered.html exists)
        output.json
        meta.json

Both variants are saved when available so the page object can declare either
HttpResponse (WebPage) or BrowserResponse (BrowserPage) as its input.
"""

import argparse
import json
import sys
from pathlib import Path


def convert_headers(http_headers: dict) -> dict:
    """Convert flat header dict to web-poet format (values as lists)."""
    result = {}
    for key, value in http_headers.items():
        if isinstance(value, list):
            result[key] = value
        else:
            result[key] = [str(value)]
    return result


def write_http_response(inputs_dir: Path, html_path: Path, meta: dict) -> None:
    html_content = html_path.read_text(errors="replace")
    (inputs_dir / "HttpResponse-body.html").write_text(html_content)

    info = {
        "url": meta.get("url", ""),
        "status": meta.get("http_status", 200),
        "headers": convert_headers(meta.get("http_headers", {})),
        "_encoding": "utf-8",
    }
    (inputs_dir / "HttpResponse-info.json").write_text(json.dumps(info, indent=2))


def write_browser_response(inputs_dir: Path, html_path: Path, meta: dict) -> None:
    html_content = html_path.read_text(errors="replace")
    (inputs_dir / "BrowserResponse-body.html").write_text(html_content)

    info = {
        "url": meta.get("url", ""),
        "status": meta.get("http_status", 200),
    }
    (inputs_dir / "BrowserResponse-info.json").write_text(json.dumps(info, indent=2))


def create_fixture(
    fixture_dir: Path,
    page_dir: Path,
    meta: dict,
    values: dict,
) -> list[str]:
    """Create a single web-poet fixture directory. Returns the list of input
    types written (e.g., ["HttpResponse", "BrowserResponse"])."""
    inputs_dir = fixture_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    written = []

    raw_html = page_dir / "raw.html"
    if raw_html.exists():
        write_http_response(inputs_dir, raw_html, meta)
        written.append("HttpResponse")

    rendered_html = page_dir / "rendered.html"
    if rendered_html.exists():
        write_browser_response(inputs_dir, rendered_html, meta)
        written.append("BrowserResponse")

    (fixture_dir / "output.json").write_text(json.dumps(values, indent=2))

    captured_at = meta.get("captured_at", "2026-01-01T00:00:00+00:00")
    fixture_meta = {"frozen_time": captured_at}
    (fixture_dir / "meta.json").write_text(json.dumps(fixture_meta, indent=2))

    return written


def main():
    parser = argparse.ArgumentParser(
        description="Convert extraction spec snapshots to web-poet fixtures"
    )
    parser.add_argument("spec_path", help="Path to the spec folder")
    parser.add_argument("project_dir", help="Path to the Scrapy project")
    parser.add_argument(
        "fixture_class_path",
        help="Fully qualified class path (e.g., project.pages.books_toscrape_com.ProductPage)",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec_path)
    project_dir = Path(args.project_dir)
    fixture_class_path = args.fixture_class_path

    pages_dir = spec_path / "pages"
    values_dir = spec_path / "values"

    page_dirs = sorted(
        [d for d in pages_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    if not page_dirs:
        print("Error: no pages found", file=sys.stderr)
        sys.exit(1)

    fixture_base = project_dir / "fixtures" / fixture_class_path
    created = []

    for i, page_dir in enumerate(page_dirs, 1):
        page_id = page_dir.name  # e.g., "detail-1", "start-1", "list-1"

        if not (page_dir / "raw.html").exists() and not (page_dir / "rendered.html").exists():
            print(f"Warning: no HTML found for {page_id}, skipping", file=sys.stderr)
            continue

        meta_path = page_dir / "meta.json"
        if not meta_path.exists():
            print(f"Warning: no meta.json for {page_id}, skipping", file=sys.stderr)
            continue
        meta = json.loads(meta_path.read_text())

        values_path = values_dir / f"{page_id}.json"
        if not values_path.exists():
            print(f"Warning: no values for {page_id}, skipping", file=sys.stderr)
            continue

        values_data = json.loads(values_path.read_text())
        # The values file has {"url": "...", "values": {...}}
        values = values_data.get("values", values_data)

        fixture_dir = fixture_base / f"test-{i}"
        written = create_fixture(fixture_dir, page_dir, meta, values)
        created.append({
            "page_id": page_id,
            "fixture": str(fixture_dir),
            "inputs": written,
        })

    result = {
        "fixture_class_path": fixture_class_path,
        "fixture_base": str(fixture_base),
        "fixtures_created": len(created),
        "fixtures": created,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
