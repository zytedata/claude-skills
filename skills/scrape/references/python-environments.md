This file is 48 lines long; read all of them.

# Python Environments

Skills use `uv` for all Python execution. Never use bare `python` or `pip`.
Install `uv` if missing.

## Running scripts (uv run)

**Scripts with inline deps** (`# /// script` header):
```bash
uv run path/to/script.py ARGS
```
uv creates an isolated env with the declared dependencies. Most skill scripts
use this pattern (e.g., `download.py`, `clean_html.py`).

**Scripts that need the user's project packages** (no inline deps header):
```bash
uv run --project PROJECT_DIR path/to/script.py ARGS
```
Runs in the project's venv so the script can import project modules (items, page
objects, etc.).

## Running project commands (uv run)

```bash
cd PROJECT_DIR && uv run --with pytest python -m pytest fixtures/
cd PROJECT_DIR && uv run scrapy crawl spider_name
```

Uses the project's venv, created when the project is set up (which runs `uv sync`).

## Running CLI tools (uvx)

```bash
uvx cookiecutter TEMPLATE_PATH
```

`uvx` runs a CLI tool by package name in a temporary env. It does NOT run scripts
— use `uv run` for that.

## Project setup

Creating the project runs `uv sync` to install all dependencies. After that,
`uv run` inside the project directory uses this env.

`.venv/`, `uv.lock`, `*.egg-info` and `build/` are expected project state, not
temporary files: leave them in place.
