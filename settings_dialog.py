import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude" / "token_monitor_config.json"
DEFAULT_CONFIG = {
    "cost_limit_usd": 8.0,
    "refresh_seconds": 300,   # API rate limit: poll at most every 5min
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # migrate old token_limit key
            if "token_limit" in data and "cost_limit_usd" not in data:
                data.pop("token_limit", None)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def open_settings(current_config: dict, on_save=None, get_current_cost=None):
    root = tk.Tk()
    root.title("Claude Token Monitor — Configurações")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=16)
    frame.grid()

    # --- Limit (USD) ---
    ttk.Label(frame, text="Limite de custo por 5h (USD):").grid(row=0, column=0, sticky="w", pady=4)
    limit_var = tk.StringVar(value=str(current_config.get("cost_limit_usd", 8.0)))
    ttk.Entry(frame, textvariable=limit_var, width=12).grid(row=0, column=1, padx=8, sticky="w")

    # --- Refresh ---
    ttk.Label(frame, text="Intervalo de atualização (s):").grid(row=1, column=0, sticky="w", pady=4)
    refresh_var = tk.StringVar(value=str(current_config.get("refresh_seconds", 30)))
    ttk.Entry(frame, textvariable=refresh_var, width=12).grid(row=1, column=1, padx=8, sticky="w")

    # --- Calibration ---
    ttk.Separator(frame, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
    ttk.Label(frame, text="Calibrar pelo Claude Code:").grid(row=3, column=0, sticky="w")
    ttk.Label(frame, text="% atual no Claude:").grid(row=4, column=0, sticky="w", pady=4)
    calib_var = tk.StringVar(value="")
    ttk.Entry(frame, textvariable=calib_var, width=8).grid(row=4, column=1, sticky="w", padx=8)

    calib_result = tk.StringVar(value="")
    ttk.Label(frame, textvariable=calib_result, foreground="green").grid(
        row=5, column=0, columnspan=2, pady=2)

    def do_calibrate():
        try:
            claude_pct = float(calib_var.get().replace("%", "").strip())
            if not (0 < claude_pct <= 100):
                calib_result.set("Valor inválido (1–100)")
                return
            current_cost = get_current_cost() if get_current_cost else None
            if current_cost is None:
                calib_result.set("Erro ao ler custo atual")
                return
            new_limit = round(current_cost / (claude_pct / 100), 4)
            limit_var.set(str(new_limit))
            calib_result.set(f"Limite calculado: ${new_limit:.4f}")
        except ValueError:
            calib_result.set("Valor inválido")

    ttk.Button(frame, text="Calcular limite", command=do_calibrate).grid(
        row=4, column=1, sticky="e", padx=8)

    # --- Buttons ---
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=6, column=0, columnspan=2, pady=10)

    def on_ok():
        try:
            new_cfg = {
                "cost_limit_usd": float(limit_var.get()),
                "refresh_seconds": max(10, int(refresh_var.get())),
            }
            save_config(new_cfg)
            if on_save:
                on_save(new_cfg)
        except ValueError:
            pass
        root.destroy()

    ttk.Button(btn_frame, text="Salvar", command=on_ok).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Cancelar", command=root.destroy).pack(side="left", padx=4)

    root.mainloop()
