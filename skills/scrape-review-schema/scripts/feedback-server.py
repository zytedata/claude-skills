#!/usr/bin/env python3
"""One-shot HTTP server that patches data.js, opens the review page, and receives feedback."""

import pathlib
import re
import sys
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

# Matches the loopback host:port in data.js whether it still holds the literal
# placeholder or a real port left behind by an earlier (possibly crashed) run.
# Rewriting the host:port unconditionally keeps the substitution idempotent, so
# data.js always points at the port this process actually bound to.
_HOST_PORT_RE = re.compile(r"127\.0\.0\.1:(?:AGENT_PORT_PLACEHOLDER|\d+)")


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


def patch_data_js_port(data_js, port):
    """Point data.js at ``port``, whether it holds the placeholder or a stale port.

    Always reads and writes as UTF-8 so non-ASCII content (e.g. £ in prices) does
    not depend on the platform's default encoding (cp1252 on Windows).
    """
    content = data_js.read_text(encoding="utf-8")
    content = _HOST_PORT_RE.sub(f"127.0.0.1:{port}", content)
    data_js.write_text(content, encoding="utf-8")


def review_url(review_dir):
    """Absolute file:// URL for the review page.

    ``Path.as_uri()`` raises ValueError on a relative path, so resolve first.
    """
    return (review_dir.resolve() / "review.html").as_uri()


def main(argv):
    review_dir = pathlib.Path(argv[1])
    Handler.output_path = argv[2]

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]

    patch_data_js_port(review_dir / "data.js", port)

    webbrowser.open(review_url(review_dir))
    srv.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
