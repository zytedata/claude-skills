---
name: scrape-ensure-project
description: Ensure a Scrapy project exists with scrapy-poet and Zyte API support
argument-hint: "[project-dir] [project-name]"
allowed-tools: Bash, Read, Write
---

You are ensuring a Scrapy project exists and is properly configured for web-poet
page objects and Zyte API.

Read `${CLAUDE_SKILL_DIR}/../scrape/references/python-environments.md`.

## Input

The raw argument string is `$ARGUMENTS`. Split it into 2 whitespace-separated positional arguments:

1. **project_dir**: project directory (e.g. `./books-project`)
2. **project_name**: Python package name (e.g. `books_project`)

## Process

### 1. Check if project already exists

If `{project_dir}/pyproject.toml` exists, this is an existing project. Go to step 3.

Otherwise, create the project from scratch (step 2).

### 2. Create new project

Use the bundled cookiecutter template:

```bash
uvx cookiecutter --no-input ${CLAUDE_SKILL_DIR}/assets/project-template -o PARENT_DIR project_name=PROJECT_NAME
```

This creates a Scrapy project with:
- `pyproject.toml` with dependencies (scrapy, scrapy-poet, scrapy-zyte-api, web-poet)
- `scrapy.cfg` with deploy settings
- `settings.py` with scrapy-poet and Zyte API addons configured
- `pages/`, `spiders/`, `fixtures/` directories
- `items.py` (empty, ready for item classes)

Then install:

```bash
cd PROJECT_DIR && uv sync
```

Report what was created and return.

### 3. Verify existing project dependencies

Read the project's `pyproject.toml` and check that these packages are in
`dependencies`:

- `scrapy`
- `scrapy-poet`
- `web-poet`
- `extruct`
- `price-parser`
- `pytest`

If any are missing, **warn the user** — list the missing dependencies and ask
whether to add them. Do NOT modify the project without confirmation.

Also check that `fixtures/` directory exists (create it if missing — it's just
a directory).

### 4. Report result

For new projects:
```
Created project at {project_dir}:
  - {project_name}/settings.py — scrapy-poet + Zyte API configured
  - {project_name}/items.py — ready for item classes
  - {project_name}/pages/ — ready for page objects
  - fixtures/ — ready for test fixtures
```

For existing projects:
```
Using existing project at {project_dir}.
```

Or if dependencies are missing:
```
Using existing project at {project_dir}.
Warning: missing dependencies: {list}
Add them to pyproject.toml?
```
