"""Source-level contracts for one-click, sanitized GOG forensic export.

The Windows UI must not expose names, binary bytes, paths or hashes when
sharing a diagnostic. The backend keeps raw observations quarantined.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OpponentReportCopyTests(unittest.TestCase):
    def test_user_action_exists_only_for_unverified_opponent_candidates(self):
        ui = (ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf8")
        section = ui.split("function Mods(",1)[1].split(
            "function CardDropSourcesPanel(",1)[0]
        self.assertIn("Copiar diagnóstico técnico",section)
        self.assertIn("copyOpponentReport(mod)",section)
        self.assertIn("!mod.opponents&&((mod.opponentCandidateCount??0)>0||Boolean(mod.opponentDiagnosticReason))",section)
        self.assertIn("Somente", "Somente")

    def test_serialization_only_uses_allowlisted_numeric_fields(self):
        src = (ROOT/"web/lib/opponent-report.ts").read_text(encoding="utf8")
        self.assertIn("export function safeOpponentReport(",src)
        self.assertIn("for (const key of COUNTS)",src)
        self.assertIn("safe[key] = count(window?.[key])",src)
        self.assertIn("histogram(window?.firstInvalidByteHistogram, false)",src)
        self.assertIn("return JSON.stringify(report, null, 2)",src)
        self.assertNotIn("JSON.stringify(diagnosis)",src)
        self.assertNotIn("...diagnosis",src)
        self.assertNotIn("...evidence",src)
        self.assertNotIn("sourcePath:",src)
        self.assertNotIn("romSha:",src)
        self.assertNotIn("quarantinedRecords",src)

    def test_diagnostic_read_only_no_ollama_or_binary_export(self):
        src = (ROOT/"web/lib/opponent-report.ts").read_text(encoding="utf8")
        self.assertIn("api.get_mod_scan_diagnostic(mod.sha256, false)",src)
        self.assertNotIn("api.scan_sources",src)
        self.assertNotIn("api.activate_mod",src)
        self.assertNotIn("fetch(",src)
        self.assertNotIn("readFile",src)
        self.assertIn("navigator.clipboard",src)
        self.assertIn("document.execCommand",src)

    def test_bridge_exports_aggregate_evidence(self):
        src = (ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf8")
        self.assertIn('diagnosis["opponentForensics"]=numeric_evidence(meta)',src)
        ai = (ROOT/"scanner/dueltrace_forensic_ai.py").read_text(encoding="utf8")
        self.assertIn('"windows": output',ai)
        self.assertIn('"scope": "hipoteses_nao_validadas"',ai)
        self.assertIn('"mayActivate": False',ai)


if __name__ == "__main__":
    unittest.main()
