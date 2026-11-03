"""Proteções de inicialização do DUELTRACE — não dependem de ROMs."""
from __future__ import annotations

import builtins
import dis
import inspect
import sys
import tempfile
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

import abrir_biblioteca
import dueltrace_desktop
import dueltrace_visuals
from auto_mods import ModCatalog


def missing_runtime_globals(cls):
    """Encontra nomes de módulo usados por métodos mas não importados."""
    missing = []
    for method_name, method in inspect.getmembers(cls, inspect.isfunction):
        if method.__module__ != cls.__module__:
            continue
        defined = method.__globals__
        for instruction in dis.get_instructions(method):
            if instruction.opname == "LOAD_GLOBAL":
                name = instruction.argval
                if name not in defined and not hasattr(builtins, name):
                    missing.append(f"{cls.__name__}.{method_name}: {name}")
    return sorted(set(missing))


class DesktopBootstrapTests(unittest.TestCase):
    def test_desktop_has_no_unresolved_global_names(self):
        classes = (
            dueltrace_desktop.DueltraceDesktop,
            dueltrace_visuals.QuickTile,
            dueltrace_visuals.HeroArt,
            dueltrace_visuals.CardArt,
            dueltrace_visuals.CategoryMeters,
        )
        missing = [message for cls in classes for message in missing_runtime_globals(cls)]
        self.assertEqual(missing, [], f"Referências sem import: {missing}")

    def test_failing_startup_records_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dueltrace_startup.log"
            def simulate_failure():
                raise RuntimeError("Falha de inicialização de teste")
            fake_desktop = types.SimpleNamespace(main=simulate_failure)
            with (
                patch.object(abrir_biblioteca, "startup_log_path", return_value=path),
                patch.dict(sys.modules, {"dueltrace_desktop": fake_desktop}),
                patch("tkinter.Tk") as tk_root,
                patch("tkinter.messagebox.showerror") as showerror,
            ):
                with self.assertRaisesRegex(RuntimeError, "Falha de inicialização"):
                    abrir_biblioteca.main()
                self.assertTrue(tk_root.called)
                self.assertTrue(showerror.called)
            self.assertIn("RuntimeError: Falha de inicialização de teste", path.read_text(encoding="utf-8"))

    @unittest.skipUnless(sys.platform == "win32", "Smoke test GUI para runner Windows")
    def test_initial_window_and_pages_on_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = ModCatalog(home=Path(folder))
            try:
                app = dueltrace_desktop.DueltraceDesktop(catalog=catalog)
            except tk.TclError as exc:
                if "display" in str(exc).lower() or "screen" in str(exc).lower():
                    self.skipTest(f"Runner sem sessão gráfica: {exc}")
                raise
            try:
                app.withdraw()
                app.update_idletasks()
                for _, key in dueltrace_desktop.PAGES:
                    app.go(key)
                    app.update_idletasks()
                self.assertIn("DUELTRACE", app.title())
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
