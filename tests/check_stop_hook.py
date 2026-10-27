import json
import os
from pathlib import Path
import subprocess
import tempfile


def check_stop_hook():
    plugin = Path(__file__).resolve().parents[1]
    config = json.loads((plugin / "hooks/hooks.json").read_text())
    command = config["hooks"]["Stop"][0]["hooks"][0]["command"]
    hosts = {
        "CLAUDE_PLUGIN_ROOT": "claude_code",
        "PLUGIN_ROOT": "codex_cli",
        "COPILOT_PLUGIN_ROOT": "copilot_cli",
    }
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        plugin_link = temporary / "plugin root with spaces"
        plugin_link.symlink_to(plugin, target_is_directory=True)
        for variable, source in hosts.items():
            log = temporary / f"{source}.jsonl"
            environment = {key: value for key, value in os.environ.items() if key not in hosts}
            environment.update({
                variable: str(plugin_link),
                "SCRAPE_FEEDBACK_STATE_FILE": str(temporary / "state.json"),
                "SCRAPE_FEEDBACK_MARKER_FILE": str(temporary / "marker.json"),
                "SCRAPE_FEEDBACK_EVENT_LOG_FILE": str(log),
                "UV_OFFLINE": "1",
                "UV_PYTHON_DOWNLOADS": "never",
            })
            result = subprocess.run(command, shell=True, input="{}", env=environment,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, f"{source}: {result.stderr or result.stdout}"
            assert result.stdout == "", f"{source}: unexpected hook output: {result.stdout}"
            event = json.loads(log.read_text().splitlines()[-1])
            assert (event["source"], event["reason"]) == (source, "no_marker"), event
    print("Stop hook passed for Claude, Codex and Copilot, including paths with spaces.")


if __name__ == "__main__":
    check_stop_hook()
