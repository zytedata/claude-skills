---
name: scrape-zyte-login
description: Set up the user's Zyte account and credentials. Use when the user asks to set up, log in, sign up, or get an API key for Zyte; when ZYTE_API_KEY is missing; when a site is blocked; or before Scrapy Cloud deployment.
allowed-tools: Bash
---

API keys must never appear in the transcript. Do not echo, read, or write key values directly.

Setup page: `${ZYTE_AGENT_SETUP_URL:-https://app.zyte.com/agent-setup}`

### 1. Check credentials

```bash
[ -n "$ZYTE_API_KEY" ] && echo "ZYTE_API_KEY: present" || echo "ZYTE_API_KEY: missing"
[ -n "$SHUB_APIKEY" ] && echo "SHUB_APIKEY: present" || echo "SHUB_APIKEY: missing"
```

If both are present, proceed to step 4.

### 2. Open the agent-setup page

Tell the user:

> I'm opening the Zyte agent setup page in your browser. Please sign up or log in, download and run the keys file using the command shown on the page for your OS, and note the Scrapy Cloud project ID.
>
> Once you're done, confirm here and provide the project ID.

```bash
open "${ZYTE_AGENT_SETUP_URL:-https://app.zyte.com/agent-setup}"
```

Run verbatim — let the shell expand the variable, don't substitute it yourself.

### 3. Verify credentials

Re-check presence:

```bash
[ -n "$ZYTE_API_KEY" ] && echo "ZYTE_API_KEY: present" || echo "ZYTE_API_KEY: missing"
[ -n "$SHUB_APIKEY" ] && echo "SHUB_APIKEY: present" || echo "SHUB_APIKEY: missing"
```

If either key is missing, ask the user for the path to the downloaded keys file. Load it based on the extension:

- `.ps1`: `powershell -File /path/to/zyte-keys.ps1`
- otherwise: `source /path/to/zyte-keys.txt`

Then re-check. Loop until both are present or the user cancels.

### 4. Save project ID

If the user provided a numeric project ID in their previous message, save it:

```bash
mkdir -p .scrape/.zyte
echo "PROJECT_ID" > .scrape/.zyte/project-id
```

If they did not provide one, skip. Tell the user: "Zyte credentials are active."

Return to the caller:
```
Zyte setup complete:
  ZYTE_API_KEY: present
  SHUB_APIKEY: present
  Project ID: 12345 (or not saved)
```
