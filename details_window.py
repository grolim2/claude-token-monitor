"""
Details window — Apple-inspired flat design.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta
from token_tracker import get_window_series, get_all_jsonl_files
import ctypes

# Enable per-monitor DPI awareness before any Tk window is created
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _apply_light_titlebar(win):
    """Set white title bar and remove icon via Windows DWM + Win32 (Win10/11)."""
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        # DWM: disable dark mode
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(0)), 4)
        # DWM: white caption background (Win11 attr 35)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(ctypes.c_int(0x00FFFFFF)), 4)
        # DWM: dark caption text (Win11 attr 36)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(ctypes.c_int(0x001D1D1F)), 4)
        # Remove icon: WS_EX_DLGMODALFRAME suppresses the icon area
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00000001)  # WS_EX_DLGMODALFRAME
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, 0)  # WM_SETICON ICON_BIG = NULL
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, 0)  # WM_SETICON ICON_SMALL = NULL
        # Force title bar redraw to apply the new style
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            0x0001 | 0x0002 | 0x0004 | 0x0020)  # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED
    except Exception:
        pass


def _make_slim_scrollbar(parent, canvas):
    """Thin 6px ttk scrollbar without arrows, matching the light palette."""
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Slim.Vertical.TScrollbar",
        background=BORDER,
        troughcolor=BG,
        borderwidth=0,
        relief="flat",
        arrowsize=0,
        width=6,
    )
    style.layout("Slim.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {
            "sticky": "ns",
            "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
            ]
        })
    ])
    sb = ttk.Scrollbar(parent, orient="vertical",
                       command=canvas.yview, style="Slim.Vertical.TScrollbar")
    return sb

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

W = 340


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
    canvas.update_idletasks()
    CW = canvas.winfo_width() or int(canvas["width"]) if canvas["width"] != "" else 300
    CH = canvas.winfo_height() or int(canvas["height"]) if canvas["height"] != "" else 140
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

    # Extend series to now so OLS accounts for any flat period since last event
    ols_xs = xs + ([now_sec] if now_sec > xs[-1] else [])
    ols_ys = ys + ([ys[-1]] if now_sec > xs[-1] else [])
    slope, intercept, r2 = _wols(ols_xs, ols_ys)

    # Anchor projection to actual current value to avoid intercept drift
    cur_val  = ys[-1]
    rem_sec  = max(0.0, window_sec - now_sec)
    proj_end = max(cur_val, cur_val + slope * rem_sec)

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

    # ── Projection line anchored at current real value ──
    proj_pts = []
    for i in range(41):
        t = now_sec + rem_sec * i / 40
        v = max(0, cur_val + slope * (t - now_sec))
        proj_pts += [tx(t), ty(v)]
    if len(proj_pts) >= 4:
        canvas.create_line(*proj_pts, fill=C_PROJ, width=1, dash=(5, 4))

    # Projection end dot
    canvas.create_oval(tx(window_sec) - 3, ty(proj_end) - 3,
                       tx(window_sec) + 3, ty(proj_end) + 3,
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
                           capstyle="round", joinstyle="round", smooth=True)

    # Endpoint dot at now — draw ring for crispness
    dx, dy = tx(now_sec), ty(ys[-1])
    canvas.create_oval(dx - 5, dy - 5, dx + 5, dy + 5, fill=BG, outline=C_LINE, width=2)
    canvas.create_oval(dx - 2, dy - 2, dx + 2, dy + 2, fill=C_LINE, outline="")

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

    return slope, cur_val, r2, proj_end, implied_limit


# ── Helper widgets ─────────────────────────────────────────────────────────
def _divider(parent, row):
    f = tk.Frame(parent, bg=BORDER, height=1)
    f.grid(row=row, column=0, sticky="ew", padx=0)


def _section(parent, row):
    f = tk.Frame(parent, bg=BG)
    f.grid(row=row, column=0, sticky="ew", padx=16, pady=(12, 12))
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
def open_details(get_api_usage, get_local_usage, limit_usd: float, win_ref=None):
    win = tk.Tk()
    win.title("")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.minsize(300, 360)

    win.geometry(f"{W}x560")

    # Transparent 16x16 ICO to hide the default Tkinter feather icon
    try:
        from PIL import Image
        import tempfile, os
        _ico = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        _fd, _ico_path = tempfile.mkstemp(suffix=".ico")
        os.close(_fd)
        _ico.save(_ico_path, format="ICO")
        win.iconbitmap(default=_ico_path)
    except Exception:
        pass
    if win_ref is not None:
        win_ref[0] = win
    win.after(50, lambda: _apply_light_titlebar(win))

    # ── Scrollable container ───────────────────────────────────────────────
    _scroll_cv = tk.Canvas(win, bg=BG, highlightthickness=0, bd=0)
    _scrollbar = _make_slim_scrollbar(win, _scroll_cv)
    _scroll_cv.configure(yscrollcommand=_scrollbar.set)
    _scrollbar.pack(side="right", fill="y")
    _scroll_cv.pack(side="left", fill="both", expand=True)

    outer = tk.Frame(_scroll_cv, bg=BG)
    outer.columnconfigure(0, weight=1)
    _outer_id = _scroll_cv.create_window((0, 0), window=outer, anchor="nw")

    def _on_content_resize(event):
        _scroll_cv.configure(scrollregion=_scroll_cv.bbox("all"))

    def _on_canvas_resize(event):
        _scroll_cv.itemconfig(_outer_id, width=event.width)

    outer.bind("<Configure>", _on_content_resize)
    _scroll_cv.bind("<Configure>", _on_canvas_resize)

    def _on_mousewheel(event):
        _scroll_cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

    win.bind_all("<MouseWheel>", _on_mousewheel)

    def _extract(api_usage, local_usage):
        five_h = api_usage.get("five_hour") if not api_usage.get("error") else None
        if five_h:
            pct            = float(five_h.get("utilization", 0))
            window_end_dt  = _parse_dt(five_h.get("resets_at", ""))
            window_start_dt= (window_end_dt - timedelta(hours=5)) if window_end_dt else None
        else:
            pct             = 0.0
            window_end_dt   = None
            window_start_dt = None

        usage = local_usage
        cost  = usage.get("cost_usd", 0.0)
        total = (usage.get("input_tokens", 0) + usage.get("output_tokens", 0) +
                 usage.get("cache_creation_5m", 0) + usage.get("cache_creation_1h", 0) +
                 usage.get("cache_read_input_tokens", 0))
        lim   = (total / (pct / 100.0)) if pct > 0 and total > 0 else None
        return pct, window_end_dt, window_start_dt, cost, total, lim, usage

    pct, window_end_dt, window_start_dt, cost, total_tokens, implied_limit, usage = \
        _extract(get_api_usage(), get_local_usage())

    row = 0

    # ── HEADER ─────────────────────────────────────────────────────────────
    hdr = tk.Frame(outer, bg=BG)
    hdr.grid(row=row, column=0, sticky="ew", padx=16, pady=(14, 10))
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
    countdown_var = tk.StringVar(master=win, value="--:--:--")
    tk.Label(cd_blk, textvariable=countdown_var, bg=BG, fg=T_PRI,
             font=("Segoe UI", 26, "bold"), anchor="w").pack(anchor="w")

    rng_blk = tk.Frame(mid, bg=BG)
    rng_blk.pack(side="right")
    range_start_var = tk.StringVar(master=win)
    range_end_var   = tk.StringVar(master=win)
    tk.Label(rng_blk, textvariable=range_start_var, bg=BG, fg=T_TER,
             font=("Segoe UI", 10), anchor="e").pack(anchor="e")
    tk.Label(rng_blk, textvariable=range_end_var, bg=BG, fg=T_TER,
             font=("Segoe UI", 10), anchor="e").pack(anchor="e")

    def _update_range(wstart, wend):
        if wstart and wend:
            local_tz = datetime.now().astimezone().tzinfo
            fmt = "%d/%m %H:%M"
            range_start_var.set(f"início  {wstart.astimezone(local_tz).strftime(fmt)}")
            range_end_var.set(  f"término {wend.astimezone(local_tz).strftime(fmt)}")
        else:
            range_start_var.set("sem sessão ativa")
            range_end_var.set("")

    _update_range(window_start_dt, window_end_dt)

    # ── CONSUMPTION ────────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec1 = _section(outer, row); row += 1

    _section_title(sec1, "consumo", 0)

    num_row = tk.Frame(sec1, bg=BG)
    num_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    pct_var   = tk.StringVar(master=win, value=f"{pct:.0f}%")
    pct_label = tk.Label(num_row, textvariable=pct_var, bg=BG, fg=BAR_NRM,
                         font=("Segoe UI", 36, "bold"), anchor="w")
    pct_label.pack(side="left")

    meta = tk.Frame(num_row, bg=BG)
    meta.pack(side="right", anchor="se")
    tok_var  = tk.StringVar(master=win, value=f"{total_tokens:,} tokens".replace(",", "."))
    cost_var = tk.StringVar(master=win, value=f"${cost:.4f} USD")
    tk.Label(meta, textvariable=tok_var,  bg=BG, fg=T_SEC,
             font=("Segoe UI", 12), anchor="e").pack(anchor="e")
    tk.Label(meta, textvariable=cost_var, bg=BG, fg=T_TER,
             font=("Segoe UI", 10), anchor="e").pack(anchor="e")

    bar_canvas = tk.Canvas(sec1, height=6, bg=SURFACE, highlightthickness=0, bd=0)
    bar_canvas.grid(row=2, column=0, sticky="ew")

    def _update_bar(p, col):
        bar_canvas.update_idletasks()
        bw = bar_canvas.winfo_width() or (W - 40)
        bar_canvas.delete("all")
        fw = int(bw * min(p / 100, 1.0))
        if fw > 0:
            bar_canvas.create_rectangle(0, 0, fw, 6, fill=col, outline="")

    _update_bar(pct, BAR_DANG if pct >= 80 else (BAR_WARN if pct >= 50 else BAR_NRM))

    # ── CHART ──────────────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec2 = _section(outer, row); row += 1

    _section_title(sec2, "consumo acumulado", 0)

    chart_cv = tk.Canvas(sec2, height=140, bg=BG, highlightthickness=0, bd=0)
    chart_cv.grid(row=1, column=0, sticky="ew")

    proj_frame = tk.Frame(sec2, bg=BG)
    proj_frame.grid(row=2, column=0, sticky="w", pady=(8, 0))
    proj_badge_holder = tk.Frame(proj_frame, bg=BG)
    proj_badge_holder.pack(side="left")
    proj_text_var = tk.StringVar(master=win, value="calculando projeção...")
    tk.Label(proj_frame, textvariable=proj_text_var, bg=BG, fg=T_SEC,
             font=("Segoe UI", 10), wraplength=W - 60, justify="left").pack(
                 side="left", padx=(8, 0))

    _proj_badge = [None]

    def _update_proj(proj_pct, r2, t_hit, window_sec):
        for w in proj_badge_holder.winfo_children():
            w.destroy()
        remaining_pct = max(0.0, 100 - proj_pct)
        if t_hit is not None and t_hit <= window_sec:
            badge = _badge_label(proj_badge_holder, "atenção", "danger")
            proj_text_var.set(
                f"limite atingido {_fmt_hm(window_sec - t_hit)} antes do fim")
        else:
            badge = _badge_label(proj_badge_holder, "projeção", "warn" if proj_pct > 80 else "ok")
            proj_text_var.set(
                f"{proj_pct:.0f}% ao fim · {remaining_pct:.0f}% restante")
        badge.pack()

    # ── TOKEN BREAKDOWN ────────────────────────────────────────────────────
    _divider(outer, row); row += 1
    sec3 = _section(outer, row); row += 1

    _section_title(sec3, "detalhes de tokens", 0)
    sec3.columnconfigure(0, weight=1)
    sec3.columnconfigure(1, weight=1)

    tok_card_labels = [
        ("input",         "input_tokens"),
        ("output",        "output_tokens"),
        ("cache 5m",      "cache_creation_5m"),
        ("cache leitura", "cache_read_input_tokens"),
    ]
    _tok_vars = []
    for i, (lbl, _key) in enumerate(tok_card_labels):
        r2c, c2c = divmod(i, 2)
        card = tk.Frame(sec3, bg=SURFACE, padx=10, pady=8)
        card.grid(row=r2c + 1, column=c2c, sticky="nsew",
                  padx=(0, 4) if c2c == 0 else (4, 0), pady=3)
        tk.Label(card, text=lbl, bg=SURFACE, fg=T_TER,
                 font=("Segoe UI", 10)).pack(anchor="w")
        v = tk.StringVar(master=win, value="–")
        tk.Label(card, textvariable=v, bg=SURFACE, fg=T_PRI,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        _tok_vars.append((v, _key))

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
    # mutable state updated each tick
    _state = {
        "pct": pct,
        "window_end_dt":   window_end_dt,
        "window_start_dt": window_start_dt,
        "implied_limit":   implied_limit,
    }

    def _tick():
        if not win.winfo_exists():
            return
        try:
            # ── Refresh API + local data ──────────────────────────────────
            new_pct, new_wed, new_wsd, new_cost, new_tok, new_lim, new_usage = \
                _extract(get_api_usage(), get_local_usage())

            state_changed = (new_pct != _state["pct"] or
                             new_wed != _state["window_end_dt"])

            _state["pct"]            = new_pct
            _state["window_end_dt"]  = new_wed
            _state["window_start_dt"]= new_wsd
            _state["implied_limit"]  = new_lim

            bar_col = BAR_DANG if new_pct >= 80 else (BAR_WARN if new_pct >= 50 else BAR_NRM)
            pct_var.set(f"{new_pct:.0f}%")
            pct_label.config(fg=bar_col)
            tok_var.set(f"{new_tok:,} tokens".replace(",", "."))
            cost_var.set(f"${new_cost:.4f} USD")
            _update_bar(new_pct, bar_col)
            if state_changed:
                _update_range(new_wsd, new_wed)
            # Update token detail cards
            for var, key in _tok_vars:
                val = new_usage.get(key, 0)
                var.set(f"{val:,}".replace(",", "."))

            # ── Countdown ─────────────────────────────────────────────────
            wed = _state["window_end_dt"]
            if wed:
                secs = int((wed - datetime.now(timezone.utc)).total_seconds())
                if secs > 0:
                    h, rem = divmod(secs, 3600)
                    m, s   = divmod(rem, 60)
                    countdown_var.set(f"{h:02d}:{m:02d}:{s:02d}")
                else:
                    countdown_var.set("Encerrado!")
            else:
                countdown_var.set("--:--:--")

            # ── JSONL watcher → chart ─────────────────────────────────────
            snap = _jsonl_snapshot()
            if snap != _last_snap[0]:
                _last_snap[0] = snap
                _cached_series[0] = get_window_series()

            wsd = _state["window_start_dt"]
            now_sec = 0.0
            if wsd:
                now_sec = min(
                    (datetime.now(timezone.utc) - wsd).total_seconds(),
                    _window_sec)

            lim    = _state["implied_limit"]
            result = _draw_chart(chart_cv, _cached_series[0],
                                 _window_sec, _state["pct"], now_sec, lim)

            if result and lim:
                sl, cur_val, r2val, proj_end, _ = result
                proj_pct = min(proj_end / lim * 100, 999)
                # t_hit: seconds from now until slope hits limit (anchored to cur_val)
                remaining_to_lim = lim - cur_val
                t_hit = (now_sec + remaining_to_lim / sl) if sl > 0 and remaining_to_lim > 0 else None
                _update_proj(proj_pct, r2val, t_hit, _window_sec)

        except Exception:
            import traceback, pathlib
            log = pathlib.Path.home() / "claude_token_debug.txt"
            with open(log, "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        win.after(1_000, _tick)

    win.after(100, _tick)
    win.mainloop()
    if win_ref is not None:
        win_ref[0] = None
