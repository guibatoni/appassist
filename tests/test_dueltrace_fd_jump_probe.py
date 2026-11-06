"""Synthetic 0xFD lo/hi jump diagnostics and PS-X EXE header-reason regressions."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))

from scanner_multiiso import (
    SLUS_PTR_BASE,SLUS_TEXT_BASE,SLUS_GLYPHS,SCAN_PARSER_REVISION)
from dueltrace_name_boundaries import read_name_table
from dueltrace_fd_jump_probe import audit_fd_jumps,inspect_fd_jump_windows
from dueltrace_mips_reference_probe import inspect_mips_table_references
from dueltrace_opponent_forensics import summarize_alternative_layouts
from dueltrace_forensic_ai import numeric_evidence
from dueltrace_independent_opponents import compact_opponent_evidence
from test_dueltrace_independent_opponents import relocated_opponents,probe
from test_dueltrace_mips_reference_probe import exe_at,ins_lui,ins_ori,HIGH,LOW,TABLE_OFFSET

START=0x360

def make_jump(*, target=0x5000, fd_at=2):
    exe=bytearray(relocated_opponents())
    ptr=struct.unpack_from("<H",exe,SLUS_PTR_BASE+START*2)[0]
    pos=SLUS_TEXT_BASE+ptr
    # The original 16-byte record's first glyphs are kept, and then
    # a branch FD low hi is inserted ahead of the original FF.
    exe[pos+fd_at:pos+fd_at+4]=bytes((0xFD,target&255,target>>8,0xFF))
    dest=SLUS_TEXT_BASE+target
    exe[dest:dest+4]=bytes((5,6,7,0xFF))
    return bytes(exe),pos


def scan_jumps(exe):
    indices=tuple(range(START,START+39))
    rows=read_name_table(exe,pointer_base=SLUS_PTR_BASE,
        text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
        indices=indices,max_bytes=96)
    ptrs={i:struct.unpack_from("<H",exe,SLUS_PTR_BASE+i*2)[0]
          for i in indices}
    return audit_fd_jumps(exe,start_index=START,
                          records=rows,pointers=ptrs,text_base=SLUS_TEXT_BASE)


class FDJumpTests(unittest.TestCase):
    def test_fd_lo_hi_points_to_independent_terminated_bank_entry(self):
        exe,_=make_jump()
        metrics=scan_jumps(exe)
        self.assertEqual(metrics["state"],"salto_fd_hipotese_estrutural")
        self.assertEqual(metrics["fdRecords"],1)
        self.assertEqual(metrics["fdWithTwoArguments"],1)
        self.assertEqual(metrics["jumpTargetInBank"],1)
        self.assertEqual(metrics["jumpTargetDistinctCount"],1)
        self.assertEqual(metrics["jumpTargetHasFF"],1)
        self.assertEqual(metrics["fdArgumentHighNonZero"],1)
        self.assertFalse(metrics["mayPromote"])
        self.assertFalse(metrics["inGameVerified"])
        self.assertFalse(metrics["dropsVerified"])

    def test_fd_target_is_not_promoted_to_a_duelist_name(self):
        exe,_=make_jump()
        report=probe(exe)
        self.assertIsNone(report["selected"])
        compact=compact_opponent_evidence(report)
        self.assertFalse(compact["inGameVerified"])
        self.assertFalse(compact["rankVerified"])
        windows=compact["forensicEvidence"]["fdJumpWindows"]
        self.assertEqual(len(windows),5)
        self.assertEqual(windows[0]["jumpTargetInBank"],1)
        safe=numeric_evidence({"independent_opponent_discovery":compact})
        self.assertEqual(safe["schema"],4)
        self.assertEqual(safe["fdJumpWindows"][0]["jumpTargetInBank"],1)
        self.assertNotIn("OPP",json.dumps(safe))
        self.assertNotIn("target",str(safe["fdJumpWindows"][0]).lower().replace("jumptarget",""))

    def test_corrupt_or_missing_fd_args_do_not_follow_outside_bank(self):
        invalid=audit_fd_jumps(b"\0"*128,start_index=START,
                               records={},pointers={},text_base=SLUS_TEXT_BASE)
        self.assertEqual(invalid["state"],"ponteiros_ausentes")
        self.assertFalse(invalid["mayPromote"])

    def test_header_reason_is_retained_without_disassembly(self):
        original=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        ok=inspect_mips_table_references(original,[TABLE_OFFSET])
        self.assertEqual(ok["headerEvidence"]["state"],
                         "cabecalho_coerente_nao_validado")
        self.assertTrue(ok["headerEvidence"]["mappingCoherent"])
        bad=inspect_mips_table_references(b"X"+original[1:],[TABLE_OFFSET])
        self.assertEqual(bad["state"],"psx_header_invalido")
        self.assertEqual(bad["headerEvidence"]["state"],"cabecalho_invalido")
        self.assertFalse(bad["headerEvidence"]["magicPresent"])
        self.assertFalse(bad["headerEvidence"]["mappingCoherent"])
        self.assertEqual(bad["references"],[])
        report=summarize_alternative_layouts({"mips_name_pointer_evidence":bad})
        header=report["probes"]["mipsStaticReferences"]["headerEvidence"]
        self.assertEqual(header["state"],"cabecalho_invalido")
        self.assertFalse(header["validated"])
        self.assertNotIn("exeSha256",json.dumps(report))

    def test_inconsistent_declared_payload_is_not_assumed_valid(self):
        blob=bytearray(exe_at([]))
        struct.pack_into("<I",blob,0x1c,0x1f0000)
        bad=inspect_mips_table_references(bytes(blob),[TABLE_OFFSET])
        self.assertEqual(bad["state"],"psx_header_invalido")
        self.assertEqual(bad["headerEvidence"]["state"],
                         "payload_truncado_ou_invalido")
        self.assertFalse(bad["executionConfirmed"])

    def test_ui_copies_bounded_jump_counters_and_header_reason(self):
        js=(ROOT/"web/lib/opponent-report.ts").read_text("utf8")
        self.assertIn("fdJumpWindows,",js)
        self.assertIn("for (const key of FD_JUMP_COUNTS)",js)
        self.assertIn("HEADER_STATES.has(raw.state)",js)
        self.assertNotIn("targetOffset:",js)
        self.assertNotIn("rawBytes:",js)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,27)


if __name__=="__main__":
    unittest.main()
