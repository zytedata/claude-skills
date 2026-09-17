This file is 77 lines long; read all of them.

# Scheduling and managing jobs

Start jobs on Scrapy Cloud with `shub`, and list or stop them through the Jobs
HTTP API. Read `scrapy-cloud.md` for the API wrapper script and environment
variables.

## Scheduling a job

Use `uvx shub schedule` to start a job that runs a spider on Scrapy Cloud
without redeploying. For a *recurring* schedule ("every day at 9", "weekly"),
use `periodic-jobs.md` instead.

Tag jobs with `skill`.

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

The spider name can be prefixed with a project ID to target a project other than
the configured one, and the run is tuned with these flags:

| Flag           | Description                                     |
|----------------|-------------------------------------------------|
| `-a KEY=VALUE` | Spider argument; repeat for each                |
| `-s KEY=VALUE` | Scrapy setting for this job only; repeat        |
| `-u`           | Number of Scrapy Cloud units to use (1–6)       |
| `-p`           | Job priority: 0 (lowest) to 4 (highest)         |

```bash
uvx shub schedule 33333/myspider \
  -a start_url=https://example.com \
  -s LOG_LEVEL=DEBUG \
  -p 2 \
  -u 1 \
  --tag skill
```

After scheduling, wait for the job and validate its results — see
`job-validation.md`.

## Managing jobs

Use the Scrapy Cloud Jobs HTTP API for listing and stopping jobs.

### List jobs

```bash
# All running jobs
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET jobs/list.json -q project=PROJECT_ID -q state=running

# Latest 3 finished jobs for a specific spider
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET jobs/list.json -q project=PROJECT_ID -q spider=SPIDER_NAME -q state=finished -q count=3

# Jobs that lack the "consumed" tag
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET jobs/list.json -q project=PROJECT_ID -q lacks_tag=consumed
```

Available `state` values: `pending`, `running`, `finished`, `deleted`.
Available filter parameters: `job`, `spider`, `state`, `has_tag`, `lacks_tag`, `count`.

### Stop a job

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py POST jobs/stop.json -b project=PROJECT_ID -b job=PROJECT_ID/SPIDER_ID/JOB_ID
```
