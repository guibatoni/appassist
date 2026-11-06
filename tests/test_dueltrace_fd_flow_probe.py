"""Regression: bounded text cursor traversal and PS-X EXE payload diagnostics.

Synthetic binaries only. The FD branch semantics remain a hypothesis
for unknown mods, and nothing may publish opponent IDs or drops.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))
from scanner_multiiso import SLUS_PTR_BASE, SLUS_TEXT_BASE, SCAN_PARSER_REVISION
from dueltrace_fd_flow_probe import trace_one_stream, audit_flow_window
from dueltrace_name_boundaries import read_glyphs, read_name_table
from dueltrace_forensic_ai import numeric_evidence
from dueltrace_independent_opponents import compact_opponent_evidence
from test_dueltrace_independent_opponents import relocated_opponents, probe
from test_dueltrace_mips_reference_probe import (
    exe_at, ins_lui, ins_ori, HIGH, LOW, TABLE_OFFSET)
from dueltrace_mips_reference_probe import inspect_mips_table_references
from dueltrace_opponent_forensics import summarize_alternative_layouts

FIRST=0x360


def fixture_jump(*, control_at_destination=None, circular=False):
    exe=bytearray(relocated_opponents())
    ptr=struct.unpack_from("<H",exe,SLUS_PTR_BASE+FIRST*2)[0]
    pos=SLUS_TEXT_BASE+ptr
    target=0x5000
    exe[pos+2:pos+5]=bytes((0xFD,target&255,target>>8))
    exe[pos+5]=0xff
    dest=SLUS_TEXT_BASE+target
    exe[dest:dest+4]=bytes((5,6,7,0xff))
    if control_at_destination is not None:
        exe[dest]=control_at_destination
    if circular:
        exe[dest:dest+3]=bytes((0xFD,target&255,target>>8))
    return bytes(exe)


def measure(exe):
    indexes=tuple(range(FIRST,FIRST+39))
    ptrs={i:struct.unpack_from("<H",exe,SLUS_PTR_BASE+i*2)[0] for i in indexes}
    rows=read_name_table(
        exe,pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
        glyph_base=0x1C9800,indices=indexes,max_bytes=96)
    return audit_flow_window(
        exe,start_index=FIRST,records=rows,pointers=ptrs,
        text_base=SLUS_TEXT_BASE,glyph_base=0x1C9800)


class FDFlowTests(unittest.TestCase):
    def test_fd_jump_reaches_real_ff_after_legible_glyphs(self):
        rows=measure(fixture_jump())
        self.assertEqual(rows["recordsExamined"],39)
        self.assertEqual(rows["fdRoutes"],1)
        self.assertEqual(rows["ffReachedAfterFd"],1)
        self.assertEqual(rows["fdRoutesWithGlyphs"],1)
        self.assertEqual(rows["cycleCount"],0)
        self.assertFalse(rows["validated"])
        self.assertFalse(rows["mayPromote"])

    def test_unknown_f8_cannot_be_assumed_to_continue_to_ff(self):
        rows=measure(fixture_jump(control_at_destination=0xF8))
        self.assertEqual(rows["fdRoutes"],1)
        self.assertEqual(rows["f8ControlCount"],1)
        self.assertEqual(rows["ffReachedAfterFd"],0)
        self.assertFalse(rows["inGameVerified"])

    def test_repeated_fd_destination_is_flagged_as_cycle(self):
        rows=measure(fixture_jump(circular=True))
        self.assertEqual(rows["cycleCount"],1)
        self.assertEqual(rows["ffReachedAfterFd"],0)

    def test_jump_without_full_fd_arguments_is_truncated(self):
        exe=b"\x05\xfd\x12"
        # The explicit boundary forbids reading an imaginary following arg.
        glyphs=tuple("a" for _ in range(93))
        state=trace_one_stream(exe,start=0,local_end=len(exe),
                               text_base=0,glyphs=glyphs)
        self.assertEqual(state["state"],"argumento_fd_truncado")
        self.assertFalse(bool(state["fdJumps"]))

    def test_new_metrics_remain_sanitized_and_non_promoting(self):
        report=compact_opponent_evidence(probe(fixture_jump()))
        forensic=report["forensicEvidence"]
        self.assertEqual(len(forensic["fdFlowWindows"]),5)
        forensic["fdFlowWindows"][0]["privateName"]="SECRET-DUELIST"
        safe=numeric_evidence({"independent_opponent_discovery":report})
        self.assertEqual(safe["schema"],4)
        self.assertEqual(safe["fdFlowWindows"][0]["fdRoutes"],1)
        self.assertNotIn("SECRET-DUELIST",str(safe))
        self.assertFalse(safe["mayActivate"])
        self.assertFalse(report["dropsVerified"])
        self.assertFalse(report["rankVerified"])

    def test_declared_payload_mismatch_is_classified_without_guessing_ram(self):
        good=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        valid=inspect_mips_table_references(good,[TABLE_OFFSET])
        h=valid["headerEvidence"]
        self.assertTrue(h["payloadFitsFile"])
        self.assertEqual(h["payloadOverhangBytes"],0)
        self.assertTrue(h["payloadAligned2048"])
        self.assertTrue(h["entryWithinLoadedRange"])
        invalid=bytearray(good)
        declared=len(good)+4096
        struct.pack_into("<I",invalid,0x1c,declared)
        result=inspect_mips_table_references(bytes(invalid),[TABLE_OFFSET])
        bad=result["headerEvidence"]
        self.assertFalse(bad["payloadFitsFile"])
        self.assertEqual(bad["payloadAvailableBytes"],len(good)-0x800)
        self.assertEqual(bad["payloadDeclaredBytes"],declared)
        self.assertEqual(bad["payloadOverhangBytes"],declared-(len(good)-0x800))
        self.assertEqual(result["state"],"psx_header_invalido")
        self.assertEqual(result["references"],[])
        safe=summarize_alternative_layouts({"mips_name_pointer_evidence":result})
        exposed=safe["probes"]["mipsStaticReferences"]["headerEvidence"]
        self.assertEqual(exposed["payloadOverhangBytes"],bad["payloadOverhangBytes"])
        self.assertNotIn("loadAddress",exposed)

    def test_clipboard_has_flow_and_header_sizes_but_no_raw_addresses(self):
        js=(ROOT/"web/lib/opponent-report.ts").read_text(encoding="utf8")
        self.assertIn("fdFlowWindows,",js)
        self.assertIn("for (const key of FD_FLOW_COUNTS)",js)
        self.assertIn("payloadOverhangBytes",js)
        self.assertNotIn("rawBytes:",js)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,27)


if __name__=="__main__":
    unittest.main()
