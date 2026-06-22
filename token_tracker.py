import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude"
WINDOW_HOURS = 5


def get_all_jsonl_files():
    """Find all session JSONL files under ~/.claude/projects/"""
    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return []
    return list(projects_dir.rglob("*.jsonl"))


def parse_usage_from_file(filepath: Path, since: datetime) -> dict:
    """Read a JSONL file and sum token usage after `since`."""
    totals = dict(input_tokens=0, output_tokens=0,
                  cache_creation_input_tokens=0, cache_read_input_tokens=0)
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = obj.get("timestamp")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if ts < since:
                    continue

                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage", {})
                if not isinstance(usage, dict):
                    continue

                for key in totals:
                    val = usage.get(key, 0)
                    if isinstance(val, (int, float)):
                        totals[key] += int(val)
    except (OSError, PermissionError):
        pass
    return totals


def get_usage_last_5h() -> dict:
    """Aggregate token usage across all projects for the last WINDOW_HOURS."""
    since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    totals = dict(input_tokens=0, output_tokens=0,
                  cache_creation_input_tokens=0, cache_read_input_tokens=0)

    for filepath in get_all_jsonl_files():
        partial = parse_usage_from_file(filepath, since)
        for key in totals:
            totals[key] += partial[key]

    totals["total_tokens"] = (
        totals["input_tokens"]
        + totals["output_tokens"]
        + totals["cache_creation_input_tokens"]
        + totals["cache_read_input_tokens"]
    )
    totals["window_hours"] = WINDOW_HOURS
    totals["since"] = since.isoformat()
    return totals
