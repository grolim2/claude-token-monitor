"""
Details window — Apple-inspired flat design.
"""

import tkinter as tk
from datetime import datetime, timezone, timedelta
from token_tracker import get_window_series, get_all_jsonl_files

# ── Palette ────────────────────────────────────────────────────────────────
BG       = "#FFFFFF"
SURFACE  = "#F5F5F7"
BORDER   = "#D2D2D7"
T_PRI    = "#1D1D1F"
T_SEC    = "#6E6E73"
T_TER    = "#AEAEB2"
BAR_NRM  = "#1D1D1F"
BAR_WARN = "#FF9F0A"
BAR_DANG = "#FF3B30"
C_LINE   = "#1D1D1F"
C_PROJ   = "#AEAEB2"
C_LIM    = "#FF3B30"
C_NOW    = "#AEAEB2"
BADGE_OK   = ("#D1F0DB", "#1A7A3A")
BADGE_WARN = ("#FDEECE", "#854F0B")
BADGE_DANG = ("#FDDCDC", "#A32D2D")

W = 420


def _parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt_tok(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}k"
    return str(int(v))


def _fmt_hm(sec):
    h, r = divmod(int(abs(sec)), 3600)
    m = r // 60
    return f"{h}h {m:02d}min" if h else f"{m}min"


# ── Weighted OLS ───────────────────────────────────────────────────────────
def _wols(xs, ys):
    import math
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    k = 3.0
    ws = [math.exp(k * i / (n - 1)) for i in range(n)]
    W  = sum(ws)
    xm = sum(w * x for w, x in zip(ws, xs)) / W
    ym = sum(w * y for w, y in zip(ws, ys)) / W
    num = sum(w * (x - xm) * (y - ym) for w, x, y in zip(ws, xs, ys))
    den = sum(w * (x - xm) ** 2        for w, x     in zip(ws, xs))
    if den == 0:
        return 0.0, ym, 0.0
    slope = num / den
    intercept = ym - slope * xm
    ss_res = sum(w * (y - (slope * x + intercept)) ** 2 for w, x, y in zip(ws, xs, ys))
    ss_tot = sum(w * (y - ym) ** 2                      for w, y     in zip(ws, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return slope, intercept, r2


# ── Chart ──────────────────────────────────────────────────────────────────
def _draw_chart(canvas, series, window_sec, api_pct, now_sec, implied_limit):
    CW, CH = int(canvas["width"]), int(canvas["height"])
    L, R, T, B = 38, 12, 10, 24
    pw = CW - L - R
    ph = CH - T - B

    canvas.delete("all")

    if len(series) < 2 or not implied_limit:
        canvas.create_text(CW // 2, CH // 2,
                           text="Dados insuficientes", fill=T_TER,
                           font=("Segoe UI", 9))
        return

    xs = [p[0] for p in series]
    ys = [p[1] for p in series]
    slope, intercept, r2 = _wols(xs, ys)
    proj_end = max(0.0, slope * window_sec + intercept)

    def tx(t): return L + pw * t / window_sec
    def ty(v): return T + ph * (1 - min(v / implied_limit, 1.1))

    # ── Grid ──
    for pct_v in [25, 50, 75, 100]:
        yp = ty(implied_limit * pct_v / 100)
        canvas.create_line(L, yp, CW - R, yp, fill=BORDER, dash=(3, 4))
        canvas.create_text(L - 4, yp, text=f"{pct_v}%",
                           anchor="e", font=("Segoe UI", 8), fill=T_TER)

    # X labels
    for h in range(0, 6):
        xp = tx(h * 3600)
        canvas.create_line(xp, T, xp, CH - B, fill=BORDER, dash=(3, 4))
        canvas.create_text(xp, CH - B + 4, text=f"{h}h",
                           anchor="n", font=("Segoe UI", 8), fill=T_TER)

    # Axes
    canvas.create_line(L, T, L, CH - B, fill=BORDER)
    canvas.create_line(L, CH - B, CW - R, CH - B, fill=BORDER)

    # ── Limit line ──
    yp_lim = ty(implied_limit)
    canvas.create_line(L, yp_lim, CW - R, yp_lim,
                       fill=C_LIM, dash=(5, 3), width=1)

    # ── Projection line (from now to window end) ──
    proj_x0 = max(0, now_sec)
    proj_pts = []
    for i in range(41):
        t = proj_x0 + (window_sec - proj_x0) * i / 40
        v = max(0, slope * t + intercept)
        proj_pts += [tx(t), ty(v)]
    if len(proj_pts) >= 4:
        canvas.create_line(*proj_pts, fill=C_PROJ, width=1, dash=(5, 4))

    # Projection end dot
    canvas.create_oval(tx(window_sec) - 3, ty(max(0, proj_end)) - 3,
                       tx(window_sec) + 3, ty(max(0, proj_end)) + 3,
                       fill=C_PROJ, outline="")

    # ── Actual line (extended to now) ──
    display = list(series)
    if now_sec > xs[-1]:
        display.append((now_sec, ys[-1]))
    pts = []
    for t, v in display:
        pts += [tx(t), ty(v)]
    if len(pts) >= 4:
        canvas.create_line(*pts, fill=C_LINE, width=2,
                           capstyle="round", joinstyle="round")

    # Endpoint dot at now
    dx, dy = tx(now_sec), ty(ys[-1])
    canvas.create_oval(dx - 4, dy - 4, dx + 4, dy + 4,
                       fill=C_LINE, outline=BG, width=2)

    # ── Now line ──
    xn = tx(now_sec)
    canvas.create_line(xn, T, xn, CH - B, fill=C_NOW, dash=(3, 3))
    canvas.create_text(xn + 3, T + 2, text="agora",
                       anchor="nw", font=("Segoe UI", 8), fill=T_TER)

    # ── Legend ──
    lx, ly = L + 4, T + 4
    canvas.create_line(lx, ly + 5, lx + 14, ly + 5, fill=C_LINE, width=2)
    canvas.create_text(lx + 18, ly + 5, text="real", anchor="w",
                       font=("Segoe UI", 8), fill=T_SEC)
    canvas.create_line(lx, ly + 17, lx + 14, ly + 17,
                       fill=C_PROJ, width=1, dash=(4, 3))
    canvas.create_text(lx + 18, ly + 17, text="projeção", anchor="w",
                       font=("Segoe UI", 8), fill=T_SEC)

    return slope, intercept, r2, proj_end, implied_limit


# ── Helper widgets ─────────────────────────────────────────────────────────
def _divider(parent, row):
    f = tk.Frame(parent, bg=BORDER, height=1)
    f.grid(row=row, column=0, sticky="ew", padx=0)


def _section(parent, row):
    f = tk.Frame(parent, bg=BG)
    f.grid(row=row, column=0, sticky="ew", padx=20, pady=(14, 14))
    f.columnconfigure(0, weight=1)
    return f


def _label(parent, text, size=11, color=T_TER, bold=False, row=0, col=0,
           anchor="w", colspan=1, pady=0):
    weight = "bold" if bold else "normal"
    lbl = tk.Label(parent, text=text, bg=BG, fg=color,
                   font=("Segoe UI", size, weight), anchor=anchor)
    lbl.grid(row=row, column=col, columnspan=colspan,
             sticky="w" if anchor == "w" else "e", pady=pady)
    return lbl


def _section_title(parent, text, row):
    tk.Label(parent, text=text.upper(), bg=BG, fg=T_TER,
             font=("Segoe UI", 10, "normal"),
             anchor="w").grid(row=row, column=0, sticky="w", pady=(0, 8))


def _tok_card(parent, label, value, row, col):
    card = tk.Frame(parent, bg=SURFACE, padx=10, pady=8)
    card.grid(row=row, column=col, sticky="nsew", padx=(0 if col else 0, 6 if col == 0 else 0), pady=3)
    tk.Label(card, text=label, bg=SURFACE, fg=T_TER,
             font=("Segoe UI", 10)).pack(anchor="w")
    tk.Label(card, text=value, bg=SURFACE, fg=T_PRI,
             font=("Segoe UI", 13, "bold")).pack(anchor="w")


# ── Badge ──────────────────────────────────────────────────────────────────
def _badge_label(parent, text, style="ok"):
    colors = {"ok": BADGE_OK, "warn": BADGE_WARN, "danger": BADGE_DANG}
    bg, fg = colors.get(style, BADGE_OK)
    f = tk.Frame(parent, bg=bg, padx=7, pady=2)
    tk.Label(f, text=text, bg=bg, fg=fg,
             font=("Segoe UI", 10)).pack()
    return f


# ── Main window ────────────────────────────────────────────────────────────
def open_details(api_usage: dict, window_info: dict, usage: dict, limit_usd: float):
    win = tk.Tk()
    win.title("Claude Token Monitor")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.attributes("-topmost", True)

    outer = tk.Frame(win, bg=BG, width=W)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)

    five_h = api_usage.get("five_hour") if not api_usage.get("error") else None

    if five_h:
        pct = float(five_h.get("utilization", 0))
        window_end_dt   = _parse_dt(five_h.get("resets_at", ""))
        window_start_dt = (window_end_dt - timedelta(hours=5)) if window_end_dt else None
        is_active = window_end_dt is not None
    else:
        is_active = window_info.get("is_active", False)
        window_end_dt   = _parse_dt(window_info.get("window_end", "")) if is_active else None
        window_start_dt = _parse_dt(window_info.get("window_start", "")) if is_active else None
        pct = 0.0

    cost = usage.get("cost_usd", 0.0)
    total_tokens = (
        usage.get("input_tokens", 0) +
        usage.get("output_tokens", 0) +
        usage.get("cache_creation_5m", 0) +
        usage.get("cache_creation_1h", 0) +
        usage.get("cache_read_input_tokens", 0)
    )
    implied_limit = (total_tokens / (pct / 100.0)) if pct > 0 and total_tokens > 0 else None

    row = 0

    # ── HEADER ─────────────────────────────────────────────────────────────
    hdr = tk.Frame(outer, bg=BG)
    hdr.grid(row=row, column=0, sticky="ew", padx=20, pady=(18, 14))
    hdr.columnconfigure(0, weight=1)
    row += 1

    # Logo + title
    top = tk.Frame(hdr, bg=BG)
    top.pack(fill="x", anchor="w")

    logo = tk.Frame(top, bg=T_PRI, width=32, height=32)
    logo.pack(side="left")
    logo.pack_propagate(False)
    tk.Label(logo, text="C", bg=T_PRI, fg="white",
             font=("Segoe UI", 15, "bold")).place(relx=0.5, rely=0.5, anchor="center")

    title_blk = tk.Frame(top, bg=BG)
    title_blk.pack(side="left", padx=(10, 0))
    tk.Label(title_blk, text="Claude Token Monitor", bg=BG, fg=T_PRI,
             font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
    tk.Label(title_blk, text="Sessão atual · janela de 5h", bg=BG, fg=T_SEC,
             font=("Segoe UI", 10), anchor="w").pack(anchor="w")

    # Countdown + window range
    mid = tk.Frame(hdr, bg=BG)
    mid.pack(fill="x", pady=(14, 0))

    cd_blk = tk.Frame(mid, bg=BG)
    cd_blk.pack(side="left")
    tk.Label(cd_blk, text="encerra em", bg=BG, fg=T_TER,
             font=("Segoe UI", 10)).pack(anchor="w")
    countdown_var = tk.StringVar(value="--:--:--")
    tk.Label(cd_blk, textvariable=countdown_var, bg=BG, fg=T_PRI,
             font=("Segoe UI", 26, "bold"), anchor="w").pack(anchor="w")

    if is_active and window_start_dt and window_end_dt:
        local_tz = datetime.now().astimezone().tzinfo
        fmt = "%d/%m %H:%M"
        s_str = window_start_dt.astimezone(local_tz).strftime(fmt)
        e_str = window_end_dt.astimezone(local_tz).strftime(fmt)
        rng_blk = tk.Frame(mid, bg=BG)
        rng_blk.pack(side="right")
        tk.Label(rng_blk, text=f"início  {s_str}", bg=BG, fg=T_TER,
                 font=("Segoe UI", 10), anchor="e").pack(anchor="e")
        tk.Label(rng_blk, text=f"término {e_str}", bg=BG, fg=T_TER,
                 font=("Segoe UI", 10), anchor="e").pack(anchor="e")

    # ── CONSUMPTION ────────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec1 = _section(outer, row); row += 1

    _section_title(sec1, "consumo", 0)

    num_row = tk.Frame(sec1, bg=BG)
    num_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    bar_color = BAR_DANG if pct >= 80 else (BAR_WARN if pct >= 50 else BAR_NRM)

    tk.Label(num_row, text=f"{pct:.0f}%", bg=BG, fg=bar_color,
             font=("Segoe UI", 36, "bold"), anchor="w").pack(side="left")

    meta = tk.Frame(num_row, bg=BG)
    meta.pack(side="right", anchor="se")
    tk.Label(meta, text=f"{total_tokens:,} tokens".replace(",", "."),
             bg=BG, fg=T_SEC, font=("Segoe UI", 12), anchor="e").pack(anchor="e")
    tk.Label(meta, text=f"${cost:.4f} USD",
             bg=BG, fg=T_TER, font=("Segoe UI", 10), anchor="e").pack(anchor="e")

    # Progress bar (Canvas)
    bar_w = W - 40
    bar_canvas = tk.Canvas(sec1, width=bar_w, height=6, bg=SURFACE,
                           highlightthickness=0, bd=0)
    bar_canvas.grid(row=2, column=0, sticky="ew")
    fill_w = int(bar_w * min(pct / 100, 1.0))
    if fill_w > 0:
        bar_canvas.create_rectangle(0, 0, fill_w, 6, fill=bar_color, outline="")

    # ── CHART ──────────────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec2 = _section(outer, row); row += 1

    _section_title(sec2, "consumo acumulado", 0)

    chart_w = W - 40
    chart_cv = tk.Canvas(sec2, width=chart_w, height=140, bg=BG,
                         highlightthickness=0, bd=0)
    chart_cv.grid(row=1, column=0, sticky="ew")

    proj_frame = tk.Frame(sec2, bg=BG)
    proj_frame.grid(row=2, column=0, sticky="w", pady=(8, 0))
    proj_badge_holder = tk.Frame(proj_frame, bg=BG)
    proj_badge_holder.pack(side="left")
    proj_text_var = tk.StringVar(value="calculando projeção...")
    tk.Label(proj_frame, textvariable=proj_text_var, bg=BG, fg=T_SEC,
             font=("Segoe UI", 11)).pack(side="left", padx=(8, 0))

    _proj_badge = [None]

    def _update_proj(proj_pct, r2, t_hit, window_sec):
        for w in proj_badge_holder.winfo_children():
            w.destroy()
        remaining_pct = max(0.0, 100 - proj_pct)
        if t_hit is not None and t_hit <= window_sec:
            badge = _badge_label(proj_badge_holder, "atenção", "danger")
            proj_text_var.set(
                f"limite atingido {_fmt_hm(window_sec - t_hit)} antes do fim  ·  R²={r2:.2f}")
        else:
            badge = _badge_label(proj_badge_holder, "projeção", "warn" if proj_pct > 80 else "ok")
            proj_text_var.set(
                f"{proj_pct:.0f}% ao fim · {remaining_pct:.0f}% restante  ·  R²={r2:.2f}")
        badge.pack()

    # ── TOKEN BREAKDOWN ────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec3 = _section(outer, row); row += 1

    _section_title(sec3, "detalhes de tokens", 0)
    sec3.columnconfigure(0, weight=1)
    sec3.columnconfigure(1, weight=1)

    tok_data = [
        ("input",        usage.get("input_tokens", 0)),
        ("output",       usage.get("output_tokens", 0)),
        ("cache 5m",     usage.get("cache_creation_5m", 0)),
        ("cache leitura",usage.get("cache_read_input_tokens", 0)),
    ]
    for i, (lbl, val) in enumerate(tok_data):
        r2c, c2c = divmod(i, 2)
        card = tk.Frame(sec3, bg=SURFACE, padx=10, pady=8)
        card.grid(row=r2c + 1, column=c2c, sticky="nsew",
                  padx=(0, 4) if c2c == 0 else (4, 0), pady=3)
        tk.Label(card, text=lbl, bg=SURFACE, fg=T_TER,
                 font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(card, text=f"{val:,}".replace(",", "."),
                 bg=SURFACE, fg=T_PRI,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

    # Close button
    _divider(outer, row); row += 1
    btn_frame = tk.Frame(outer, bg=BG)
    btn_frame.grid(row=row, column=0, pady=14)
    tk.Button(btn_frame, text="Fechar", command=win.destroy,
              bg=BG, fg=T_PRI, relief="flat", bd=0,
              font=("Segoe UI", 12),
              activebackground=SURFACE, cursor="hand2",
              padx=20, pady=6).pack()

    # ── JSONL watcher ──────────────────────────────────────────────────────
    def _jsonl_snapshot():
        result = {}
        for f in get_all_jsonl_files():
            try:
                result[str(f)] = f.stat().st_mtime
            except OSError:
                pass
        return result

    _cached_series = [get_window_series()]
    _last_snap     = [_jsonl_snapshot()]
    _window_sec    = 5 * 3600

    def _chart_tick():
        if not win.winfo_exists():
            return
        try:
            snap = _jsonl_snapshot()
            if snap != _last_snap[0]:
                _last_snap[0] = snap
                _cached_series[0] = get_window_series()

            now_sec = 0.0
            if window_start_dt:
                now_sec = min(
                    (datetime.now(timezone.utc) - window_start_dt).total_seconds(),
                    _window_sec)

            series = _cached_series[0]
            lim = implied_limit

            result = _draw_chart(chart_cv, series, _window_sec, pct, now_sec, lim)

            if result and lim:
                sl, ic, r2val, proj_end, _ = result
                proj_pct = min(proj_end / lim * 100, 999)
                t_hit = ((lim - ic) / sl) if sl > 0 else None
                _update_proj(proj_pct, r2val, t_hit, _window_sec)
        except Exception:
            pass
        win.after(1_000, _chart_tick)

    def _countdown_tick():
        if not win.winfo_exists():
            return
        try:
            if window_end_dt:
                secs = int((window_end_dt - datetime.now(timezone.utc)).total_seconds())
                if secs > 0:
                    h, rem = divmod(secs, 3600)
                    m, s   = divmod(rem, 60)
                    countdown_var.set(f"{h:02d}:{m:02d}:{s:02d}")
                else:
                    countdown_var.set("Encerrado!")
            else:
                countdown_var.set("--:--:--")
        except Exception:
            pass
        win.after(1_000, _countdown_tick)

    win.after(100, _chart_tick)
    _countdown_tick()
    win.mainloop()
