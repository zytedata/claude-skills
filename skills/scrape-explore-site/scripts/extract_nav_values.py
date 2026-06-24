"""Extract navigation values from links.json files.

Usage: uv run extract_nav_values.py <nav_dir>

Reads pages/ subdirectories in nav_dir. For each page that has both
links.json and meta.json, produces a navigation values file in values/.

Maps links.json format → navigation schema:
  items         → items (array of {url, text})
  nextPage[0]   → next_page (string URL, or null)
  subCategories → subcategories (array of {url, text})
"""

import json
import sys
from pathlib import Path
from typing import Optional


def extract_nav_values(page_dir: Path) -> Optional[dict]:
    links_path = page_dir / "links.json"
    meta_path = page_dir / "meta.json"
    if not links_path.exists() or not meta_path.exists():
        return None

    links = json.loads(links_path.read_text())
    meta = json.loads(meta_path.read_text())

    next_pages = links.get("nextPage", [])
    next_page = next_pages[0]["url"] if next_pages else None

    return {
        "url": meta["url"],
        "values": {
            "items": links.get("items", []),
            "next_page": next_page,
            "subcategories": links.get("subCategories", []),
        },
    }


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <nav_dir>", file=sys.stderr)
        sys.exit(1)

    nav_dir = Path(sys.argv[1])
    pages_dir = nav_dir / "pages"
    values_dir = nav_dir / "values"

    if not pages_dir.exists():
        print(f"No pages directory: {pages_dir}", file=sys.stderr)
        sys.exit(1)

    values_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for page_dir in sorted(pages_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        result = extract_nav_values(page_dir)
        if result is None:
            continue
        out_path = values_dir / f"{page_dir.name}.json"
        out_path.write_text(json.dumps(result, indent=2) + "\n")
        count += 1

    print(f"Wrote {count} navigation values to {values_dir}/")


if __name__ == "__main__":
    main()
