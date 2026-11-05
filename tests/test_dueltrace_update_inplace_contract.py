"""Contrato de atualização in-place: sem outra pasta de instalação.

A execução Windows real e rollback constam em test_dueltrace_preview_installer.py.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class UpdateInPlaceContractTests(unittest.TestCase):
    def test_temporary_files_and_rollback_are_staged_in_user_data(self):
        updater=(ROOT/"scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")
        self.assertIn('work=home/"preview_updates"',updater)
        self.assertIn('stage=work/("stage-"+token)',updater)
        self.assertIn('backup=work/("rollback-"+token)',updater)
        self.assertNotIn('stage=original.parent/',updater)
        self.assertNotIn('\n    backup=original.parent/',updater)
        self.assertIn('Move-Item -LiteralPath $target -Destination (Join-Path $backup $name)',updater)
        self.assertIn('Start-Process -FilePath $exe -WorkingDirectory $old -PassThru',updater)
        self.assertIn('if ($newProcess.HasExited)',updater)
        self.assertIn('Remove-Item -LiteralPath $stage',updater)
        self.assertIn('ultima-atualizacao.log',updater)

    def test_interface_prefers_portable_zip_and_explains_relaunch(self):
        ui=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        self.assertLess(ui.index("if(fresh.automaticPortableReady)"),
                        ui.index("else if(fresh.automaticInstallReady)"))
        self.assertIn("reinicia automaticamente no mesmo local",ui)
        self.assertIn("Atualizar agora",ui)

    def test_no_untrusted_package_can_skip_previous_security_check(self):
        updater=(ROOT/"scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")
        self.assertIn('(unpacker or unpack_preview_zip)(archive,stage,info)',updater)
        self.assertIn('"Conteúdo do pacote não corresponde ao build publicado."',updater)
        self.assertIn('"SHA-256 do download divergente da release."',updater)


if __name__=="__main__":
    unittest.main()
