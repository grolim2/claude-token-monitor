"""
Claude Token Monitor — Windows system tray app
Uses claude.ai/api/organizations/{org_id}/usage for real usage % and reset time.
Falls back to local JSONL cost calculation if API is unavailable.
"""

import threading
import tkinter as tk
from tkinter import messagebox

import pystray

from api_client import get_usage as get_api_usage
from token_tracker import get_usage_last_5h, get_window_info
from icon_generator import make_icon
from details_window import open_details
from settings_dialog import load_config, save_config, open_settings


_config = load_config()
_tray_icon = None
_stop_event = threading.Event()
_last_api_usage  = {}
_last_window_info = {}
_last_local_usage = {}


def _build_tooltip(api_usage: dict, window_info: dict, local_usage: dict) -> str:
    five_h = api_usage.get("five_hour") if not api_usage.get("error") else None
    if five_h:
        pct = five_h.get("utilization", 0)
        resets_at = five_h.get("resets_at", "")
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
            time_str = dt.astimezone().strftime("%H:%M")
        except Exception:
            time_str = resets_at[11:16] if len(resets_at) > 15 else "?"
        return f"Claude (5h): {pct:.0f}% | encerra {time_str}"[:128]
    # fallback: sem dado da API
    remaining = window_info.get("remaining_seconds", 0)
    h, r = divmod(int(remaining), 3600)
    m = r // 60
    cost = local_usage.get("cost_usd", 0.0)
    return f"Claude (5h): -- | encerra em {h}h{m:02d}m (${cost:.3f})"[:128]


def _do_refresh():
    """Fetch data from API + local, update tray icon and tooltip."""
    global _last_api_usage, _last_window_info, _last_local_usage
    try:
        api_usage   = get_api_usage()
        _last_api_usage = api_usage

        window_info = get_window_info()
        _last_window_info = window_info

        local_usage = get_usage_last_5h()
        _last_local_usage = local_usage

        five_h = api_usage.get("five_hour") if not api_usage.get("error") else None
        pct = float(five_h.get("utilization", 0)) if five_h else 0.0

        cost = local_usage.get("cost_usd", 0.0)
        icon_img = make_icon(pct, cost)
        tooltip  = _build_tooltip(api_usage, window_info, local_usage)

        if _tray_icon:
            _tray_icon.icon  = icon_img
            _tray_icon.title = tooltip

    except Exception as e:
        if _tray_icon:
            _tray_icon.title = f"Erro: {e}"[:128]


def _resets_at_dt():
    """Return the resets_at datetime from last API result, or None."""
    from datetime import datetime
    five_h = (_last_api_usage.get("five_hour")
              if not _last_api_usage.get("error") else None)
    if not five_h:
        return None
    try:
        return datetime.fromisoformat(
            five_h["resets_at"].replace("Z", "+00:00"))
    except Exception:
        return None


def _refresh():
    from datetime import datetime, timezone
    _do_refresh()
    last_poll = datetime.now(timezone.utc)
    reset_triggered = False

    while not _stop_event.is_set():
        _stop_event.wait(1)          # tick every second
        if _stop_event.is_set():
            break

        now = datetime.now(timezone.utc)
        resets_at = _resets_at_dt()

        # Detect window reset: resets_at just passed → poll immediately
        if resets_at and not reset_triggered and now >= resets_at:
            reset_triggered = True
            _do_refresh()
            last_poll = now
            continue

        # Reset the trigger guard once we're past the reset and have fresh data
        if resets_at and reset_triggered and now < resets_at:
            reset_triggered = False

        # Normal periodic poll
        elapsed = (now - last_poll).total_seconds()
        if elapsed >= _config.get("refresh_seconds", 60):
            _do_refresh()
            last_poll = now


def _show_details(icon, item):
    def get_api_usage():
        return dict(_last_api_usage)

    def get_local_usage():
        return dict(_last_local_usage)

    threading.Thread(
        target=open_details,
        args=(get_api_usage, get_local_usage, 0.0),
        daemon=True,
    ).start()


def _open_settings(icon, item):
    def on_save(new_cfg):
        global _config
        _config = new_cfg
        _stop_event.set()
        _stop_event.clear()
        threading.Thread(target=_refresh, daemon=True).start()

    threading.Thread(
        target=open_settings,
        args=(_config,),
        kwargs={"on_save": on_save},
        daemon=True,
    ).start()


def _quit_app(icon, item):
    _stop_event.set()
    icon.stop()


def main():
    global _tray_icon

    initial_img = make_icon(0, 0.0)

    menu = pystray.Menu(
        pystray.MenuItem("Ver detalhes", _show_details, default=True),
        pystray.MenuItem("Configurações", _open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", _quit_app),
    )

    _tray_icon = pystray.Icon(
        name="claude_token_monitor",
        icon=initial_img,
        title="Claude Token Monitor",
        menu=menu,
    )

    threading.Thread(target=_refresh, daemon=True).start()
    _tray_icon.run()


if __name__ == "__main__":
    main()
