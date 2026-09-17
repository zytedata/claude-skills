This file is 94 lines long; read all of them.

# Waiting for and validating a job

A deploy or a schedule isn't done until the job has finished and its results
look right, so validation is the default tail of every run. The exception is a
user who opted out — "just schedule it", "don't wait for it", "no need to check
the results" — in which case the job link is the whole answer.

## Waiting

This polls the Jobs API with backoff until the job reaches a terminal state:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/wait_for_job.py PROJECT/SPIDER/JOB
```

`--poll-interval SECONDS` sets the initial gap (default 10, backing off to 60)
and `--max-wait SECONDS` how long to wait at all (default 1200). It blocks until
the job is done, which can take minutes. Give the call a `timeout` that covers the whole run, up to its 600000 ms maximum, and beyond that start it with `run_in_background` and read its output once the harness reports it finished. Progress goes to
stderr; stdout gets exactly one line at the end:

- `JOB_FINISHED {...job json...}` (exit 0) — the job is in a terminal state, and
  the JSON carries `state`, `close_reason`, `errors_count`, `items_scraped` and
  the rest of what validation starts from.
- `JOB_TIMEOUT {...last known job json...}` (exit 1) — still running when
  `--max-wait` elapsed. Waiting longer means re-running with a larger
  `--max-wait`; the user chooses between that and checking back later.

## Health

`close_reason` should be `"finished"`. `failed`, `cancelled` or an unexpected
`closespider_*` is worth investigating. `errors_count` is a signal rather than
proof — a `0` count means nothing if the log level suppressed errors.

Download the log once and search it locally; paginating the HTTP API line by
line over a log that runs to thousands of lines is far slower:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage logs/PROJECT/SPIDER/JOB > job.log.jl
```

Entries are `{"time": <unix-ms>, "level": <int>, "message": <str>}` — see the
log-level table and the logs API docs in `items-and-logs.md` — so `"level": ?(40|50)`
finds the ERROR and CRITICAL ones.

Projects using scrapy-zyte-api dump `scrapy-zyte-api/*` counters in the Scrapy
stats at close: success/error ratios, `429`s, `error_types/*`, bans. They often
explain a bad close reason or low coverage and are easy to misread; what each
one means is at
https://scrapy-zyte-api.readthedocs.io/en/latest/reference/stats.md

No DEBUG messages in the log means `LOG_LEVEL` is above DEBUG, and a job whose
problem isn't diagnosable from the available logs is worth re-running with
`LOG_LEVEL=DEBUG`. It can be set in code or in Scrapy Cloud's project/spider
settings; if setting it in code has no effect, cloud settings are overriding it,
and there is no public API to read or change those — only the user can, in the
dashboard.

## Data

The item stats endpoint (see `items-and-logs.md`) gives per-field population
counts without downloading every item: compare `counts[field]` against
`totals.input_values`. Which fields were expected comes from
`.scrape/{site}/{data-type}/spec.json` when the job is part of the `/scrape`
workflow (see `${CLAUDE_SKILL_DIR}/../scrape/references/extraction-spec.md`),
and otherwise from the item or page-object class in the deployed project.

Any expected field at 0% coverage is a finding. For fields in between, download
a few items missing the field and judge whether it is legitimately absent or an
extraction bug.

Coverage says nothing about whether the right things were scraped, so also read
a small sample:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/scrapy_cloud_api.py GET --storage items/PROJECT/SPIDER/JOB -q count=5
```

Do the sampled items match what the user asked for — the right categories,
filters, product types, judged against the spec's schema, examples and start
URLs, or against the conversation? This is a judgment call, not a scripted
assertion.

## Reporting and fixing

The summary is the job link, `close_reason`, error count, a short field-coverage
table, and the verdict on the sample.

A finding — errors, low coverage, wrong-category items — is fixed in the project
code, then redeployed (`uvx shub deploy`), rescheduled and re-validated. Cap that
at 3 attempts, matching the local validation loop in `scrapy-extra`; past that,
report
what remains broken instead of looping.
