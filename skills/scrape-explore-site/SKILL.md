---
name: scrape-explore-site
description: Explore a website to find and save diverse pages (start, list, detail) with classified links
argument-hint: "[url] [project-path] [detail-count] [list-count]"
allowed-tools: Bash, Read, Write
---

You are exploring a website to discover and save a diverse set of pages. Given a start URL, find start, list/category, and detail pages within its scope.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into up to 4 whitespace-separated positional arguments:

1. **url**: start URL, typically homepage
2. **project_path**: path to save output
3. **DETAIL_COUNT**: number of detail pages to find (default: 3)
4. **LIST_COUNT**: number of list/category pages to save (default: 2)

The start page is always saved.

## Scope

Treat the start URL as the scope root:
- Site root: explore broadly across categories.
- Category/list page: stay within that subtree. Follow pagination and deeper subcategories in scope, but do not widen to sibling or parent categories.

Examples:
```
/scrape-explore-site https://example.com .scrape/myspec
  → DETAIL_COUNT=3, LIST_COUNT=2

/scrape-explore-site https://example.com dataset/site-slug 8 4
  → DETAIL_COUNT=8, LIST_COUNT=4
```

## Tools

### download.py — capture pages (HTTP + Playwright + screenshot)

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --log-file {pages_dir}/download.log <<'EOF'
[...]
EOF
```

Reads a JSON array of download tasks from stdin:
```json
[
  {"url": "...", "output_dir": "...", "page_type": "...",
   "discovered_from": {"page": "...", "url": "..."}}
]
```

Creates `OUTPUT_DIR/{raw.html, rendered.html, screenshot.png, meta.json}` for each task. Multiple tasks are downloaded in parallel. Log file is appended to across runs.

NEVER use WebFetch to download pages — it loads full HTML into context.
NEVER read screenshot.png files — they are saved for later use, not for exploration. Use link groups and HTML structure for classification.

### extract_links.py — extract links

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/extract_links.py PAGE.html [PAGE2.html ...] --base-url-from-meta --group --link-limit N
```

Outputs numbered JSON groups:
```
0: {"path": "article.product_pod > h3 > a", "count": 20, "links": [...]}
1: {"path": "ul.nav > li > a", "count": 50, "links": [...], "file": "list-1"}
```

You need to pass a value of `--link-limit` that is either `DETAIL_COUNT` or `LIST_COUNT`, whichever is higher. This is to limit the size of the output.

Save output to a file for classification. With multiple input files, groups are numbered globally and each has a `"file"` key.

NEVER save stderr of this script, only stdout.

### apply_classification.py — classify and write links.json

After deciding which groups map to which types, apply the classification:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py GROUPS_FILE --classify "items=0 subCategories=1 nextPage=4" --pages-dir {pages_dir}
```

Reads the saved groups file and writes `links.json` into each source page's directory. No need to use `Write` tool — the script writes the files directly.

### Choosing HTML for link extraction

Prefer `rendered.html` (handles JS-rendered sites). Fall back to `raw.html` if `rendered.html` doesn't exist.

## Classifying links

After step 1 (extract groups), classify each numbered group as one of:

- **items**: links to detail pages. Many links sharing the same path pattern, with unique IDs or slugs in URLs.
- **subCategories**: links to listing/category pages that narrow or refine the current page's topic. Groups receive one label, so every URL must qualify. Before applying this label, note the last URL in the group in your reasoning — if any URL in the group is off-topic for the current page, put the whole group in **skip** instead.
- **nextPage**: pagination links. Page numbers in URL or text, or "next"/"previous" text.
- **skip**: (omit from --classify) navigation, footer, account, header links, and off-topic category links.

Use all three signals: **path** (structural position), **href** (URL pattern), **text** (anchor text).

Then run `apply_classification.py` with `--classify "items=0,3 subCategories=1 nextPage=2"` to write the JSON files. Omit skip groups from the classify string.

## Backlinks

For every saved page (except the start page), include `discovered_from` in the task. This writes the backlink directly into meta.json at download time — no separate read/write step needed.

## Output structure

All output goes under `{pages_dir}` which is `{project_path}/pages/`:
```
start-1/          — start page
  raw.html  rendered.html  screenshot.png  meta.json  links.json
list-1/           — category/listing page (from start page)
list-2/           — sub-category page (from list-1, deeper navigation)
detail-1/         — item/article page
unknown-1/        — explored page that didn't fit list/detail (still kept)
...
```

Each page directory contains `raw.html`, `rendered.html`, `screenshot.png`, `meta.json`, and `links.json` (if links were classified for that page).

## Handling blocked sites

Check both `raw.html` (HTTP) and `rendered.html` (Playwright) — they may behave differently. A site is only fully blocked if **both** return bot detection content (CAPTCHA, "verify you are human", 403, Cloudflare challenge). If raw is blocked but rendered works, proceed using rendered — this is fine.

If the start page is fully blocked (both raw and rendered), **stop immediately**. Report the block and return `"blocked": true` in your summary — do not attempt workarounds, retries, header changes, or alternative URLs. The caller will handle offering alternatives.

If the start page succeeds but later pages get blocked, continue with the pages that worked. Do not retry blocked URLs or try to circumvent the block.

When a block is detected on any page, add `"blocked": true` (or `"blocked": "raw"` if only HTTP is blocked) to that page's `meta.json`.

## Process

### 1. Download and classify the start page

Download:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --log-file {pages_dir}/download.log <<'EOF'
[{"url": "URL", "output_dir": "{pages_dir}/start-1", "page_type": "start"}]
EOF
```

Extract links and save groups to a file:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/extract_links.py {pages_dir}/start-1/rendered.html --base-url-from-meta --group > {pages_dir}/start-1/groups.txt
```

Read the groups, decide classification, then apply:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py {pages_dir}/start-1/groups.txt --classify "items=N subCategories=N nextPage=N" --pages-dir {pages_dir}/start-1
```

### 2. Download and classify list pages

From the start page's `subCategories` links, pick `LIST_COUNT` URLs:
- If the start page is the site root, prefer different categories.
- If it is already a category/list page, stay within that subtree. Prefer descendants; do not jump to sibling or parent categories.

Download all candidates in one call:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --log-file {pages_dir}/download.log <<'EOF'
[
  {"url": "LIST_URL_1", "output_dir": "{pages_dir}/list-1", "page_type": "list", "discovered_from": {"page": "start-1", "url": "START_URL"}},
  {"url": "LIST_URL_2", "output_dir": "{pages_dir}/list-2", "page_type": "list", "discovered_from": {"page": "start-1", "url": "START_URL"}}
]
EOF
```

Extract links from ALL list pages in a single batch call and save groups:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/extract_links.py {pages_dir}/list-*/rendered.html --group --base-url-from-meta > {pages_dir}/list-groups.txt
```

Read the numbered groups (each has a `"file"` key like `"list-1"`), classify them, then apply:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/apply_classification.py {pages_dir}/list-groups.txt --classify "items=N,N subCategories=N,N nextPage=N" --pages-dir {pages_dir}
```

After classifying, check each page's `links.json`. If a list page has no `items`, add `"warning": "no_items"` to its `meta.json` — this likely indicates a link classification error.

### 3. Follow sub-subcategories (deeper navigation)

Check if any list page has `subCategories` links pointing deeper into the current scope. If yes, and you still need more list pages to reach `LIST_COUNT`:

- Pick 1-2 diverse sub-subcategory URLs
- Download, classify them
- These become additional list pages with `discovered_from` referencing the parent list page

This gives depth without widening the crawl. Even if LIST_COUNT is already met, follow 1 deeper in-scope subcategory if available.

### 4. Select and download detail pages

Collect ALL `items` links from the start page and all list pages. Pick `DETAIL_COUNT` diverse candidates:
- Different IDs or slugs in URLs
- From different categories/list pages when possible
- Not variants of the same item (e.g., different colors/sizes)

Track which page each candidate came from (for backlinks).

Download all candidates in one call:
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --log-file {pages_dir}/download.log <<'EOF'
[
  {"url": "ITEM_URL_1", "output_dir": "{pages_dir}/detail-1", "page_type": "detail", "discovered_from": {"page": "list-1", "url": "LIST_URL_1"}},
  {"url": "ITEM_URL_2", "output_dir": "{pages_dir}/detail-2", "page_type": "detail", "discovered_from": {"page": "list-2", "url": "LIST_URL_2"}}
]
EOF
```

### 5. Clean up

Remove empty directories from failed downloads.

Renumber remaining pages to be sequential (no gaps): `detail-1`, `detail-2`, etc.

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

Pages saved to {pages_dir}/
```

If targets were not met, explain why.

Return the start page link classification: item count, subCategory count, and a few example URLs. This is useful for the caller.
