This file is 234 lines long; read all of them.

# Explore a website

You are exploring a website to discover and save a diverse set of pages. Given a start URL, find start, list/category, and detail pages within its scope.

This document is followed by the `scrape-plan` skill — inline by the main agent for a minimal initial pass, or by a spawned subagent for a full exploration.

This document lives in the skill's `references/` directory, so `${CLAUDE_SKILL_DIR}` is the parent of this document's directory.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

The invoking prompt provides:

1. **url**: start URL, typically homepage
2. **project_path**: path to save output
3. **DETAIL_COUNT**: number of detail pages to find (default: 3)
4. **LIST_COUNT**: number of list/category pages to save (default: 2)

The start page is always saved.

## Reusing an existing exploration

`{project_path}` may already contain pages from an earlier run (e.g. an initial single-page exploration). Do not delete or re-download them: reuse the saved start page and its `links.json`, count existing list/detail pages toward `LIST_COUNT`/`DETAIL_COUNT`, and download only what is missing. Continue numbering after the highest existing page of each type. Re-extract and re-classify the start page's links (from the saved HTML) only if `links.json` is missing, or if it holds too few links to pick diverse pages for the current counts (an earlier run may have used a lower `--link-limit`).

## Scope

Treat the start URL as the scope root:
- Site root: explore broadly across categories.
- Category/list page: stay within that subtree. Follow pagination and deeper subcategories in scope, but do not widen to sibling or parent categories.

## Tools

### download.py — capture pages (HTTP + Playwright)

```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/download.py <<'EOF'
[...]
EOF
```

Reads a JSON array of download tasks from stdin:
```json
[
  {"url": "...", "output_dir": "...", "page_type": "..."}
]
```

Creates `OUTPUT_DIR/{raw.html, rendered.html, meta.json}` for each task. Multiple tasks are downloaded in parallel. Logs are appended to `download.log` next to the task output dirs (`--log-file` overrides).

Expect minutes per call. It prints `Crawled N pages` to stderr every 15 seconds; half-filled page directories and log entries mid-run are normal. Give the call a `timeout` that covers the whole run, up to its 600000 ms maximum, and beyond that start it with `run_in_background` and read its output once the harness reports it finished. NEVER interrupt it, and NEVER start a second call while one is running.

NEVER download pages with a web fetch tool — it loads full HTML into context.
Use link groups and HTML structure for classification.

### extract_links.py — extract links

```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/extract_links.py PAGE.html [PAGE2.html ...] --base-url-from-meta --group --link-limit N
```

Outputs numbered JSON groups:
```
0: {"path": "article.product_pod > h3 > a", "count": 20, "links": [...], "file": "detail-1"}
1: {"path": "ul.nav > li > a", "count": 50, "links": [...], "file": "list-1"}
```

Pass `--link-limit` equal to `max(DETAIL_COUNT, LIST_COUNT)` with a minimum of 3. Examples: DETAIL_COUNT=1, LIST_COUNT=0 → `--link-limit 3`; DETAIL_COUNT=8, LIST_COUNT=4 → `--link-limit 8`. This limits output size while keeping enough examples for reliable classification.

Save output to a file for classification. Groups are numbered globally across input files, and each carries the `"file"` key that tells `apply_classification.py` which page directory it came from.

NEVER save stderr of this script, only stdout.

### apply_classification.py — classify and write links.json

After deciding which groups map to which types, apply the classification:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py GROUPS_FILE --classify "items=0 subCategories=1 nextPage=4" --pages-dir {pages_dir}
```

Reads the saved groups file and writes `links.json` into each source page's directory. The script writes those files itself.

### Choosing HTML for link extraction

`{variant}` in the commands below is `raw` or `rendered`. Prefer `raw`. Switch to `rendered` only if raw is missing or lacks the meaningful navigation links (e.g. a JS-rendered site whose raw HTML is essentially empty). Decide once on the start page — even when reusing an existing start-page classification, make this decision yourself — then use the same variant for every page and report the chosen variant in the summary.

## Classifying links

After step 1 (extract groups), classify each numbered group as one of:

- **items**: links to detail pages. Many links sharing the same path pattern, with unique IDs or slugs in URLs.
- **subCategories**: links to listing/category pages that narrow or refine the current page's topic. Groups receive one label, so every URL must qualify. Before applying this label, note the last URL in the group in your reasoning — if any URL in the group is off-topic for the current page, put the whole group in **skip** instead.
- **nextPage**: pagination links. Page numbers in URL or text, or "next"/"previous" text.
- **skip**: (omit from --classify) navigation, footer, account, header links, and off-topic category links.

Use all three signals: **path** (structural position), **href** (URL pattern), **text** (anchor text).

Then run `apply_classification.py` with `--classify "items=0,3 subCategories=1 nextPage=2"` to write the JSON files. Omit skip groups from the classify string.

## Output structure

All output goes under `{pages_dir}` which is `{project_path}/pages/`:
```
start-1/          — start page
  raw.html  rendered.html  meta.json  links.json
list-1/           — category/listing page (from start page)
list-2/           — sub-category page (from list-1, deeper navigation)
detail-1/         — item/article page
...
```

`links.json` is only there for pages whose links were classified.

## Handling blocked sites

Check both `raw.html` (HTTP) and `rendered.html` (Playwright) — they may behave differently. A site is only fully blocked if **both** return bot detection content (CAPTCHA, "verify you are human", 403, Cloudflare challenge). If raw is blocked but rendered works, proceed using rendered — this is fine.

When following this document inline (the main agent must not read HTML files), judge blocking from `meta.json` (`http_status`, `errors`) and the link-extraction output instead: a page with a normal status but no meaningful link groups is likely a challenge page.

If the start page is fully blocked (both raw and rendered), **stop immediately**. Report the block and return `"blocked": true` in your summary — do not attempt workarounds, retries, header changes, or alternative URLs. The caller will handle offering alternatives.

If the start page succeeds but later pages get blocked, continue with the pages that worked. Do not retry blocked URLs or try to circumvent the block.

When a block is detected on any page, add `"blocked": true` (or `"blocked": "raw"` if only HTTP is blocked) to that page's `meta.json`.

## Process

### 1. Download and classify the start page

Download:
```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/download.py <<'EOF'
[{"url": "URL", "output_dir": "{pages_dir}/start-1", "page_type": "start"}]
EOF
```

Extract links and save groups to a file (LIMIT = max(DETAIL_COUNT, LIST_COUNT, 3)):
```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/extract_links.py {pages_dir}/start-1/{variant}.html --base-url-from-meta --group --link-limit LIMIT > {pages_dir}/start-1/groups.txt
```

Read the groups, decide classification, then apply:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py {pages_dir}/start-1/groups.txt --classify "items=N subCategories=N nextPage=N" --pages-dir {pages_dir}/start-1
```

### 2. Download and classify list pages

Skip this step and step 3 if `LIST_COUNT` is 0.

From the start page's `subCategories` links, pick `LIST_COUNT` URLs:
- If the start page is the site root, prefer different categories.
- If it is already a category/list page, stay within that subtree. Prefer descendants; do not jump to sibling or parent categories.

Download all candidates in one call:
```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/download.py <<'EOF'
[
  {"url": "LIST_URL_1", "output_dir": "{pages_dir}/list-1", "page_type": "list"},
  {"url": "LIST_URL_2", "output_dir": "{pages_dir}/list-2", "page_type": "list"}
]
EOF
```

Extract links from ALL list pages in a single batch call and save groups (LIMIT = max(DETAIL_COUNT, LIST_COUNT, 3)):
```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/extract_links.py {pages_dir}/list-*/{variant}.html --group --base-url-from-meta --link-limit LIMIT > {pages_dir}/list-groups.txt
```

Read the numbered groups (each has a `"file"` key like `"list-1"`), classify them, then apply:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py {pages_dir}/list-groups.txt --classify "items=N,N subCategories=N,N nextPage=N" --pages-dir {pages_dir}
```

After classifying, check each page's `links.json`. A list page with no `items` likely indicates a link classification error — re-check its groups before moving on.

### 3. Follow sub-subcategories (deeper navigation)

Check if any list page has `subCategories` links pointing deeper into the current scope. If yes, and you still need more list pages to reach `LIST_COUNT`:

- Pick 1-2 diverse sub-subcategory URLs
- Download, classify them
- These become additional list pages

This gives depth without widening the crawl. Even if LIST_COUNT is already met, follow 1 deeper in-scope subcategory if available.

### 4. Select and download detail pages

Collect ALL `items` links from the start page and all list pages. Pick `DETAIL_COUNT` diverse candidates:
- Different IDs or slugs in URLs
- From different categories/list pages when possible
- Not variants of the same item (e.g., different colors/sizes)

Download all candidates in one call:
```bash
uv run --python 3.14 ${CLAUDE_SKILL_DIR}/scripts/download.py <<'EOF'
[
  {"url": "ITEM_URL_1", "output_dir": "{pages_dir}/detail-1", "page_type": "detail"},
  {"url": "ITEM_URL_2", "output_dir": "{pages_dir}/detail-2", "page_type": "detail"}
]
EOF
```

### 5. Clean up

Remove empty directories from failed downloads. Nothing else: the wider
`.scrape/.work/` tree is shared with the orchestrator and other concurrently
running agents — never delete their files or any of your own outputs.

### 6. Generate navigation values

After link classification, generate navigation values from `links.json` files:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/extract_nav_values.py {project_path}
```

This reads `links.json` + `meta.json` from each page in `{pages_dir}/` and writes navigation values to `{project_path}/values/`. Only pages with classified links get values files.

### 7. Return summary

```
Explored {domain}:
  start: 1 page
  list: N pages (target: LIST_COUNT)
  detail: N pages (target: DETAIL_COUNT)
  link extraction variant: raw|rendered

Pages saved to {pages_dir}/
```

If targets were not met, explain why. Also return the start page link classification for the caller: item count, subCategory count, and a few example URLs.
