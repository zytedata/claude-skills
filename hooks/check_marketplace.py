# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

OLD_REPO = "zyte-ai/claude-skills"
NEW_REPO = "zytedata/claude-skills"


def old_marketplace_name(known_marketplaces: Path) -> str | None:
    """Return the name of the marketplace added from :data:`OLD_REPO`, if any."""
    try:
        marketplaces = json.loads(known_marketplaces.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(marketplaces, dict):
        return None
    for name, entry in marketplaces.items():
        source = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict):
            continue
        location = f"{source.get('repo', '')} {source.get('url', '')}".lower()
        if OLD_REPO in location:
            return name
    return None


def warning(name: str) -> str:
    return (
        f"The Zyte plugin marketplace moved from {OLD_REPO} to {NEW_REPO}. "
        "To switch to the new location, run:\n"
        f"  claude plugin marketplace remove {name}\n"
        f"  claude plugin marketplace add {NEW_REPO}\n"
        "  claude plugin install zyte-web-data@zyte-ai"
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    name = old_marketplace_name(config_dir / "plugins" / "known_marketplaces.json")
    if name is not None:
        print(json.dumps({"systemMessage": warning(name)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
