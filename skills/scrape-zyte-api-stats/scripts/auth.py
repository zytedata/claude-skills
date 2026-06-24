# /// script
# requires-python = ">=3.11"
# dependencies = ["shub"]
# ///

from __future__ import annotations

import os
from base64 import b64encode


APIKEY_ENV_VAR = "SHUB_APIKEY"


def get_api_key() -> str:
    apikey = os.getenv(APIKEY_ENV_VAR)
    if apikey:
        return apikey

    import shub.config

    config = shub.config.load_shub_config()
    apikey = config.apikeys.get("default")
    if apikey:
        return str(getattr(apikey, "value", apikey))

    raise RuntimeError(
        "Scrapy Cloud API key not found. "
        "Use the scrape-zyte-login skill or run 'shub login', or set the SHUB_APIKEY environment variable, then try again. "
        "If you don't have a Zyte account, sign up at https://app.zyte.com. "
        "See https://shub.readthedocs.io/en/latest/configuration.md"
    )


def build_basic_auth_headers(apikey: str, *, accept: str = "application/json") -> dict[str, str]:
    auth_token = b64encode(f"{apikey}:".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {auth_token}",
        "Accept": accept,
    }