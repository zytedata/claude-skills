This file is 59 lines long; read all of them.

# Periodic (recurring) jobs

Scrapy Cloud can run a spider or script on a cron schedule. These are *periodic
jobs*, managed through their own HTTP API — not `shub schedule`, which starts a
single job now. Read `scrapy-cloud.md` for the API wrapper script and
environment variables.

A periodic job has a `cron` field (five fields: `minute hour day-of-month month
day-of-week`, accepting only single values or `*` — no ranges, steps, or lists;
`0 9 * * 1` means Mondays at 09:00), a `tasks` list (each with `name` — prefixed
`py:` for scripts — `priority` 0–4, and `spider_args` / `script_args`), plus
`addtags`, `description`, and `disabled` to pause it without deleting.

Manage them with the same wrapper script, under
`projects/PROJECT_ID/periodicjobs`:

```bash
# List a project's periodic jobs (paginated: {"count":N,"next":...,"results":[...]})
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET projects/PROJECT_ID/periodicjobs

# Retrieve one
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET projects/PROJECT_ID/periodicjobs/PERIODIC_JOB_ID

# Reschedule, or pause without deleting (PATCH; all fields optional)
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py PATCH projects/PROJECT_ID/periodicjobs/PERIODIC_JOB_ID -b cron="30 18 * * 2"
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py PATCH projects/PROJECT_ID/periodicjobs/PERIODIC_JOB_ID -b disabled:=true

# Delete
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py DELETE projects/PROJECT_ID/periodicjobs/PERIODIC_JOB_ID
```

Creating one (POST) needs a nested body, so write it to a `periodicjob.json`
file:

```json
{
  "cron": "0 14 * * 1",
  "tasks": [{"name": "SPIDER_NAME", "priority": 2, "spider_args": {"limit": "100"}}],
  "addtags": ["skill"],
  "disabled": false,
  "description": "Weekly crawl"
}
```

And pass it with `-j`:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py POST projects/PROJECT_ID/periodicjobs -j periodicjob.json
```

Creating, rescheduling, and deleting a periodic job changes what runs on the
user's account on an ongoing basis — confirm the schedule and spider with the
user before a POST, PATCH, or DELETE, and report back the periodic job's `id`
and next run.

Field reference and validation rules:
https://docs.zyte.com/scrapy-cloud/usage/reference/http/periodicjobs.md
