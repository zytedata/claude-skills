"""Extract item values from analysis files, filtered by schema.

Reads analysis JSON (from scrape-analyze-page), keeps only fields present
in the schema, applies renames and value patches, writes values files.

Single-file mode:
  uv run extract_values.py detail-1.rendered.json spec.json -o values/detail-1.json

Directory mode (all pages matching a variant):
  uv run extract_values.py analyze-page/ spec.json --variant rendered -O values/

Renames are read from spec.json's field_mapping (analysis name → schema name).
Override with --renames if needed.

Options:
  --renames '{"old_name": "new_name"}'  Extra renames (merged with field_mapping)
  --patches '{"field": "corrected_value"}'  Override specific field values (single-file)
  --patches '{"detail-1": {"field": "val"}}'  Per-page patches (directory mode)
"""

import argparse
import json
import sys
from pathlib import Path


def load_schema_fields(spec_path: Path) -> set[str]:
    """Return the set of field names from spec.json's schema.properties."""
    spec = json.loads(spec_path.read_text())
    return set(spec.get("schema", {}).get("properties", {}).keys())


def extract_values(
    analysis: dict,
    schema_fields: set[str],
    renames: dict[str, str],
    patches: dict[str, object],
) -> dict:
    """Extract values from a single analysis result."""
    fields = analysis.get("fields", {})

    # Apply renames: map old analysis field names to new names
    renamed = {}
    for name, data in fields.items():
        new_name = renames.get(name, name)
        renamed[new_name] = data

    # Filter to schema fields only
    values = {}
    for name in schema_fields:
        if name in renamed:
            values[name] = renamed[name].get("value")

    # Apply patches (override specific values)
    for name, value in patches.items():
        if name in schema_fields:
            values[name] = value

    return {"url": analysis.get("url", ""), "values": values}


def process_single(
    analysis_path: Path,
    spec_path: Path,
    output_path: Path,
    renames: dict,
    patches: dict,
):
    schema_fields = load_schema_fields(spec_path)
    analysis = json.loads(analysis_path.read_text())
    result = extract_values(analysis, schema_fields, renames, patches)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {output_path} ({len(result['values'])} fields)")


def process_directory(
    analysis_dir: Path,
    spec_path: Path,
    variant: str,
    output_dir: Path,
    renames: dict,
    patches: dict,
):
    schema_fields = load_schema_fields(spec_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = f"*.{variant}.json"
    files = sorted(analysis_dir.glob(pattern))
    if not files:
        print(f"No files matching {pattern} in {analysis_dir}", file=sys.stderr)
        sys.exit(1)

    count = 0
    for f in files:
        # detail-1.rendered.json → page_id = detail-1
        page_id = f.name.rsplit(".", 2)[0]
        analysis = json.loads(f.read_text())
        page_patches = patches.get(page_id, {})
        result = extract_values(analysis, schema_fields, renames, page_patches)
        out_path = output_dir / f"{page_id}.json"
        out_path.write_text(json.dumps(result, indent=2) + "\n")
        count += 1

    print(f"Wrote {count} values files to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Extract values from analysis files")
    parser.add_argument("analysis", help="Analysis file or directory")
    parser.add_argument("spec", help="Path to data-type spec.json")
    parser.add_argument("-o", "--output", help="Output file (single-file mode)")
    parser.add_argument("-O", "--output-dir", help="Output directory (directory mode)")
    parser.add_argument("--variant", help="HTML variant filter (directory mode)")
    parser.add_argument("--renames", default="{}", help="JSON: {old_name: new_name}")
    parser.add_argument("--patches", default="{}", help="JSON: patches to apply")
    args = parser.parse_args()

    renames = json.loads(args.renames)
    patches = json.loads(args.patches)
    analysis_path = Path(args.analysis)
    spec_path = Path(args.spec)

    if analysis_path.is_file():
        if not args.output:
            print("Single-file mode requires -o/--output", file=sys.stderr)
            sys.exit(1)
        process_single(analysis_path, spec_path, Path(args.output), renames, patches)
    elif analysis_path.is_dir():
        if not args.variant or not args.output_dir:
            print(
                "Directory mode requires --variant and -O/--output-dir", file=sys.stderr
            )
            sys.exit(1)
        process_directory(
            analysis_path, spec_path, args.variant, Path(args.output_dir), renames, patches
        )
    else:
        print(f"Not found: {analysis_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
