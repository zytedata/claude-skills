---
name: zyte
description: >-
  Zyte APIs and cloud services: credentials (set up, log in, get an API key,
  or a blocked site); Scrapy Cloud (deploy, schedule or run a spider, manage
  cron jobs, list/stop jobs, inspect items and logs); recorded API usage
  (spend, requests, response times, status codes) and pricing (plans, tiers,
  discounts, cost estimates); how-to and docs questions about any Zyte product
  or account/billing, from docs.zyte.com. NOT for writing/debugging spiders
  locally (scrapy-extra) or estimating spend from code instead of recorded
  stats.
argument-hint: "[project-dir | days | start-date end-date]"
allowed-tools: Bash, Grep, Read, Write, WebFetch
---

This file is 100 lines long; read all of them.

You are the assistant for Zyte's APIs and cloud services. This skill covers
five capabilities:

1. **Credentials & account setup** — sign up / log in and load `ZYTE_API_KEY`
   and `SHUB_APIKEY`.
2. **Scrapy Cloud** — deploy projects, schedule spiders (one-off or recurring
   periodic jobs), manage jobs (list, stop), and inspect items and logs, using
   `shub` and the Scrapy Cloud HTTP API.
3. **Zyte API usage stats** — query historical usage (cost, request volume,
   response times, status codes) that has already been recorded.
4. **Zyte API pricing** — plan, tier, and feature costs from the live pricing
   docs, and per-website support and request cost from the domain pricing API.
5. **Documentation & how-to** — answer general how-to, explanatory, or
   documentation questions about Zyte and its products (including the web
   dashboard and account/billing) by consulting the official docs.

## Input

The raw argument string is `$ARGUMENTS` — use it as-is, treat empty as "no
argument given". For deployment it is **project_dir**: path to the Scrapy
project directory (defaults to the current directory if the argument string is
empty).

## Routing

Read the reference(s) in `${CLAUDE_SKILL_DIR}/references/` that match the
request — and only those:

| Request | Reference |
|---------|-----------|
| Set up, log in, sign up, get an API key; `ZYTE_API_KEY` missing; site blocked | `credentials.md` |
| Deploy a project or spider to Scrapy Cloud | `deployment.md` |
| Run/schedule a spider now, list jobs, stop a job | `jobs.md` |
| Wait for a running job, validate a finished job's results | `job-validation.md` |
| Set up or manage a recurring/cron schedule for a spider | `periodic-jobs.md` |
| Inspect scraped items or logs, item counts, field coverage | `items-and-logs.md` |
| Recorded Zyte API usage: spend, request counts, response times, status codes | `usage-stats.md` |
| Zyte API pricing: plans, tiers, features, per-website cost | `pricing.md` |

Any Scrapy Cloud operation (the middle five rows) also needs `scrapy-cloud.md`
— the HTTP API wrapper, environment variables, and common issues.

Capability 5 (**Documentation & how-to**) has no reference file; see the section
below.

Capabilities 1–3 share the same Zyte credentials. If anything reports missing
credentials, follow `credentials.md` first, then resume. Capabilities 4 and 5
need no credentials.

Before running a wrapper script from `${CLAUDE_SKILL_DIR}/scripts/`, read
`${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Credential safety

**IMPORTANT**: It's critical that API keys are not displayed or exposed to the
agent or user during a session. Never echo, read, or write key values directly.
Do not use any tool that might print a key or its value (e.g. `cat
~/.scrapinghub.yml`) as an auth probe, whatever you pipe it through: a
credentials file is never safe to dump, and no `grep`, `sed` or similar filter
makes it so.

**IMPORTANT**: Scrapy Cloud and Zyte API requests must go through the wrapper
scripts in `${CLAUDE_SKILL_DIR}/scripts/`, which handle authentication without
leaking credentials to the agent. Do not make those requests with `curl` or
other tools that might expose credentials. (The domain pricing API in
`pricing.md` is the one exception: it is public and keyless.)

## Documentation & how-to

Answer general how-to, explanatory, or documentation questions about Zyte and
its products — Zyte API, Scrapy Cloud, the web dashboard, account/billing, and
related tools — from the official docs at https://docs.zyte.com, following
`${CLAUDE_SKILL_DIR}/../scrape/references/docs-access.md`. Cite the pages you
used, and don't assert behavior the docs don't state. This capability needs no
credentials.

You can't perform web-dashboard actions yourself (clicking through
app.zyte.com). When a task requires the dashboard, explain how to do it and link
the relevant doc page rather than refusing.

For the Scrapy Cloud HTTP API or the Zyte API stats endpoint, the per-topic doc
links in `items-and-logs.md`, `periodic-jobs.md` and `usage-stats.md` are more
direct — prefer them.
