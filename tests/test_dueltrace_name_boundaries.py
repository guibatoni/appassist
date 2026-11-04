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
from dueltrace_name_boundaries import inspect_opponent_name_boundaries, read_name_record, read_glyphs, read_name_table


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
        self.assertEqual(result["commonFirstInvalidByte"],"0xFE")
        self.assertEqual(result["commonFirstInvalidCount"],39)
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

    def test_final_visible_v_is_preserved_with_its_glyph_index(self):
        sl=bytearray(make_exe())
        struct.pack_into('<H',sl,SLUS_GLYPHS+4*4,
                         int.from_bytes('ｖ'.encode('shift_jis'),'big'))
        for number in range(39):
            start=SLUS_TEXT_BASE+1000+number*16
            sl[start:start+6]=bytes([1,2,3,4,0xFE,0])
        result=self.run_probe(bytes(sl))
        self.assertEqual(len(result['records']),39)
        self.assertEqual(result['commonFirstInvalidCount'],39)
        self.assertEqual(result['samples'][0]['readablePrefix'],'ABCv')
        self.assertEqual(result['samples'][0]['lastGlyph'],'v')
        self.assertEqual(result['samples'][0]['lastGlyphHex'],'0x04')
        self.assertEqual(result['samples'][0]['firstInvalidHex'],'0xFE')
        self.assertEqual(result['terminatedRecords'],0)
        self.assertFalse(result['validated'])

    def test_ff_after_invalid_control_is_present_but_not_a_decoded_name(self):
        sl=bytearray(make_exe())
        start=SLUS_TEXT_BASE+1000
        sl[start+10]=0xFF
        result=self.run_probe(bytes(sl))
        row=result['samples'][0]
        self.assertTrue(row['hasFFBeforeNext'])
        self.assertFalse(row['hasFF'])
        self.assertEqual(row['firstFFOffset'],10)
        self.assertEqual(row['recordStatus'],'glifo_invalido')
        self.assertEqual(result['terminatedRecords'],0)

    def test_out_of_order_and_shared_pointers_are_audited_without_joining_names(self):
        sl=bytearray(make_exe(suffix=0xFF))
        ptr=lambda number: SLUS_PTR_BASE+(0x328+number)*2
        struct.pack_into('<H',sl,ptr(1),1016)
        struct.pack_into('<H',sl,ptr(2),1000)
        struct.pack_into('<H',sl,ptr(3),1000)
        struct.pack_into('<H',sl,ptr(39),0xFFFF)
        result=self.run_probe(bytes(sl))
        self.assertEqual(result['pointerAudit']['outOfFile'],1)
        self.assertEqual(result['pointerAudit']['sharedRecords'],2)
        self.assertEqual(result['pointerAudit']['nonIncreasingPairs'],2)
        self.assertEqual(result['records'][0]['nextPointerDelta'],-16)
        self.assertEqual(result['records'][0]['physicalBoundaryDelta'],32)
        self.assertEqual(result['records'][0]['readablePrefix'],'ABCABA')
        self.assertTrue(result['records'][1]['sharedPointer'])
        self.assertEqual(result['records'][-1]['recordStatus'],'texto_fora_do_arquivo')
        self.assertFalse(result['validated'])

    def test_budget_does_not_claim_absence_before_unread_boundary(self):
        sl=bytearray(make_exe(suffix=0xFF))
        # One distant pointer; other pointers alias it. The long first record
        # cannot be read past the 128-byte budget even if FF exists later.
        for number in range(2,40):
            struct.pack_into('<H',sl,SLUS_PTR_BASE+(0x328+number)*2,1400)
        start=SLUS_TEXT_BASE+1000
        sl[start:start+400]=bytes([1])*399+b'\xff'
        result=self.run_probe(bytes(sl))
        row=result['records'][0]
        self.assertTrue(row['boundaryKnown'])
        self.assertFalse(row['boundaryReached'])
        self.assertIsNone(row['hasFFBeforeNext'])
        self.assertEqual(row['bytesExamined'],128)
        self.assertEqual(row['recordStatus'],'limite_leitura_sem_ff')
        self.assertEqual(result['noFFBeforeNext'],0)

    def test_header_cannot_cross_next_record_and_last_record_requires_ff(self):
        glyphs=read_glyphs(make_exe(),SLUS_GLYPHS)
        partial=read_name_record(b'\xf8\x0a\x01\xff',position=0,
            glyphs=glyphs,next_position=2)
        self.assertEqual(partial['recordStatus'],'cabecalho_incompleto')
        self.assertFalse(partial['hasFF'])
        last=read_name_record(b'\x01\x02\x03',position=0,glyphs=glyphs)
        self.assertEqual(last['recordStatus'],'fim_arquivo_sem_ff')
        self.assertEqual(last['readablePrefix'],'ABC')
        self.assertFalse(last['hasFF'])

    def test_shared_suffix_is_ambiguous_and_exact_pointer_alias_is_supported(self):
        sl=bytearray(make_exe(suffix=0xFF))
        start=SLUS_TEXT_BASE+1000
        sl[start:start+7]=bytes([1,2,0,3,1,2,0xFF])
        for number,ptr in ((1,1000),(2,1003),(3,1003)):
            struct.pack_into('<H',sl,SLUS_PTR_BASE+(0x328+number)*2,ptr)
        records=read_name_table(bytes(sl),pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
            indices=(0x329,0x32A,0x32B))
        outer=records[0x329]
        self.assertTrue(outer['ambiguousBoundary'])
        self.assertEqual(outer['recordStatus'],'sem_ff_antes_proximo')
        self.assertFalse(outer['hasFF'])
        self.assertEqual(outer['readablePrefix'],'AB')
        self.assertEqual(records[0x32A]['readablePrefix'],'CAB')
        self.assertEqual(records[0x32B]['readablePrefix'],'CAB')
        self.assertTrue(records[0x32A]['hasFF'])
        self.assertTrue(records[0x32B]['hasFF'])
        diagnostic=self.run_probe(bytes(sl))
        self.assertTrue(diagnostic['records'][0]['ambiguousBoundary'])
        self.assertTrue(diagnostic['records'][1]['sharedPointer'])
        self.assertFalse(diagnostic['validated'])


if __name__=="__main__":
    unittest.main()
