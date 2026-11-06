"""PS1 name control-byte forensics with synthetic, private-free executables."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))

from scanner_multiiso import (
    SCAN_PARSER_REVISION,SLUS_PTR_BASE,SLUS_TEXT_BASE,SLUS_GLYPHS)
from dueltrace_name_boundaries import read_name_table
from dueltrace_opponent_control_probe import (
    audit_control_window, inspect_control_windows)
from dueltrace_independent_opponents import compact_opponent_evidence
from dueltrace_forensic_ai import numeric_evidence
from test_dueltrace_independent_opponents import relocated_opponents, probe

START=0x360
SHA="d"*64


def mixed_executable(*, ff_after_fd=False, nonzero_after_ff=False):
    exe=bytearray(relocated_opponents())
    for ordinal in range(39):
        address=SLUS_PTR_BASE+(START+ordinal)*2
        pointer=struct.unpack_from("<H",exe,address)[0]
        beginning=SLUS_TEXT_BASE+pointer
        marker=exe.index(0xFF,beginning,beginning+48)
        if ordinal<22:
            exe[marker]=0xFD
            if ordinal==0 and ff_after_fd:
                exe[marker+1]=5 # valid glyph index
                exe[marker+2]=0xFF
        elif ordinal==22:
            exe[marker]=5 # neither FD nor FF
        elif ordinal==23 and nonzero_after_ff:
            exe[marker+1]=5
    return bytes(exe)


def control(exe):
    indices=tuple(range(START,START+39))
    rows=read_name_table(exe,pointer_base=SLUS_PTR_BASE,
        text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
        indices=indices,max_bytes=96)
    pointers={i:struct.unpack_from("<H",exe,SLUS_PTR_BASE+i*2)[0]
              for i in indices}
    return audit_control_window(exe,start_index=START,records=rows,
        pointers=pointers,text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS)


class MixedControlTests(unittest.TestCase):
    def test_22_fd_and_16_ff_remain_diagnostic_not_39_verified_names(self):
        exe=mixed_executable()
        metrics=control(exe)
        self.assertEqual(metrics["state"],"controles_mistos_necessitam_validacao")
        self.assertEqual(metrics["recordsExamined"],39)
        self.assertEqual(metrics["distinctPointers"],39)
        self.assertEqual(metrics["ffPresent"],16)
        self.assertEqual(metrics["fdPresent"],22)
        self.assertEqual(metrics["fdWithoutFf"],22)
        self.assertEqual(metrics["nonFfControlHistogram"]["0xFD"],22)
        self.assertFalse(metrics["mayPromote"])
        self.assertFalse(metrics["inGameVerified"])
        self.assertFalse(metrics["dropsVerified"])
        result=probe(exe)
        self.assertIsNone(result["selected"])
        compact=compact_opponent_evidence(result)
        self.assertFalse(compact["validated"])
        self.assertFalse(compact["rankVerified"])
        self.assertEqual(len(compact["forensicEvidence"]["controlWindows"]),5)

    def test_fd_followed_by_legible_byte_and_ff_is_measured_not_interpreted(self):
        metrics=control(mixed_executable(ff_after_fd=True))
        self.assertEqual(metrics["fdBeforeFf"],1)
        self.assertEqual(metrics["ffPresent"],17)
        self.assertGreaterEqual(metrics["fdFollowedByGlyph"],1)
        self.assertGreaterEqual(metrics["fdWithGlyphBeforeFf"],1)
        self.assertFalse(metrics["mayPromote"])

    def test_nonzero_after_ff_is_not_treated_as_padding(self):
        metrics=control(mixed_executable(nonzero_after_ff=True))
        self.assertGreaterEqual(metrics["nonZeroAfterFf"],1)
        self.assertFalse(metrics["validated"])

    def test_numeric_evidence_whitelists_counts_and_control_codes(self):
        report=compact_opponent_evidence(probe(mixed_executable()))
        report["forensicEvidence"]["controlWindows"][0]["privateName"]="EXFILTRATE_ME"
        report["forensicEvidence"]["controlWindows"][0]["nonFfControlHistogram"]["PRIVATE"]=99
        output=numeric_evidence({"independent_opponent_discovery":report})
        self.assertEqual(output["schema"],4)
        self.assertEqual(output["controlWindows"][0]["fdPresent"],22)
        self.assertEqual(output["controlWindows"][0]["nonFfControlHistogram"],{"0xFD":22})
        self.assertNotIn("EXFILTRATE_ME",json.dumps(output))
        self.assertNotIn("PRIVATE",json.dumps(output))
        self.assertFalse(output["mayActivate"])

    def test_missing_or_corrupt_executable_fails_closed(self):
        invalid=audit_control_window(b"\0"*256,start_index=START,
            records={},pointers={},text_base=SLUS_TEXT_BASE,
            glyph_base=SLUS_GLYPHS)
        self.assertIn(invalid["state"],("layout_nao_acessivel","ponteiros_ou_registros_invalidos"))
        self.assertFalse(invalid["mayPromote"])

    def test_mips_scan_exposes_real_state_not_inferred_unavailability(self):
        scanner=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf8")
        self.assertIn('target_source="janelas_candidatas_nao_verificadas"',scanner)
        self.assertIn('"state":"sem_alvos_candidatos"',scanner)
        self.assertIn('info["mips_name_pointer_evidence"]=inspect_mips_table_references(',scanner)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,25)

    def test_clipboard_contains_only_control_counts(self):
        js=(ROOT/"web/lib/opponent-report.ts").read_text(encoding="utf8")
        self.assertIn('controlFlowWindows: controlWindows',js)
        self.assertIn('for (const key of CONTROL_COUNTS)',js)
        self.assertIn('safe.nonFfControlHistogram = controlHistogram',js)
        self.assertNotIn('rawText:',js)
        self.assertNotIn('rawBytes:',js)
        self.assertNotIn('position:',js)

if __name__=="__main__":
    unittest.main()
