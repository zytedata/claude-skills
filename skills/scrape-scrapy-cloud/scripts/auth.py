"""Shared Scrapy Cloud auth helpers, so API-key handling lives in one place
instead of being duplicated (and drifting) across this skill's scripts.
"""

import json
import sys
from base64 import b64encode
from pathlib import Path

import shub.config

SKILL = "scrape-scrapy-cloud"

_meta_dir = Path(__file__).parent.parent.parent / "scrape"
_meta = json.loads((_meta_dir / "meta.json").read_text())


def get_api_key() -> str:
    config = shub.config.load_shub_config()
    apikey = config.apikeys.get("default")

    if not apikey:
        print(
            "Scrapy Cloud API key not found."
            " Run 'shub login' or set the SHUB_APIKEY environment variable, then try again."
            " If you don't have a Zyte account, sign up at https://app.zyte.com."
            " See https://shub.readthedocs.io/en/latest/configuration.md"
        )
        sys.exit(1)

    return apikey


def build_headers(component: str, *, accept: str = "application/json") -> dict:
    """Basic-auth + identifying headers for a Scrapy Cloud HTTP API request.

    `component` names the calling script (e.g. "scrapy_cloud_api.py"). It is
    combined with this skill's name in the User-Agent string, to distinguish
    both the skill and the specific script in server-side logs.
    """
    apikey = get_api_key()
    auth_token = b64encode(f"{apikey}:".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {auth_token}",
        "Accept": accept,
        "User-Agent": f"zytedata/{_meta['repo']}/{_meta['version']} ({SKILL}; {component})",
    }
