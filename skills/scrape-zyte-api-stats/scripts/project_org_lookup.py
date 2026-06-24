# /// script
# requires-python = ">=3.11"
# dependencies = ["shub"]
# ///
"""Resolve a Zyte organization id from local shub configuration.

Project IDs are read from the standard shub config files
(`scrapinghub.yml` in the project root, `~/.scrapinghub.yml`, env vars).
Credentials are never read or printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import shub.config

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from auth import build_basic_auth_headers, get_api_key  # noqa: E402

_meta_dir = SCRIPT_DIR.parent.parent / "scrape"
_meta = json.loads((_meta_dir / "meta.json").read_text())

PROJECT_API_URL = "https://app.zyte.com/api/v2/projects/{project_id}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Zyte organization ids from shub config")
    parser.add_argument(
        "--project",
        help="Optional project selection by configured target name, numeric project id, or 1-based list index.",
    )
    return parser.parse_args()


def collect_candidates(config: "shub.config.ShubConfig") -> list[dict[str, Any]]:
    """Return discovered projects as [{id, name, default}, ...]."""
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()
    for name in config.projects:
        try:
            project_id = config.get_project_id(name)
        except Exception:
            continue
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            continue
        if project_id in seen:
            continue
        seen.add(project_id)
        candidates.append(
            {
                "id": project_id,
                "name": str(name),
                "default": str(name) == "default",
            }
        )
    return candidates


def format_project(candidate: dict[str, Any], *, index: int, organization_id: int | None = None) -> dict[str, Any]:
    payload = {
        "default": candidate.get("default", False),
        "id": candidate["id"],
        "index": index,
        "name": candidate.get("name"),
    }
    if organization_id is not None:
        payload["organization_id"] = organization_id
    return payload


def choose_candidate(
    candidates: list[dict[str, Any]], selection: str | None
) -> dict[str, Any] | None:
    if not candidates:
        return None
    if selection is None:
        if len(candidates) == 1:
            return candidates[0]
        return None

    normalized = selection.strip()
    if normalized.isdigit():
        numeric = int(normalized)
        if 1 <= numeric <= len(candidates):
            return candidates[numeric - 1]
        for candidate in candidates:
            if candidate["id"] == numeric:
                return candidate
    for candidate in candidates:
        if candidate.get("name") == normalized:
            return candidate
    raise RuntimeError("Selected project does not match any discovered configured project.")


def fetch_organization_id(project_id: int) -> int:
    apikey = get_api_key()
    request = Request(
        PROJECT_API_URL.format(project_id=project_id),
        headers={**build_basic_auth_headers(apikey), "User-Agent": f"zytedata/{_meta['repo']}/{_meta['version']} (scrape-zyte-api-stats)"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Project lookup failed for {project_id}: HTTP {exc.code}. {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Project lookup failed for {project_id}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Project lookup returned invalid JSON.") from exc

    organization = payload.get("organization")
    try:
        return int(organization)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Project lookup did not return a numeric organization id.") from exc


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


def resolve_candidate_organizations(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        organization_id = fetch_organization_id(candidate["id"])
        resolved.append(format_project(candidate, index=index, organization_id=organization_id))
    return resolved


def summarize_organizations(resolved_projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for project in resolved_projects:
        grouped.setdefault(project["organization_id"], []).append(project)

    organizations: list[dict[str, Any]] = []
    for index, organization_id in enumerate(sorted(grouped), start=1):
        projects = grouped[organization_id]
        representative = next((project for project in projects if project.get("default")), projects[0])
        organizations.append(
            {
                "index": index,
                "organization_id": organization_id,
                "projects": projects,
                "selection": representative["index"],
            }
        )
    return organizations


def main() -> None:
    args = parse_args()

    try:
        config = shub.config.load_shub_config()
    except Exception as exc:
        print_json({"status": "no_project_configured", "error": str(exc)})
        return

    candidates = collect_candidates(config)
    if not candidates:
        print_json({"status": "no_project_configured"})
        return

    try:
        candidate = choose_candidate(candidates, args.project)
    except RuntimeError as exc:
        print_json({"error": str(exc), "status": "invalid_selection"})
        return

    if candidate is None:
        try:
            resolved_projects = resolve_candidate_organizations(candidates)
        except RuntimeError as exc:
            print_json(
                {
                    "error": str(exc),
                    "projects": [
                        format_project(item, index=index)
                        for index, item in enumerate(candidates, start=1)
                    ],
                    "status": "organization_lookup_failed",
                }
            )
            return

        organizations = summarize_organizations(resolved_projects)
        if len(organizations) == 1:
            representative = next(
                (project for project in resolved_projects if project.get("default")),
                resolved_projects[0],
            )
            print_json(
                {
                    "organization_id": organizations[0]["organization_id"],
                    "project": representative,
                    "projects": resolved_projects,
                    "status": "resolved_project_with_organization",
                }
            )
            return

        print_json(
            {
                "organizations": organizations,
                "projects": resolved_projects,
                "status": "multiple_projects_found",
            }
        )
        return

    candidate_index = candidates.index(candidate) + 1

    try:
        organization_id = fetch_organization_id(candidate["id"])
    except RuntimeError as exc:
        print_json(
            {
                "error": str(exc),
                "project": format_project(candidate, index=candidate_index),
                "status": "organization_lookup_failed",
            }
        )
        return

    print_json(
        {
            "organization_id": organization_id,
            "project": format_project(candidate, index=candidate_index, organization_id=organization_id),
            "status": "resolved_project_with_organization",
        }
    )


if __name__ == "__main__":
    main()
