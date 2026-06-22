"""
Claude Token Monitor — Windows system tray app
Uses claude.ai/api/organizations/{org_id}/usage for real usage % and reset time.
Falls back to local JSONL cost calculation if API is unavailable.
"""

import threading
import tkinter as tk
from tkinter import messagebox

import pystray

from token_tracker import get_usage_last_5h, get_window_info
from icon_generator import make_icon
from details_window import open_details
from settings_dialog import load_config, save_config, open_settings


_config = load_config()
_tray_icon = None
_stop_event = threading.Event()
_last_window_info = {}
_last_local_usage = {}


def _build_tooltip(window_info: dict, local_usage: dict) -> str:
    cost = local_usage.get("cost_usd", 0.0)
    limit = _config.get("cost_limit_usd", 8.0)
    pct = cost / limit * 100 if limit > 0 else 0
    remaining = window_info.get("remaining_seconds", 0)
    if window_info.get("is_active") and remaining > 0:
        h, r = divmod(int(remaining), 3600)
        m = r // 60
        return f"Claude (5h): ${cost:.3f} ~{pct:.0f}% | encerra em {h}h{m:02d}m"[:128]
    return f"Claude: ${cost:.3f} (sem sessao ativa)"[:128]


def _refresh():
    global _last_window_info, _last_local_usage
    while not _stop_event.is_set():
        try:
            window_info = get_window_info()
            _last_window_info = window_info

            local_usage = get_usage_last_5h()
            _last_local_usage = local_usage

            cost = local_usage.get("cost_usd", 0.0)
            limit = _config.get("cost_limit_usd", 8.0)
            pct = min(cost / limit * 100, 999.0) if limit > 0 else 0.0

            icon_img = make_icon(pct, cost)
            tooltip = _build_tooltip(window_info, local_usage)

            if _tray_icon:
                _tray_icon.icon = icon_img
                _tray_icon.title = tooltip

        except Exception as e:
            if _tray_icon:
                _tray_icon.title = f"Erro: {e}"[:128]

        _stop_event.wait(_config.get("refresh_seconds", 30))


def _show_details(icon, item):
    window_info = dict(_last_window_info)
    local_usage = dict(_last_local_usage)
    limit_usd = _config.get("cost_limit_usd", 8.0)

    threading.Thread(
        target=open_details,
        args=(window_info, local_usage, limit_usd),
        daemon=True,
    ).start()


def _open_settings(icon, item):
    def on_save(new_cfg):
        global _config
        _config = new_cfg
        _stop_event.set()
        _stop_event.clear()
        threading.Thread(target=_refresh, daemon=True).start()

    def get_current_cost():
        return _last_local_usage.get("cost_usd")

    threading.Thread(
        target=open_settings,
        args=(_config,),
        kwargs={"on_save": on_save, "get_current_cost": get_current_cost},
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
