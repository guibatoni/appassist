"""Regression contracts: Batoni Dev manager matches DUELTRACE's design system.

Visual tests for real Windows desktop navigation also run via smoke_admin_ui.py.
These static checks do not create customer licenses or require a GUI session.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"tools/licensing/dueltrace_license_admin.py").read_text(encoding="utf-8")
CSS=(ROOT/"web/app/globals.css").read_text(encoding="utf-8")
CORE=(ROOT/"tools/licensing/dueltrace_license_admin_core.py").read_text(encoding="utf-8")
WORKFLOW=(ROOT/".github/workflows/publicar-gerenciador-admin-teste.yml").read_text(encoding="utf-8")


class DuoDesignTests(unittest.TestCase):
    def test_exact_visual_tokens_are_shared(self):
        mapping={
            "BG":"--background","SURFACE":"--panel",
            "PANEL":"--panel-strong","BORDER":"--border",
            "TEXT":"--foreground","MUTED":"--muted",
            "GOLD":"--gold","CYAN":"--primary",
            "ERROR":"--danger","SUCCESS":"--success",
        }
        for python_token,css_token in mapping.items():
            with self.subTest(token=python_token):
                py=re.search(rf"^{python_token}=\"(#[0-9a-f]{{6}})\"",UI,re.M)
                css=re.search(rf"{css_token}:\s*(#[0-9a-f]{{6}});",CSS)
                self.assertIsNotNone(py)
                self.assertIsNotNone(css)
                self.assertEqual(py.group(1),css.group(1))

    def test_native_shell_and_unified_navigation(self):
        self.assertIn("class LicenseManager(ctk.CTk):",UI)
        self.assertIn("self.overrideredirect(True)",UI)
        self.assertIn("self._minimize_window",UI)
        self.assertIn("self._toggle_maximize",UI)
        self.assertIn("self.destroy",UI)
        self.assertIn("canvas.create_polygon",UI)
        self.assertIn("DUELTRACE",UI)
        for page in ("Emitir licença","Licenças emitidas","Chaves e segurança"):
            self.assertIn(page,UI)
        self.assertIn('class _BrandDialogs:',UI)
        self.assertIn('def _password(',UI)
        self.assertNotIn("simpledialog.askstring",UI)

    def test_signing_logic_remains_private(self):
        self.assertIn('from dueltrace_license_admin_core import (',UI)
        self.assertIn('issue_license(',UI)
        self.assertIn('create_keys(self.home, first, second)',UI)
        self.assertIn('resend_issued(self.home, lic, Path(output))',UI)
        self.assertIn("purchase_confirmed=True",UI)
        self.assertIn("MAX_DEVICES_PER_ORDER = 2",CORE)
        self.assertNotIn("private_key_bytes",UI)
        self.assertNotIn("requests.get",UI)

    def test_private_release_packs_ui_resources(self):
        self.assertIn("customtkinter==6.0.0",WORKFLOW)
        self.assertIn("--collect-all customtkinter",WORKFLOW)
        self.assertIn("smoke_admin_ui.py",WORKFLOW)
        self.assertIn("commercial/dueltrace-license-manager-redesign-v42",WORKFLOW)
        self.assertIn("admin-test-v42-r",WORKFLOW)
        self.assertIn("repo.private",WORKFLOW)
        self.assertIn("Start-MpScan",WORKFLOW)


if __name__=="__main__":
    unittest.main()
