# /// script
# requires-python = ">=3.11"
# ///
"""Read and update the credential variables kept in the project's dotenv file,
without ever printing their values.

Run it to report which credentials are available:

    uv run env_keys.py
"""

import os
import sys
from pathlib import Path

ENV_FILE = Path(".env")
KEYS = ("ZYTE_API_KEY", "SHUB_APIKEY")


def stored_names(path: Path = ENV_FILE) -> set[str]:
    """Return the names of the variables defined in the dotenv file."""
    if not path.exists():
        return set()
    return {
        line.split("=", 1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }


def is_set(key: str, path: Path = ENV_FILE) -> bool:
    """Whether *key* is exported in the environment or defined in the dotenv file."""
    return bool(os.environ.get(key)) or key in stored_names(path)


def set_var(key: str, value: str, path: Path = ENV_FILE) -> None:
    """Insert or update ``key=value`` in the dotenv file. The value is never logged."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    kept = [line for line in lines if not line.startswith(f"{key}=")]
    kept.append(f"{key}={value}")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    for key in KEYS:
        print(f"{key}: {'present' if is_set(key) else 'missing'}")
