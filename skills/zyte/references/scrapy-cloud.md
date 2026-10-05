This file is 26 lines long; read all of them.

# Scrapy Cloud environment and common issues

Shared mechanics for `shub`, read alongside `deployment.md` or
`bulk-export.md`.

## Environment variables

| Variable                         | Default                            | Description                                              |
|----------------------------------|------------------------------------|----------------------------------------------------------|
| `SHUB_APIKEY`                    | *(none)*                           | Scrapy Cloud API key; falls back to `~/.scrapinghub.yml` |
| `SCRAPY_CLOUD_ENDPOINT`          | `https://app.zyte.com/api/`        | Scrapy Cloud API base URL (override for staging)         |

## Common issues

| Symptom                                      | Cause                                        | Fix                                                     |
|----------------------------------------------|----------------------------------------------|---------------------------------------------------------|
| `Error: No such command` / `shub not found`  | `shub` invoked directly but not installed    | Invoke it as `uvx shub …` — fetched on demand, no install |
| `Error: Not logged in` / `Authentication error` / `401` | API key missing or invalid          | Follow `credentials.md`, then retry                     |
| `Invalid value for target`                   | No project ID in `scrapinghub.yml`           | Add one (see `deployment.md`) and retry                 |
| `403`                                        | API key lacks access to this project         | Verify the project ID and key permissions               |
| `Project N does not exist`                   | Wrong project ID or alias                    | Check `scrapinghub.yml` or specify the correct ID       |
| `Could not find requirements file`           | Wrong path in `scrapinghub.yml`              | Fix the `requirements.file` path and redeploy           |
| `No module named scrapy` / build errors      | Dependency missing or wrong stack            | Update requirements file and redeploy                   |
| `sh_scrapy` errors in job logs               | Stack's `scrapinghub-entrypoint-scrapy` may not support the Scrapy version in `requirements.txt` | If a newer version of `scrapinghub-entrypoint-scrapy` exists on PyPI than the one bundled in the stack, add it to the dependency specification, regenerate `requirements.txt`, and redeploy |
