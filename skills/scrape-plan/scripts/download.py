# /// script
# dependencies = ["scrapy", "scrapy-playwright", "scrapy-zyte-api", "brotli"]
# ///
"""Download web pages via Scrapy + Playwright or Zyte API.

Usage:
    uv run --python 3.14 download.py [--log-file FILE] < tasks.json
    uv run --python 3.14 download.py [--log-file FILE] <<'EOF'
    [...]
    EOF

Reads a JSON array of download tasks from stdin:
    [{"url": "...", "output_dir": "...", "page_type": "..."}]

Creates OUTPUT_DIR/ per task with:
    raw.html          — HTTP response body
    rendered.html     — browser-rendered HTML
    meta.json         — capture metadata

If no Zyte API key is available, Playwright mode is used, and Chromium is
installed on the fly if missing.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy_zyte_api.utils import USER_AGENT as ZAPI_USER_AGENT

_meta_dir = Path(__file__).parent.parent.parent / "scrape"
_meta = json.loads((_meta_dir / "meta.json").read_text(encoding="utf-8"))

SHARED_SETTINGS = {
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "CONCURRENT_REQUESTS": 8,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    "DOWNLOAD_TIMEOUT": 30,
    "RETRY_ENABLED": True,
    "ROBOTSTXT_OBEY": False,
    "USER_AGENT": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
    "LOG_LEVEL": "INFO",
    "LOGSTATS_INTERVAL": 15,
}

PLAYWRIGHT_SETTINGS = {
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
    "PLAYWRIGHT_CONTEXTS": {
        "default": {"viewport": {"width": 1280, "height": 720}},
    },
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000,
}

def _zyte_api_settings(skill: str) -> dict:
    ua = f"zytedata/{_meta['repo']}/{_meta['version']} ({skill}) {ZAPI_USER_AGENT}"
    return {
        "ADDONS": {"scrapy_zyte_api.Addon": 500},
        "ZYTE_API_TRANSPARENT_MODE": True,
        "_ZYTE_API_USER_AGENT": ua,
    }


def normalize_zyte_api_key(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value == "None":
        return None
    return value


def get_zyte_api_key() -> str | None:
    env_key = normalize_zyte_api_key(os.environ.get("ZYTE_API_KEY"))
    if env_key:
        return env_key
    settings = get_project_settings()
    key_from_settings = normalize_zyte_api_key(settings.get("ZYTE_API_KEY"))
    if key_from_settings:
        return key_from_settings
    return None


class DownloadSpider(scrapy.Spider):
    name = "download"

    def __init__(self, tasks=None, **kwargs):
        super().__init__(**kwargs)
        self.tasks = tasks or []

    def _write_meta(self, output_dir, task, extra=None):
        """Write/update meta.json with task info and any extra fields."""
        meta_path = os.path.join(output_dir, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        else:
            meta = {
                "url": task["url"],
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            if task.get("page_type"):
                meta["page_type"] = task["page_type"]
        if extra:
            for key, value in extra.items():
                if key == "errors":
                    meta.setdefault("errors", {}).update(value)
                else:
                    meta[key] = value
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    async def start(self):
        for task in self.tasks:
            url = task["url"]
            output_dir = task["output_dir"]
            os.makedirs(output_dir, exist_ok=True)

            # Plain HTTP request
            yield scrapy.Request(
                url,
                callback=self.parse_http,
                errback=self.errback_http,
                meta={"task": task},
                dont_filter=True,
            )

            # Browser request
            if self.crawler.settings.get("ZYTE_API_KEY"):
                yield scrapy.Request(
                    url,
                    callback=self.parse_zyte,
                    errback=self.errback_zyte,
                    meta={
                        "task": task,
                        "zyte_api_automap": {"browserHtml": True},
                    },
                    dont_filter=True,
                )
            else:
                # Playwright request
                yield scrapy.Request(
                    url,
                    callback=self.parse_playwright,
                    errback=self.errback_playwright,
                    meta={
                        "task": task,
                        "playwright": True,
                        "playwright_include_page": True,
                    },
                    dont_filter=True,
                )

    def parse_http(self, response):
        task = response.meta["task"]
        output_dir = task["output_dir"]

        with open(os.path.join(output_dir, "raw.html"), "wb") as f:
            f.write(response.body)

        extra = {
            "http_status": response.status,
            "http_headers": {
                k.decode("utf-8", errors="replace"): response.headers[k].decode(
                    "utf-8", errors="replace"
                )
                for k in response.headers
            },
        }
        if str(response.url) != task["url"]:
            extra["final_url"] = str(response.url)
        self._write_meta(output_dir, task, extra)

    def errback_http(self, failure):
        task = failure.request.meta["task"]
        self._write_meta(task["output_dir"], task, {"errors": {"http": str(failure.value)}})

    def parse_zyte(self, response):
        task = response.meta["task"]
        output_dir = task["output_dir"]

        html_path = Path(output_dir) / "rendered.html"
        html_path.write_text(response.text, encoding="utf-8")

    def errback_zyte(self, failure):
        task = failure.request.meta["task"]
        self._write_meta(task["output_dir"], task, {"errors": {"zyte_api": str(failure.value)}})

    async def parse_playwright(self, response):
        task = response.meta["task"]
        output_dir = task["output_dir"]
        page = response.meta["playwright_page"]

        try:
            # Wait for network idle like the original — catch timeout
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            html = await page.content()
            with open(
                os.path.join(output_dir, "rendered.html"), "w", encoding="utf-8"
            ) as f:
                f.write(html)
        except Exception as e:
            self._write_meta(output_dir, task, {"errors": {"playwright": str(e)}})
        finally:
            await page.close()

    def errback_playwright(self, failure):
        task = failure.request.meta["task"]
        self._write_meta(
            task["output_dir"], task, {"errors": {"playwright": str(failure.value)}}
        )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Download web pages via Zyte API or Scrapy + Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-file",
        help="Log file (default: download.log next to the tasks' output dirs)",
    )
    parser.add_argument(
        "--skill", default="scrape-plan", help="Skill name for User-Agent identification."
    )

    args = parser.parse_args()

    tasks = json.loads(sys.stdin.buffer.read())

    log_file = args.log_file
    if not log_file:
        parent = os.path.dirname(tasks[0]["output_dir"]) if tasks else ""
        log_file = os.path.join(parent or ".", "download.log")

    zyte_api_key = get_zyte_api_key()
    # Configure logging to append to file (Scrapy's LOG_FILE always overwrites)
    if zyte_api_key:
        settings = {
            **SHARED_SETTINGS,
            **_zyte_api_settings(args.skill),
            "ZYTE_API_KEY": zyte_api_key,
            "LOG_ENABLED": False,
        }
    else:
        settings = {
            **SHARED_SETTINGS,
            **PLAYWRIGHT_SETTINGS,
            "LOG_ENABLED": False,
        }
        # Chromium is a separate download from the Playwright package, and the
        # first request fails without it. This is a no-op once installed.
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            stdout=sys.stderr,
        )

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    logging.root.addHandler(file_handler)
    logging.root.setLevel(logging.INFO)


    logger = logging.getLogger(__name__)
    if zyte_api_key:
        logger.info("Using Zyte API.")
    else:
        logger.info("Using Playwright (no Zyte API key found).")

    process = CrawlerProcess(settings=settings)

    # Send the periodic crawl stats to stderr as well, so that callers see
    # progress while the log file gets the details. CrawlerProcess resets the
    # handlers of every scrapy logger, hence the placement.
    progress_handler = logging.StreamHandler()
    progress_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("scrapy.extensions.logstats").addHandler(progress_handler)

    process.crawl(DownloadSpider, tasks=tasks)
    process.start()

    # Print results after crawl completes
    all_files = ["raw.html", "rendered.html", "meta.json"]
    for task in tasks:
        output_dir = task["output_dir"]
        meta_path = os.path.join(output_dir, "meta.json")
        result = {
            "url": task["url"],
            "output_dir": output_dir,
            "files": [f for f in all_files if os.path.exists(os.path.join(output_dir, f))],
        }
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            if "http_status" in meta:
                result["http_status"] = meta["http_status"]
            if "errors" in meta:
                result["errors"] = meta["errors"]
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
