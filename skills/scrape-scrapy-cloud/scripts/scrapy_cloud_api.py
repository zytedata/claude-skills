# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "shub>=2.18.1",
# ]
# ///
"""Wrapper to interact with the Scrapy Cloud API while avoiding leaking API keys.

Prints the HTTP response status code on the first line, followed by the
response body on the remaining lines. Callers that only need the body should
skip the first line (e.g. `tail -n +2`).

Usage:
    uv run scrapy_cloud_api.py HTTP_METHOD API_URL [-q QUERY_ARG=VALUE]... [-b BODY_ARG=VALUE]...

    Multiple -q and -b flags are supported to pass arbitrarily many query and body arguments.

Examples:
    uv run scrapy_cloud_api.py GET https://app.zyte.com/api/jobs/list.json -q project=859188 -q state=running
    uv run scrapy_cloud_api.py POST https://app.zyte.com/api/jobs/stop.json -b project=859188 -b job=859188/1/1
"""

import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from auth import build_headers

TIMEOUT_SECONDS = 10


def make_api_request(
    method: str, url: str, headers: dict, body: dict | None = None
) -> tuple[int, str]:
    """Return the ``(status_code, body)`` of the API response.

    HTTP error responses are returned like any other response rather than
    raised, so the caller can inspect the status code and body uniformly.
    """
    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Wrapper to interact with the Scrapy Cloud API while avoiding leaking API keys."
    )
    parser.add_argument(
        "method",
        help="The HTTP method to use for the API request (e.g., GET, POST).",
        choices=["GET", "POST", "PUT", "DELETE", "PATCH"],
        default="GET",
    )
    parser.add_argument(
        "api_url", help="The URL of the Scrapy Cloud API endpoint to call."
    )
    parser.add_argument(
        "-q",
        "--query",
        action="append",
        help="Query argument in the form KEY=VALUE. Can be specified multiple times.",
    )
    parser.add_argument(
        "-b",
        "--body",
        action="append",
        help="Body argument in the form KEY=VALUE. Can be specified multiple times.",
    )
    args = parser.parse_args()

    query_params = {}
    if args.query:
        for q in args.query:
            key, value = q.split("=", 1)
            query_params[key] = value

    body_params = {}
    if args.body:
        for b in args.body:
            key, value = b.split("=", 1)
            body_params[key] = value

    full_url = args.api_url
    if query_params:
        full_url += "?" + urlencode(query_params)

    # make the API request using urllib, passing the API key in the Authorization header
    headers = build_headers("scrapy_cloud_api.py")
    status, response = make_api_request(
        args.method, full_url, headers, body_params if body_params else None
    )
    print(status)
    print(response)
