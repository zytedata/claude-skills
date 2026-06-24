# /// script
# dependencies = ["extruct", "lxml"]
# ///
"""Extract structured metadata from HTML: JSON-LD, OpenGraph, microdata, microformat.

Skips RDFa and Dublin Core (too noisy / too sparse to be useful).

Usage:
    uv run extract_metadata.py PAGE.html              # JSON to stdout
    uv run extract_metadata.py PAGE.html -o meta.json  # write to file
"""

import argparse
import json
import sys

import extruct


FORMATS = ["json-ld", "opengraph", "microdata", "microformat"]


def extract_metadata(html: str, base_url: str = "") -> dict:
    data = extruct.extract(html, base_url=base_url, syntaxes=FORMATS,
                           errors="log")
    # Drop empty formats
    return {fmt: items for fmt, items in data.items() if items}


def read_html(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file", help="Path to HTML file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("-u", "--url", default="", help="Base URL for resolving relative URLs")
    args = parser.parse_args()

    html = read_html(args.html_file)
    metadata = extract_metadata(html, base_url=args.url)

    out = json.dumps(metadata, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
    else:
        sys.stdout.write(out)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
