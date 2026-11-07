"""Contratos da visualização de revisão de parser por ISO (sem ROMs)."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class OpponentRevisionUiTests(unittest.TestCase):
    def test_bridge_uses_registry_revision_and_does_not_fake_current_revision(self):
        source=(ROOT/"scanner"/"dueltrace_web_bridge.py").read_text(encoding="utf-8")
        self.assertIn('"scanParserRevision":entry.get("scan_parser_revision")',source)
        self.assertIn('type(entry.get("scan_parser_revision")) is int else None',source)
        self.assertNotIn('"scanParserRevision":19',source)

    def test_types_allow_old_or_missing_revision(self):
        source=(ROOT/"web"/"lib"/"desktop.ts").read_text(encoding="utf-8")
        self.assertIn('scanParserRevision?: number | null',source)

    def test_public_ui_explains_stale_scan_without_dumping_raw_evidence(self):
        source=(ROOT/"web"/"components"/"desktop"/"desktop-page.tsx").read_text(
            encoding="utf-8")
        mods=source.split("function Mods(",1)[1].split("function CardDropSourcesPanel(",1)[0]
        self.assertNotIn('mod.scanParserRevision<19',mods)
        self.assertNotIn('Análise anterior à revisão 19',mods)
        self.assertNotIn('Motivo ainda não registrado neste perfil.',mods)
        self.assertIn('Atualizar dados',mods)
        self.assertNotIn('quarantinedRecords',mods)
        self.assertNotIn('get_mod_scan_diagnostic',mods)


if __name__=="__main__":
    unittest.main()
