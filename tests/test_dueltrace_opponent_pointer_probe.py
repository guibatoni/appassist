"""Sondagem limitada de nomes de oponentes deslocados em executáveis PS1.

Apenas bytes de teste criados localmente; não utiliza ROM licenciada.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from scanner_multiiso import SLUS_PTR_BASE,SLUS_TEXT_BASE,SLUS_GLYPHS
from dueltrace_name_layout_probe import find_opponent_pointer_candidates


def make_executable(*, shifted=980, install=True) -> bytes:
    result=bytearray(SLUS_GLYPHS+93*4+1000)
    # Índices zero terminados devem permanecer inválidos.
    result[SLUS_TEXT_BASE]=255
    alphabet={1:"Ａ",2:"Ｂ",3:"Ｃ"}
    alphabet.update({4+i:chr(ord("０")+i) for i in range(10)})
    for code,letter in alphabet.items():
        bits=letter.encode("shift_jis")
        struct.pack_into("<H",result,SLUS_GLYPHS+code*4,int.from_bytes(bits,"big"))
    if install:
        for i in range(39):
            offset=500+i*8
            struct.pack_into("<H",result,SLUS_PTR_BASE+(shifted+i)*2,offset)
            a,b=divmod(i,10)
            result[SLUS_TEXT_BASE+offset:SLUS_TEXT_BASE+offset+6]=bytes(
                [1,2,3,4+a,4+b,255])
    return bytes(result)


class RelocatedOpponentPointerProbeTests(unittest.TestCase):
    def probe(self,buf):
        return find_opponent_pointer_candidates(
            buf,pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS)

    def test_relocated_39_names_are_candidates_not_catalog(self):
        result=self.probe(make_executable())
        self.assertFalse(result["validated"])
        self.assertEqual(result["state"],"hipoteses_de_ponteiros")
        self.assertEqual(result["candidates"][0]["startIndex"],980)
        self.assertEqual(result["candidates"][0]["plausible"],39)
        self.assertEqual(result["candidates"][0]["distinct"],39)
        self.assertEqual(result["candidates"][0]["samples"][0],"ABC00")
        self.assertFalse(result["candidates"][0]["validated"])

    def test_empty_or_invalid_strings_dont_become_opponents(self):
        result=self.probe(make_executable(install=False))
        self.assertEqual(result["candidates"],[])
        self.assertFalse(result["validated"])

    def test_short_executable_is_not_accessed_out_of_bounds(self):
        result=self.probe(bytes(1000))
        self.assertEqual(result["state"],"executavel_insuficiente")
        self.assertEqual(result["candidates"],[])

    def test_bounded_range_cannot_reclassify_card_names_as_opponents(self):
        result=self.probe(make_executable(shifted=10))
        self.assertEqual(result["candidates"],[])
        self.assertFalse(result["validated"])


if __name__=="__main__":
    unittest.main()
