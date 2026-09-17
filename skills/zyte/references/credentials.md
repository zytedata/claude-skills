This file is 101 lines long; read all of them.

# Credentials & account setup

Zyte work needs two keys:

- `SHUB_APIKEY` — Scrapy Cloud: `shub`, the Scrapy Cloud HTTP API, and the
  organization lookup behind usage stats.
- `ZYTE_API_KEY` — Zyte API requests, including from spiders.

Both are persisted in the project's `.env`, which must stay out of version
control: read `.gitignore` and add a line for `.env` if none lists it.

A third thing worth having is the Scrapy Cloud project ID, saved as the only
content of `.scrape/.zyte/project-id` so deployment doesn't have to ask for it
later.

## What is already there

This prints one `present`/`missing` line per key, for both the environment and
`.env`, and never a value:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/env_keys.py
```

Both present means there is nothing to obtain — report and stop.

`SHUB_APIKEY` also resolves from `shub`'s own config, e.g. after `shub login`,
so a `missing` line for it is not conclusive. Since obtaining it opens a browser
tab, confirm with this probe first and treat it as present if the probe finds a
key:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" --check-key
```

Nothing here should ever be echoed, `cat`-ed or otherwise read for its value —
not `.env`, not `~/.scrapinghub.yml`.

## Obtaining the keys

One OAuth flow yields everything. It opens a browser tab for the user to log in
and consent, so let them know before running it:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/oauth.py --production
```

Run it exactly as written, once, in the foreground, whatever it prints.
**Never** run it a second time, in the background, or with an altered
environment (unsetting a variable, say): a second run starts a new server with a
new authorization URL, invalidating the one the user is already following, and
whatever the script reports is the outcome of the setup attempt, not a
configuration problem to work around.

On success it writes `SHUB_APIKEY` into `.env` (the value is never printed) and
saves a projects-and-keys file, printing lines like `Saved data to /path/to/file`
and `Saved SHUB_APIKEY to .env`. If it exits without saving those, setup is
incomplete: say so, say what would finish it — completing login in the browser,
or re-running setup somewhere a browser is available — and stop. Manual
credential or project configuration is not an alternative to offer.

## Picking a project and a Zyte API key

The projects-and-keys file lists the projects (`project id`, `project name`) and
Zyte API keys (`apikey name`) the account has. Show those to the user and let
them pick one of each; API key values never appear, only names.

The chosen key is then downloaded from its URL in that same file and stored
under `ZYTE_API_KEY`, replacing any existing entry. `--save-env` does that
safely — the response body lands in `.env` only on a `200`, so an auth-error
body can't be stored as if it were a key, and the value is never printed:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET DOWNLOAD_URL --save-env ZYTE_API_KEY
```

It prints the status, and either `ZYTE_API_KEY stored in .env` or the server
response, exiting non-zero and leaving `.env` untouched. A failure here is
usually an unresolved `SHUB_APIKEY`, meaning the OAuth flow did not complete or
did not write it — redo that, then retry rather than continuing.

Delete the projects-and-keys file once read:

```bash
rm /path/to/projects-and-keys.json
```

The chosen project ID goes to `.scrape/.zyte/project-id`.

## Reporting

Close with which keys are now present and the saved project ID, if any:

```
Zyte setup complete:
  ZYTE_API_KEY: present
  SHUB_APIKEY: present
  Project ID: 12345 (or not saved)
```
