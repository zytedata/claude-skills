# /// script
# dependencies = []
# ///
"""Apply link classification to extracted groups and write links.json files.

Usage:
    uv run apply_classification.py groups.json --classify "items=0,3 subCategories=1 nextPage=2" --pages-dir pages/

Reads the numbered groups output from extract_links.py (saved to a file),
applies the classification mapping, and writes links.json into each source
page's directory.

The groups file should contain the raw output from extract_links.py --group,
with one "N: {json}" line per group.
"""

import argparse
import json
import os
import sys
from collections import OrderedDict


def parse_groups(groups_file):
    """Parse the numbered groups output from extract_links.py --group."""
    groups = []
    with open(groups_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Format: "N: {json}"
            colon_pos = line.index(":")
            group = json.loads(line[colon_pos + 1 :].strip())
            groups.append(group)
    return groups


def parse_classify(classify_str):
    """Parse classify string like 'items=0,3 subCategories=1 nextPage=2'.

    Returns dict mapping group index -> type name.
    """
    index_to_type = {}
    for part in classify_str.split():
        if "=" not in part:
            continue
        type_name, indices_str = part.split("=", 1)
        for idx_str in indices_str.split(","):
            idx_str = idx_str.strip()
            if idx_str:
                index_to_type[int(idx_str)] = type_name
    return index_to_type


def write_classified(groups, index_to_type, pages_dir):
    """Write links.json into each source page's directory."""
    file_classified = OrderedDict()
    for i, group in enumerate(groups):
        type_name = index_to_type.get(i)
        if not type_name or type_name == "skip":
            continue
        file_key = group.get("file", "default")
        if file_key not in file_classified:
            file_classified[file_key] = {}
        if type_name not in file_classified[file_key]:
            file_classified[file_key][type_name] = []
        for link in group["links"]:
            file_classified[file_key][type_name].append(
                {"url": link["href"], "text": link["text"]}
            )

    for file_key, classified in file_classified.items():
        classified = {k: v for k, v in classified.items() if v}
        if file_key == "default":
            page_dir = pages_dir
        else:
            page_dir = os.path.join(pages_dir, file_key)
        if not os.path.isdir(page_dir):
            print(
                f"[classify] WARNING: directory '{page_dir}' not found, skipping",
                file=sys.stderr,
            )
            continue
        out_path = os.path.join(page_dir, "links.json")
        with open(out_path, "w") as f:
            json.dump(classified, f, indent=2, ensure_ascii=False)
        total = sum(len(v) for v in classified.values())
        print(f"[classify] wrote {out_path} ({total} links)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups_file", help="Path to saved extract_links.py --group output")
    parser.add_argument(
        "--classify",
        required=True,
        help='Classify groups by index: "items=0,3 subCategories=1 nextPage=2"',
    )
    parser.add_argument(
        "--pages-dir",
        required=True,
        help="Base directory containing page subdirectories (e.g. pages/)",
    )
    args = parser.parse_args()

    groups = parse_groups(args.groups_file)
    index_to_type = parse_classify(args.classify)
    write_classified(groups, index_to_type, args.pages_dir)


if __name__ == "__main__":
    main()
