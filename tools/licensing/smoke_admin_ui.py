"""Interactive-shell smoke test for GitHub Windows runner.

Creates the REAL CustomTkinter window with a temporary empty admin home,
checks each page and navigation, then closes. NEVER generates keys or licenses.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scanner"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dueltrace_license_admin import BG, BORDER, CYAN, GOLD, LicenseManager


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("O teste gráfico do gerenciador exige Windows.")
    with tempfile.TemporaryDirectory(prefix="batonidev-ui-smoke-") as tmp:
        app=LicenseManager(home=Path(tmp)/"admin")
        try:
            app.update_idletasks()
            if app.cget("fg_color") != BG:
                raise AssertionError("Fundo fora do design system DUELTRACE.")
            if len(app.pages) != 3 or len(app.nav_buttons) != 3:
                raise AssertionError("Navegação do gerenciador incompleta.")
            for page in ("issue","history","security","issue"):
                app._show_page(page)
                app.update_idletasks()
                if app._current_page != page:
                    raise AssertionError(f"Página não selecionada: {page}")
            if not all((BG,BORDER,CYAN,GOLD)):
                raise AssertionError("Faltam tokens do design.")
            if app.ledger_tree["style"] != "Admin.Treeview":
                raise AssertionError("Histórico não recebeu o tema personalizado.")
            if app.key_status_var.get() == "":
                raise AssertionError("Falta orientação de chaves ao usuário.")
            if app.total_var.get() != "0":
                raise AssertionError("Histórico temporário não está vazio.")
            print("PASS: CustomTkinter abriu; páginas, atalhos e identidade visual OK.")
        finally:
            app.destroy()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
