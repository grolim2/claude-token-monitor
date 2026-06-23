import tkinter as tk
from tkinter import ttk
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
    tk.Label(frame, text="Intervalo (segundos):", bg="#FFFFFF", fg="#1D1D1F",
             font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=4)
    refresh_var = tk.StringVar(value=str(current_config.get("refresh_seconds", 60)))
    tk.Entry(frame, textvariable=refresh_var, width=8, font=("Segoe UI", 11),
             relief="flat", highlightthickness=1,
             highlightbackground="#D2D2D7").grid(row=1, column=1, padx=(8, 0), sticky="w")
    tk.Label(frame, text="mínimo 10 s", bg="#FFFFFF", fg="#AEAEB2",
             font=("Segoe UI", 9)).grid(row=2, column=0, columnspan=2, sticky="w")

    # ── Aparência ────────────────────────────────────────────────────────────
    _div(3)
    _sec("Aparência", 4)

    dark_var = tk.BooleanVar(value=current_config.get("dark_mode", False))

    def _on_dark():
        if live_callbacks and "theme" in live_callbacks:
            live_callbacks["theme"](dark_var.get())

    tk.Checkbutton(frame, text="Modo escuro", variable=dark_var,
                   bg="#FFFFFF", fg="#1D1D1F", font=("Segoe UI", 11),
                   activebackground="#FFFFFF", relief="flat",
                   command=_on_dark).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=2)

    topmost_var = tk.BooleanVar(value=current_config.get("always_on_top", False))

    def _on_topmost():
        if live_callbacks and "topmost" in live_callbacks:
            live_callbacks["topmost"](topmost_var.get())

    tk.Checkbutton(frame, text="Sempre visível (sobre outras janelas)",
                   variable=topmost_var,
                   bg="#FFFFFF", fg="#1D1D1F", font=("Segoe UI", 11),
                   activebackground="#FFFFFF", relief="flat",
                   command=_on_topmost).grid(
        row=6, column=0, columnspan=2, sticky="w", pady=2)

    # Opacity
    tk.Label(frame, text="Opacidade:", bg="#FFFFFF", fg="#1D1D1F",
             font=("Segoe UI", 11)).grid(row=7, column=0, sticky="w", pady=(10, 0))

    opacity_var = tk.IntVar(value=current_config.get("opacity", 100))
    opacity_lbl = tk.Label(frame, text=f"{opacity_var.get()}%",
                           bg="#FFFFFF", fg="#6E6E73",
                           font=("Segoe UI", 11), width=5, anchor="e")
    opacity_lbl.grid(row=7, column=1, sticky="e", pady=(10, 0))

    def _on_opacity(val):
        v = int(float(val))
        opacity_lbl.config(text=f"{v}%")
        if live_callbacks and "opacity" in live_callbacks:
            live_callbacks["opacity"](v)

    tk.Scale(frame, from_=15, to=100, orient="horizontal",
             variable=opacity_var, command=_on_opacity,
             showvalue=False, bg="#FFFFFF", fg="#1D1D1F",
             troughcolor="#D2D2D7", highlightthickness=0,
             length=220, sliderlength=14, width=8).grid(
        row=8, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    # ── Buttons ──────────────────────────────────────────────────────────────
    _div(9)
    btn_frame = tk.Frame(frame, bg="#FFFFFF")
    btn_frame.grid(row=10, column=0, columnspan=2, pady=(10, 0), sticky="e")

    def _saved_config():
        return load_config()

    def on_ok():
        try:
            new_cfg = {
                "refresh_seconds": max(10, int(refresh_var.get())),
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
        # Revert live changes to last saved state
        saved = _saved_config()
        if live_callbacks:
            if "opacity" in live_callbacks:
                live_callbacks["opacity"](saved.get("opacity", 100))
            if "topmost" in live_callbacks:
                live_callbacks["topmost"](saved.get("always_on_top", False))
            if "theme" in live_callbacks:
                live_callbacks["theme"](saved.get("dark_mode", False))
        root.destroy()

    tk.Button(btn_frame, text="Salvar", command=on_ok,
              bg="#1D1D1F", fg="white", font=("Segoe UI", 11),
              relief="flat", padx=16, pady=6,
              cursor="hand2", activebackground="#3D3D3F",
              activeforeground="white").pack(side="right", padx=(6, 0))
    tk.Button(btn_frame, text="Cancelar", command=on_cancel,
              bg="#F5F5F7", fg="#1D1D1F", font=("Segoe UI", 11),
              relief="flat", padx=16, pady=6,
              cursor="hand2", activebackground="#E5E5EA").pack(side="right")

    root.mainloop()
