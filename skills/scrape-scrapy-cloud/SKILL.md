---
name: scrape-scrapy-cloud
description: General-purpose Scrapy Cloud skill — deploy projects, schedule spiders, list/stop jobs, and view items or logs. Use when asked to deploy a project or spider to Scrapy Cloud / Zyte Cloud / Scrapinghub, schedule or run a spider remotely, manage jobs, or inspect scraped items and logs.
argument-hint: "[project-dir]"
allowed-tools: Bash, Read, Write, WebFetch
---

You are a general-purpose Scrapy Cloud assistant. You can deploy projects, schedule
spiders, manage jobs (list, stop), and direct users to the web UI to inspect items
and logs — all using `shub` and the Scrapy Cloud HTTP API.

Read `python-environments.md` and `docs-access.md` from `${CLAUDE_SKILL_DIR}/../scrape/references`.

## Rules

- **DO NOT prematurely ask the user** for project ID, endpoint, credentials, or deployment
  target. All of these are discovered by following the Process steps below
  (checking `scrapinghub.yml`, `~/.scrapinghub.yml`, and environment variables).
- **Execute the Process steps sequentially** — only ask the user when a step
  explicitly says to.
- If the user's open file or current directory contains a `scrapinghub.yml`,
  use it to determine which project to deploy.

## Input

The raw argument string is `$ARGUMENTS` — use it as-is, treat empty as "no argument given":

1. **project_dir**: path to the Scrapy project directory (defaults to current directory if the argument string is empty)

## Process

**IMPORTANT**: It's critical that API keys are not displayed or exposed to the agent or user during a session.
Do not use any tool that might print the key or its value (e.g. `cat ~/.scrapinghub.yml`) as an auth probe.

### 1. Locate the project root

Navigate to `project_dir` (or the current directory if none was given). Confirm `scrapy.cfg` exists:

```bash
ls scrapy.cfg
```

If `scrapy.cfg` is not in the current directory, walk up the directory tree to find it. Once found, `cd` into that directory — all subsequent commands must run from there.

### 2. Check for existing scrapinghub.yml

```bash
ls scrapinghub.yml 2>/dev/null || echo "(not found)"
```

If the file exists skip step 3 and proceed directly to step 4.

### 3. Create scrapinghub.yml

**Get the project ID**

Check for a saved project ID from a previous `scrape-zyte-login`:

```bash
cat .scrape/.zyte/project-id 2>/dev/null || echo "(not set)"
```

If present, use it and skip asking.

Otherwise, open the Zyte projects page:

```bash
xdg-open "https://app.zyte.com/o/projects/" 2>/dev/null || open "https://app.zyte.com/o/projects/"
```

Ask the user:
```
Please open https://app.zyte.com/o/projects/ and provide the numeric project ID
for this spider (e.g. 12345). If you don't have a project yet, create one first.
```

Wait for the user to supply a numeric project ID.

**Prepare requirements**

If `requirements.txt` already exists, use it as-is.

Otherwise, look for a dependency specification in the project (any standard file where Python dependencies are declared). If one is found, generate a freeze `requirements.txt` (all packages pinned with `==`) from it by automatic means. If none is found, inspect the project source files to identify third-party packages, write a non-freeze dependency specification file listing them, then generate a freeze `requirements.txt` from that file by automatic means.

In all cases, `scrapinghub.yml` points at `requirements.txt`.

If `requirements.txt` did not exist before, tell the user the exact command used to generate it, and what to run when dependencies change or they wish to upgrade them.

**Specify a Scrapy stack**

Use the Docker Hub API or scrape the tags page to find the most recent stack tag for the `scrapinghub/scrapinghub-stack-scrapy` repository that matches the Scrapy version in the requirements file:

* API endpoint: `https://hub.docker.com/v2/repositories/scrapinghub/scrapinghub-stack-scrapy/tags`
* Web page: `https://hub.docker.com/r/scrapinghub/scrapinghub-stack-scrapy/tags`

Tags follow the format `{VERSION}-{YYYYMMDD}` (e.g. `2.14-20260326`). Select the tag with the highest version number and, among equal versions, the latest frozen date. Use that tag as the `stack` value in `scrapinghub.yml`, prefixed with `scrapy:` (e.g. `scrapy:2.14-20260326`).
If the requirements file doesn't specify a Scrapy version, or no stack tag matches the version it specifies, use the latest tag overall.

**Write scrapinghub.yml**

Create the file. If `SCRAPY_CLOUD_ENDPOINT` is set, add an `endpoint:` key.

```yaml
project: 12345

stack: scrapy:2.14-20260326  # replace with the latest tag fetched above

requirements:
  file: requirements.txt

endpoint: https://app-staging.zyte.com/api/  # include when SCRAPY_CLOUD_ENDPOINT is set
```

### 4. Deploy

Run the deploy from the project root with `uvx`, which fetches `shub` on
demand — no separate install step, and it works whether or not `shub` is
already on `PATH`:

```bash
uvx shub deploy
```

Stream and display the full output. A successful deploy looks like:

```
Packing version 3af023e-master
Deploying to Scrapy Cloud project "12345"
{"status": "ok", "project": 12345, "version": "3af023e-master", "spiders": 2}
Run your spiders at: https://app.zyte.com/p/12345/
```

**On failure**, diagnose the error and fix before retrying:

- `Error: Not logged in. Please run 'shub login' first.` → not authenticated; invoke `/scrape-zyte-login`.
- `Error: Invalid value for target: Please specify target or configure a default target in scrapinghub.yml.` → no project ID configured; ask the user for a project ID, update `scrapinghub.yml` and retry.
- `Authentication error` / `403` → API key is wrong or missing; invoke `/scrape-zyte-login`.
- `Project N does not exist` → wrong project ID; correct `scrapinghub.yml` and retry.
- `Could not find requirements file` → the `requirements.file` path in `scrapinghub.yml` is wrong; fix the path and retry.
- `No module named scrapy` or build errors → a dependency is missing or incompatible with the selected stack; update the requirements file and retry.
- Any other error → show the full error message to the user and ask how to proceed.

### 5. Report success

Tell the user the deploy succeeded, and include the version, spider count,
and project link (https://app.zyte.com/p/<project>/).

If the stack's Scrapy version is older than the version in `requirements.txt`, strongly recommend running a test job, and note that if issues arise, stack incompatibility is a possible — not assumed — root cause.

---

## Scheduling a job

Use `uvx shub schedule` to start a job that runs a spider on Scrapy Cloud
without redeploying.

Tag jobs with `skill`.

### Basic schedule

```bash
uvx shub schedule SPIDER --tag skill
```

On success, shub prints the job ID and convenience links:

```
Spider myspider scheduled, job ID: 12345/2/15
Watch the log on the command line:
    shub log -f 2/15
or watch it running in Zyte's web interface:
    https://app.zyte.com/p/12345/job/2/15
```

### With spider arguments (`-a`)

Repeat `-a KEY=VALUE` for each argument:

```bash
uvx shub schedule myspider -a ARG1=VALUE1 -a ARG2=VALUE2 --tag skill
```

### With job-specific Scrapy settings (`-s`)

```bash
uvx shub schedule myspider -s LOG_LEVEL=DEBUG -s CLOSESPIDER_PAGECOUNT=10 --tag skill
```

### With a specific project

```bash
uvx shub schedule 33333/myspider --tag skill
```

### With units and priority

| Flag | Description                                    |
|------|------------------------------------------------|
| `-u` | Number of Scrapy Cloud units to use (1–6)      |
| `-p` | Job priority: 0 (lowest) to 4 (highest)        |

```bash
uvx shub schedule myspider -p 3 -u 3 --tag skill
```

### Combined example

```bash
uvx shub schedule myspider \
  -a start_url=https://example.com \
  -s LOG_LEVEL=DEBUG \
  -p 2 \
  -u 1 \
  --tag skill
```

---

## Managing jobs

Use the Scrapy Cloud Jobs HTTP API for listing and stopping jobs.

**Base URL**: `${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}`

### Wrapper script

**IMPORTANT** It is critical that API requests are made with the wrapper script at `scripts/scrapy_cloud_api.py`
which handles authentication without leaking credentials to the agent. Do not make API requests with `curl` or other
tools that might expose credentials.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py HTTP_METHOD API_URL [-q QUERY_ARG=VALUE]... [-b BODY_ARG=VALUE]...
```

With arbitrary query parameters (`-q`) and body parameters (`-b`) as needed per endpoint. See the script's help message for details.

### List jobs

```bash
# All running jobs
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET "${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}jobs/list.json" -q project=PROJECT_ID -q state=running

# Latest 3 finished jobs for a specific spider
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET "${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}jobs/list.json" -q project=PROJECT_ID -q spider=SPIDER_NAME -q state=finished -q count=3

# Jobs that lack the "consumed" tag
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET "${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}jobs/list.json" -q project=PROJECT_ID -q lacks_tag=consumed
```

Available `state` values: `pending`, `running`, `finished`, `deleted`.
Available filter parameters: `job`, `spider`, `state`, `has_tag`, `lacks_tag`, `count`.

### Stop a job

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py POST "${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}jobs/stop.json" -b project=PROJECT_ID -b job=PROJECT_ID/SPIDER_ID/JOB_ID
```

---

## Viewing items and logs

Direct the user to the Scrapy Cloud web UI to inspect items and logs.

Derive the **web UI base URL** from `SCRAPY_CLOUD_ENDPOINT` by stripping the
trailing `/api/` path (default: `https://app.zyte.com`).

### Items page

```
${SCRAPY_CLOUD_ENDPOINT%api/}p/PROJECT_ID/SPIDER_ID/JOB_ID/items
```

Open with:

```bash
BASE_UI="${SCRAPY_CLOUD_ENDPOINT%api/}"
xdg-open "${BASE_UI:-https://app.zyte.com/}p/PROJECT_ID/SPIDER_ID/JOB_ID/items" 2>/dev/null \
  || open "${BASE_UI:-https://app.zyte.com/}p/PROJECT_ID/SPIDER_ID/JOB_ID/items"
```

### Item stats (HTTP API)

For a quick summary of item counts and field coverage without downloading all
items, use the stats endpoint directly:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET "${SCRAPY_CLOUD_ENDPOINT:-https://app.zyte.com/api/}items/PROJECT_ID/SPIDER_ID/JOB_ID/stats"
# Response: {"counts":{"field1":9350,"field2":514},"totals":{"input_bytes":14390294,"input_values":10000}}
```

Response fields:

| Field               | Description                                |
|---------------------|--------------------------------------------|
| `counts[field]`     | Number of times each field was populated.  |
| `totals.input_bytes`| Total size of all items in bytes.          |
| `totals.input_values` | Total number of items.                   |

### Log page

```
${SCRAPY_CLOUD_ENDPOINT%api/}p/PROJECT_ID/SPIDER_ID/JOB_ID/log
```

Open with:

```bash
BASE_UI="${SCRAPY_CLOUD_ENDPOINT%api/}"
xdg-open "${BASE_UI:-https://app.zyte.com/}p/PROJECT_ID/SPIDER_ID/JOB_ID/log" 2>/dev/null \
  || open "${BASE_UI:-https://app.zyte.com/}p/PROJECT_ID/SPIDER_ID/JOB_ID/log"
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

### Advanced programmatic access

For bulk downloads, pagination, field filtering, and format options (JSON, JSON
Lines), refer to the HTTP API documentation:

- **Items**: https://docs.zyte.com/scrapy-cloud/usage/reference/http/items.md
- **Logs**: https://docs.zyte.com/scrapy-cloud/usage/reference/http/logs.md

---

## When to Use

Invoke this skill when the user asks to:

- Deploy a Scrapy project or spider to the cloud
- Run a spider on Scrapy Cloud / Zyte Cloud / Scrapinghub Cloud
- Upload a project to Zyte / Scrapinghub
- Schedule a spider remotely (with arguments, settings, priority, or units)
- Push code to Scrapy Cloud
- List, filter, or inspect jobs
- Stop a running job
- View scraped items or logs for a job

Example phrases that should trigger this skill:

- "Deploy my project"
- "Deploy my spider to Scrapy Cloud"
- "I want to run my spider in the cloud"
- "How do I get my spider running on Scrapy Cloud?"
- "Upload my Scrapy project to Zyte"
- "Push my project to Zyte"
- "I want to schedule my spider remotely"
- "Schedule myspider on Scrapy Cloud"
- "List all running jobs"
- "Stop job 123/1/5"
- "Show items from job 123/1/5"
- "Show logs for job 123/1/5"

## Environment Variables

| Variable                         | Default                            | Description                                              |
|----------------------------------|------------------------------------|----------------------------------------------------------|
| `SHUB_APIKEY`                    | *(none)*                           | Scrapy Cloud API key; falls back to `~/.scrapinghub.yml` |
| `SCRAPY_CLOUD_ENDPOINT`          | `https://app.zyte.com/api/`        | Jobs API base URL (override for staging)                 |
| `SCRAPY_CLOUD_STORAGE_ENDPOINT`  | `https://storage.zyte.com/`        | Items/logs storage base URL (override for staging)       |

The **web UI base URL** is derived from `SCRAPY_CLOUD_ENDPOINT` by stripping the
trailing `/api/` path. For example:

- `https://app.zyte.com/api/` → `https://app.zyte.com`
- `https://app-staging.zyte.com/api/` → `https://app-staging.zyte.com`

---

## Common issues

| Symptom                                      | Cause                                        | Fix                                                     |
|----------------------------------------------|----------------------------------------------|---------------------------------------------------------|
| `Error: No such command` / `shub not found`  | `shub` invoked directly but not installed    | Invoke it as `uvx shub …` — fetched on demand, no install |
| `Authentication error` / `401`               | API key missing or invalid                   | Run `shub login` or set `$SHUB_APIKEY`                  |
| `403`                                        | API key lacks access to this project         | Verify the project ID and key permissions               |
| `Spider not found`                           | Spider name is wrong or project not deployed | Verify the spider name; deploy with `uvx shub deploy` first |
| `Project N does not exist`                   | Wrong project ID or alias                    | Check `scrapinghub.yml` or specify the correct ID       |
| `Could not find requirements file`           | Wrong path in `scrapinghub.yml`              | Fix the `requirements.file` path and redeploy           |
| `No module named scrapy` / build errors      | Dependency missing or wrong stack            | Update requirements file and redeploy                   |
| `sh_scrapy` errors in job logs               | Stack's `scrapinghub-entrypoint-scrapy` may not support the Scrapy version in `requirements.txt` | If a newer version of `scrapinghub-entrypoint-scrapy` exists on PyPI than the one bundled in the stack, add it to the dependency specification, regenerate `requirements.txt`, and redeploy |
