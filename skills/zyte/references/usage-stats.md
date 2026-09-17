This file is 105 lines long; read all of them.

# Zyte API usage stats

Recorded historical Zyte API usage: cost, request volume, response times, status
codes. Also projections that extrapolate from it ("based on this month's usage
so far, project month-end spend"). Not what a spider, job or workload *might*,
*would* or *could* generate — those are hypothetical, with no recorded data to
query, even when the spider exists in the project. General how-to, explanatory
and documentation questions, dashboard and account topics included, are answered
from the docs instead.

Two bundled scripts do the work. Both resolve the Scrapy Cloud API key the way
`shub` does, so neither exposes a key value; `zyte_api_stats.py --check-key`
confirms auth is available without querying anything, and a missing key means
`credentials.md` (or `shub login`).

## Resolving the organization

Stats queries are scoped by `organization_id`, which is derived from the project
config rather than asked for. This helper reads project IDs from the standard
`shub` config — `scrapinghub.yml` in the project root, `~/.scrapinghub.yml`,
environment variables — and calls the Zyte project endpoint to map them to
organizations:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/project_org_lookup.py"
```

Its JSON `status` says what was found:

| Status | Meaning |
|--------|---------|
| `resolved_project_with_organization` | Use the returned `organization_id`. A `projects` list alongside it means several configured projects mapped to that same organization and were collapsed safely. |
| `multiple_projects_found` | Ambiguous. Let the user choose, from the `organizations` list when there is one, otherwise from the listed projects. |
| `no_project_configured`, `organization_lookup_failed` | Nothing to query. Follow `credentials.md`. |

Raw organization IDs and raw project IDs are never something to ask the user
for, or to offer as a fallback — the options presented are the ones the helper
discovered, shown by `organization_id` exactly as returned. If you cannot ask
interactive questions, list those same options in your reply and end the turn
there, waiting for the user to pick one. Keep each option's
`selection` value to yourself; it is what re-runs the helper once the user has
chosen:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/project_org_lookup.py" --project 2
```

Without a way to ask interactively, those same options go in the reply and the
turn ends there, waiting for the user to pick one.

Sending the user through `credentials.md` means waiting for them to complete
login in a browser, so that ends the turn: tell them to finish setup and ask for
the stats again, rather than retrying the query straight away. Finishing that
login is the only thing to ask for — never an "alternatively" where the user
supplies a project themselves, by typing an id, editing `scrapinghub.yml` or
writing `.scrape/.zyte/project-id` — and the stats wrapper stays uncalled,
`--check-key` included. When the flow does not complete, say so and stop there.

## Querying

Query parameters go in as a JSON object:

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" \
	--params '{"organization_id": 3}'
```

Build `--params` straight from the Stats API docs — the wrapper neither
translates nor validates parameter names. Supported parameters, filters,
grouping options and response fields are documented at
https://docs.zyte.com/zyte-api/usage/stats/index.md; only its `Reference`
section applies, the dashboard setup content does not.

```bash
uv run --no-project "${CLAUDE_SKILL_DIR}/scripts/zyte_api_stats.py" \
	--params '{"organization_id": 3, "start_time": "2026-03-01T00:00:00Z", "end_time": "2026-03-31T23:59:59Z", "page": 1, "groupby_time": "day", "extraction_type": "article", "extraction_from": "browserHtml"}'
```

An explicit relative window — `last 7 days`, `last 30 days`, `this month` —
becomes one concrete UTC `start_time`/`end_time` pair, computed in a single step
rather than through exploratory shell retries. A bare "recent" gets no dates at
all, so the API's own default range applies. `page`, `page_size` and
`total_result_count` in the response say whether more pages exist; fetching one
means incrementing `page` and leaving every other parameter alone.

## Reporting

The wrapper prints the raw Stats API JSON and nothing else, so the presentation
is yours to write — and everything in it has to come from that JSON. Cost
changes, response times and status-code mixes arrive without explanations
attached, so don't supply one: caching, article size, site availability and
outages are inferences the data does not carry. Status codes like `520` have
Zyte-specific meanings; the docs are where to look them up. `cost_microusd_*`
fields are micro-USD: 1 USD is 1,000,000 of them.

Every number describes the query that returned it, filters included. Results of
separate queries stay apart: a figure from a broader query — a cost, a request
count, a status-code tally — is never the narrower query's figure, nor a figure
for whatever the narrower filters named.

An empty `results` list is itself the answer. Say there was no data for that
query and stop, rather than going looking with wider windows or fewer filters;
different dates or filters are something to suggest, for the user to ask for.
