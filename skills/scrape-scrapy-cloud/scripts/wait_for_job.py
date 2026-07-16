# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "shub>=2.18.1",
# ]
# ///
"""Block until a Scrapy Cloud job finishes, then print its final job object.

Designed to be launched as a background task by the agent: it polls the Jobs
API with backoff instead of the agent burning turns polling by hand. Progress
goes to stderr; the single machine-readable result line goes to stdout, prefixed
with a marker so the agent can grep it out of buffered background output:

    JOB_FINISHED {"state": "finished", "close_reason": "finished", ...}
    JOB_TIMEOUT  {"state": "running", ...}     # --max-wait exceeded

Exit code is 0 when the job reached a terminal state, 1 on timeout.

Usage:
    uv run wait_for_job.py PROJECT/SPIDER/JOB [--poll-interval 10] [--max-wait 1200]
"""

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from auth import build_headers

DEFAULT_ENDPOINT = "https://app.zyte.com/api/"
TIMEOUT_SECONDS = 30
BACKOFF_FACTOR = 1.5
MAX_POLL_INTERVAL = 60.0
TERMINAL_STATES = {"finished", "deleted"}


def endpoint() -> str:
    base = os.getenv("SCRAPY_CLOUD_ENDPOINT", DEFAULT_ENDPOINT)
    return base if base.endswith("/") else base + "/"


def fetch_job(job_key: str, headers: dict) -> dict | None:
    """Return the job object for `job_key` (PROJECT/SPIDER/JOB), or None if the
    API returned no matching job."""
    project = job_key.split("/", 1)[0]
    query = urlencode({"project": project, "job": job_key})
    url = f"{endpoint()}jobs/list.json?{query}"
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    jobs = payload.get("jobs") or []
    return jobs[0] if jobs else None


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", help="Job key in PROJECT/SPIDER/JOB form, e.g. 123/1/45")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Initial seconds between polls (backs off ×1.5, capped at 60s). Default: 10.",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=1200.0,
        help="Give up after this many seconds and print JOB_TIMEOUT. Default: 1200 (20 min).",
    )
    args = parser.parse_args()

    if args.job.count("/") != 2:
        parser.error("job must be in PROJECT/SPIDER/JOB form, e.g. 123/1/45")

    headers = build_headers("wait_for_job.py")

    start = time.monotonic()
    interval = args.poll_interval
    last_job: dict = {}

    while True:
        try:
            job = fetch_job(args.job, headers)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            log(f"HTTP {exc.code} polling job {args.job}: {body}")
            job = None
        except URLError as exc:
            log(f"network error polling job {args.job}: {exc.reason}")
            job = None

        if job is not None:
            last_job = job
            state = job.get("state", "unknown")
            elapsed = int(time.monotonic() - start)
            if state in TERMINAL_STATES:
                print("JOB_FINISHED " + json.dumps(job), flush=True)
                return 0
            log(
                f"state={state} items={job.get('items_scraped', '?')} "
                f"errors={job.get('errors_count', '?')} waited={elapsed}s"
            )

        if time.monotonic() - start >= args.max_wait:
            print("JOB_TIMEOUT " + json.dumps(last_job), flush=True)
            return 1

        # Don't overshoot max-wait on the final sleep.
        remaining = args.max_wait - (time.monotonic() - start)
        time.sleep(max(0.0, min(interval, remaining)))
        interval = min(interval * BACKOFF_FACTOR, MAX_POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
