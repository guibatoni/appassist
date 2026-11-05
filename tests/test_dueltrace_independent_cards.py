"""Independent card catalogue regressions: synthetic data, no game ROMs."""
from __future__ import annotations
import csv
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))

from scanner_multiiso import (
    SLUS_PTR_BASE,SLUS_ATTRIBUTES,decode_names,
    select_known_executable_layout,SCAN_PARSER_REVISION
)
from test_dueltrace_card_opponent_discovery import synthetic_executable
from importador_perfis import analyse
from auto_mods import report_level, supported_for_runtime


def make_known_layout(*, opponents=True, attributes=True):
    data=bytearray(synthetic_executable(shift=0))
    for index in range(1,723):
        a=((index*17)%101)*5
        d=((index*37)%103)*5
        value=(a | d<<9 | ((index%12)<<18)
               | ((index%11)<<22) | (((index*3)%21)<<26))
        if attributes:
            struct.pack_into("<I",data,SLUS_ATTRIBUTES+(index-1)*4,value)
            data[0x1C5B33+index-1]=(index%12+1)|((index%7+1)<<4)
    if not opponents:
        # Invalid opponents, valid card names. No trimmed v suffixes or
        # borrowing of names from another mod is permitted.
        for index in range(0x329,0x350):
            struct.pack_into("<H",data,SLUS_PTR_BASE+index*2,0)
    return bytes(data)


class IndependentCardTests(unittest.TestCase):
    def test_full_classic_layout_unchanged(self):
        opponents,cards,status=decode_names(make_known_layout())
        self.assertEqual(len(opponents),39)
        self.assertEqual(len(cards),722)
        self.assertIn("39 adversários",status)
        self.assertEqual(cards[-1]["nome"],"CARD0722")

    def test_valid_cards_survive_invalid_opponent_names(self):
        opponents,cards,status=decode_names(make_known_layout(opponents=False))
        self.assertEqual(opponents,[])
        self.assertEqual(len(cards),722)
        self.assertEqual(cards[0]["nome"],"CARD0001")
        self.assertIn("identidade em jogo não verificada",status)

    def test_neither_layout_nor_random_stats_are_promoted(self):
        opponents,cards,status=decode_names(
            make_known_layout(opponents=False,attributes=False))
        self.assertEqual(opponents,[])
        self.assertEqual(cards,[])
        self.assertIn("incompleto",status)

    def test_select_exe_prefers_full_catalogue_over_partial(self):
        partial=make_known_layout(opponents=False)
        full=make_known_layout()
        class FakeDisc:
            files={"FIRST.EXE":(1,len(partial)),"SECOND.EXE":(100,len(full))}
            def get(self,name):
                return partial if name=="FIRST.EXE" else full
        chosen,sl,opponents,cards,status,tried=select_known_executable_layout(
            FakeDisc(),["FIRST.EXE","SECOND.EXE"])
        self.assertEqual(chosen,"SECOND.EXE")
        self.assertEqual(len(opponents),39)
        self.assertEqual(len(cards),722)
        self.assertEqual(len(tried),2)
        self.assertEqual(tried[0]["opponents"],0)

    def test_only_partial_exe_is_still_selected(self):
        partial=make_known_layout(opponents=False)
        class FakeDisc:
            files={"FIRST.EXE":(1,len(partial))}
            def get(self,name):
                return partial
        chosen,sl,opponents,cards,status,tried=select_known_executable_layout(
            FakeDisc(),["FIRST.EXE"])
        self.assertEqual(chosen,"FIRST.EXE")
        self.assertEqual(len(cards),722)
        self.assertEqual(opponents,[])

    def test_profile_import_cards_without_opponents_never_enable_drops_or_rank(self):
        iso_sha="e"*64
        opponents,cards,_=decode_names(make_known_layout(opponents=False))
        self.assertEqual(opponents,[])
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            with (folder/"cartas.csv").open("w",newline="",encoding="utf-8-sig") as handle:
                writer=csv.DictWriter(handle,fieldnames=list(cards[0]))
                writer.writeheader()
                writer.writerows(cards)
            profile=analyse(folder,{"sha256":iso_sha,
                  "nomes_status":"cartas isoladas",
                  "candidate_catalogue":{"cards":0,"opponents":0}},folder/"mod.iso")
            self.assertEqual(len(profile["cards"]),722)
            self.assertTrue(profile["supported_features"]["cards"])
            self.assertFalse(profile["supported_features"]["opponents"])
            self.assertFalse(profile["supported_features"]["drops"])
            self.assertFalse(profile["supported_features"]["ranks"])
            self.assertFalse(profile["supported_features"]["scoring"])
            self.assertEqual(profile["verified"]["cartas"],"extraidas_estruturalmente")
            self.assertEqual(profile["verified"]["oponentes"],"pendente")
            self.assertEqual(report_level(profile),"parcial_revisar")
            self.assertTrue(supported_for_runtime(profile)["nomes_cartas"])
            self.assertFalse(supported_for_runtime(profile)["rank"])

    def test_parser_revision_forces_rescan(self):
        self.assertGreaterEqual(SCAN_PARSER_REVISION,17)


if __name__=="__main__":
    unittest.main()
