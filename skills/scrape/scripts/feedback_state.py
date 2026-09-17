# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate and deliver the scrape feedback prompt.

The scrape workflow writes a one-shot final-outcome marker (``mark``) when spider
creation finishes with success, failure after retries, or incomplete data after
retries. A session-stop hook (``hook``) consumes that valid marker and shows the
feedback line at most once per cooldown window. Because a Stop hook's plain
stdout is not shown to the user in Claude Code, ``hook`` emits JSON with a
``systemMessage`` field so hosts that support that payload can surface the line
directly. Hosts that run hooks without surfacing their output can use
``maybe-show`` as a cooldown-gated, model-visible fallback. The helper can also
surface the line on explicit request (``show``), which prints plain text for the
model to relay.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

UTC = timezone.utc
COOLDOWN_DAYS = 14
# A marker older than this is treated as stale and discarded without prompting,
# so a crash or abandoned session never triggers feedback on an unrelated run.
MARKER_TTL = timedelta(hours=6)
DEFAULT_STATE_FILE = Path.home() / ".scraping-agent-skills" / "scrape-feedback-state.json"
DEFAULT_MARKER_FILE = Path.home() / ".scraping-agent-skills" / "scrape-feedback-marker.json"
DEFAULT_EVENT_LOG_FILE = Path.home() / ".scraping-agent-skills" / "scrape-feedback-events.jsonl"

FEEDBACK_DISPLAY_URL = os.environ.get(
    "SCRAPE_FEEDBACK_DISPLAY_URL",
    "https://forms.gle/mQdY2ww68ycvDv4s5",
)
FEEDBACK_FORM_CLAUDE = os.environ.get(
    "SCRAPE_FEEDBACK_FORM_CLAUDE",
    "https://forms.gle/Uvg4sCKPJgmqi6CL7",
)
FEEDBACK_FORM_COPILOT = os.environ.get(
    "SCRAPE_FEEDBACK_FORM_COPILOT",
    "https://forms.gle/BQwVSenaN5YZUBk76",
)
FEEDBACK_FORM_CODEX = os.environ.get(
    "SCRAPE_FEEDBACK_FORM_CODEX",
    "https://forms.gle/bDkbVG1mckTpAioY9",
)
DEFAULT_CONTEXT = "scrape_success"


def detect_source() -> str:
    copilot_root = os.environ.get("COPILOT_PLUGIN_ROOT")
    codex_root = os.environ.get("PLUGIN_ROOT")
    claude_root = os.environ.get("CLAUDE_PLUGIN_ROOT")

    if copilot_root:
        return "copilot_cli"
    if codex_root:
        return "codex_cli"
    return "claude_code" if claude_root else "unknown"


# Only sources with a working Stop-hook path should consume feedback markers.
PLUGIN_ROOT_ENV_BY_SOURCE = {
    "claude_code": "CLAUDE_PLUGIN_ROOT",
    "codex_cli": "PLUGIN_ROOT",
    "copilot_cli": "COPILOT_PLUGIN_ROOT",
}

def plugin_root_present(source: str) -> bool:
    env_var = PLUGIN_ROOT_ENV_BY_SOURCE.get(source)
    return bool(env_var and os.environ.get(env_var))


def feedback_line(context: str, source: str, url: str | None = None) -> str:
    """Plain-text variant for the Stop-hook ``systemMessage``, which hosts
    render without markdown."""
    url = url or automatic_feedback_url(context, source)
    lead = (
        "The spider is ready. How did it go?"
        if context == DEFAULT_CONTEXT
        else "The scrape workflow finished. How did it go?"
    )
    return (
        f"{lead}\n"
        "3 questions • 30 seconds. Tell us how we can make this workflow better for you:\n"
        f"{url}"
    )


def feedback_line_markdown(context: str, source: str, url: str | None = None) -> str:
    """Markdown variant for model-visible delivery (maybe-show/show), appended
    verbatim to the final report where markdown renders."""
    url = url or automatic_feedback_url(context, source)
    lead = (
        "The spider is ready — how did it go?"
        if context == DEFAULT_CONTEXT
        else "The scrape workflow finished — how did it go?"
    )
    return (
        "---\n\n"
        f"**\U0001f4dd {lead}** 3 questions • 30 seconds. "
        f"Tell us how we can make this workflow better for you: {url}"
    )


def automatic_feedback_url(context: str, source: str) -> str:
    if context != DEFAULT_CONTEXT:
        return FEEDBACK_DISPLAY_URL
    if source == "claude_code" and FEEDBACK_FORM_CLAUDE:
        return FEEDBACK_FORM_CLAUDE
    if source == "copilot_cli" and FEEDBACK_FORM_COPILOT:
        return FEEDBACK_FORM_COPILOT
    if source == "codex_cli" and FEEDBACK_FORM_CODEX:
        return FEEDBACK_FORM_CODEX
    return FEEDBACK_DISPLAY_URL


def hook_feedback_line() -> str:
    source = detect_source()
    return feedback_line(DEFAULT_CONTEXT, source, automatic_feedback_url(DEFAULT_CONTEXT, source))


def parse_timestamp(value: str) -> datetime | None:
    try:
        normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def read_last_prompted(state_file: Path) -> datetime | None:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    if not isinstance(state, dict):
        return None

    last_prompted = state.get("last_prompted")
    if not isinstance(last_prompted, str):
        return None

    return parse_timestamp(last_prompted)


def write_last_prompted(state_file: Path, now: datetime) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"last_prompted": format_timestamp(now)}, indent=2) + "\n",
        encoding="utf-8",
    )


def append_event(log_file: Path, event: dict[str, Any]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as log:
        log.write(json.dumps(event, sort_keys=True) + "\n")


def event(
    command: str,
    now: datetime,
    source: str,
    **details: Any,
) -> dict[str, Any]:
    payload = {
        "time": format_timestamp(now),
        "command": command,
        "source": source,
        "plugin_root_present": plugin_root_present(source),
    }
    payload.update(details)
    return payload


def decide_prompt(state_file: Path, now: datetime) -> dict[str, Any]:
    now = now.astimezone(UTC)
    last_prompted = read_last_prompted(state_file)

    if last_prompted is not None and now - last_prompted < timedelta(days=COOLDOWN_DAYS):
        return {
            "should_prompt": False,
            "reason": "cooldown_active",
            "last_prompted": format_timestamp(last_prompted),
            "state_file": str(state_file),
        }

    write_last_prompted(state_file, now)
    return {
        "should_prompt": True,
        "reason": "never_prompted" if last_prompted is None else "cooldown_elapsed",
        "last_prompted": format_timestamp(now),
        "state_file": str(state_file),
    }


def write_marker(marker_file: Path, now: datetime, context: str, source: str) -> None:
    marker_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.write_text(
        json.dumps(
            {
                "created": format_timestamp(now),
                "context": context,
                "source": source,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_mark(
    marker_file: Path,
    log_file: Path,
    now: datetime,
    context: str,
    source: str,
) -> dict[str, Any]:
    write_marker(marker_file, now, context, source)
    append_event(
        log_file,
        event(
            "mark",
            now,
            source,
            context=context,
            marker_file=str(marker_file),
        ),
    )
    return {"action": "mark", "marker_file": str(marker_file)}


def read_marker(marker_file: Path) -> dict[str, Any] | None:
    try:
        marker = json.loads(marker_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    if not isinstance(marker, dict):
        return None

    created = marker.get("created")
    if not isinstance(created, str):
        return None

    parsed_created = parse_timestamp(created)
    if parsed_created is None:
        return None

    context = marker.get("context", DEFAULT_CONTEXT)
    source = marker.get("source", "unknown")
    return {
        "created": parsed_created,
        "context": context if isinstance(context, str) and context else DEFAULT_CONTEXT,
        "source": source if isinstance(source, str) and source else "unknown",
    }


def clear_marker(marker_file: Path) -> None:
    try:
        marker_file.unlink()
    except (FileNotFoundError, OSError):
        pass


def prompt_source(marker_source: str, hook_source: str) -> str:
    return hook_source if hook_source != "unknown" else marker_source


def render_hook_output(result: dict[str, Any]) -> str | None:
    """Render the Stop-hook stdout payload, or None when nothing should print.

    A Stop hook's plain stdout is not surfaced to the user by Claude Code, so the
    line is delivered as JSON with a ``systemMessage`` field. Other hosts may run
    the hook but ignore this display payload.
    """
    if result["action"] != "show":
        return None
    return json.dumps({"systemMessage": result["line"]})


def run_hook(
    marker_file: Path,
    state_file: Path,
    log_file: Path,
    now: datetime,
    hook_source: str,
    plugin_root_available: bool | None = None,
) -> dict[str, Any]:
    """Session-stop entry point: prompt only if a fresh success marker is pending."""
    now = now.astimezone(UTC)
    if plugin_root_available is None:
        plugin_root_available = plugin_root_present(hook_source)

    if not plugin_root_available:
        append_event(
            log_file,
            event(
                "hook",
                now,
                hook_source,
                action="skip",
                reason="wrong_caller",
                marker_present=marker_file.exists(),
                marker_file=str(marker_file),
                plugin_root_present=False,
            ),
        )
        return {"action": "skip", "reason": "wrong_caller"}

    marker = read_marker(marker_file)
    if marker is None:
        if marker_file.exists():
            clear_marker(marker_file)
            append_event(
                log_file,
                event(
                    "hook",
                    now,
                    hook_source,
                    action="skip",
                    reason="invalid_marker",
                    marker_present=True,
                    marker_file=str(marker_file),
                ),
            )
            return {"action": "skip", "reason": "invalid_marker"}
        append_event(
            log_file,
            event(
                "hook",
                now,
                hook_source,
                action="skip",
                reason="no_marker",
                marker_present=False,
                marker_file=str(marker_file),
            ),
        )
        return {"action": "skip", "reason": "no_marker"}

    # One-shot: consume the marker whatever we decide below.
    clear_marker(marker_file)

    created = marker["created"]
    if now - created > MARKER_TTL:
        append_event(
            log_file,
            event(
                "hook",
                now,
                hook_source,
                action="skip",
                reason="marker_stale",
                marker_present=True,
                marker_context=marker["context"],
                marker_source=marker["source"],
                marker_created=format_timestamp(created),
            ),
        )
        return {"action": "skip", "reason": "marker_stale"}

    decision = decide_prompt(state_file, now)
    if not decision["should_prompt"]:
        append_event(
            log_file,
            event(
                "hook",
                now,
                hook_source,
                action="skip",
                reason=decision["reason"],
                marker_present=True,
                marker_context=marker["context"],
                marker_source=marker["source"],
                marker_created=format_timestamp(created),
            ),
        )
        return {"action": "skip", "reason": decision["reason"]}

    source = prompt_source(marker["source"], hook_source)
    line = feedback_line(marker["context"], source, automatic_feedback_url(marker["context"], source))
    append_event(
        log_file,
        event(
            "hook",
            now,
            hook_source,
            action="show",
            reason=decision["reason"],
            marker_present=True,
            marker_context=marker["context"],
            marker_source=marker["source"],
            prompt_source=source,
            marker_created=format_timestamp(created),
        ),
    )
    return {
        "action": "show",
        "reason": decision["reason"],
        "line": line,
    }


def run_maybe_show(
    state_file: Path,
    log_file: Path,
    now: datetime,
    context: str,
    source: str,
) -> dict[str, Any]:
    """Model-visible fallback for hosts that run hooks without showing output."""
    decision = decide_prompt(state_file, now)
    if not decision["should_prompt"]:
        append_event(
            log_file,
            event(
                "maybe-show",
                now,
                source,
                action="skip",
                reason=decision["reason"],
                context=context,
            ),
        )
        return {"action": "skip", "reason": decision["reason"]}

    line = feedback_line_markdown(context, source, automatic_feedback_url(context, source))
    append_event(
        log_file,
        event("maybe-show", now, source, action="show", reason=decision["reason"], context=context),
    )
    return {"action": "show", "reason": decision["reason"], "line": line}


def run_show(
    state_file: Path,
    log_file: Path,
    now: datetime,
    context: str,
    source: str,
) -> dict[str, Any]:
    """Explicit entry point: show the link and refresh the shared prompt state."""
    write_last_prompted(state_file, now.astimezone(UTC))
    line = feedback_line_markdown(context, source)
    append_event(
        log_file,
        event("show", now, source, action="show", reason="explicit_request", context=context),
    )
    return {"action": "show", "reason": "explicit_request", "line": line}


def run_status(marker_file: Path, state_file: Path, log_file: Path) -> dict[str, Any]:
    return {
        "marker_file": str(marker_file),
        "marker_present": marker_file.exists(),
        "state_file": str(state_file),
        "state_present": state_file.exists(),
        "event_log_file": str(log_file),
        "event_log_present": log_file.exists(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate and deliver scrape feedback")
    parser.add_argument(
        "command",
        choices=("mark", "hook", "maybe-show", "show", "status"),
        help=(
            "mark: record a successful pipeline; hook: session-stop check; "
            "maybe-show: cooldown-gated model-visible fallback; "
            "show: explicit prompt; status: print local marker/log paths."
        ),
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(os.environ.get("SCRAPE_FEEDBACK_STATE_FILE", DEFAULT_STATE_FILE)),
        help="Path to the feedback cooldown state file.",
    )
    parser.add_argument(
        "--marker-file",
        type=Path,
        default=Path(os.environ.get("SCRAPE_FEEDBACK_MARKER_FILE", DEFAULT_MARKER_FILE)),
        help="Path to the one-shot success marker file.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(os.environ.get("SCRAPE_FEEDBACK_EVENT_LOG_FILE", DEFAULT_EVENT_LOG_FILE)),
        help="Path to the local JSONL event log used for hook diagnostics.",
    )
    parser.add_argument(
        "--now",
        type=parse_timestamp,
        default=datetime.now(UTC),
        help="Current UTC timestamp, mainly for tests.",
    )
    parser.add_argument(
        "--context",
        default=DEFAULT_CONTEXT,
        help="Feedback trigger context, used for prefilled form tracking when configured.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Host/source identifier, defaults to the detected plugin runtime.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_file = args.state_file.expanduser()
    marker_file = args.marker_file.expanduser()
    log_file = args.log_file.expanduser()
    source = args.source or detect_source()

    if args.command == "mark":
        run_mark(marker_file, log_file, args.now, args.context, source)
        return 0

    if args.command == "status":
        print(json.dumps(run_status(marker_file, state_file, log_file), indent=2))
        return 0

    if args.command == "hook":
        result = run_hook(marker_file, state_file, log_file, args.now, source)
        payload = render_hook_output(result)
        if payload is not None:
            print(payload)
        return 0

    if args.command == "maybe-show":
        result = run_maybe_show(state_file, log_file, args.now, args.context, source)
        if result["action"] == "show":
            print(result["line"])
        return 0

    result = run_show(state_file, log_file, args.now, args.context, source)
    if result["action"] == "show":
        print(result["line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
