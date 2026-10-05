# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "shub>=2.18.1",
# ]
# ///
"""Download a Zyte API key into the project's .env file, without printing it.

Usage:
    uv run download_key.py DOWNLOAD_URL
    uv run download_key.py --check
"""

import argparse
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from auth import build_headers, get_api_key
from env_keys import ENV_FILE, set_var

TIMEOUT_SECONDS = 10
VARIABLE = "ZYTE_API_KEY"


def download(url: str, headers: dict) -> tuple[int, str]:
    """Return the ``(status_code, body)`` of a GET to *url*, errors included."""
    try:
        with urlopen(Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def store(status: int, body: str) -> int:
    """Store a successful *body* as the key and return the exit code.

    A failed body is an error message, not a key, so it is printed for the
    caller to report and the dotenv file is left alone.
    """
    print(status)
    if status != 200:
        if body.lstrip()[:1] == "<":
            body = f"[{len(body)} bytes of HTML omitted; the URL is probably wrong]"
        print(body)
        return 1
    set_var(VARIABLE, body.strip())
    print(f"{VARIABLE} stored in {ENV_FILE}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs="?", metavar="DOWNLOAD_URL")
    group.add_argument(
        "--check",
        action="store_true",
        help="Only verify that a Scrapy Cloud API key is available, then exit.",
    )
    args = parser.parse_args()
    if args.check:
        get_api_key()
        print("Scrapy Cloud API key: available")
        sys.exit(0)
    sys.exit(store(*download(args.url, build_headers("download_key.py"))))
