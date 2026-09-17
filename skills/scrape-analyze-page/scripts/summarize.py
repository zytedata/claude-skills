# /// script
# dependencies = ["pyyaml"]
# ///
"""Print the extraction summary for a saved analysis file (JSON or YAML).

Every saved field is reported with its name, type and value; long strings and
long lists or dicts are truncated to their first 100 characters or entries.

Usage:
    uv run --python 3.14 summarize.py output.json
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


MAX_CHARS = 100


def load(path: Path):
    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def render(value, budget: int = MAX_CHARS) -> str:
    """Return *value* as text, truncated to about *budget* characters."""
    if isinstance(value, str):
        if len(value) > MAX_CHARS:
            head = json.dumps(value[:MAX_CHARS], ensure_ascii=False)
            return f"{head} ({len(value)} chars)"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, dict)):
        entries = (
            [render(entry, budget // 2) for entry in value]
            if isinstance(value, list)
            else [
                f"{json.dumps(key, ensure_ascii=False)}: {render(entry, budget // 2)}"
                for key, entry in value.items()
            ]
        )
        shown, used = [], 0
        for entry in entries:
            if shown and used + len(entry) > budget:
                break
            shown.append(entry)
            used += len(entry) + 2
        body = ", ".join(shown)
        open_, close = ("[", "]") if isinstance(value, list) else ("{", "}")
        if len(shown) < len(entries):
            return f"{open_}{body}, ...{close} ({len(entries)} items)"
        return f"{open_}{body}{close}"
    return json.dumps(value, ensure_ascii=False)


def fields(data: dict):
    """Yield a (name, type, value) triple per saved field."""
    for name, entry in data.items():
        if isinstance(entry, dict) and "value" in entry:
            value = entry["value"]
            yield name, entry.get("type") or type(value).__name__, value
        else:
            yield name, type(entry).__name__, entry


def summarize(data, path: Path) -> str:
    values = data.get("values") if isinstance(data, dict) else data
    if isinstance(values, list):
        page_id = data.get("page_id", path.stem) if isinstance(data, dict) else path.stem
        url = data.get("url") if isinstance(data, dict) else None
        header = f"{page_id} ({url})" if url else page_id
        lines = [f"{header}, saved to {path}:", f"  {len(values)} items extracted"]
        if values:
            sample = ", ".join(
                f"{name}={render(value, MAX_CHARS // 2)}"
                for name, _, value in fields(values[0])
            )
            lines.append(f"  sample: {sample}")
        return "\n".join(lines)

    if isinstance(data, dict) and isinstance(data.get("fields"), dict):
        data = data["fields"]
    lines = ["These fields were discovered:"]
    lines += [
        f"  {name} ({type_name}): {render(value)}"
        for name, type_name, value in fields(data)
    ]
    lines.append(f"The full report is saved to {path}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_file", help="Analysis file written by the skill")
    args = parser.parse_args()

    path = Path(args.output_file)
    data = load(path)
    if not isinstance(data, (dict, list)):
        sys.exit(f"{path}: not a mapping or a list of items")
    print(summarize(data, path))


if __name__ == "__main__":
    main()
