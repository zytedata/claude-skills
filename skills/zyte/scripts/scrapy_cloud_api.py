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
    uv run scrapy_cloud_api.py HTTP_METHOD API_PATH [--storage] [-q QUERY_ARG=VALUE]... \
        [-b BODY_ARG=VALUE | -b BODY_ARG:=JSON]... | [-j BODY_JSON_FILE]

    Multiple -q and -b flags are supported to pass arbitrarily many query and body arguments.
    `-b KEY=VALUE` sends VALUE as a string; `-b KEY:=JSON` sends it as a parsed
    JSON value (number, boolean, null, array, object). For a whole nested body,
    write it to a file and pass `-j PATH` instead.

Examples:
    uv run scrapy_cloud_api.py GET jobs/list.json -q project=859188 -q state=running
    uv run scrapy_cloud_api.py POST jobs/stop.json -b project=859188 -b job=859188/1/1
    uv run scrapy_cloud_api.py PATCH projects/859188/periodicjobs/3 -b disabled:=true
    uv run scrapy_cloud_api.py POST projects/859188/periodicjobs -j body.json
    uv run scrapy_cloud_api.py GET --storage items/859188/1/1 -q count=5
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from auth import build_headers
from env_keys import ENV_FILE, set_var

TIMEOUT_SECONDS = 10
DEFAULT_API_ENDPOINT = "https://app.zyte.com/api/"
DEFAULT_STORAGE_ENDPOINT = "https://storage.zyte.com/"


def resolve_url(target: str, *, storage: bool = False) -> str:
    """Return the full URL for *target*.

    A path such as ``jobs/list.json`` is joined to the Scrapy Cloud API base
    URL, or to the storage base URL when *storage* is true, honoring the
    ``SCRAPY_CLOUD_ENDPOINT`` and ``SCRAPY_CLOUD_STORAGE_ENDPOINT`` overrides so
    that callers never have to spell out an endpoint. A *target* that already
    carries a scheme is returned unchanged.
    """
    if "://" in target:
        return target
    if storage:
        base = os.getenv("SCRAPY_CLOUD_STORAGE_ENDPOINT") or DEFAULT_STORAGE_ENDPOINT
    else:
        base = os.getenv("SCRAPY_CLOUD_ENDPOINT") or DEFAULT_API_ENDPOINT
    return f"{base.rstrip('/')}/{target.lstrip('/')}"


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


def emit_response(status: int, body: str, save_env: str | None = None) -> int:
    """Print the API response and return the process exit code.

    An HTML error body is replaced by a one-line summary: it is a web page,
    such as a login form, that carries no information the status code does not
    already give, and printing it floods the caller with markup.

    With *save_env*, a successful body is stored in the dotenv file under that
    variable name instead of being printed, so that a secret never reaches the
    terminal. The body of a failed request is an error message rather than a
    secret, and the caller needs it to report the failure, so it is printed and
    the dotenv file is left alone.
    """
    print(status)
    if status >= 400 and body.lstrip()[:1] == "<":
        body = f"[{len(body)} bytes of HTML omitted; the path is probably wrong]"
    if not save_env:
        print(body)
        return 0
    if status != 200:
        print(body)
        return 1
    set_var(save_env, body.strip())
    print(f"{save_env} stored in {ENV_FILE}")
    return 0


def parse_body_args(items: list[str]) -> dict:
    """Turn ``-b`` arguments into a request body.

    ``KEY=VALUE`` keeps VALUE as a string; ``KEY:=JSON`` parses VALUE as JSON,
    which is how non-string fields (booleans, numbers, lists, objects) are
    expressed. Raises ``ValueError`` on malformed input.
    """
    body = {}
    for item in items:
        sep = item.find("=")
        if sep < 1:
            raise ValueError(f"body argument must be KEY=VALUE or KEY:=JSON: {item!r}")
        if item[sep - 1] == ":":  # KEY:=JSON
            key, raw = item[: sep - 1], item[sep + 1 :]
            if not key:
                raise ValueError(f"body argument is missing a key: {item!r}")
            try:
                body[key] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"value of {key!r} is not valid JSON: {exc}") from exc
        else:
            body[item[:sep]] = item[sep + 1 :]
    return body


def load_json_body(path: str) -> dict:
    """Read a request body from a JSON file. Raises ``ValueError`` if the file
    is missing, unreadable, not valid JSON, or not a JSON object.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(body).__name__}")
    return body


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
        "api_url",
        metavar="API_PATH",
        help="Path of the Scrapy Cloud API endpoint to call (e.g. jobs/list.json),"
        " or a full URL.",
    )
    parser.add_argument(
        "--storage",
        action="store_true",
        help="Resolve API_PATH against the storage API (items, logs) instead of"
        " the Scrapy Cloud API.",
    )
    parser.add_argument(
        "--save-env",
        metavar="VAR",
        help="Write the response body to the .env file as VAR instead of printing"
        " it, and only if the request succeeded. For secrets, e.g. API keys.",
    )
    parser.add_argument(
        "-q",
        "--query",
        action="append",
        help="Query argument in the form KEY=VALUE. Can be specified multiple times.",
    )
    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument(
        "-b",
        "--body",
        action="append",
        help="Body argument in the form KEY=VALUE (string value) or KEY:=JSON"
        " (parsed JSON value, e.g. disabled:=true). Can be specified multiple times.",
    )
    body_group.add_argument(
        "-j",
        "--json-body",
        metavar="PATH",
        help="Path to a file containing the whole request body as a JSON object."
        " Use this for nested bodies instead of -b.",
    )
    args = parser.parse_args()

    query_params = {}
    if args.query:
        for q in args.query:
            key, value = q.split("=", 1)
            query_params[key] = value

    body_params = {}
    try:
        if args.json_body:
            body_params = load_json_body(args.json_body)
        elif args.body:
            body_params = parse_body_args(args.body)
    except ValueError as exc:
        parser.error(str(exc))

    full_url = resolve_url(args.api_url, storage=args.storage)
    if query_params:
        full_url += "?" + urlencode(query_params)

    # make the API request using urllib, passing the API key in the Authorization header
    headers = build_headers("scrapy_cloud_api.py")
    status, response = make_api_request(
        args.method, full_url, headers, body_params if body_params else None
    )
    sys.exit(emit_response(status, response, args.save_env))
