"""Contracts for the missing Windows build/release entry points.

These checks can run on Linux as source/static regressions. Actual Windows
signing and application startup still require Windows validation.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/"tools/release"
WINDOWS=(RELEASE/"assistente_windows.ps1").read_text(encoding="utf-8")
PUBLISHER=(RELEASE/"publicar_cliente.ps1").read_text(encoding="utf-8")
UPDATER=(ROOT/"scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")
DOCS=(ROOT/"docs/DUELTRACE_ATUALIZACOES_CLIENTES.md").read_text(encoding="utf-8")


class WindowsBuildKitTests(unittest.TestCase):
    def test_four_one_click_launchers_exist_and_are_wired(self):
        expected={
            "01_VERIFICAR_AMBIENTE_WINDOWS.cmd":"Verificar",
            "02_GERAR_DUELTRACE_COMPLETO.cmd":"Compilar",
            "03_PREPARAR_CANAL_PUBLICO.cmd":"PrepararCanal",
            "04_PUBLICAR_DUELTRACE_WINDOWS.cmd":"Publicar",
        }
        for name,mode in expected.items():
            with self.subTest(name=name):
                source=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn("powershell.exe -NoProfile",source)
                self.assertIn("tools\\release\\assistente_windows.ps1",source)
                self.assertIn("-Acao "+mode,source)
                self.assertIn("if errorlevel 1",source)
                self.assertIn("pause",source)

    def test_public_repository_creation_requires_explicit_confirmation(self):
        self.assertIn('Read-Host "Digite CRIAR',WINDOWS)
        self.assertIn('if ($confirm -cne "CRIAR")',WINDOWS)
        self.assertIn('gh repo create $destination --public --add-readme',WINDOWS)
        self.assertIn('found.private -ne $false',WINDOWS)
        self.assertIn('guibatoni/dueltrace-releases',WINDOWS)
        self.assertNotIn('gh repo create guibatoni/appassist',WINDOWS)

    def test_clients_do_not_need_maintainer_credentials(self):
        self.assertIn('gh auth status',WINDOWS)  # publisher only
        self.assertIn('Get-ChildItem Cert:\\CurrentUser\\My',WINDOWS)
        self.assertIn('CertificateThumbprint',WINDOWS)
        self.assertIn('ExpectedPublisherSubject',WINDOWS)
        self.assertIn('if ($Publish)',PUBLISHER)
        self.assertIn('Get-AuthenticodeSignature',PUBLISHER)
        self.assertIn('pip_audit',PUBLISHER)
        self.assertIn('npm.cmd',PUBLISHER)
        self.assertIn('gate_windows_package.ps1',PUBLISHER)
        self.assertIn('https://github.com/$publicRepo/releases/download/$tag/$assetName',PUBLISHER)
        self.assertNotIn('gh release download',PUBLISHER)
        self.assertNotIn('actions/runs',PUBLISHER)
        self.assertIn('https://github\\.com/guibatoni/appassist',PUBLISHER)
        self.assertIn('git@github\\.com:guibatoni/appassist',PUBLISHER)
        self.assertNotIn('malicious',PUBLISHER)

    def test_signed_customer_readme_is_accepted_by_installer(self):
        self.assertIn('"LEIA-ME-ATUALIZACAO.txt"',UPDATER)
        self.assertIn("'LEIA-ME-ATUALIZACAO.txt'",UPDATER)
        self.assertIn("rollback",UPDATER)
        self.assertIn("SHA-256",UPDATER)

    def test_documentation_names_local_entry_points(self):
        self.assertIn('tools/release/publicar_cliente.ps1',DOCS)
        self.assertIn("sem GitHub Actions",DOCS)
        self.assertIn("guibatoni/dueltrace-releases",DOCS)


if __name__=="__main__":
    unittest.main()
