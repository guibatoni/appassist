"""Sondagem de tabela de nomes relocada, usando apenas MIPS sintético.

Os testes não possuem nomes reais do jogo, ISOs comerciais nem modificam
perfis. Uma hipótese nunca se torna carta/oponente validado automaticamente.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_card_opponent_discovery import (
    discover_relocated_name_table,MAX_SHIFT_BYTES)
from scanner_multiiso import (
    SLUS_PTR_BASE,SLUS_TEXT_BASE,SLUS_GLYPHS,decode_names,
    SCAN_PARSER_REVISION,
)

CHARACTERS="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CODES={letter:i+1 for i,letter in enumerate(CHARACTERS)}


def synthetic_executable(*,shift=0x1000,duplicate_shift=None,
                         damage_last=False):
    data=bytearray(max(SLUS_GLYPHS+93*4+256,
                       SLUS_PTR_BASE+0x3800+1800))
    for letter,index in CODES.items():
        wide=chr(ord(letter)+0xFEE0)
        encoded=wide.encode("shift_jis")
        assert len(encoded)==2
        struct.pack_into("<H",data,SLUS_GLYPHS+4*index,
                         int.from_bytes(encoded,"big"))

    name_locations={}
    for card_id in range(1,723):
        name_locations[card_id]=f"CARD{card_id:04d}"
    for oid in range(1,40):
        name_locations[0x328+oid]=f"OPP{oid:02d}"

    starts=(shift,) if duplicate_shift is None else (shift,duplicate_shift)
    for i,(index,name) in enumerate(name_locations.items()):
        position=SLUS_TEXT_BASE+0x900+i*16
        payload=bytes(CODES[ch] for ch in name)
        prefix=bytes((0xF8,0x0A,0x04)) if index%2==0 else b""
        raw=prefix+payload+(b"\x00" if damage_last and index==0x34F else b"\xff")
        data[position:position+len(raw)]=raw
        ptr=0x900+i*16
        for offset in starts:
            struct.pack_into("<H",data,
                             SLUS_PTR_BASE+offset+index*2,ptr)
    return bytes(data)


class RelocatedNameTableTests(unittest.TestCase):
    def search(self,sl,max_shift=MAX_SHIFT_BYTES):
        return discover_relocated_name_table(
            sl,pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
            glyph_base=SLUS_GLYPHS,max_shift=max_shift)

    def test_recovers_shifted_722_card_39_opponent_names_as_evidence(self):
        sl=synthetic_executable()
        bad_opp,bad_cards,_=decode_names(sl)
        self.assertFalse(bad_cards)
        self.assertFalse(bad_opp)
        found=self.search(sl)
        self.assertEqual(found["state"],"tabela_candidata_localizada")
        self.assertFalse(found["validated"])
        self.assertEqual(len(found["candidates"]),1)
        match=found["candidates"][0]
        self.assertEqual(match["pointerBase"],SLUS_PTR_BASE+0x1000)
        self.assertEqual(match["relativeShift"],0x1000)
        self.assertEqual(match["cardNamesTerminated"],722)
        self.assertEqual(match["opponentNamesTerminated"],39)
        self.assertEqual(match["distinctCardNames"],722)
        self.assertEqual(match["distinctOpponentNames"],39)
        self.assertFalse(match["validated"])
        self.assertEqual(match["cardSamples"][0]["text"],"CARD0001")
        self.assertEqual(match["cardSamples"][-1]["text"],"CARD0722")
        self.assertEqual(match["opponentSamples"][-1]["text"],"OPP39")

    def test_two_valid_shifted_tables_are_ambiguous(self):
        result=self.search(synthetic_executable(shift=0x1000,
                                                duplicate_shift=0x2000))
        self.assertEqual(result["state"],"hipoteses_ambiguas")
        self.assertFalse(result["validated"])
        self.assertGreaterEqual(len(result["candidates"]),2)
        self.assertTrue(all(not c["validated"] for c in result["candidates"]))

    def test_corrupted_last_opponent_never_gives_complete_catalogue(self):
        result=self.search(synthetic_executable(damage_last=True))
        self.assertEqual(result["state"],"nao_encontrado")
        self.assertFalse(result["candidates"])

    def test_scan_radius_is_bounded_and_can_not_overflow_budget(self):
        sl=synthetic_executable()
        limited=self.search(sl,max_shift=256)
        self.assertEqual(limited["scanRadiusBytes"],256)
        self.assertEqual(limited["state"],"nao_encontrado")
        self.assertLessEqual(limited["scannedPositions"],256)
        full=self.search(sl,max_shift=10**10)
        self.assertEqual(full["scanRadiusBytes"],MAX_SHIFT_BYTES)
        self.assertEqual(full["state"],"tabela_candidata_localizada")

    def test_glyphs_missing_and_executable_short_fail_closed(self):
        self.assertEqual(self.search(b"\0"*200)["state"],
                         "executavel_ou_glifos_incompativeis")
        zeros=bytes(SLUS_GLYPHS+93*4+256)
        self.assertEqual(self.search(zeros)["state"],"glifos_insuficientes")
        self.assertEqual(self.search(synthetic_executable()+
                                     b"\0"*(8*1024*1024))["state"],
                         "executavel_ou_glifos_incompativeis")

    def test_report_is_internal_only_and_cache_revision_updated(self):
        source=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertIn("discover_relocated_name_table(",source)
        self.assertIn('info["name_pointer_discovery"]=',source)
        self.assertIn("if not opponents or not cards:",source)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,9)
        self.assertNotIn("candidate['name']",source)


if __name__=="__main__":
    unittest.main()
