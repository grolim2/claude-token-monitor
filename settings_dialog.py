import tkinter as tk
import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude" / "token_monitor_config.json"
DEFAULT_CONFIG = {
    "refresh_seconds": 60,
    "dark_mode":       False,
    "always_on_top":   False,
    "opacity":         100,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


class _Slider(tk.Canvas):
    """Custom slider: thin track line + circle thumb."""
    _R  = 11   # thumb radius
    _TH = 2    # track thickness

    def __init__(self, parent, from_, to, variable, command=None,
                 bg="#FFFFFF", **kw):
        super().__init__(parent, height=self._R * 2 + 6,
                         highlightthickness=0, bg=bg, cursor="hand2", **kw)
        self._from = from_
        self._to   = to
        self._var  = variable
        self._cmd  = command
        self._PAD  = self._R + 4   # keeps thumb inside canvas

        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>",  self._move)
        self.bind("<B1-Motion>", self._move)

    # ── internals ──────────────────────────────────────────────────────────
    def _frac(self):
        v = max(self._from, min(self._to, self._var.get()))
        return (v - self._from) / (self._to - self._from)

    def _draw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 4:
            return
        cy  = H // 2
        cx  = self._PAD + self._frac() * (W - 2 * self._PAD)

        # Grey full track
        self.create_line(self._PAD, cy, W - self._PAD, cy,
                         fill="#D2D2D7", width=self._TH, capstyle="round")
        # Filled portion
        if cx > self._PAD + 1:
            self.create_line(self._PAD, cy, cx, cy,
                             fill="#1D1D1F", width=self._TH, capstyle="round")

        r = self._R
        # Subtle shadow
        self.create_oval(cx - r + 1, cy - r + 1, cx + r + 1, cy + r + 1,
                         fill="#C8C8CC", outline="")
        # Thumb: white fill, dark border
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill="#FFFFFF", outline="#1D1D1F", width=1.5)

    def _move(self, e):
        W = self.winfo_width()
        f = max(0.0, min(1.0, (e.x - self._PAD) / (W - 2 * self._PAD)))
        val = round(self._from + f * (self._to - self._from))
        self._var.set(val)
        self._draw()
        if self._cmd:
            self._cmd(str(val))


def open_settings(current_config: dict, on_save=None, live_callbacks=None, **_):
    root = tk.Tk()
    root.title("Configurações")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg="#FFFFFF")

    frame = tk.Frame(root, bg="#FFFFFF", padx=20, pady=16)
    frame.pack(fill="both", expand=True)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _sec(text, row):
        tk.Label(frame, text=text.upper(), bg="#FFFFFF", fg="#AEAEB2",
                 font=("Segoe UI", 9)).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(14, 4))

    def _div(row):
        tk.Frame(frame, bg="#D2D2D7", height=1).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    # ── Atualização ─────────────────────────────────────────────────────────
    _sec("Atualização", 0)
    tk.Label(frame,
             text="Frequência de atualização da informação de consumo.",
             bg="#FFFFFF", fg="#6E6E73", font=("Segoe UI", 10),
             wraplength=260, justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
    tk.Label(frame, text="Intervalo (segundos):", bg="#FFFFFF", fg="#1D1D1F",
             font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=4)
    refresh_var = tk.StringVar(value=str(current_config.get("refresh_seconds", 60)))
    tk.Entry(frame, textvariable=refresh_var, width=8, font=("Segoe UI", 11),
             relief="flat", highlightthickness=1,
             highlightbackground="#D2D2D7").grid(
        row=2, column=1, padx=(8, 0), sticky="w")
    tk.Label(frame, text="mínimo 20 s", bg="#FFFFFF", fg="#AEAEB2",
             font=("Segoe UI", 9)).grid(row=3, column=0, columnspan=2, sticky="w")

    # ── Aparência ────────────────────────────────────────────────────────────
    _div(4)
    _sec("Aparência", 5)

    dark_var = tk.BooleanVar(value=current_config.get("dark_mode", False))

    def _on_dark():
        if live_callbacks and "theme" in live_callbacks:
            live_callbacks["theme"](dark_var.get())

    tk.Checkbutton(frame, text="Modo escuro", variable=dark_var,
                   bg="#FFFFFF", fg="#1D1D1F", font=("Segoe UI", 11),
                   activebackground="#FFFFFF", relief="flat",
                   command=_on_dark).grid(
        row=6, column=0, columnspan=2, sticky="w", pady=2)

    topmost_var = tk.BooleanVar(value=current_config.get("always_on_top", False))

    def _on_topmost():
        if live_callbacks and "topmost" in live_callbacks:
            live_callbacks["topmost"](topmost_var.get())

    tk.Checkbutton(frame, text="Sempre visível (sobre outras janelas)",
                   variable=topmost_var, bg="#FFFFFF", fg="#1D1D1F",
                   font=("Segoe UI", 11), activebackground="#FFFFFF",
                   relief="flat", command=_on_topmost).grid(
        row=7, column=0, columnspan=2, sticky="w", pady=2)

    # Opacity
    tk.Label(frame, text="Opacidade:", bg="#FFFFFF", fg="#1D1D1F",
             font=("Segoe UI", 11)).grid(row=8, column=0, sticky="w", pady=(12, 0))

    opacity_var = tk.IntVar(value=current_config.get("opacity", 100))
    opacity_lbl = tk.Label(frame, text=f"{opacity_var.get()}%",
                           bg="#FFFFFF", fg="#6E6E73",
                           font=("Segoe UI", 11), width=5, anchor="e")
    opacity_lbl.grid(row=8, column=1, sticky="e", pady=(12, 0))

    def _on_opacity(val):
        v = int(float(val))
        opacity_lbl.config(text=f"{v}%")
        if live_callbacks and "opacity" in live_callbacks:
            live_callbacks["opacity"](v)

    _Slider(frame, from_=15, to=100, variable=opacity_var,
            command=_on_opacity).grid(
        row=9, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    # ── Buttons ──────────────────────────────────────────────────────────────
    _div(10)
    btn_frame = tk.Frame(frame, bg="#FFFFFF")
    btn_frame.grid(row=11, column=0, columnspan=2, pady=(10, 0), sticky="e")

    def on_ok():
        try:
            new_cfg = {
                "refresh_seconds": max(20, int(refresh_var.get())),
                "dark_mode":       dark_var.get(),
                "always_on_top":   topmost_var.get(),
                "opacity":         opacity_var.get(),
            }
            save_config(new_cfg)
            if on_save:
                on_save(new_cfg)
        except ValueError:
            pass
        root.destroy()

    def on_cancel():
        saved = load_config()
        if live_callbacks:
            for key, cfg_key, default in [
                ("opacity",  "opacity",      100),
                ("topmost",  "always_on_top", False),
                ("theme",    "dark_mode",     False),
            ]:
                if key in live_callbacks:
                    live_callbacks[key](saved.get(cfg_key, default))
        root.destroy()

    tk.Button(btn_frame, text="Salvar", command=on_ok,
              bg="#1D1D1F", fg="white", font=("Segoe UI", 11),
              relief="flat", padx=16, pady=6, cursor="hand2",
              activebackground="#3D3D3F",
              activeforeground="white").pack(side="right", padx=(6, 0))
    tk.Button(btn_frame, text="Cancelar", command=on_cancel,
              bg="#F5F5F7", fg="#1D1D1F", font=("Segoe UI", 11),
              relief="flat", padx=16, pady=6, cursor="hand2",
              activebackground="#E5E5EA").pack(side="right")

    root.mainloop()
