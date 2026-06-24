# /// script
# requires-python = ">=3.11"
# dependencies = ["shub"]
# ///
"""Fetch Zyte API stats using standard shub auth resolution.

The caller passes query parameters as a JSON object matching the Stats API
OpenAPI spec. Auth is handled internally via shub.

Usage examples:
    uv run zyte_api_stats.py --params '{"organization_id": 3}'
    uv run zyte_api_stats.py --params '{"organization_id": 3, "start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-31T23:59:59Z", "page": 2}'
    uv run zyte_api_stats.py --params '{"organization_id": 3, "groupby_time": "day", "extraction_type": "article"}'
    uv run zyte_api_stats.py --check-key
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from auth import build_basic_auth_headers, get_api_key

_meta_dir = SCRIPT_DIR.parent.parent / "scrape"
_meta = json.loads((_meta_dir / "meta.json").read_text())

API_URL = "https://zyte-api-stats.zyte.com/api/stats"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Zyte API usage stats")
    parser.add_argument(
        "--params",
        help="JSON object of query parameters per the Stats API OpenAPI spec.",
    )
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Only verify that a Scrapy Cloud API key is available, then exit.",
    )
    return parser.parse_args()


def read_stats_api_key() -> str:
    try:
        return get_api_key()
    except RuntimeError as exc:
        fail(str(exc))


def build_request_url(params: dict[str, Any]) -> str:
    return f"{API_URL}?{urlencode({k: str(v) for k, v in params.items()})}"


def fetch_page(params: dict[str, Any], stats_api_key: str) -> dict[str, Any]:
    url = build_request_url(params)
    headers = {**build_basic_auth_headers(stats_api_key), "User-Agent": f"zytedata/{_meta['repo']}/{_meta['version']} (scrape-zyte-api-stats)"}

    last_response_text = ""
    for attempt in range(1, 4):
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request) as response:
                http_code = response.getcode()
                response_text = response.read().decode("utf-8")
        except HTTPError as exc:
            http_code = exc.code
            response_text = exc.read().decode("utf-8", errors="replace")
        except URLError as exc:
            fail(f"Request failed: {exc.reason}")

        last_response_text = response_text

        if http_code == 429 and attempt < 3:
            time.sleep(5)
            continue
        if http_code == 429:
            fail("Rate limited by the Stats API after 3 attempts. Please try again in a minute.")
        if http_code == 401:
            fail(
                "Authentication failed. Check that you are using your Zyte dashboard API key, not your Zyte API key."
            )

        payload = parse_json_response(response_text)

        if http_code == 422:
            fail(json.dumps(payload, indent=2, ensure_ascii=True))

        detail = payload.get("detail")
        if detail:
            if isinstance(detail, str):
                fail(detail)
            fail(json.dumps(detail, indent=2, ensure_ascii=True))

        if http_code >= 400:
            fail(json.dumps(payload, indent=2, ensure_ascii=True))

        return payload

    fail(f"Request failed: {last_response_text}")


def parse_json_response(response_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        fail("Stats API returned a non-JSON response.")
    if not isinstance(payload, dict):
        fail("Stats API returned an unexpected response shape.")
    return payload


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    args = parse_args()
    if args.check_key:
        read_stats_api_key()
        return
    if not args.params:
        fail("--params is required unless --check-key is used.")
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as exc:
        fail(f"--params must be valid JSON: {exc}")
    if not isinstance(params, dict):
        fail("--params must be a JSON object.")
    if "organization_id" not in params:
        fail("--params must include organization_id.")
    stats_api_key = read_stats_api_key()
    payload = fetch_page(params, stats_api_key)
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()