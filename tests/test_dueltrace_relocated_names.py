"""Regressões da descoberta conjunta de ponteiros, texto e glifos.

Usa somente um executável fictício com 722 registros de cartas e 39
oponentes, sem ROMs distribuídas. Nenhuma hipótese vira perfil verificado.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scanner"))

from scanner_multiiso import SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS, SCAN_PARSER_REVISION
from dueltrace_relocated_names import discover_relocated_name_layout
from test_dueltrace_card_opponent_discovery import synthetic_executable

ALL_INDICES = list(range(1, 723)) + list(range(0x329, 0x350))


def shifted_fixture(*, pointer_shift=0x1000, text_shift=0x1000,
                    glyph_shift=0x2000, corrupt_last=False,
                    keep_original_glyphs=False) -> bytes:
    raw=bytearray(synthetic_executable(shift=pointer_shift))
    origin=bytes(raw)
    table_base=SLUS_PTR_BASE+pointer_shift
    old_text=SLUS_TEXT_BASE
    new_text=SLUS_TEXT_BASE+text_shift
    new_glyph=SLUS_GLYPHS+glyph_shift
    needed=max(new_text+0x900+(len(ALL_INDICES)+1)*16,
               new_glyph+93*4,len(raw))
    if len(raw)<needed:
        raw.extend(b"\0"*(needed-len(raw)))
    # Capturar cada registro antes de apagar a fonte; janelas podem cruzar.
    records={}
    for idx in ALL_INDICES:
        off=struct.unpack_from("<H",origin,table_base+idx*2)[0]
        records[idx]=(off,origin[old_text+off:old_text+off+16])
    if text_shift:
        raw[old_text+0x900:old_text+0x900+len(ALL_INDICES)*16]=(
            b"\0"*(len(ALL_INDICES)*16))
        for off, rec in records.values():
            raw[new_text+off:new_text+off+len(rec)]=rec
    if corrupt_last:
        off=records[0x34F][0]
        pos=new_text+off if text_shift else old_text+off
        raw[pos+5:pos+16]=b"\x00"*11
    if glyph_shift:
        data=bytes(raw[SLUS_GLYPHS:SLUS_GLYPHS+93*4])
        if not keep_original_glyphs:
            raw[SLUS_GLYPHS:SLUS_GLYPHS+93*4]=b"\0"*(93*4)
        raw[new_glyph:new_glyph+93*4]=data
    return bytes(raw)


class RelocatedTextGlyphTests(unittest.TestCase):
    def discover(self, raw, **kwargs):
        return discover_relocated_name_layout(
            raw, pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
            glyph_base=SLUS_GLYPHS,**kwargs)

    def test_finds_relocated_pointer_text_and_glyph_tables(self):
        report=self.discover(shifted_fixture())
        self.assertEqual(report["state"],"layout_candidato_localizado")
        self.assertFalse(report["validated"])
        self.assertFalse(report["executionConfirmed"])
        self.assertEqual(len(report["candidates"]),1)
        c=report["candidates"][0]
        self.assertEqual(c["pointerShift"],0x1000)
        self.assertEqual(c["textShift"],0x1000)
        self.assertEqual(c["glyphShift"],0x2000)
        self.assertEqual(c["cardNamesTerminated"],722)
        self.assertEqual(c["opponentNamesTerminated"],39)
        self.assertEqual(c["cardSamples"][0]["text"],"CARD0001")
        self.assertEqual(c["opponentSamples"][-1]["text"],"OPP39")
        self.assertFalse(c["validated"])

    def test_supports_text_shift_with_original_pointer_and_glyph_table(self):
        report=self.discover(shifted_fixture(
            pointer_shift=0,text_shift=0x1000,glyph_shift=0))
        self.assertEqual(report["state"],"layout_candidato_localizado")
        row=report["candidates"][0]
        self.assertEqual(row["pointerBase"],SLUS_PTR_BASE)
        self.assertEqual(row["textBase"],SLUS_TEXT_BASE+0x1000)
        self.assertEqual(row["glyphBase"],SLUS_GLYPHS)

    def test_supports_only_glyph_shift_and_original_text_base(self):
        report=self.discover(shifted_fixture(
            pointer_shift=0,text_shift=0,glyph_shift=0x2000))
        self.assertEqual(report["state"],"layout_candidato_localizado")
        self.assertEqual(report["candidates"][0]["textShift"],0)
        self.assertEqual(report["candidates"][0]["glyphShift"],0x2000)

    def test_ambiguous_glyph_copies_never_promote_one_layout(self):
        report=self.discover(shifted_fixture(
            pointer_shift=0x1000,text_shift=0x1000,glyph_shift=0x2000,
            keep_original_glyphs=True))
        self.assertEqual(report["state"],"hipoteses_ambiguas")
        self.assertGreaterEqual(len(report["candidates"]),2)
        self.assertFalse(report["validated"])
        self.assertTrue(all(not c["validated"] for c in report["candidates"]))

    def test_last_opponent_corrupted_prevents_catalogue_promotion(self):
        report=self.discover(shifted_fixture(corrupt_last=True))
        self.assertEqual(report["state"],"nao_encontrado")
        self.assertEqual(report["candidates"],[])

    def test_shift_limits_are_enforced_for_all_three_structures(self):
        raw=shifted_fixture()
        report=self.discover(raw,max_shift=256,max_glyph_shift=256)
        self.assertEqual(report["state"],"ponteiros_ou_glifos_nao_localizados")
        self.assertFalse(report["validated"])
        self.assertEqual(report["limits"]["pointerAndTextShift"],256)
        self.assertEqual(report["limits"]["glyphShift"],256)

    def test_short_or_empty_executable_fails_closed(self):
        report=self.discover(b"\0"*256)
        self.assertEqual(report["state"],"executavel_incompativel")
        report=self.discover(b"\0"*(SLUS_GLYPHS+93*4+32),
                             max_shift=32,max_glyph_shift=32)
        self.assertEqual(report["state"],"ponteiros_ou_glifos_nao_localizados")
        self.assertFalse(report["validated"])

    def test_scanner_revision_and_private_evidence(self):
        code=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertIn('info["relocated_name_layouts"]=',code)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,11)
        self.assertNotIn('cards=info["relocated_name_layouts"]',code)
        self.assertNotIn('opponents=info["relocated_name_layouts"]',code)


if __name__=="__main__":
    unittest.main()
