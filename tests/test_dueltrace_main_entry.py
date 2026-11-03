"""Testes de migração reversível: novo Desktop como entrada principal."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from instalar_inicio_dueltrace import START, END, migrate, patch_source, restore_source


LEGACY = '''"""Assistente antigo."""
from __future__ import annotations
from pathlib import Path
class App:
    pass
if __name__ == "__main__":
    Path(__file__).with_suffix(".mode").write_text("antigo", encoding="utf-8")
'''


class EntryBridgeTests(unittest.TestCase):
    def _fixture(self, base: Path):
        app = base / "app"
        tools = app / "tools"
        tools.mkdir(parents=True)
        script = app / "assistente_x15.py"
        script.write_text(LEGACY, encoding="utf-8")
        for name in ("dueltrace_desktop.py", "dueltrace_visuals.py"):
            (tools / name).write_text("# fixture", encoding="utf-8")
        (tools / "abrir_biblioteca.py").write_text(
            "from pathlib import Path\n"
            "def main():\n"
            "    (Path(__file__).resolve().parent.parent / 'assistente_x15.mode').write_text('moderno', encoding='utf-8')\n",
            encoding="utf-8")
        return script

    def test_routing_and_safe_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._fixture(Path(temp))
            changed, backup = migrate(path)
            self.assertTrue(changed)
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_text(encoding="utf-8"), LEGACY)
            content = path.read_text(encoding="utf-8")
            self.assertIn(START, content)
            self.assertIn(END, content)
            compile(content, str(path), "exec")
            subprocess.run([sys.executable, str(path)], check=True)
            self.assertEqual(path.with_suffix(".mode").read_text(encoding="utf-8"), "moderno")
            subprocess.run([sys.executable, str(path), "--legacy"], check=True)
            self.assertEqual(path.with_suffix(".mode").read_text(encoding="utf-8"), "antigo")
            changed_again, duplicate = migrate(path)
            self.assertFalse(changed_again)
            self.assertIsNone(duplicate)
            reverted, _ = migrate(path, restore=True)
            self.assertTrue(reverted)
            subprocess.run([sys.executable, str(path)], check=True)
            self.assertEqual(path.with_suffix(".mode").read_text(encoding="utf-8"), "antigo")
            self.assertNotIn(START, path.read_text(encoding="utf-8"))

    def test_rejects_unrecognized_or_broken_markers(self):
        with self.assertRaises(ValueError):
            patch_source("print('unrelated application')\n")
        with self.assertRaises(ValueError):
            patch_source(START + "\n")
        with self.assertRaises(ValueError):
            restore_source(START + "\n")

    def test_install_requires_validated_desktop_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "assistente_x15.py"
            path.write_text(LEGACY, encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                migrate(path)
            self.assertEqual(path.read_text(encoding="utf-8"), LEGACY)


if __name__ == "__main__":
    unittest.main()
