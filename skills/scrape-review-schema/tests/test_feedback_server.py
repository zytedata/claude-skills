"""Regression tests for feedback-server.py's data.js patching.

These reproduce the Windows failures reported by QA (see EES-576): a
UnicodeDecodeError when data.js held non-ASCII prices, a ValueError when the
review page URL was built from a relative directory, and — the user-facing
symptom — a stale port surviving in data.js after an earlier run crashed
mid-startup, so the browser POSTed feedback to a dead port.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "feedback-server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("feedback_server_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


feedback_server = load_module()

DATA_JS_TEMPLATE = 'const AGENT_URL = "http://127.0.0.1:{port}/feedback";\n'


def test_patch_replaces_placeholder(tmp_path):
    data_js = tmp_path / "data.js"
    data_js.write_text(DATA_JS_TEMPLATE.format(port="AGENT_PORT_PLACEHOLDER"), encoding="utf-8")

    feedback_server.patch_data_js_port(data_js, 55555)

    assert data_js.read_text(encoding="utf-8") == DATA_JS_TEMPLATE.format(port=55555)


def test_patch_is_idempotent_over_a_stale_port(tmp_path):
    """A crashed earlier run leaves a real (now stale) port and no placeholder.

    The next run binds a different port; the patch must still rewrite data.js to
    the new port. A plain str.replace("AGENT_PORT_PLACEHOLDER", ...) is a no-op
    here, leaving the browser pointed at a dead port -> connection refused.
    """
    data_js = tmp_path / "data.js"
    data_js.write_text(DATA_JS_TEMPLATE.format(port=60601), encoding="utf-8")

    feedback_server.patch_data_js_port(data_js, 49123)

    content = data_js.read_text(encoding="utf-8")
    assert "60601" not in content
    assert content == DATA_JS_TEMPLATE.format(port=49123)


def test_review_url_is_absolute_from_a_relative_dir(tmp_path, monkeypatch):
    """review_dir may be relative; Path.as_uri() rejects relative paths."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reviewdir").mkdir()

    url = feedback_server.review_url(Path("reviewdir"))

    assert url.startswith("file://")
    assert url.endswith("/reviewdir/review.html")


def test_patch_handles_non_ascii_under_non_utf8_locale(tmp_path):
    """data.js with a £ price must patch cleanly even when the process default
    encoding is not UTF-8 (cp1252 on Windows, ascii under LC_ALL=C here)."""
    data_js = tmp_path / "data.js"
    data_js.write_text(
        DATA_JS_TEMPLATE.format(port="AGENT_PORT_PLACEHOLDER") + '// price: £5.00\n',
        encoding="utf-8",
    )

    code = textwrap.dedent(
        f"""
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location("m", {str(SCRIPT)!r})
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.patch_data_js_port(pathlib.Path({str(data_js)!r}), 55555)
        """
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    env["PYTHONUTF8"] = "0"

    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    patched = data_js.read_text(encoding="utf-8")
    assert "55555" in patched
    assert "£5.00" in patched


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
