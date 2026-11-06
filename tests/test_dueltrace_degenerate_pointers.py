"""Regression for real GOG evidence: 39 rereads of ONE pointer are not 39 opponents.

The supplied GOG diagnostic reported 39 readable/FF-terminated names,
pointerCountDistinct=1, pointerAliasCount=38 and maxAliasMultiplicity=39.
These fixtures model this failure with entirely synthetic bytes; never
include game ROMs, executable contents, or opponent-name data from a mod.
"""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scanner"))
sys.path.insert(0, str(ROOT/"tests"))

from scanner_multiiso import SLUS_PTR_BASE, SCAN_PARSER_REVISION
from dueltrace_independent_opponents import (
    compact_opponent_evidence, explain_opponent_blocker)
from test_dueltrace_independent_opponents import probe, relocated_opponents


def collapsed_pointer_table():
    exe = bytearray(relocated_opponents())
    base = SLUS_PTR_BASE + 0x360 * 2
    pointer = struct.unpack_from("<H", exe, base)[0]
    for ordinal in range(39):
        struct.pack_into("<H", exe, base + ordinal * 2, pointer)
    return bytes(exe)


class DegeneratePointerTests(unittest.TestCase):
    def test_39_terminated_reads_of_one_pointer_are_zero_independent_candidates(self):
        result = probe(collapsed_pointer_table())
        self.assertIsNone(result["selected"])
        self.assertEqual(result["candidateOpponentCount"], 0)
        self.assertEqual(result["candidateCount"], 0)
        self.assertEqual(result["state"], "tabela_de_ponteiros_degenerada")
        self.assertEqual(result["degenerateEvidence"]["distinctPointerCount"], 1)
        self.assertEqual(result["degenerateEvidence"]["maxRepeatedReads"], 38)
        self.assertGreater(result["degenerateEvidence"]["rejectedWindows"], 0)
        compact = compact_opponent_evidence(result)
        self.assertEqual(compact["candidateOpponentCount"], 0)
        self.assertEqual(compact["reasonCode"], "tabela_colapsada_um_ponteiro")
        self.assertIn("um único endereço", compact["reason"])
        self.assertNotIn("OPP", str(compact))
        self.assertFalse(compact["inGameVerified"])
        self.assertFalse(compact["dropsVerified"])

    def test_rejected_layout_remains_forensically_readable_and_shareable(self):
        compact = compact_opponent_evidence(probe(collapsed_pointer_table()))
        windows = compact["forensicEvidence"]["windows"]
        self.assertGreaterEqual(len(windows), 1)
        first = windows[0]
        self.assertEqual(first["candidateReadable"], 39)
        self.assertEqual(first["pointerCountDistinct"], 1)
        self.assertEqual(first["pointerAliasCount"], 38)
        self.assertEqual(first["maxAliasMultiplicity"], 39)
        self.assertEqual(first["pointerSpanMin"], 0)
        self.assertEqual(first["pointerSpanMax"], 0)
        self.assertFalse(first["eligibleForStructuralOnly"])

    def test_39_truly_distinct_records_are_still_available(self):
        result = probe(relocated_opponents())
        self.assertIsNotNone(result["selected"])
        self.assertEqual(len(result["selected"]["opponents"]), 39)
        self.assertEqual(result["candidateOpponentCount"], 39)
        self.assertFalse(result["inGameVerified"])

    def test_ui_explains_no_candidates_and_can_export_diagnostic(self):
        source = (ROOT/"web/components/desktop/desktop-page.tsx").read_text(
            encoding="utf-8")
        self.assertIn("Nenhuma sequência independente de adversários", source)
        self.assertIn("Boolean(mod.opponentDiagnosticReason)", source)
        self.assertIn("Copiar diagnóstico técnico", source)
        self.assertGreaterEqual(SCAN_PARSER_REVISION, 24)


if __name__ == "__main__":
    unittest.main()
