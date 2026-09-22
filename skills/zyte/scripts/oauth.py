# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "flask>=3.0.0",
#   "requests>=2.32.0",
#   "waitress>=3.0.0",
# ]
# ///

"""
Native OAuth authentication for Zyte skills.

Run with:
    uv run oauth.py [--production]
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from flask import Flask, make_response, request
from waitress import serve as wsgi_serve

from env_keys import ENV_FILE, set_var


DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8013
CALLBACK_PATH: str = "/callback"
CALLBACK_TIMEOUT_SECONDS: int = 300

# OAuth params
AUTH_SCOPES: str = "openid profile email"

# Per-environment configuration. Staging is the default; pass --production to
# switch. The production Federated App details are placeholders until it is live.
AUTH_CONFIG: dict[str, dict[str, str]] = {
    "staging": {
        "auth_host": "https://auth.app-staging.zyte.com",
        "auth_app_id": "SA3DdoIGdtyhu1PfGpxaf4F0itQ4J",  # federated app ID
        "auth_project_id": "P2rKxzFKCz6VIYQCAXD03hmFP5hB",  # used as client_id
        "scrapy_cloud_base_url": "https://app-staging.zyte.com",
    },
    "production": {
        "auth_host": "https://auth.app.zyte.com",
        "auth_app_id": "SA3GVDfVKRKETGAJxlZcHJjz1d3ER",
        "auth_project_id": "Peuc12uXaw1Kx4I4bASuEH6qejB46s0j",
        "scrapy_cloud_base_url": "https://app.zyte.com",
    },
}

# Scrapy Cloud API endpoint paths, resolved against the selected environment's
# scrapy_cloud_base_url at runtime.
PROJECTS_PATH: str = "/api/v2/projects?page_size=50"
ORGANIZATIONS_PATH: str = "/api/v3/organizations?page_size=50"
ZYTE_API_LIST_PATH: str = "/api/v2/zyteapi?page_size=50&organization={org_id}"
SHUB_APIKEY_PATH: str = "/api/v2/users/me/download_apikey"
ZYTE_APIKEY_PATH: str = (
    "/api/v3/organizations/{org_id}/zyteapi/download_apikey/{key_id}"
)


app = Flask(__name__)

oauth_result: dict[str, str] = {}  # shared between threads
callback_received = threading.Event()


logging.basicConfig(level=logging.INFO)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE verifier + challenge pair."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@app.route(CALLBACK_PATH)
def callback():
    if error := request.args.get("error"):
        description = request.args.get("error_description", "")
        logging.error("OAuth error: %s (%s)", error, description)
        return make_response(f"Authentication failed: {error}", 400)

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return make_response("Missing authorization code", 400)

    oauth_result["code"] = code
    oauth_result["state"] = state or ""

    callback_received.set()

    return make_response(
        """
        <html>
          <body style="font-family: sans-serif; padding: 2rem;">
            <h2>Authentication successful</h2>
            <p>You may now close this window.</p>
          </body>
        </html>
        """,
        200,
    )


def build_authorize_url(
    *, config: dict[str, str], redirect_uri: str, state: str, code_challenge: str
) -> str:
    """Build the OIDC authorization URL."""
    authorize_endpoint = (
        f"{config['auth_host']}/{config['auth_app_id']}/oauth2/v1/authorize"
    )
    params = {
        "response_type": "code",
        "client_id": config["auth_project_id"],
        "redirect_uri": redirect_uri,
        "scope": AUTH_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # "prompt": "login",
    }
    return f"{authorize_endpoint}?{urlencode(params)}"


def exchange_code_for_token(
    *, config: dict[str, str], code: str, code_verifier: str, redirect_uri: str
) -> dict:
    """Exchange authorization code for access token."""

    token_endpoint = f"{config['auth_host']}/{config['auth_app_id']}/oauth2/v1/token"

    response = requests.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "client_id": config["auth_project_id"],
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        logging.error(
            "Token exchange failed: %s",
            response.text,
        )
        raise

    return response.json()


def _get_paginated_data(*, access_token: str, endpoint: str) -> list[dict]:
    """Fetch all data from the given endpoint, paginating as needed."""
    out = []
    url = endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    while url:
        response = requests.get(url=url, headers=headers, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logging.error(
                "Backend error when getting data from %s: %s", url, response.text
            )
            raise
        data = response.json()
        for result in data["results"]:
            obj = {"id": result["id"], "name": result["name"]}
            try:
                # project description, optional
                if result["info"]["description"]:
                    obj["description"] = result["info"]["description"]
            except KeyError:
                pass
            out.append(obj)
        url = data.get("next")
    return out


def get_organizations(*, config: dict[str, str], access_token: str) -> list[dict]:
    endpoint = urljoin(config["scrapy_cloud_base_url"], ORGANIZATIONS_PATH)
    return _get_paginated_data(access_token=access_token, endpoint=endpoint)


def get_projects(*, config: dict[str, str], access_token: str) -> list[dict]:
    endpoint = urljoin(config["scrapy_cloud_base_url"], PROJECTS_PATH)
    return _get_paginated_data(access_token=access_token, endpoint=endpoint)


def get_zyte_api_apikey_metadata(
    *, config: dict[str, str], access_token: str, org_ids: list[int]
) -> dict:
    """Get metadata about Zyte API keys for the given organization IDs.

    Returns a dict mapping org ID to a list of API keys, where each key is a dict with `id`,
    `name`, and `url` (download URL for the key, resolved from the API) fields. No actual key
    values are returned.
    """
    base_url = config["scrapy_cloud_base_url"]
    list_endpoint = urljoin(base_url, ZYTE_API_LIST_PATH)
    apikey_endpoint = urljoin(base_url, ZYTE_APIKEY_PATH)
    creds = {}
    for org_id in org_ids:
        endpoint = list_endpoint.format(org_id=org_id)
        if result := _get_paginated_data(access_token=access_token, endpoint=endpoint):
            for item in result:
                item["url"] = apikey_endpoint.format(org_id=org_id, key_id=item["id"])
            creds[org_id] = result
    return creds


def get_shub_apikey(*, config: dict[str, str], access_token: str) -> str:
    """Get the Scrapy Cloud API key for the authenticated user.

    The key value is returned as a string, not printed, logged or stored.
    """
    endpoint = urljoin(config["scrapy_cloud_base_url"], SHUB_APIKEY_PATH)
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url=endpoint, headers=headers, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logging.error("Backend error when getting SHUB_APIKEY: %s", response.text)
        raise
    return response.text


def save_file(data: str, path: Path) -> Path:
    with path.open("w", encoding="utf-8") as fp:
        fp.write(data)
    logging.info("Saved data to %s", path)
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use the production environment (default: staging).",
    )
    args = parser.parse_args()

    env = "production" if args.production else "staging"
    config = AUTH_CONFIG[env]
    logging.info("Using %s environment", env)

    # start local server to receive OAuth callback
    logging.info("Starting localhost callback server")
    server_thread = threading.Thread(
        target=lambda: wsgi_serve(app, host=args.host, port=args.port),
        daemon=True,  # stop server when main thread exits
    )
    server_thread.start()
    time.sleep(0.5)  # give waitress a moment to bind

    # build URL and open browser for user authentication
    redirect_uri = f"http://{args.host}:{args.port}{CALLBACK_PATH}"
    logging.info("Using redirect URI: %s", redirect_uri)
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    auth_url = build_authorize_url(
        config=config,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
    )
    # ZYTE_OAUTH_TEST_MODE keeps an automated run off the desktop: the
    # authorization URL is logged instead of opened, and the callback wait drops
    # to zero, so the run reaches the same timeout as a run where nobody
    # completes login, without sitting out the full wait or leaving a browser
    # tab behind. Never set it in production use.
    test_mode = bool(os.environ.get("ZYTE_OAUTH_TEST_MODE"))

    if test_mode:
        logging.info(f"Test mode, not opening a browser. Authorize at: {auth_url}")
    else:
        logging.info("Opening browser for authentication")
        webbrowser.open(auth_url)

    logging.info("Waiting for OAuth callback")

    callback_timeout = 0 if test_mode else CALLBACK_TIMEOUT_SECONDS

    if not callback_received.wait(timeout=callback_timeout):
        raise SystemExit("Authentication timed out")

    if oauth_result["state"] != state:
        raise SystemExit("OAuth state mismatch")

    logging.info("Received authorization code")

    # get session token from authorization code
    token_response = exchange_code_for_token(
        config=config,
        code=oauth_result["code"],
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
    )
    logging.info("Successfully exchanged session token")

    # get project & organization lists, save them to a file
    organizations = get_organizations(
        config=config, access_token=token_response["access_token"]
    )
    zyte_apikeys = get_zyte_api_apikey_metadata(
        config=config,
        access_token=token_response["access_token"],
        org_ids=[org["id"] for org in organizations],
    )
    data = {
        "projects": get_projects(
            config=config, access_token=token_response["access_token"]
        ),
        "zyte_apikeys_by_org": zyte_apikeys,
    }
    save_file(json.dumps(data, indent=2), Path.home() / ".zyte_projects_and_keys.json")

    # get Scrapy Cloud apikey, store it in the project .env file
    shub_apikey = get_shub_apikey(
        config=config, access_token=token_response["access_token"]
    )
    set_var("SHUB_APIKEY", shub_apikey.strip())
    logging.info("Saved SHUB_APIKEY to %s", ENV_FILE)

    logging.info("Authentication complete")


if __name__ == "__main__":
    main()
