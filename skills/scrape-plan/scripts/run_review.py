# /// script
# dependencies = []
# ///
"""Open a browser review of schema/values and wait for user feedback.

Usage:
    uv run run_review.py SPEC_PATH WORK_PATH --variant rendered
    uv run run_review.py SPEC_PATH WORK_PATH --variant raw --changes '["Dropped field isbn"]'

SPEC_PATH is a data-type spec folder (spec.json + pages/); WORK_PATH is the
site working directory (with analyze-page/). Builds a temp review directory
(bundled assets, flattened page HTML, data.js pointing at this process's
feedback endpoint), opens the review page in the browser, waits for the user
to submit feedback, then prints the feedback and exits.

The schema shown in the review is read from SPEC_PATH/spec.json, so persist
any pending schema changes there first.
"""

import argparse
import json
import shutil
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ASSETS = ["review.html", "style.css", "review.js"]


def load_pages(spec_path: Path, work_path: Path, variant: str) -> dict:
    """Collect page metadata and analysis results, keyed by page id."""
    pages = {}
    pages_dir = spec_path / "pages"
    for page_dir in sorted(p for p in pages_dir.iterdir() if p.is_dir()):
        html = page_dir / f"{variant}.html"
        if not html.exists():
            print(f"Skipping {page_dir.name}: no {variant}.html", file=sys.stderr)
            continue
        meta_path = page_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        analysis_path = work_path / "analyze-page" / f"{page_dir.name}.{variant}.json"
        analysis = (
            json.loads(analysis_path.read_text(encoding="utf-8"))
            if analysis_path.exists()
            else {}
        )
        pages[page_dir.name] = {
            "html": html,
            "url": analysis.get("url") or meta.get("url", ""),
            "fields": analysis.get("fields", {}),
        }
    return pages


def build_review_data(schema: dict, pages: dict) -> dict:
    """Build the REVIEW_DATA object review.js expects."""
    fields = []
    for name, prop in schema.get("properties", {}).items():
        values = {}
        for page_id, page in pages.items():
            if name in page["fields"]:
                values[page_id] = {
                    "value": page["fields"][name].get("value"),
                    "url": page["url"],
                }
        fields.append(
            {
                "name": name,
                "type": prop.get("type", ""),
                "description": prop.get("description", ""),
                "source": prop.get("source", "requested"),
                "values": values,
            }
        )
    return {
        "fields": fields,
        "pages": {
            page_id: {"url": page["url"], "html_file": f"pages/{page_id}.html"}
            for page_id, page in pages.items()
        },
    }


def write_review_dir(
    spec_path: Path, work_path: Path, variant: str, changes: str | None, port: int
) -> Path | None:
    """Create the temp review directory: assets, flattened pages, data.js.

    Returns None if no page has the requested HTML variant. data.js is written
    once with the real port — there is no placeholder to patch later. Always
    written as UTF-8 so non-ASCII content (e.g. £ in prices) does not depend on
    the platform's default encoding (cp1252 on Windows).
    """
    spec = json.loads((spec_path / "spec.json").read_text(encoding="utf-8"))
    pages = load_pages(spec_path, work_path, variant)
    if not pages:
        return None

    review_dir = Path(tempfile.mkdtemp(prefix="scrape-review-"))
    assets_dir = Path(__file__).parent.parent / "assets"
    for asset in ASSETS:
        shutil.copy(assets_dir / asset, review_dir / asset)
    (review_dir / "pages").mkdir()
    for page_id, page in pages.items():
        shutil.copy(page["html"], review_dir / "pages" / f"{page_id}.html")

    data_js = f'const AGENT_URL = "http://127.0.0.1:{port}/feedback";\n'
    if changes:
        data_js += f"const REVIEW_CHANGES = {json.dumps(json.loads(changes))};\n"
    review_data = build_review_data(spec.get("schema", {}), pages)
    data_js += f"const REVIEW_DATA = {json.dumps(review_data, indent=2)};\n"
    (review_dir / "data.js").write_text(data_js, encoding="utf-8")
    return review_dir


class Handler(BaseHTTPRequestHandler):
    output_path = None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with open(self.output_path, "wb") as f:
            f.write(body)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
        threading.Thread(target=self.server.shutdown).start()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *a):
        pass


def review_url(review_dir: Path) -> str:
    """Absolute file:// URL for the review page."""
    return (review_dir.resolve() / "review.html").as_uri()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Open a browser review and wait for feedback"
    )
    parser.add_argument("spec_path", help="Data-type spec folder (spec.json + pages/)")
    parser.add_argument("work_path", help="Site working directory (with analyze-page/)")
    parser.add_argument("--variant", required=True, choices=["raw", "rendered"])
    parser.add_argument(
        "--changes", help="JSON array of change descriptions from the previous round"
    )
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]

    review_dir = write_review_dir(
        Path(args.spec_path), Path(args.work_path), args.variant, args.changes, port
    )
    if review_dir is None:
        print(f"No pages with {args.variant}.html in {args.spec_path}/pages/", file=sys.stderr)
        sys.exit(1)

    feedback_path = review_dir / "feedback.txt"
    Handler.output_path = feedback_path

    print(f"Review page: {review_url(review_dir)}", flush=True)
    webbrowser.open(review_url(review_dir))
    server.serve_forever()  # Handler shuts the server down once feedback arrives

    print("--- Feedback ---")
    print(feedback_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
