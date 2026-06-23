"""
Token cost calculation following ccusage formula:
  cost = input * inputPrice
       + output * outputPrice
       + cache_5m * (inputPrice * 1.25)
       + cache_1h * (inputPrice * 2.0)
       + cache_read * cacheReadPrice

Source: https://github.com/ryoppippi/ccusage
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
WINDOW_HOURS = 5

# Prices in USD per million tokens
MODEL_PRICING = {
    "claude-opus-4":    dict(input=15.00, output=75.00, cache_read=1.50),
    "claude-sonnet-4":  dict(input=3.00,  output=15.00, cache_read=0.30),
    "claude-haiku-4":   dict(input=0.80,  output=4.00,  cache_read=0.08),
    "default":          dict(input=3.00,  output=15.00, cache_read=0.30),
}

def _get_pricing(model: str) -> dict:
    model = (model or "").lower()
    for key in MODEL_PRICING:
        if key != "default" and key in model:
            return MODEL_PRICING[key]
    return MODEL_PRICING["default"]


def _calc_cost(usage: dict, model: str) -> float:
    p = _get_pricing(model)
    input_price  = p["input"]
    output_price = p["output"]
    read_price   = p["cache_read"]
    write_5m_price = input_price * 1.25
    write_1h_price = input_price * 2.0

    inp  = usage.get("input_tokens", 0)
    out  = usage.get("output_tokens", 0)
    cr   = usage.get("cache_read_input_tokens", 0)

    # Prefer split cache_creation; fall back to total at 5m rate
    cc = usage.get("cache_creation", {}) or {}
    c5m = cc.get("ephemeral_5m_input_tokens", 0)
    c1h = cc.get("ephemeral_1h_input_tokens", 0)
    if c5m == 0 and c1h == 0:
        c5m = usage.get("cache_creation_input_tokens", 0)

    cost = (
        inp  * input_price  / 1_000_000
        + out  * output_price / 1_000_000
        + c5m  * write_5m_price / 1_000_000
        + c1h  * write_1h_price / 1_000_000
        + cr   * read_price   / 1_000_000
    )
    return cost


def get_all_jsonl_files():
    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return []
    return list(projects_dir.rglob("*.jsonl"))


def get_window_info() -> dict:
    """
    Detect the current 5h session window by scanning JSONL timestamps.
    The window starts at the FIRST request of the current block.
    A new block starts after a gap > 5h with no activity.

    Returns: {window_start, window_end, is_active, remaining_seconds}
    """
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=10)  # look back 10h to catch window start

    timestamps = []
    for filepath in get_all_jsonl_files():
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                        ts_str = obj.get("timestamp")
                        if not ts_str:
                            continue
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts >= lookback:
                            # only include messages that actually made API calls
                            if obj.get("message", {}).get("usage"):
                                timestamps.append(ts)
                    except Exception:
                        continue
        except (OSError, PermissionError):
            pass

    if not timestamps:
        return {"is_active": False}

    timestamps.sort()
    most_recent = timestamps[-1]

    # If most recent is > 5h ago, there is no active window
    if now - most_recent > timedelta(hours=WINDOW_HOURS):
        return {"is_active": False}

    # Walk back to find the start of the current block:
    # The block starts at the earliest timestamp within 5h of the most recent
    window_start = most_recent
    for ts in reversed(timestamps[:-1]):
        if most_recent - ts <= timedelta(hours=WINDOW_HOURS):
            window_start = ts
        else:
            break  # gap > 5h: this timestamp belongs to a previous block

    window_end = window_start + timedelta(hours=WINDOW_HOURS)
    remaining = (window_end - now).total_seconds()

    return {
        "is_active": True,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "remaining_seconds": max(0, remaining),
    }


def get_window_series() -> list:
    """
    Returns list of (t_seconds, cumulative_tokens) for every API call
    in the current 5h window, sorted by time.
    t_seconds = seconds elapsed since window_start.
    cumulative_tokens = input + output + cache_creation + cache_read
    """
    window = get_window_info()
    if not window.get("is_active"):
        return []

    since = datetime.fromisoformat(window["window_start"])
    window_end = datetime.fromisoformat(window["window_end"])

    events = []
    for filepath in get_all_jsonl_files():
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
                    if ts < since or ts > window_end:
                        continue
                    msg = obj.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage", {})
                    if not isinstance(usage, dict) or not usage:
                        continue

                    cc = usage.get("cache_creation", {}) or {}
                    c5m = cc.get("ephemeral_5m_input_tokens", 0)
                    c1h = cc.get("ephemeral_1h_input_tokens", 0)
                    if c5m == 0 and c1h == 0:
                        c5m = usage.get("cache_creation_input_tokens", 0)

                    tokens = (
                        usage.get("input_tokens", 0)
                        + usage.get("output_tokens", 0)
                        + c5m + c1h
                        + usage.get("cache_read_input_tokens", 0)
                    )
                    t_sec = (ts - since).total_seconds()
                    events.append((t_sec, tokens))
        except (OSError, PermissionError):
            pass

    events.sort(key=lambda x: x[0])

    # Build cumulative series
    cumulative = 0
    series = [(0, 0)]
    for t_sec, tokens in events:
        cumulative += tokens
        series.append((t_sec, cumulative))
    return series


def get_usage_last_5h() -> dict:
    window = get_window_info()
    if window.get("is_active") and window.get("window_start"):
        since = datetime.fromisoformat(window["window_start"])
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)

    totals = dict(
        input_tokens=0,
        output_tokens=0,
        cache_creation_5m=0,
        cache_creation_1h=0,
        cache_read_input_tokens=0,
        cost_usd=0.0,
    )

    for filepath in get_all_jsonl_files():
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

                    model = msg.get("model", "")

                    totals["input_tokens"]  += usage.get("input_tokens", 0)
                    totals["output_tokens"] += usage.get("output_tokens", 0)
                    totals["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)

                    cc = usage.get("cache_creation", {}) or {}
                    c5m = cc.get("ephemeral_5m_input_tokens", 0)
                    c1h = cc.get("ephemeral_1h_input_tokens", 0)
                    if c5m == 0 and c1h == 0:
                        c5m = usage.get("cache_creation_input_tokens", 0)

                    totals["cache_creation_5m"] += c5m
                    totals["cache_creation_1h"] += c1h
                    totals["cost_usd"] += _calc_cost(usage, model)

        except (OSError, PermissionError):
            pass

    totals["window_hours"] = WINDOW_HOURS
    totals["since"] = since.isoformat()
    return totals
