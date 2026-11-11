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

    def test_node_26_is_accepted_without_installing_node_22(self):
        self.assertIn('^v(?:22|24|26)',WINDOWS)
        self.assertNotIn("Utilize Node.js 22 (encontrado:",WINDOWS)
        self.assertNotIn('Instale Node.js 22.',WINDOWS)
        self.assertIn("node --version",WINDOWS)
        self.assertIn("Node.js 22, 24 ou 26",WINDOWS)

    def test_system_python_314_is_accepted_without_python_312_install(self):
        helper=(RELEASE/"python_build_bootstrap.ps1").read_text(encoding="utf-8")
        ignore=(ROOT/".gitignore").read_text(encoding="utf-8")
        requirements=(ROOT/"tools/security/requirements-webui-build.txt").read_text(encoding="utf-8")
        self.assertIn('python_build_bootstrap.ps1',WINDOWS)
        self.assertIn('Test-Interpreter',helper)
        self.assertIn('3\\.(?:14|12)',helper)
        self.assertIn('python -c',helper)
        self.assertIn('-m venv $venv',helper)
        self.assertIn('env:PATH',helper)
        self.assertIn('env:VIRTUAL_ENV',helper)
        self.assertIn('.dueltrace-build-py314/',ignore)
        self.assertIn('pythonnet==3.2.1',requirements)
        self.assertNotIn('winget install',helper)
        self.assertNotIn('Python.Python.3.12',helper)
        self.assertNotIn('Utilize Python 3.12 no Windows (encontrado:',WINDOWS)
        self.assertNotIn('python312_bootstrap.ps1',WINDOWS)
        self.assertNotIn('Require-Command "python"',WINDOWS)
        self.assertIn('Nenhum Python adicional foi instalado',helper)

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

    def test_publisher_is_not_truncated_or_accidentally_duplicated(self):
        # Catch regressions caused by unsafe text replacement around the
        # PowerShell regex ending in a literal dollar/apostrophe pair.
        self.assertLess(len(PUBLISHER),20000)
        self.assertEqual(PUBLISHER.count("function Invoke-Checked("),1)
        self.assertEqual(PUBLISHER.count("Push-Location $workspace"),1)
        self.assertEqual(PUBLISHER.count("DUELTRACE-WebUI.exe"),1)
        self.assertIn("if ($LASTEXITCODE -ne 0 -or !$trustedOrigin)",PUBLISHER)
        self.assertIn("$notes=(Get-Content",PUBLISHER)
        self.assertIn("--draft",PUBLISHER)
        self.assertIn("--draft=false",PUBLISHER)
        self.assertIn("$published.draft",PUBLISHER)
        self.assertIn("SHA-256 ZIP: $digest",PUBLISHER)
        self.assertEqual(PUBLISHER.count("DOWNLOAD DIRETO"),1)

    def test_powershell_diagnostic_stage_colon_is_parsed_safely(self):
        import re
        self.assertIn('Falha na etapa ${stage}:',PUBLISHER)
        self.assertNotIn('Falha na etapa $stage:',PUBLISHER)
        # Unbraced variables adjacent to ':' cause InvalidVariableReferenceWithDrive
        # in Windows PowerShell 5.1, except for explicit drive scopes.
        for script in (WINDOWS,PUBLISHER,
                       (RELEASE/"python_build_bootstrap.ps1").read_text(
                           encoding="utf-8")):
            invalid=[
                match.group(0) for match in re.finditer(
                    r"\$([A-Za-z_][A-Za-z0-9_]*):",script)
                if match.group(1) not in {
                    "env","script","global","local","private","using"
                }
            ]
            self.assertEqual(invalid,[])

    def test_pip_security_patch_before_dependency_audit(self):
        upgrade='Invoke-Checked "python" @("-m","pip","install","--upgrade","pip==26.3")'
        audit='Invoke-Checked "python" @("-m","pip_audit","--local")'
        project='Invoke-Checked "python" @("-m","pip","install","-r"'
        self.assertIn(upgrade,PUBLISHER)
        self.assertIn(audit,PUBLISHER)
        self.assertIn(project,PUBLISHER)
        self.assertLess(PUBLISHER.index(upgrade),PUBLISHER.index(project))
        self.assertLess(PUBLISHER.index(project),PUBLISHER.index(audit))
        self.assertIn('m.version(\'pip\')',PUBLISHER)
        self.assertIn('(26,2)',PUBLISHER)
        self.assertNotIn('"--ignore-vuln"',PUBLISHER)
        self.assertNotIn('"--disable-pip-version-check"',PUBLISHER)

    def test_failure_reports_real_python_step_and_keeps_local_logs(self):
        self.assertIn("dist/build-diagnostics",PUBLISHER)
        self.assertIn("ULTIMA_FALHA.txt",PUBLISHER)
        self.assertIn("$Command $argsText",PUBLISHER)
        self.assertIn("2>&1 | ForEach-Object",PUBLISHER)
        self.assertIn("etapa-",PUBLISHER)
        self.assertIn("$code=$LASTEXITCODE",PUBLISHER)
        self.assertIn("Falha na etapa $stage",PUBLISHER)
        self.assertNotIn(
            'Comando de build/validação falhou: $Command (exit $LASTEXITCODE)',
            PUBLISHER)

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
