"""Contrato de integração: drops por carta + atualizador Windows de um clique.

Testes locais de leitura, sem ROM, execução de instalador ou acesso à rede.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CardSourcesAndUpdateContractTests(unittest.TestCase):
    def test_library_is_wired_to_protected_card_drop_api(self):
        sources = {
            "scanner/dueltrace_drops.py": "def get_card_drop_sources(",
            "scanner/dueltrace_web_bridge.py": "def get_card_drop_sources(self, card_id)",
            "scanner/dueltrace_web_security.py": "def get_card_drop_sources(self, credential, card_id)",
            "web/lib/desktop.ts": "get_card_drop_sources(cardId: number)",
            "web/components/desktop/desktop-page.tsx": "get_card_drop_sources(card.id)",
        }
        for filename, expected in sources.items():
            with self.subTest(file=filename):
                self.assertIn(expected, (ROOT / filename).read_text(encoding="utf-8"))

    def test_updater_requires_one_click_without_disabling_package_checks(self):
        view = (ROOT / "web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        installer = (ROOT / "scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")
        self.assertIn("Atualizar agora", view)
        self.assertIn("Patch notes", view)
        self.assertNotIn("Ver builds Preview", view)
        self.assertNotIn("Ver versões estáveis", view)
        self.assertNotIn("window.confirm(", view)
        self.assertIn("await api.check_updates()", view)
        self.assertIn("SHA-256", installer)
        self.assertIn("$managed=@", installer)
        self.assertIn("Move-Item -LiteralPath $target", installer)
        self.assertNotIn("Rename-Item -LiteralPath $old", installer)
        self.assertIn("Start-Process", installer)


if __name__ == "__main__":
    unittest.main()
