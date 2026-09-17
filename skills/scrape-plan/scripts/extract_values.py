"""Extract item values from analysis files, filtered by schema.

Reads the analysis JSON files (from scrape-analyze-page) matching an HTML
variant, keeps only fields present in the schema, writes one values file
per page:

  uv run extract_values.py analyze-page/ spec.json --variant rendered -O values/
"""

import argparse
import json
import sys
from pathlib import Path


def load_schema_fields(spec_path: Path) -> set[str]:
    """Return the set of field names from spec.json's schema.properties."""
    spec = json.loads(spec_path.read_text())
    return set(spec.get("schema", {}).get("properties", {}).keys())


def extract_values(analysis: dict, schema_fields: set[str]) -> dict:
    """Extract values from a single analysis result."""
    fields = analysis.get("fields", {})

    values = {}
    for name in schema_fields:
        if name in fields:
            values[name] = fields[name].get("value")

    return {"url": analysis.get("url", ""), "values": values}


def main():
    parser = argparse.ArgumentParser(description="Extract values from analysis files")
    parser.add_argument("analysis_dir", help="Directory with analysis files")
    parser.add_argument("spec", help="Path to data-type spec.json")
    parser.add_argument("--variant", required=True, help="HTML variant filter")
    parser.add_argument("-O", "--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    analysis_dir = Path(args.analysis_dir)
    if not analysis_dir.is_dir():
        print(f"Not a directory: {analysis_dir}", file=sys.stderr)
        sys.exit(1)

    schema_fields = load_schema_fields(Path(args.spec))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = f"*.{args.variant}.json"
    files = sorted(analysis_dir.glob(pattern))
    if not files:
        print(f"No files matching {pattern} in {analysis_dir}", file=sys.stderr)
        sys.exit(1)

    count = 0
    for f in files:
        # detail-1.rendered.json → page_id = detail-1
        page_id = f.name.rsplit(".", 2)[0]
        analysis = json.loads(f.read_text())
        result = extract_values(analysis, schema_fields)
        out_path = output_dir / f"{page_id}.json"
        out_path.write_text(json.dumps(result, indent=2) + "\n")
        count += 1

    print(f"Wrote {count} values files to {output_dir}/")


if __name__ == "__main__":
    main()
