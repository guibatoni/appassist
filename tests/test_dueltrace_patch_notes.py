"""Notas da atualização verificadas, simples e limitadas; sem renderizar HTML."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_patch_notes import summarize_patch_notes
from dueltrace_preview_installer import select_preview_release, ASSET_NAME


class PatchNotesTests(unittest.TestCase):
    def test_markdown_sections_are_simple_and_ordered(self):
        notes=summarize_patch_notes("""# Notas
## Novidades
- Janela de novidades dentro do aplicativo.
## Melhorias
- Tela mais limpa e botões simples.
## Correções
- Prioridade da atualização estável.
---
Build 123 | SHA-256: abc
""")
        self.assertEqual([s["title"] for s in notes],
                         ["Novidades","Melhorias","Correções"])
        self.assertEqual(notes[0]["items"],["Janela de novidades dentro do aplicativo."])
        self.assertEqual(notes[2]["items"],["Prioridade da atualização estável."])

    def test_old_technical_release_has_no_invented_notes(self):
        self.assertEqual(summarize_patch_notes(
            "Preview privada Windows sem assinatura. Commit abc. SHA-256 XYZ. CI aprovada."),[])
        self.assertEqual(summarize_patch_notes(None),[])

    def test_content_is_plaintext_bounded_and_unique(self):
        body="## Novidades\n"+"\n".join(
            ["- **Atalho** [saiba mais](https://example.com)"]*2+
            ["- Atualização número "+str(i) for i in range(20)])
        notes=summarize_patch_notes(body)
        self.assertEqual(len(notes[0]["items"]),5)
        self.assertEqual(notes[0]["items"][0],"Atalho saiba mais")
        self.assertNotIn("https://",str(notes))

    def test_verified_preview_selects_its_own_notes(self):
        tag="preview-v0.9.7-r42422493893"
        pkg={"tag_name":tag,"draft":False,"prerelease":True,
             "target_commitish":"a"*40,
             "html_url":f"https://github.com/guibatoni/appassist/releases/tag/{tag}",
             "body":"## Melhorias\n- Interface mais limpa.",
             "assets":[{
                 "name":ASSET_NAME,"size":2000,
                 "digest":"sha256:"+"b"*64,
                 "browser_download_url":
                     f"https://github.com/guibatoni/appassist/releases/download/{tag}/{ASSET_NAME}"
             }]}
        found=select_preview_release(pkg,current_version="0.9.7",installed_run_id=100)
        self.assertEqual(found["patchNotes"],[
            {"title":"Melhorias","items":["Interface mais limpa."]}])

    def test_ui_uses_local_dialog_and_release_publishing_sources_notes(self):
        ui=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        dialog=(ROOT/"web/components/shell/update-patch-notes.tsx").read_text(encoding="utf-8")
        workflow=(ROOT/".github/workflows/validar-webui-desktop.yml").read_text(encoding="utf-8")
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
        self.assertIn('onClick={()=>setNotesOpen(true)}',ui)
        self.assertIn('aria-modal="true"',dialog)
        self.assertIn('backdrop-blur-md',dialog)
        self.assertIn('notes={patchNotes}',ui)
        self.assertIn('status["patchNotes"]',bridge)
        self.assertIn("patchNotesVersion",bridge)
        self.assertIn("--notes-file",workflow)
        self.assertIn("DUELTRACE_UPDATE_NOTES.md",workflow)


if __name__=="__main__":
    unittest.main()
