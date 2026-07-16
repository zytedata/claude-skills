---
name: scrape-zyte-login
description: Set up the user's Zyte account and credentials. Use when the user asks to set up, log in, sign up, or get an API key for Zyte; when ZYTE_API_KEY is missing; when a site is blocked; or before Scrapy Cloud deployment.
allowed-tools: Bash
---

API keys must never appear in the transcript. Do not echo, read, or write key values directly.

`SHUB_APIKEY` and `ZYTE_API_KEY` are persisted in the project's `.env` file. Keep `.env` out of version control.

### 1. Check credentials

Report whether each key is set in the environment or stored in `.env` (do not export anything):

```bash
{ [ -n "$ZYTE_API_KEY" ] || grep -q '^ZYTE_API_KEY=' .env 2>/dev/null; } && echo "ZYTE_API_KEY: present" || echo "ZYTE_API_KEY: missing"
{ [ -n "$SHUB_APIKEY" ] || grep -q '^SHUB_APIKEY=' .env 2>/dev/null; } && echo "SHUB_APIKEY: present" || echo "SHUB_APIKEY: missing"
```

If both are present, proceed to step 3.

### 2. Run OAuth setup flow

Tell the user:

> I'm starting the Zyte OAuth setup flow in your browser. Please complete login/consent there.

Run the OAuth flow script:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/oauth.py --production
```

The script stores `SHUB_APIKEY` directly in `.env` (the value is never printed) and saves a projects-and-keys file. Its output includes lines like `Saved data to /path/to/file` and `Saved SHUB_APIKEY to .env`. Scan the output and identify the path for the projects-and-keys file.

Make sure `.env` stays out of version control:

```bash
grep -qxF '.env' .gitignore 2>/dev/null || echo '.env' >> .gitignore
```

### 3. Let user pick project and Zyte API key

From the projects-and-keys file found in step 2, list to the user:

- All available projects: `project id` and `project name`
- All available Zyte API keys: `apikey name` (never show key values)

Ask the user to choose exactly one project and one API key by name.

After the user picks an API key, resolve its download URL from the same file, download it, and store it in `.env` under `ZYTE_API_KEY`, replacing any existing entry. The value is never printed to the terminal and is not exported to the shell (`SHUB_APIKEY` is read from `.env`).

The wrapper script prints the HTTP status code on its first line and the response body on the rest. The command below guards against writing a failed response (e.g. an auth error body) into `.env` as if it were a key: it saves the key only when the status is `200`, and otherwise prints the server response so you can report the failure to the user (the key value is never printed):

```bash
OUT="$(uv run ${CLAUDE_SKILL_DIR}/../scrape-scrapy-cloud/scripts/scrapy_cloud_api.py GET $URL)"
if [ "$(printf '%s\n' "$OUT" | head -n1)" = "200" ]; then
  { grep -v '^ZYTE_API_KEY=' .env 2>/dev/null; printf 'ZYTE_API_KEY=%s\n' "$(printf '%s\n' "$OUT" | tail -n +2)"; } > .env.tmp && mv .env.tmp .env
  echo "ZYTE_API_KEY stored in .env"
else
  echo "Failed to download Zyte API key; .env left unchanged. Server response:"
  printf '%s\n' "$OUT"
fi
```

If it reports a failure, do not proceed; the most common cause is a missing or unresolved `SHUB_APIKEY` (needs `shub>=2.18.1`, which reads it from `.env`).

Cleanup the projects-and-keys file after reading:

```bash
rm /path/to/projects-and-keys.json
```

### 4. Save selected project ID

If the user selected a project ID in step 3, save it:

```bash
mkdir -p .scrape/.zyte
echo "PROJECT_ID" > .scrape/.zyte/project-id
```

If no project was selected, skip. Tell the user: "Zyte credentials are active."

Return to the caller:
```
Zyte setup complete:
  ZYTE_API_KEY: present
  SHUB_APIKEY: present
  Project ID: 12345 (or not saved)
```
