"""Contratos para o fluxo simples de atualização na mesma pasta.

São testes estruturais: os testes de PowerShell/rollback e do pacote ZIP
continuam em test_dueltrace_preview_installer.py.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
BRIDGE=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
INSTALLER=(ROOT/"scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")


class UpdateInPlaceFlowTests(unittest.TestCase):
    def test_explicit_download_button_and_no_installer_redirect(self):
        self.assertIn('"Baixar atualizações"',UI)
        self.assertIn('check_updates()',UI)
        self.assertIn('install_portable_update()',UI)
        self.assertIn('install_preview_update()',UI)
        self.assertNotIn('install_signed_update()',UI)
        self.assertNotIn('open_updates_page(',UI)
        self.assertIn('disabled={!canDownload||installing||checking}',UI)
        self.assertIn('automaticPortableReady === true',UI)

    def test_prefers_stable_zip_and_does_not_require_signed_installer(self):
        block=BRIDGE.split('    def check_updates(self):',1)[1].split(
            '    def install_signed_update(self):',1)[0]
        self.assertIn('fetch_portable_stable_package(',block)
        self.assertIn('if not status["automaticPortableReady"]:',block)
        self.assertIn('fetch_latest_preview_package(',block)
        self.assertNotIn('select_signed_installer(',block)

    def test_existing_helper_keeps_original_path_and_rollback(self):
        self.assertIn("$exe=Join-Path $old 'DUELTRACE-WebUI.exe'",INSTALLER)
        self.assertIn('Move-Item -LiteralPath $source -Destination (Join-Path $old $name)',INSTALLER)
        self.assertIn('Start-Process -FilePath $exe -WorkingDirectory $old',INSTALLER)
        self.assertIn('Wait-Process -Id $pidOld',INSTALLER)
        self.assertIn('rollback-',INSTALLER)
        self.assertNotIn('Rename-Item -LiteralPath $old',INSTALLER)


if __name__=="__main__":
    unittest.main()
