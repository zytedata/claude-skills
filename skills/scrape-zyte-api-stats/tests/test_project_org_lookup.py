from __future__ import annotations

import importlib.util
import sys
import types
from argparse import Namespace
from pathlib import Path


def load_project_org_lookup_module(monkeypatch):
    shub_module = types.ModuleType("shub")
    shub_config_module = types.ModuleType("shub.config")
    shub_config_module.ShubConfig = object
    shub_config_module.load_shub_config = lambda: None
    shub_module.config = shub_config_module
    monkeypatch.setitem(sys.modules, "shub", shub_module)
    monkeypatch.setitem(sys.modules, "shub.config", shub_config_module)

    auth_module = types.ModuleType("auth")
    auth_module.build_basic_auth_headers = lambda apikey: {"Authorization": apikey}
    auth_module.get_api_key = lambda: "test-key"
    monkeypatch.setitem(sys.modules, "auth", auth_module)

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "project_org_lookup.py"
    spec = importlib.util.spec_from_file_location("test_project_org_lookup_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeConfig:
    def __init__(self, projects: dict[str, int]):
        self.projects = list(projects)
        self._projects = projects

    def get_project_id(self, name: str) -> int:
        return self._projects[name]


def test_same_org_projects_auto_resolve(monkeypatch):
    module = load_project_org_lookup_module(monkeypatch)
    monkeypatch.setattr(
        module.shub.config,
        "load_shub_config",
        lambda: FakeConfig({"default": 859188, "secondary": 859189}),
    )
    monkeypatch.setattr(module, "parse_args", lambda: Namespace(project=None))
    monkeypatch.setattr(module, "fetch_organization_id", lambda project_id: 217112)

    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(module, "print_json", payloads.append)

    module.main()

    assert payloads == [
        {
            "organization_id": 217112,
            "project": {
                "default": True,
                "id": 859188,
                "index": 1,
                "name": "default",
                "organization_id": 217112,
            },
            "projects": [
                {
                    "default": True,
                    "id": 859188,
                    "index": 1,
                    "name": "default",
                    "organization_id": 217112,
                },
                {
                    "default": False,
                    "id": 859189,
                    "index": 2,
                    "name": "secondary",
                    "organization_id": 217112,
                },
            ],
            "status": "resolved_project_with_organization",
        }
    ]


def test_different_org_projects_return_grouped_organization_options(monkeypatch):
    module = load_project_org_lookup_module(monkeypatch)
    monkeypatch.setattr(
        module.shub.config,
        "load_shub_config",
        lambda: FakeConfig({"default": 859188, "secondary": 859189}),
    )
    monkeypatch.setattr(module, "parse_args", lambda: Namespace(project=None))
    monkeypatch.setattr(
        module,
        "fetch_organization_id",
        lambda project_id: {859188: 217112, 859189: 942612}[project_id],
    )

    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(module, "print_json", payloads.append)

    module.main()

    assert payloads == [
        {
            "organizations": [
                {
                    "index": 1,
                    "organization_id": 217112,
                    "projects": [
                        {
                            "default": True,
                            "id": 859188,
                            "index": 1,
                            "name": "default",
                            "organization_id": 217112,
                        }
                    ],
                    "selection": 1,
                },
                {
                    "index": 2,
                    "organization_id": 942612,
                    "projects": [
                        {
                            "default": False,
                            "id": 859189,
                            "index": 2,
                            "name": "secondary",
                            "organization_id": 942612,
                        }
                    ],
                    "selection": 2,
                },
            ],
            "projects": [
                {
                    "default": True,
                    "id": 859188,
                    "index": 1,
                    "name": "default",
                    "organization_id": 217112,
                },
                {
                    "default": False,
                    "id": 859189,
                    "index": 2,
                    "name": "secondary",
                    "organization_id": 942612,
                },
            ],
            "status": "multiple_projects_found",
        }
    ]


def test_explicit_project_selection_returns_formatted_project(monkeypatch):
    module = load_project_org_lookup_module(monkeypatch)
    monkeypatch.setattr(
        module.shub.config,
        "load_shub_config",
        lambda: FakeConfig({"default": 859188, "secondary": 859189}),
    )
    monkeypatch.setattr(module, "parse_args", lambda: Namespace(project="2"))
    monkeypatch.setattr(module, "fetch_organization_id", lambda project_id: 942612)

    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(module, "print_json", payloads.append)

    module.main()

    assert payloads == [
        {
            "organization_id": 942612,
            "project": {
                "default": False,
                "id": 859189,
                "index": 2,
                "name": "secondary",
                "organization_id": 942612,
            },
            "status": "resolved_project_with_organization",
        }
    ]