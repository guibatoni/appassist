"""Alias-aware opponent parsing tests, using synthetic executables only.

Each candidate points inside its *own* image. No ROM, game binary, save,
Memory Card or copied mod data is needed.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
sys.path.insert(0, str(ROOT / "tests"))

from scanner_multiiso import SLUS_PTR_BASE, SLUS_TEXT_BASE
from test_dueltrace_independent_opponents import relocated_opponents, probe
from dueltrace_independent_opponents import compact_opponent_evidence

START = 0x360
COUNT = 39
STRIDE = 16


def compacted_aliases(duplicates: dict[int, int]) -> bytes:
    """Build an actual compacted text pool (not orphaned bytes).

    The duplicate map is ordinal ID->earlier ordinal ID. All unaliased names
    retain their spelling but their physical locations are packed to fill
    any removed slot. The 39 pointer-table entries stay at original indices.
    """
    exe = bytearray(relocated_opponents(terminator=0xFE))
    ptrbase = SLUS_PTR_BASE + START*2
    pointers = list(struct.unpack_from("<" + "H"*COUNT, exe, ptrbase))
    pool = {
        oid: bytes(exe[SLUS_TEXT_BASE + ptr:SLUS_TEXT_BASE + ptr + STRIDE])
        for oid, ptr in enumerate(pointers, 1)
    }
    for oid, target in duplicates.items():
        if not (1 <= target < oid <= COUNT) or target in duplicates:
            raise ValueError("Target must be an earlier, non-aliased ID")
    new_pointers = {}
    next_physical = pointers[0]
    for oid in range(1, COUNT+1):
        if oid in duplicates:
            new_pointers[oid] = new_pointers[duplicates[oid]]
        else:
            new_pointers[oid] = next_physical
            next_physical += STRIDE
    start = SLUS_TEXT_BASE + pointers[0]
    end = start + COUNT * STRIDE
    exe[start:end] = b"\0" * (end-start)
    for oid in range(1, COUNT+1):
        if oid not in duplicates:
            pos = SLUS_TEXT_BASE + new_pointers[oid]
            exe[pos:pos+STRIDE] = pool[oid]
        struct.pack_into("<H", exe, ptrbase + (oid-1)*2, new_pointers[oid])
    return bytes(exe)


class OpponentAliasTests(unittest.TestCase):
    def test_one_true_compacted_alias_can_be_structural(self):
        result = probe(compacted_aliases({2: 1}))
        self.assertEqual(result["state"], "layout_terminador_alternativo_estrutural")
        self.assertEqual(result["selected"]["aliasCount"], 1)
        self.assertEqual(result["selected"]["verifiedPhysicalBoundaries"], 37)
        self.assertEqual(result["selected"]["evidence"],
                         "marcador_alternativo_com_aliases_estruturais")
        self.assertEqual(len(result["selected"]["opponents"]),39)
        self.assertEqual(result["selected"]["opponents"][0],{"id":1,"nome":"OPP01"})
        self.assertEqual(result["selected"]["opponents"][1],{"id":2,"nome":"OPP01"})
        self.assertEqual(result["selected"]["opponents"][2],{"id":3,"nome":"OPP03"})
        self.assertEqual(result["selected"]["opponents"][-1],{"id":39,"nome":"OPP39"})
        self.assertFalse(result["inGameVerified"])
        self.assertFalse(result["dropsVerified"])
        self.assertFalse(result["rankVerified"])

    def test_two_aliases_are_limit_with_37_unique_records(self):
        result = probe(compacted_aliases({2:1,4:3}))
        self.assertEqual(result["state"], "layout_terminador_alternativo_estrutural")
        selected = result["selected"]
        self.assertEqual(selected["aliasCount"],2)
        self.assertEqual(selected["verifiedPhysicalBoundaries"],36)
        self.assertEqual(selected["opponents"][3],{"id":4,"nome":"OPP03"})
        evidence = result["boundaryTerminatorEvidence"]["candidates"][0]
        self.assertEqual(evidence["physicalRecordCount"],37)
        self.assertEqual(evidence["aliasGroupsCount"],2)
        self.assertEqual(evidence["maxAliasMultiplicity"],2)
        self.assertEqual(evidence["verifiedBoundaries"],36)
        self.assertEqual(result["forensicEvidence"]["windows"][0]["pointerAliasCount"],2)
        self.assertFalse(result["validated"])

    def test_three_aliases_are_not_eligible_even_when_clean(self):
        result=probe(compacted_aliases({2:1,4:3,6:5}))
        self.assertIsNone(result["selected"])
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],0)
        evidence = result["forensicEvidence"]["windows"][0]
        self.assertEqual(evidence["pointerAliasCount"],3)
        self.assertEqual(evidence["boundaryDecision"],"aliases_excessivos")
        self.assertFalse(result["inGameVerified"])

    def test_uncompacted_duplicate_with_orphan_name_is_still_rejected(self):
        exe = bytearray(relocated_opponents(terminator=0xFE))
        base = SLUS_PTR_BASE + START * 2
        first=struct.unpack_from("<H",exe,base)[0]
        struct.pack_into("<H",exe,base+2,first)
        result = probe(bytes(exe))
        self.assertIsNone(result["selected"])
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],0)
        decision = result["forensicEvidence"]["windows"][0]["boundaryDecision"]
        self.assertIn(decision, ("dados_apos_marcador", "ponteiro_intercalado"))
        self.assertFalse(result["dropsVerified"])

    def test_compact_report_does_not_expose_alias_names_or_bytes(self):
        result = probe(compacted_aliases({2:1}))
        data = compact_opponent_evidence(result)
        serialized = json.dumps(data)
        self.assertIn("aliasCount", serialized)
        self.assertNotIn("OPP01", serialized)
        self.assertNotIn("quarantinedRecords", serialized)
        self.assertFalse(data["inGameVerified"])
        self.assertFalse(data["rankVerified"])
        self.assertFalse(data["dropsVerified"])

    def test_alias_after_reversing_ordinal_table_still_preserves_indices(self):
        exe=bytearray(compacted_aliases({2:1}))
        base=SLUS_PTR_BASE + START*2
        pointers=struct.unpack_from("<"+"H"*COUNT,exe,base)
        struct.pack_into("<"+"H"*COUNT,exe,base,*reversed(pointers))
        result=probe(bytes(exe))
        self.assertIsNotNone(result["selected"])
        self.assertEqual(result["selected"]["opponents"][0],{"id":1,"nome":"OPP39"})
        self.assertEqual(result["selected"]["opponents"][-1],{"id":39,"nome":"OPP01"})
        self.assertEqual(result["selected"]["aliasCount"],1)
        self.assertFalse(result["inGameVerified"])


if __name__ == "__main__":
    unittest.main()
