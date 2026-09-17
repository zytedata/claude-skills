This file is 90 lines long; read all of them.

# Viewing items and logs

Direct the user to the Scrapy Cloud web UI to inspect items and logs, or fetch
them through the HTTP API. Read `scrapy-cloud.md` for the API wrapper script and
environment variables.

Derive the **web UI base URL** from `SCRAPY_CLOUD_ENDPOINT` by stripping the
trailing `/api/` path (default: `https://app.zyte.com`).

### Items page

Give the user the link, for them to open:

```
WEB_UI_BASE_URL/p/PROJECT_ID/SPIDER_ID/JOB_ID/items
```

### Item stats (HTTP API)

For a quick summary of item counts and field coverage without downloading all
items, use the stats endpoint directly:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage items/PROJECT_ID/SPIDER_ID/JOB_ID/stats
# Response: {"counts":{"field1":9350,"field2":514},"totals":{"input_bytes":14390294,"input_values":10000}}
```

Response fields:

| Field               | Description                                |
|---------------------|--------------------------------------------|
| `counts[field]`     | Number of times each field was populated.  |
| `totals.input_bytes`| Total size of all items in bytes.          |
| `totals.input_values` | Total number of items.                   |

### Downloading items (HTTP API)

To read the items themselves, fetch them from the storage API through the
wrapper script (never `curl` — the wrapper keeps credentials out of the
trajectory). The default response format is JSON Lines, one item per line:

```bash
# All items
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage items/PROJECT_ID/SPIDER_ID/JOB_ID

# A bounded sample (recommended for spot-checks)
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage items/PROJECT_ID/SPIDER_ID/JOB_ID -q count=5

# Specific items by index (repeat -q index=N for each)
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage items/PROJECT_ID/SPIDER_ID/JOB_ID -q index=0 -q index=1
```

For anything beyond a quick look, redirect to a file and search that file. For
pagination (`start`, `startafter`), field filtering, gzip, and other formats
(`-q format=json`), see the items API docs linked below.

### Log page

```
WEB_UI_BASE_URL/p/PROJECT_ID/SPIDER_ID/JOB_ID/log
```

### Log levels

Logs returned by the HTTP API include a numeric `level` field:

| Value | Level    |
|-------|----------|
| 10    | DEBUG    |
| 20    | INFO     |
| 30    | WARNING  |
| 40    | ERROR    |
| 50    | CRITICAL |

Each log entry is a JSON object with fields: `time` (Unix ms), `level`, and `message`.

### Reference docs

The Scrapy Cloud docs are available as Markdown (swap `.html` → `.md`). Prefer
fetching these over guessing at API mechanics — they cover the exhaustive set
of parameters, formats, and fields:

- **Get started (entry point)**: https://docs.zyte.com/scrapy-cloud/get-started.md
- **Items API**: https://docs.zyte.com/scrapy-cloud/usage/reference/http/items.md
- **Logs API**: https://docs.zyte.com/scrapy-cloud/usage/reference/http/logs.md
- **Jobs API** (fields, filters, scheduling): https://docs.zyte.com/scrapy-cloud/usage/reference/http/jobs.md
- **Periodic Jobs API** (cron-scheduled jobs): https://docs.zyte.com/scrapy-cloud/usage/reference/http/periodicjobs.md
- **Common HTTP params** (formats, pagination, gzip, field filtering): https://docs.zyte.com/scrapy-cloud/usage/reference/http/index.md
