"""
Popup window: usage details + live countdown + cumulative token chart.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta
from token_tracker import get_window_series


def _parse_dt(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Weighted OLS linear regression on cumulative series
# ---------------------------------------------------------------------------
def _weighted_ols(xs, ys):
    """
    Weighted least-squares: y = slope*x + intercept.
    More recent points get exponentially higher weight so the projection
    reacts faster to acceleration/deceleration in usage.
    Returns (slope, intercept, r2).
    """
    n = len(xs)
    if n < 2:
        return (0.0, 0.0, 0.0)

    # Exponential weights: w_i = exp(k * i/n), k=3 → last point ~20x first
    import math
    k = 3.0
    ws = [math.exp(k * i / (n - 1)) for i in range(n)]
    W  = sum(ws)

    xm = sum(w * x for w, x in zip(ws, xs)) / W
    ym = sum(w * y for w, y in zip(ws, ys)) / W

    num = sum(w * (x - xm) * (y - ym) for w, x, y in zip(ws, xs, ys))
    den = sum(w * (x - xm) ** 2        for w, x     in zip(ws, xs))

    if den == 0:
        return (0.0, ym, 0.0)

    slope     = num / den
    intercept = ym - slope * xm

    ss_res = sum(w * (y - (slope * x + intercept)) ** 2 for w, x, y in zip(ws, xs, ys))
    ss_tot = sum(w * (y - ym) ** 2                      for w, y     in zip(ws, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0

    return (slope, intercept, r2)


# ---------------------------------------------------------------------------
# Canvas chart
# ---------------------------------------------------------------------------
def _draw_chart(canvas, series, window_sec, api_pct, now_sec):
    """
    Draw cumulative token chart on a tkinter Canvas.
    series     : [(t_sec, cumul_tokens), ...] actual data
    window_sec : total window duration in seconds (18000)
    api_pct    : utilization % from API (0-100), used to back-calculate limit
    now_sec    : elapsed seconds since window start (= current t)
    """
    W = int(canvas["width"])
    H = int(canvas["height"])
    PAD = {"l": 64, "r": 16, "t": 14, "b": 32}

    cw = W - PAD["l"] - PAD["r"]
    ch = H - PAD["t"] - PAD["b"]

    canvas.delete("all")

    if len(series) < 2:
        canvas.create_text(W // 2, H // 2, text="Dados insuficientes",
                           fill="#888", font=("Segoe UI", 9))
        return

    xs = [p[0] for p in series]
    ys = [p[1] for p in series]

    slope, intercept, r2 = _weighted_ols(xs, ys)

    # Projected value at window end
    proj_end = max(0.0, slope * window_sec + intercept)
    current_tokens = ys[-1]

    # Back-calculate implied token limit from API utilization%
    implied_limit = None
    if api_pct and api_pct > 0 and current_tokens > 0:
        implied_limit = current_tokens / (api_pct / 100.0)

    # Y axis range
    y_max = max(current_tokens, proj_end)
    if implied_limit:
        y_max = max(y_max, implied_limit * 1.05)
    y_max = y_max * 1.1 if y_max > 0 else 1

    def tx(t): return PAD["l"] + cw * t / window_sec
    def ty(v): return PAD["t"] + ch * (1 - v / y_max)

    def fmt_tok(v):
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}k"
        return str(int(v))

    def fmt_hm(sec):
        h, r = divmod(int(sec), 3600)
        m = r // 60
        return f"{h}h{m:02d}" if h else f"{m}min"

    # ── Grid & axes ──────────────────────────────────────────────────────
    # Y grid lines (4 lines)
    for i in range(1, 5):
        yv = y_max * i / 4
        yp = ty(yv)
        canvas.create_line(PAD["l"], yp, W - PAD["r"], yp, fill="#e0e0e0", dash=(3, 4))
        canvas.create_text(PAD["l"] - 4, yp, text=fmt_tok(yv),
                           anchor="e", font=("Consolas", 7), fill="#666")

    # X grid lines (every hour)
    for h in range(0, 6):
        xp = tx(h * 3600)
        canvas.create_line(xp, PAD["t"], xp, H - PAD["b"], fill="#e0e0e0", dash=(3, 4))
        canvas.create_text(xp, H - PAD["b"] + 4, text=f"{h}h",
                           anchor="n", font=("Consolas", 7), fill="#666")

    # Axes
    canvas.create_line(PAD["l"], PAD["t"], PAD["l"], H - PAD["b"], fill="#aaa", width=1)
    canvas.create_line(PAD["l"], H - PAD["b"], W - PAD["r"], H - PAD["b"], fill="#aaa", width=1)

    # ── Implied limit line ───────────────────────────────────────────────
    if implied_limit and implied_limit <= y_max:
        yp = ty(implied_limit)
        canvas.create_line(PAD["l"], yp, W - PAD["r"], yp,
                           fill="#cc4444", dash=(6, 3), width=1)
        canvas.create_text(W - PAD["r"] - 2, yp - 6,
                           text=f"Limite ~{fmt_tok(implied_limit)}",
                           anchor="e", font=("Consolas", 7), fill="#cc4444")

    # ── Projection line (extend from t=0 to t=window_sec) ────────────────
    # Draw as dashed red from now → window end
    proj_x0 = max(0, now_sec)
    proj_y0 = slope * proj_x0 + intercept
    proj_pts = []
    steps = 40
    for i in range(steps + 1):
        t = proj_x0 + (window_sec - proj_x0) * i / steps
        v = slope * t + intercept
        proj_pts += [tx(t), ty(max(0, v))]
    if len(proj_pts) >= 4:
        canvas.create_line(*proj_pts, fill="#e07b00", width=1,
                           dash=(5, 4))

    # Projection endpoint marker
    canvas.create_oval(tx(window_sec) - 3, ty(max(0, proj_end)) - 3,
                       tx(window_sec) + 3, ty(max(0, proj_end)) + 3,
                       fill="#e07b00", outline="")

    # ── Actual cumulative line ───────────────────────────────────────────
    pts = []
    for t, v in series:
        pts += [tx(t), ty(v)]
    if len(pts) >= 4:
        canvas.create_line(*pts, fill="#1565C0", width=2)

    # Actual endpoint dot
    canvas.create_oval(tx(xs[-1]) - 4, ty(ys[-1]) - 4,
                       tx(xs[-1]) + 4, ty(ys[-1]) + 4,
                       fill="#1565C0", outline="white", width=1)

    # ── "Now" vertical line ──────────────────────────────────────────────
    xnow = tx(now_sec)
    canvas.create_line(xnow, PAD["t"], xnow, H - PAD["b"],
                       fill="#555", dash=(4, 3), width=1)
    canvas.create_text(xnow + 2, PAD["t"] + 2, text="agora",
                       anchor="nw", font=("Segoe UI", 7), fill="#555")

    # ── Projection annotation ────────────────────────────────────────────
    if implied_limit and implied_limit > 0:
        # Time when projection hits the limit
        if slope > 0:
            t_hit = (implied_limit - intercept) / slope
        else:
            t_hit = float("inf")

        remaining_sec = window_sec - now_sec
        if t_hit <= window_sec:
            mins_before_end = (window_sec - t_hit) / 60
            msg = f"⚠ Projeção atinge limite {fmt_hm(window_sec - t_hit)} antes do fim (R²={r2:.2f})"
            col = "#c0392b"
        else:
            msg = f"✓ Projeção: {fmt_tok(int(proj_end))} ao fim  (R²={r2:.2f})"
            col = "#27ae60"
    else:
        msg = f"Projeção ao fim: {fmt_tok(int(proj_end))}  (R²={r2:.2f})"
        col = "#555"

    canvas.create_text(PAD["l"] + cw // 2, PAD["t"] - 2, text=msg,
                       anchor="s", font=("Segoe UI", 8), fill=col)

    # ── Legend ───────────────────────────────────────────────────────────
    lx, ly = PAD["l"] + 6, PAD["t"] + 6
    canvas.create_line(lx, ly + 4, lx + 16, ly + 4, fill="#1565C0", width=2)
    canvas.create_text(lx + 20, ly + 4, text="Real", anchor="w",
                       font=("Segoe UI", 7), fill="#1565C0")
    canvas.create_line(lx, ly + 16, lx + 16, ly + 16, fill="#e07b00",
                       width=1, dash=(5, 3))
    canvas.create_text(lx + 20, ly + 16, text="Projeção", anchor="w",
                       font=("Segoe UI", 7), fill="#e07b00")


# ---------------------------------------------------------------------------
# Details window
# ---------------------------------------------------------------------------
def open_details(api_usage: dict, window_info: dict, usage: dict, limit_usd: float):
    win = tk.Tk()
    win.title("Claude Token Monitor")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    pad = {"padx": 8, "pady": 3}
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)

    five_h = api_usage.get("five_hour") if not api_usage.get("error") else None

    if five_h:
        pct = float(five_h.get("utilization", 0))
        window_end_dt = _parse_dt(five_h.get("resets_at", ""))
        window_start_dt = (window_end_dt - timedelta(hours=5)) if window_end_dt else None
        is_active = window_end_dt is not None
    else:
        is_active = window_info.get("is_active", False)
        window_end_dt   = _parse_dt(window_info.get("window_end", "")) if is_active else None
        window_start_dt = _parse_dt(window_info.get("window_start", "")) if is_active else None
        cost = usage.get("cost_usd", 0.0)
        pct  = 0.0

    cost = usage.get("cost_usd", 0.0)

    # ── Title ──────────────────────────────────────────────────────────
    ttk.Label(frame, text="Claude Token Monitor",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    # ── Session window ─────────────────────────────────────────────────
    ttk.Label(frame, text="Sessão atual (5h):",
              font=("Segoe UI", 9, "bold")).grid(row=1, column=0, columnspan=2, sticky="w")

    if is_active and window_start_dt and window_end_dt:
        fmt = "%d/%m %H:%M:%S"
        local_tz = datetime.now().astimezone().tzinfo
        start_s = window_start_dt.astimezone(local_tz).strftime(fmt)
        end_s   = window_end_dt.astimezone(local_tz).strftime(fmt)
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

    bar_frame = ttk.Frame(frame)
    bar_frame.grid(row=6, column=0, columnspan=2, sticky="ew", **pad)
    bar = ttk.Progressbar(bar_frame, length=360, maximum=100, value=min(pct, 100))
    bar.pack(side="left")
    ttk.Label(bar_frame, text=f"  {pct:.1f}%").pack(side="left")

    total_tokens = (
        usage.get("input_tokens", 0) +
        usage.get("output_tokens", 0) +
        usage.get("cache_creation_5m", 0) +
        usage.get("cache_creation_1h", 0) +
        usage.get("cache_read_input_tokens", 0)
    )
    ttk.Label(frame, text=f"Total: {total_tokens:,} tokens  |  ${cost:.4f} USD",
              font=("Consolas", 9)).grid(row=7, column=0, columnspan=2, sticky="w", **pad)

    # ── Cumulative token chart ─────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=8, column=0, columnspan=2, sticky="ew", pady=6)
    ttk.Label(frame, text="Consumo acumulado na janela:",
              font=("Segoe UI", 9, "bold")).grid(row=9, column=0, columnspan=2, sticky="w")

    chart_canvas = tk.Canvas(frame, width=420, height=180, bg="white",
                             highlightthickness=1, highlightbackground="#ccc")
    chart_canvas.grid(row=10, column=0, columnspan=2, padx=8, pady=4)

    # ── Token breakdown ────────────────────────────────────────────────
    ttk.Separator(frame, orient="horizontal").grid(
        row=11, column=0, columnspan=2, sticky="ew", pady=6)
    ttk.Label(frame, text="Tokens na janela:",
              font=("Segoe UI", 9, "bold")).grid(row=12, column=0, columnspan=2, sticky="w")

    rows = [
        ("Input",         usage.get("input_tokens", 0)),
        ("Output",        usage.get("output_tokens", 0)),
        ("Cache 5m",      usage.get("cache_creation_5m", 0)),
        ("Cache 1h",      usage.get("cache_creation_1h", 0)),
        ("Cache leitura", usage.get("cache_read_input_tokens", 0)),
    ]
    for i, (label, val) in enumerate(rows):
        ttk.Label(frame, text=f"  {label}:",
                  font=("Consolas", 9)).grid(row=13 + i, column=0, sticky="w", padx=8)
        ttk.Label(frame, text=f"{val:,}",
                  font=("Consolas", 9)).grid(row=13 + i, column=1, sticky="e", padx=8)

    ttk.Button(frame, text="Fechar", command=win.destroy).grid(
        row=18, column=0, columnspan=2, pady=(10, 0))

    # ── Draw chart (once, after window is rendered) ────────────────────
    def _draw():
        series = get_window_series()
        window_sec = 5 * 3600
        now_sec = 0.0
        if window_start_dt:
            now_sec = min(
                (datetime.now(timezone.utc) - window_start_dt).total_seconds(),
                window_sec
            )
        _draw_chart(chart_canvas, series, window_sec, pct, now_sec)

    win.after(100, _draw)

    # ── Countdown tick (every second) ─────────────────────────────────
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
