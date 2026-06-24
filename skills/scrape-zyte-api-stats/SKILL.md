---
name: scrape-zyte-api-stats
description: Query usage stats for Zyte API requests that have already been sent, including cost, request volume, response times, status codes, filters, grouping, and pagination. Use this skill when the user asks to query historical Zyte API usage, spend, request counts, response times, grouped stats, or filtered stats. Do not use it for dashboard setup, documentation, configuration, or account-help questions.
argument-hint: "[days|start-date end-date]"
allowed-tools: Bash
---

Query historical Zyte API usage stats using the wrapper bundled with this skill.
The bundled scripts handle auth, project lookup, and retries without exposing
API keys to the model. The stats wrapper returns the raw Stats API JSON
response; the agent is responsible for presenting that data to the user.

This skill is for querying historical usage that already happened, not for
forecasts, predictions, dashboard setup, documentation, or configuration help.

Always resolve `organization_id` by running the project lookup helper first:

1. Run the project lookup helper:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/project_org_lookup.py"
```

2. Read the JSON status and follow this branch logic:
	 - `resolved_project_with_organization`: use the returned `organization_id`
		 in the stats query. If the payload also includes a `projects` list, the
		 helper found multiple configured projects that all map to the same
		 organization and already collapsed them safely.
	 - `multiple_projects_found`: if the payload includes an `organizations`
		 list, ask the user to choose among those discovered safe organization
		 options, not by typing a raw organization id or project id. Each
		 organization option includes a representative `selection` value that you
		 can pass back to `--project` when rerunning the helper. If no
		 `organizations` list is present, fall back to the listed projects.
	 - `no_project_configured` or `organization_lookup_failed`: tell the user to
		 use the `scrape-zyte-login` skill to configure a project and credentials, then retry the
		 query. Do not offer a raw organization id or raw project id as a fallback
		 in these branches.

The project lookup helper reads project IDs from the standard `shub` config
(`scrapinghub.yml` in the project root, `~/.scrapinghub.yml`, or environment
variables) and calls the Zyte project endpoint to derive `organization_id`.
That is allowed for this skill. Do not read or print credential values
directly.

If the user chooses one of several discovered organization or project options,
rerun the helper with the corresponding `selection` or project value:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/project_org_lookup.py" --project 2
```

## Wrapper

Run the wrapper with `uv`, passing query parameters as a JSON object:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" \
	--params '{"organization_id": 3}'
```

Use `${CLAUDE_SKILL_DIR}` as provided by the skill runtime. Do not prefix the
same command with an inline `CLAUDE_SKILL_DIR=...` assignment, because the
script path may be expanded before that temporary assignment applies.

Build `--params` directly from the Stats API docs. The wrapper does not
translate or validate parameter names for you.

The wrapper prints the raw Stats API JSON object. Read it and format the result
for the user yourself. Keep user-facing claims grounded in the returned JSON.
Do not assume fields exist beyond what the API returned.

When the user specifies an explicit relative window such as `last 7 days`,
`last 30 days`, or `this month`, compute one concrete UTC `start_time` /
`end_time` pair and pass those values in `--params`. Keep that workflow simple:
prefer one concise computation step when needed, and avoid repeated exploratory
shell retries.

When the user asks for `recent` usage without specifying a window, omit
`start_time` and `end_time` entirely so the API's default range applies.

If the JSON response has an empty `results` list, tell the user there was no
data for that query instead of fabricating a summary.

Use API fields such as `page`, `page_size`, and `total_result_count` to decide
whether more pages exist. If you fetch another page, keep all other query
parameters unchanged and only increment `page`.

Base claims on the wrapper output. Do not add dates, causes, feature
interpretations, or other conclusions that the wrapper did not return as data.
Do not infer caching, article size, site availability, outage causes, or other
operational explanations from cost changes, response times, or status-code
mixes unless the JSON response explicitly supports that claim.

Status codes such as `520` carry Zyte-specific semantics. Do not relabel them
unless the response or docs explicitly do so.

Both scripts resolve the Scrapy Cloud API key via `shub`. Use `--check-key`
only when you need to confirm auth is available:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" --check-key
```

If the key is missing, tell the user to run `shub login` or use the `scrape-zyte-login` skill.

## Stats API Parameters

For supported parameters, filters, grouping options, and response fields, use the official docs:

- https://docs.zyte.com/zyte-api/usage/stats.md

Use only the `Reference` section; ignore dashboard setup content.

Example with filters and grouping:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" \
	--params '{"organization_id": 3, "start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-31T23:59:59Z", "page": 1, "groupby_time": "day", "extraction_type": "article", "extraction_from": "browserHtml"}'
```
