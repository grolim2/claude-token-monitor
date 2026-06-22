import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude" / "token_monitor_config.json"
DEFAULT_CONFIG = {
    "refresh_seconds": 300,
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


def open_settings(current_config: dict, on_save=None, **_):
    root = tk.Tk()
    root.title("Claude Token Monitor — Configurações")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=16)
    frame.grid()

    ttk.Label(frame, text="Intervalo de atualização (s):").grid(row=0, column=0, sticky="w", pady=4)
    refresh_var = tk.StringVar(value=str(current_config.get("refresh_seconds", 300)))
    ttk.Entry(frame, textvariable=refresh_var, width=12).grid(row=0, column=1, padx=8, sticky="w")
    ttk.Label(frame, text="(mínimo 60s — limite da API)", foreground="gray",
              font=("Segoe UI", 8)).grid(row=1, column=0, columnspan=2, sticky="w")

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=2, column=0, columnspan=2, pady=12)

    def on_ok():
        try:
            new_cfg = {"refresh_seconds": max(60, int(refresh_var.get()))}
            save_config(new_cfg)
            if on_save:
                on_save(new_cfg)
        except ValueError:
            pass
        root.destroy()

    ttk.Button(btn_frame, text="Salvar", command=on_ok).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Cancelar", command=root.destroy).pack(side="left", padx=4)

    root.mainloop()
