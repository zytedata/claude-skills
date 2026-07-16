---
name: scrape-review-schema
description: Generate an HTML review page for schema and extracted data verification
argument-hint: "[spec-path] [work-path] [schema-json] [html-variant]"
allowed-tools: Bash, Read, Write
---

You are generating a review page that lets the user verify the proposed schema and extracted values in their browser.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into up to 5 positional arguments.
The 1st, 2nd and 4th are whitespace-separated tokens; the 3rd and 5th are JSON literals that may contain whitespace —
recognize their boundaries by matching brackets (and strip outer single/double quotes if the caller quoted them):

1. **spec_path**: path to the spec folder, e.g. `.scrape/books-toscrape`
2. **work_path**: path to the working directory, e.g. `.scrape/.work/books-toscrape`
3. **schema**: JSON object literal with the proposed schema (starts with `{`, ends with the matching `}`)
4. **html_variant**: which HTML to use — `raw` or `rendered`
5. **changes** (optional): JSON array literal of change descriptions from the previous round (starts with `[`, ends with the matching `]`), e.g. `["Re-analyzed price across all pages","Dropped field isbn"]`

The schema JSON uses JSON Schema format (see `${CLAUDE_SKILL_DIR}/../scrape/references/extraction-spec.md` for full details):
```json
{
  "type": "object",
  "properties": {
    "price": {
      "type": "string",
      "description": "Product price"
    }
  }
}
```

Fields may also carry a `source` annotation: "requested" (user asked for it) or "discovered" (AI found it).

## Process

### 1. Read analysis data

List page subdirectories in `{spec_path}/pages/` (each subdirectory is a page). For each page, read `{spec_path}/pages/{page_id}/meta.json` for metadata and `{work_path}/analyze-page/{page_id}.{html_variant}.json` for analysis data.

### 2. Create temp directory

Create a temporary directory named `scrape-review-XXXXXX` (where `XXXXXX` is a random suffix). Keep track of the resulting path as `{review_dir}` and use it in subsequent steps.

### 3. Copy static assets

Copy the bundled assets from this skill's directory to the temp dir:
- `review.html`
- `style.css`
- `review.js`

Use `${CLAUDE_SKILL_DIR}/assets/` as the source path.

### 4. Copy saved HTML pages

For each page directory in `{spec_path}/pages/`, copy the chosen variant's HTML to `{review_dir}/pages/{page_id}.html`:

```bash
cp {spec_path}/pages/{page_id}/{html_variant}.html {review_dir}/pages/{page_id}.html
```

This flattens the directory structure for the review page's iframes.

### 5. Generate data.js

Build and write `{review_dir}/data.js` with all the data the review page needs.
Use the literal placeholder `AGENT_PORT_PLACEHOLDER` for the port — the server replaces it
after binding. If `changes` was passed (the optional 5th argument), include `REVIEW_CHANGES` so the page shows what the agent did:

```javascript
const AGENT_URL = "http://127.0.0.1:AGENT_PORT_PLACEHOLDER/feedback";
const REVIEW_CHANGES = ["Re-analyzed price across all pages", "Dropped field isbn"];
const REVIEW_DATA = {
  fields: [
    {
      name: "price",
      type: "str",
      description: "Product price",
      source: "requested",
      values: {
        "detail-1": {"value": "$29.99", "url": "https://..."},
        "detail-2": {"value": "$49.99", "url": "https://..."}
      }
    }
  ],
  pages: {
    "detail-1": {
      url: "https://...",
      html_file: "pages/detail-1.html"
    }
  }
};
```

### 6. Open in browser and wait for feedback

Run exactly the command below and wait for it to finish before doing anything else:

```bash
FEEDBACK_FILE="{review_dir}/feedback.txt"
uv run "${CLAUDE_SKILL_DIR}/scripts/feedback-server.py" "{review_dir}" "${FEEDBACK_FILE}"
cat "${FEEDBACK_FILE}"
```

Report `{review_dir}` to the user in the message before running this command, in case they need to reopen it.

The script opens the review page in the browser, waits for the user
to submit feedback, and exits by itself. Your only job is to wait for the command to finish,
then read the feedback from `${FEEDBACK_FILE}`.

Return the feedback text to the caller.
