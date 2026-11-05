"""Evidência de ATK/DEF/tipo/nível/atributo vinculada a nomes da mesma ISO.

Somente executáveis PS1 sintéticos; sem ROMs reais, nenhuma função
publica automaticamente dados de catálogo, fusões, drops ou RANK.
"""
from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from scanner_multiiso import (
    SCAN_PARSER_REVISION,SLUS_ATTRIBUTES,SLUS_PTR_BASE,
    SLUS_TEXT_BASE,SLUS_GLYPHS)
from dueltrace_card_attribute_probe import discover_card_attribute_layout
from dueltrace_mod_diagnostic import diagnose_layout
from ia_local import minimal_evidence
from test_dueltrace_relocated_names import shifted_fixture

DETAIL_BASE=0x1C5B33
NAME_LAYOUT={
    "pointerBase":SLUS_PTR_BASE+0x1000,
    "textBase":SLUS_TEXT_BASE+0x1000,
    "glyphBase":SLUS_GLYPHS+0x2000
}


def make_exe(*,packed_shift=0x800,detail_shift=0x800,
             duplicate_detail_shift=None,attributes=True,
             corrupt_packed=False):
    data=bytearray(shifted_fixture())
    if not attributes:
        return bytes(data)
    pbase=SLUS_ATTRIBUTES+packed_shift
    dbase=DETAIL_BASE+detail_shift
    for i in range(1,723):
        atk_units=((i*17)%101)*5
        def_units=((i*37)%103)*5
        packed=(atk_units|def_units<<9|((i%12)<<18)
                |((i%11)<<22)|(((i*3)%21)<<26))
        struct.pack_into("<I",data,pbase+(i-1)*4,packed)
        detail=(i%12+1)|((i%7+1)<<4)
        data[dbase+i-1]=detail
        if duplicate_detail_shift is not None:
            data[DETAIL_BASE+duplicate_detail_shift+i-1]=detail
    if corrupt_packed:
        # Não usar um único candidato que parece plausível em algumas cartas.
        data[pbase:pbase+722*4]=b"\0"*(722*4)
    return bytes(data)


def discover(exe,**kw):
    return discover_card_attribute_layout(
        exe,name_layouts=[NAME_LAYOUT],packed_base=SLUS_ATTRIBUTES,
        detail_base=DETAIL_BASE,**kw)


class LinkedCardAttributeTests(unittest.TestCase):
    def test_links_real_id_names_and_both_attribute_tables_within_same_exe(self):
        exe=make_exe()
        result=discover(exe)
        self.assertEqual(result["state"],"candidatos_vinculados")
        self.assertFalse(result["validated"])
        self.assertFalse(result["inGameVerified"])
        self.assertEqual(result["exeSha256"],hashlib.sha256(exe).hexdigest())
        self.assertEqual(len(result["links"]),1)
        row=result["links"][0]
        self.assertEqual(row["namePointerBase"],NAME_LAYOUT["pointerBase"])
        self.assertEqual(row["packedBase"],SLUS_ATTRIBUTES+0x800)
        self.assertEqual(row["detailBase"],DETAIL_BASE+0x800)
        self.assertTrue(row["sharedShift"])
        self.assertEqual(row["nameCounts"]["cards"],722)
        self.assertEqual(row["nameCounts"]["opponents"],39)
        card=row["samples"][0]
        self.assertEqual(card,{"id":1,"name":"CARD0001","atk":850,
            "def":1850,"typeCode":3,"levelCode":2,
            "attributeCode":2,"star1Code":1,"star2Code":1})
        self.assertEqual(row["samples"][-1]["name"],"CARD0722")

    def test_tables_can_move_independently_without_copying_attributes(self):
        report=discover(make_exe(packed_shift=0x800,detail_shift=0x1000))
        self.assertEqual(report["state"],"candidatos_vinculados")
        row=report["links"][0]
        self.assertFalse(row["sharedShift"])
        self.assertEqual(row["packedShift"],0x800)
        self.assertEqual(row["detailShift"],0x1000)
        self.assertFalse(row["validated"])

    def test_ambiguous_detail_layouts_never_choose_automatically(self):
        result=discover(make_exe(
            packed_shift=0x800,detail_shift=0x800,
            duplicate_detail_shift=0x1000))
        self.assertEqual(result["state"],"hipoteses_ambiguas")
        self.assertGreaterEqual(len(result["links"]),2)
        self.assertFalse(result["validated"])
        self.assertTrue(all(not row["validated"] for row in result["links"]))

    def test_no_names_no_link_even_if_attributes_look_good(self):
        exe=make_exe()
        result=discover_card_attribute_layout(
            exe,name_layouts=[],packed_base=SLUS_ATTRIBUTES,
            detail_base=DETAIL_BASE)
        self.assertEqual(result["state"],"nomes_nao_identificados")
        self.assertEqual(result["packedCandidates"],[])
        self.assertEqual(result["links"],[])
        self.assertFalse(result["validated"])

    def test_no_attributes_or_truncated_table_is_rejected(self):
        empty=discover(make_exe(attributes=False))
        self.assertEqual(empty["state"],"atributos_nao_identificados")
        self.assertEqual(empty["links"],[])
        damaged=discover(make_exe(corrupt_packed=True))
        self.assertEqual(damaged["state"],"atributos_nao_identificados")
        self.assertFalse(damaged["validated"])

    def test_unsafe_ranges_and_invalid_input_fail_closed(self):
        exe=make_exe()
        for bad in (b"",b"\x00"*120, "untrusted",None):
            with self.subTest(bad=type(bad).__name__):
                result=discover_card_attribute_layout(
                    bad,name_layouts=[NAME_LAYOUT],
                    packed_base=SLUS_ATTRIBUTES,detail_base=DETAIL_BASE)
                self.assertEqual(result["state"],"entrada_invalida"
                                 if not isinstance(bad,bytes) else
                                 "nomes_nao_identificados")
                self.assertEqual(result["links"],[])
        result=discover(exe,max_shift=128)
        self.assertEqual(result["state"],"atributos_nao_identificados")
        self.assertEqual(result["radiusBytes"],128)

    def test_same_executable_provenance_reaches_only_private_diagnostics(self):
        exe=make_exe()
        evidence=discover(exe)
        scan={
            "status":"incerto",
            "arquivos_discos":[{"nome":"DATA/GAME.EXE","tamanho":len(exe),"lba":30}],
            "card_attribute_layouts":evidence
        }
        diagnostic=diagnose_layout(scan,{})
        meta=diagnostic["cardAttributeEvidence"]
        self.assertFalse(meta["validated"])
        self.assertFalse(meta["inGameVerified"])
        self.assertEqual(meta["exeSha256"],hashlib.sha256(exe).hexdigest())
        self.assertEqual(meta["links"][0]["samples"][0]["name"],"CARD0001")
        self.assertEqual(len(meta["links"][0]["samples"]),5)
        llm=minimal_evidence({
            "file":"example.iso","hash_rom":"a"*64,
            "inventory":{},"features":{},"scan_diagnostic":diagnostic
        })
        shown=llm["scan_diagnostic"]["cardAttributeEvidence"]
        self.assertFalse(shown["validated"])
        self.assertEqual(shown["links"][0]["packedBase"],SLUS_ATTRIBUTES+0x800)
        self.assertEqual(len(shown["links"][0]["samples"]),5)
        self.assertNotIn("rawExeBytes",str(shown))

    def test_scanner_uses_same_exe_without_promoting_guessed_catalog(self):
        code=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(SCAN_PARSER_REVISION,12)
        self.assertIn('info["card_attribute_layouts"]=discover_card_attribute_layout(',code)
        self.assertIn('info["mips_card_attribute_evidence"]=',code)
        self.assertNotIn('cards=info["card_attribute_layouts"]',code)
        self.assertNotIn('opponents=info["card_attribute_layouts"]',code)


if __name__=="__main__":
    unittest.main()
