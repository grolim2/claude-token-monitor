"""
Claude Token Monitor — Windows system tray app
Reads Claude Code session files from ~/.claude/projects/ and shows
token consumption for the last 5 hours in the system tray icon.
"""

import threading
import time
import sys
import tkinter as tk
from tkinter import messagebox

import pystray
from PIL import Image

from token_tracker import get_usage_last_5h
from icon_generator import make_icon
from settings_dialog import load_config, save_config, open_settings


_config = load_config()
_tray_icon = None
_stop_event = threading.Event()
_last_usage = {}


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def _build_tooltip(usage: dict, limit: int) -> str:
    total = usage.get("total_tokens", 0)
    pct = min(100, total / limit * 100) if limit > 0 else 0
    lines = [
        f"Claude Token Monitor — últimas {usage.get('window_hours', 5)}h",
        f"Total: {_fmt_tokens(total)} / {_fmt_tokens(limit)}  ({pct:.1f}%)",
        f"  Input:    {_fmt_tokens(usage.get('input_tokens', 0))}",
        f"  Output:   {_fmt_tokens(usage.get('output_tokens', 0))}",
        f"  Cache wr: {_fmt_tokens(usage.get('cache_creation_input_tokens', 0))}",
        f"  Cache rd: {_fmt_tokens(usage.get('cache_read_input_tokens', 0))}",
    ]
    return "\n".join(lines)


def _refresh_icon():
    global _last_usage
    while not _stop_event.is_set():
        try:
            usage = get_usage_last_5h()
            _last_usage = usage
            limit = _config.get("token_limit", 1_000_000)
            total = usage.get("total_tokens", 0)
            pct = min(100.0, total / limit * 100) if limit > 0 else 0.0

            icon_img = make_icon(pct)
            tooltip = _build_tooltip(usage, limit)

            if _tray_icon:
                _tray_icon.icon = icon_img
                _tray_icon.title = tooltip
        except Exception as e:
            if _tray_icon:
                _tray_icon.title = f"Erro ao ler dados: {e}"

        _stop_event.wait(_config.get("refresh_seconds", 60))


def _show_details(icon, item):
    usage = _last_usage
    limit = _config.get("token_limit", 1_000_000)
    if not usage:
        return
    msg = _build_tooltip(usage, limit)

    def _tk():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo("Claude Token Monitor", msg, parent=root)
        root.destroy()

    threading.Thread(target=_tk, daemon=True).start()


def _open_settings(icon, item):
    def on_save(new_cfg):
        global _config
        _config = new_cfg
        _stop_event.set()
        _stop_event.clear()
        threading.Thread(target=_refresh_icon, daemon=True).start()

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

    initial_img = make_icon(0)

    menu = pystray.Menu(
        pystray.MenuItem("Ver detalhes", _show_details, default=True),
        pystray.MenuItem("Configurações", _open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", _quit_app),
    )

    _tray_icon = pystray.Icon(
        name="claude_token_monitor",
        icon=initial_img,
        title="Claude Token Monitor — carregando...",
        menu=menu,
    )

    # Start background refresh thread
    refresh_thread = threading.Thread(target=_refresh_icon, daemon=True)
    refresh_thread.start()

    _tray_icon.run()


if __name__ == "__main__":
    main()
