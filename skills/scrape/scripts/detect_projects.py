# /// script
# dependencies = []
# ///
"""Detect existing Scrapy projects below the current working directory.

Usage:
    uv run detect_projects.py

Scans the current directory and its immediate child directories for Scrapy
project candidates. A candidate is simply a directory containing `scrapy.cfg`;
package contents are inspected only after the workflow selects a project.
Generated and cache directories (`.venv`, `.scrape`, `__pycache__`, VCS dirs,
...) are ignored so Scrapy templates inside virtualenvs are never mistaken for
user projects.

Prints a JSON array of candidates:
    [
      {
        "project_dir": "."
      }
    ]
"""

import json
from pathlib import Path

IGNORED = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".scrape",
    ".venv",
    "__pycache__",
}


def find_candidates(cwd: Path) -> list[dict]:
    roots = [cwd]
    roots.extend(
        sorted(
            (
                path
                for path in cwd.iterdir()
                if path.is_dir() and path.name not in IGNORED
            ),
            key=lambda path: path.name,
        )
    )

    candidates = []
    for root in roots:
        if root.name in IGNORED:
            continue
        if (root / "scrapy.cfg").is_file():
            candidates.append(
                {
                    "project_dir": str(
                        root.relative_to(cwd) if root != cwd else Path(".")
                    )
                }
            )
    return candidates


if __name__ == "__main__":
    print(json.dumps(find_candidates(Path.cwd()), indent=2))
