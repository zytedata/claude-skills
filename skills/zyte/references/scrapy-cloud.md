This file is 72 lines long; read all of them.

# Scrapy Cloud HTTP API, environment, and common issues

Shared mechanics for every Scrapy Cloud operation. Read this alongside the
reference for the operation at hand (`deployment.md`, `jobs.md`,
`job-validation.md`, `periodic-jobs.md`, `items-and-logs.md`).

## Wrapper script

**IMPORTANT** It is critical that API requests are made with the wrapper script at `scripts/scrapy_cloud_api.py`
which handles authentication without leaking credentials to the agent. Do not make API requests with `curl` or other
tools that might expose credentials.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py HTTP_METHOD API_PATH [--storage] [-q QUERY_ARG=VALUE]... [-b BODY_ARG=VALUE|-b BODY_ARG:=JSON]...
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py HTTP_METHOD API_PATH -j BODY_JSON_FILE
```

With arbitrary query parameters (`-q`) and body parameters as needed per endpoint. See the script's help message for details.

`API_PATH` is a path, e.g. `jobs/list.json`. The script resolves it against the
Scrapy Cloud API base URL, or against the storage base URL when you pass
`--storage` (items and logs live there) — see "Environment variables" below for
both bases and their overrides.

Body values are typed:

- `-b KEY=VALUE` sends VALUE as a **string** (e.g. `-b cron="0 9 * * 1"`).
- `-b KEY:=JSON` sends VALUE as a **parsed JSON value** — use it for booleans,
  numbers, arrays, and objects (e.g. `-b disabled:=true`, `-b addtags:='["periodic"]'`).
- `-j PATH` sends the whole body from a JSON file. Prefer this for nested bodies
  (write the file first) — it avoids shell-quoting mistakes. `-j` and `-b` cannot
  be combined.

**Output format**: the script prints the HTTP status code on the first line,
then the response body on the remaining lines. Use the status line to detect
errors (e.g. `401`/`403` auth failures); when you only need the body, ignore
the first line. The response bodies shown in the other references omit the
leading status line.

## Environment variables

| Variable                         | Default                            | Description                                              |
|----------------------------------|------------------------------------|----------------------------------------------------------|
| `SHUB_APIKEY`                    | *(none)*                           | Scrapy Cloud API key; falls back to `~/.scrapinghub.yml` |
| `SCRAPY_CLOUD_ENDPOINT`          | `https://app.zyte.com/api/`        | Jobs API base URL (override for staging)                 |
| `SCRAPY_CLOUD_STORAGE_ENDPOINT`  | `https://storage.zyte.com/`        | Items/logs storage base URL (override for staging)       |

The **web UI base URL** is derived from `SCRAPY_CLOUD_ENDPOINT` by stripping the
trailing `/api/` path. For example:

- `https://app.zyte.com/api/` → `https://app.zyte.com`
- `https://app-staging.zyte.com/api/` → `https://app-staging.zyte.com`

## Common issues

| Symptom                                      | Cause                                        | Fix                                                     |
|----------------------------------------------|----------------------------------------------|---------------------------------------------------------|
| `Error: No such command` / `shub not found`  | `shub` invoked directly but not installed    | Invoke it as `uvx shub …` — fetched on demand, no install |
| `Error: Not logged in` / `Authentication error` / `401` | API key missing or invalid          | Follow `credentials.md`, then retry                     |
| `Invalid value for target`                   | No project ID in `scrapinghub.yml`           | Add one (see `deployment.md`) and retry                 |
| `403`                                        | API key lacks access to this project         | Verify the project ID and key permissions               |
| `Spider not found`                           | Spider name is wrong or project not deployed | Verify the spider name; deploy with `uvx shub deploy` first |
| `Project N does not exist`                   | Wrong project ID or alias                    | Check `scrapinghub.yml` or specify the correct ID       |
| `Could not find requirements file`           | Wrong path in `scrapinghub.yml`              | Fix the `requirements.file` path and redeploy           |
| `No module named scrapy` / build errors      | Dependency missing or wrong stack            | Update requirements file and redeploy                   |
| `sh_scrapy` errors in job logs               | Stack's `scrapinghub-entrypoint-scrapy` may not support the Scrapy version in `requirements.txt` | If a newer version of `scrapinghub-entrypoint-scrapy` exists on PyPI than the one bundled in the stack, add it to the dependency specification, regenerate `requirements.txt`, and redeploy |
| `close_reason` is not `finished`             | Job failed, was cancelled, or hit a `closespider_*` limit | Read the logs (filter `level >= 40`); fix the root cause and reschedule. See `job-validation.md` |
| A field has 0% or unexpectedly low coverage  | Broken/incorrect selector in the page object | Inspect the item stats and a sample of items, fix the page object, redeploy, and re-run. See `job-validation.md` |
| `cron: Expected 5 space-separated fields` / cron rejected | Periodic job `cron` uses a range, step, or list (e.g. `*/15`, `1-5`) | Use single values or `*` only; split multiple times across separate periodic jobs |
| `tasks: This field is required` on POST      | Periodic job created without a `tasks` list, or the body was sent as flat strings | Write the full JSON body to a file and pass it with `-j` (see `periodic-jobs.md`) |
