"""Protege a publicação da Preview que o atualizador lê dentro do app.

A build no Windows e o ZIP são testados pelo workflow. Aqui validamos que
seu job de publicação (runner Linux separado) possui checkout para ler as
notas e que só publica pré-releases após a conclusão da build segura.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/validar-webui-desktop.yml").read_text(
    encoding="utf-8"
)


class PreviewPublishWorkflowTests(unittest.TestCase):
    def test_release_job_checks_out_source_before_release_notes(self):
        self.assertIn("  publish-preview-release:", WORKFLOW)
        publishing = WORKFLOW.split("  publish-preview-release:", 1)[1]
        self.assertIn("    needs: build-web-and-windows", publishing)
        self.assertIn("github.event_name == 'push'", publishing)
        self.assertIn("steps.preview_artifact.outcome == 'success'", WORKFLOW)
        self.assertIn("uses: actions/checkout@v4", publishing)
        self.assertIn("persist-credentials: false", publishing)
        self.assertLess(
            publishing.index("uses: actions/checkout@v4"),
            publishing.index("uses: actions/download-artifact@v4"),
        )
        self.assertLess(
            publishing.index("uses: actions/checkout@v4"),
            publishing.index("cp docs/DUELTRACE_UPDATE_NOTES.md"),
        )
        self.assertIn("gh release create", publishing)
        self.assertIn("--prerelease --latest=false", publishing)

    def test_release_uses_public_preview_zip_with_authenticated_ci(self):
        publishing = WORKFLOW.split("  publish-preview-release:", 1)[1]
        self.assertIn("contents: write", publishing)
        self.assertIn("GH_TOKEN: ${{ github.token }}", publishing)
        self.assertIn('preview/DUELTRACE-WebUI-Windows-Preview.zip', publishing)
        self.assertIn('expected="sha256:', publishing)
        self.assertIn('actual_digest', publishing)
        self.assertIn('actual_size', publishing)
        self.assertIn("--target \"$GITHUB_SHA\"", publishing)


if __name__ == "__main__":
    unittest.main()
