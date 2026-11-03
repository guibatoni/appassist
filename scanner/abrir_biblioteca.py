"""Entrada do DUELTRACE Desktop com registro local de falhas.

A janela e as ferramentas antigas continuam disponíveis. Falhas de abertura
ficam registradas em %LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\logs,
sem enviar dados por rede.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def startup_log_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return root / "ForbiddenMemoriesMultiMod" / "logs" / "dueltrace_startup.log"


def main() -> None:
    try:
        from dueltrace_desktop import main as start_desktop
        start_desktop()
    except Exception as exc:
        diagnostic = traceback.format_exc()
        log_path = startup_log_path()
        saved = None
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as output:
                output.write(f"\\n=== {datetime.now().astimezone().isoformat()} — startup ===\\n")
                output.write(diagnostic)
            saved = str(log_path)
        except OSError:
            pass
        print(diagnostic, file=sys.stderr, flush=True)
        description = (
            f"Não foi possível abrir DUELTRACE.\\n\\n"
            f"Erro: {type(exc).__name__}: {exc}\\n\\n"
            + (f"Diagnóstico local: {saved}" if saved else
               "O log não pôde ser salvo; execute o .bat pelo terminal para obter o erro.")
        )
        try:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror("DUELTRACE — Falha ao iniciar", description, parent=root)
            root.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
