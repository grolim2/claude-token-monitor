"""
Popup window: usage details + live countdown (updates every second).
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone


def _parse_dt(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def open_details(api_usage: dict, window_info: dict, usage: dict, limit_usd: float):
    win = tk.Tk()
    win.title("Claude Token Monitor")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    pad = {"padx": 8, "pady": 3}
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)

    # Prefer real API data; fall back to local window detection
    five_h = api_usage.get("five_hour") if not api_usage.get("error") else None
    seven_d = api_usage.get("seven_day") if not api_usage.get("error") else None

    if five_h:
        pct = float(five_h.get("utilization", 0))
        window_end_dt = _parse_dt(five_h.get("resets_at", ""))
        window_start_dt = (window_end_dt - __import__("datetime").timedelta(hours=5)
                          ) if window_end_dt else None
        is_active = window_end_dt is not None
        source = "API"
    else:
        is_active = window_info.get("is_active", False)
        window_end_dt   = _parse_dt(window_info.get("window_end", "")) if is_active else None
        window_start_dt = _parse_dt(window_info.get("window_start", "")) if is_active else None
        cost = usage.get("cost_usd", 0.0)
        pct = cost / limit_usd * 100 if limit_usd > 0 else 0
        source = "local"

    cost = usage.get("cost_usd", 0.0)

    # ── Title ──────────────────────────────────────────────────────────
    ttk.Label(frame, text="Claude Token Monitor",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    # ── Session window ─────────────────────────────────────────────────
    ttk.Label(frame, text="Sessão atual (5h):",
              font=("Segoe UI", 9, "bold")).grid(row=1, column=0, columnspan=2, sticky="w")

    if is_active and window_start_dt and window_end_dt:
        fmt = "%d/%m %H:%M:%S"
        start_s = window_start_dt.astimezone().strftime(fmt)
        end_s   = window_end_dt.astimezone().strftime(fmt)
        ttk.Label(frame, text=f"Início:  {start_s}",
                  font=("Consolas", 9)).grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(frame, text=f"Término: {end_s}",
                  font=("Consolas", 9)).grid(row=3, column=0, columnspan=2, sticky="w", **pad)
    else:
        ttk.Label(frame, text="Nenhuma sessão ativa nas últimas 5h",
                  foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", **pad)

    # ── Countdown ──────────────────────────────────────────────────────
    ttk.Label(frame, text="Encerra em:").grid(row=4, column=0, sticky="w", **pad)
    countdown_var = tk.StringVar(value="--:--:--")
    ttk.Label(frame, textvariable=countdown_var,
              font=("Consolas", 18, "bold"), foreground="#1565C0").grid(
              row=4, column=1, sticky="w", **pad)

    # ── Progress bar ───────────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=5, column=0, columnspan=2, sticky="ew", pady=6)
    ttk.Label(frame, text="Custo estimado (janela):",
              font=("Segoe UI", 9, "bold")).grid(row=6, column=0, columnspan=2, sticky="w")

    bar_frame = ttk.Frame(frame)
    bar_frame.grid(row=7, column=0, columnspan=2, sticky="ew", **pad)
    bar = ttk.Progressbar(bar_frame, length=280, maximum=100, value=min(pct, 100))
    bar.pack(side="left")
    ttk.Label(bar_frame, text=f"  {pct:.1f}%").pack(side="left")

    ttk.Label(frame, text=f"Custo: ${cost:.4f} USD  /  limite: ${limit_usd:.2f} USD",
              font=("Consolas", 9)).grid(row=8, column=0, columnspan=2, sticky="w", **pad)

    # ── Token breakdown ────────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=9, column=0, columnspan=2, sticky="ew", pady=6)
    ttk.Label(frame, text="Tokens na janela:",
              font=("Segoe UI", 9, "bold")).grid(row=10, column=0, columnspan=2, sticky="w")

    rows = [
        ("Input",         usage.get("input_tokens", 0)),
        ("Output",        usage.get("output_tokens", 0)),
        ("Cache 5m",      usage.get("cache_creation_5m", 0)),
        ("Cache 1h",      usage.get("cache_creation_1h", 0)),
        ("Cache leitura", usage.get("cache_read_input_tokens", 0)),
    ]
    for i, (label, val) in enumerate(rows):
        ttk.Label(frame, text=f"  {label}:",
                  font=("Consolas", 9)).grid(row=11+i, column=0, sticky="w", padx=8)
        ttk.Label(frame, text=f"{val:,}",
                  font=("Consolas", 9)).grid(row=11+i, column=1, sticky="e", padx=8)

    ttk.Button(frame, text="Fechar", command=win.destroy).grid(
        row=16, column=0, columnspan=2, pady=(10, 0))

    # ── Countdown tick (every second, no API call) ─────────────────────
    def _tick():
        if not win.winfo_exists():
            return
        if window_end_dt:
            secs = int((window_end_dt - datetime.now(timezone.utc)).total_seconds())
            if secs > 0:
                h, r = divmod(secs, 3600)
                m, s = divmod(r, 60)
                countdown_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            else:
                countdown_var.set("Encerrado!")
        else:
            countdown_var.set("--:--:--")
        win.after(1000, _tick)

    _tick()
    win.mainloop()
