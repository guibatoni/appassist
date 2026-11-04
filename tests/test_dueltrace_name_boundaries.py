"""Diagnóstico de limites de nomes em mods que usam outras terminações.

Dados inteiramente sintéticos. Sem ISOs do jogo nem textos copiados.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from scanner_multiiso import SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS
from dueltrace_name_boundaries import inspect_opponent_name_boundaries


def make_exe(*, suffix=0xFE, header=False):
    sl=bytearray(SLUS_GLYPHS + 93*4 + 1000)
    codes={1:"Ａ",2:"Ｂ",3:"Ｃ"}
    for idx,character in codes.items():
        raw=character.encode("shift_jis")
        struct.pack_into("<H",sl,SLUS_GLYPHS+idx*4,
                         int.from_bytes(raw,"big"))
    base=1000
    for number in range(1,40):
        ptr=base+(number-1)*16
        struct.pack_into("<H",sl,SLUS_PTR_BASE+(0x328+number)*2,ptr)
        position=SLUS_TEXT_BASE+ptr
        raw=(bytes([0xF8,0x0A,0x04]) if header else b"")
        raw+=bytes([1,2,3,1,2,1,0,0,suffix])
        # Padding after a possible alternate terminator is not interpreted
        # as evidence of the format, only the byte span is inspected.
        sl[position:position+len(raw)]=raw
    return bytes(sl)


class OpponentNameBoundaryTests(unittest.TestCase):
    def run_probe(self,data):
        return inspect_opponent_name_boundaries(
            data,pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS)

    def test_unrecognized_terminal_looks_readable_but_unverified(self):
        result=self.run_probe(make_exe(suffix=0xFE))
        self.assertFalse(result["validated"])
        self.assertEqual(result["state"],"limites_nao_validados")
        self.assertEqual(result["examined"],39)
        self.assertEqual(result["hasFFBeforeNext"],0)
        self.assertEqual(result["noFFBeforeNext"],38)
        self.assertEqual(result["samples"][0]["readablePrefix"],"ABCABA")
        self.assertEqual(result["samples"][0]["firstInvalidHex"],"0xFE")
        self.assertEqual(result["samples"][0]["nextPointerDelta"],16)
        self.assertFalse(result["samples"][0]["validated"])

    def test_known_ff_terminated_names_are_not_reported_as_broken(self):
        result=self.run_probe(make_exe(suffix=0xFF))
        self.assertEqual(result["hasFFBeforeNext"],38)
        self.assertEqual(result["noFFBeforeNext"],0)
        self.assertIsNone(result["samples"][0]["firstInvalidHex"])
        self.assertEqual(result["samples"][0]["readablePrefix"],"ABCABA")
        self.assertFalse(result["validated"])

    def test_header_aware_diagnostic_does_not_treat_f8_as_text(self):
        result=self.run_probe(make_exe(suffix=0xFE,header=True))
        self.assertTrue(result["samples"][0]["headerPresent"])
        self.assertEqual(result["samples"][0]["readablePrefix"],"ABCABA")
        self.assertEqual(result["samples"][0]["firstInvalidHex"],"0xFE")

    def test_short_or_invalid_file_does_not_get_accepted(self):
        result=self.run_probe(bytes(100))
        self.assertEqual(result["state"],"executavel_incompleto")
        self.assertEqual(result["samples"],[])
        self.assertFalse(result["validated"])


if __name__=="__main__":
    unittest.main()
