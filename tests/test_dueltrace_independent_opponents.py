"""Regressions for bounded, independent opponent pointer discovery.

All assets are synthetic; no game ROM, executable or artwork is distributed.
"""
from __future__ import annotations

import csv
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))

from scanner_multiiso import (
    SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS, decode_names,
    SCAN_PARSER_REVISION)
from dueltrace_independent_opponents import (
    discover_independent_opponents, compact_opponent_evidence)
from test_dueltrace_independent_cards import make_known_layout
from importador_perfis import analyse
from auto_mods import report_level, supported_for_runtime

SHA = "e"*64


def relocated_opponents(*, starts=(0x360,), terminator=0xff):
    exe=bytearray(make_known_layout())
    # The original table is emptied to simulate a GOG-style relocation.
    pointers=[]
    for i in range(39):
        ptr=struct.unpack_from("<H",exe,SLUS_PTR_BASE+(0x329+i)*2)[0]
        pointers.append(ptr)
        struct.pack_into("<H",exe,SLUS_PTR_BASE+(0x329+i)*2,0)
    for first in starts:
        for offset,ptr in enumerate(pointers):
            struct.pack_into("<H",exe,SLUS_PTR_BASE+(first+offset)*2,ptr)
    if terminator != 0xff:
        for ptr in pointers:
            pos=SLUS_TEXT_BASE+ptr
            ff=exe.index(0xff,pos,pos+48)
            exe[ff]=terminator
    return bytes(exe)


def probe(exe):
    return discover_independent_opponents(
        exe,pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
        glyph_base=SLUS_GLYPHS,rom_sha256=SHA)


def write_rows(path,items):
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


class IndependentOpponentTests(unittest.TestCase):
    def test_recovers_39_from_unique_shifted_block(self):
        exe=relocated_opponents()
        report=probe(exe)
        self.assertEqual(report["state"],"layout_independente_unico_estrutural")
        self.assertEqual(report["candidateOpponentCount"],39)
        self.assertEqual(report["selected"]["startIndex"],0x360)
        self.assertEqual(len(report["selected"]["opponents"]),39)
        self.assertEqual(report["selected"]["opponents"][0]["nome"],"OPP01")
        self.assertEqual(report["selected"]["opponents"][-1]["nome"],"OPP39")
        self.assertFalse(report["validated"])
        self.assertFalse(report["inGameVerified"])
        self.assertFalse(report["dropsVerified"])

    def test_old_decoder_remains_card_only(self):
        exe=relocated_opponents()
        old_opps,old_cards,_=decode_names(exe)
        self.assertFalse(old_opps)
        self.assertEqual(len(old_cards),722)
        self.assertEqual(len(probe(exe)["selected"]["opponents"]),39)

    def test_ambiguous_complete_blocks_are_not_selected(self):
        result=probe(relocated_opponents(starts=(0x360,0x3b0)))
        self.assertEqual(result["state"],"layouts_completos_ambiguos")
        self.assertIsNone(result["selected"])
        self.assertEqual(result["candidateOpponentCount"],39)
        self.assertGreaterEqual(result["candidateCount"],2)

    def test_alternative_terminator_is_only_hypothesis(self):
        result=probe(relocated_opponents(terminator=0xfe))
        self.assertEqual(result["state"],"hipotese_terminador_alternativo")
        self.assertIsNone(result["selected"])
        self.assertEqual(result["candidateOpponentCount"],39)
        self.assertTrue(any(x["possibleDifferentTerminator"]=="0xFE"
                            for x in result["candidates"]))
        self.assertFalse(result["inGameVerified"])

    def test_random_or_truncated_binary_not_promoted(self):
        self.assertIsNone(probe(bytes(3_000_000))["selected"])
        self.assertEqual(probe(b"\0"*1024)["state"],
                         "executavel_ou_parametros_incompativeis")

    def test_sha_malformed_refuses_evidence(self):
        raw=relocated_opponents()
        result=discover_independent_opponents(raw,pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,rom_sha256="wrong")
        self.assertIsNone(result["selected"])

    def test_compact_report_never_includes_card_or_opponent_names(self):
        report=compact_opponent_evidence(probe(relocated_opponents()))
        self.assertEqual(report["selectedStartIndex"],0x360)
        self.assertFalse(report["validated"])
        self.assertNotIn("OPP",str(report))
        self.assertNotIn("opponents",report)

    def test_iso_profile_displays_structural_opponents_but_blocks_all_drops(self):
        exe=relocated_opponents()
        candidates=probe(exe)
        _,cards,_=decode_names(exe)
        opponents=candidates["selected"]["opponents"]
        checks=[]
        drops=[]
        for oid in range(1,40):
            for group in ("GRUPO_1","GRUPO_2","GRUPO_3"):
                checks.append({"oponente_id":oid,"rank":group,"peso_total":2048})
                drops.append({"oponente_id":oid,"rank":group,
                              "carta_id":1,"peso":2048})
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            write_rows(folder/"cartas.csv",cards)
            write_rows(folder/"oponentes.csv",opponents)
            write_rows(folder/"validacao_pesos.csv",checks)
            write_rows(folder/"drops_por_oponente.csv",drops)
            write_rows(folder/"decks.csv",[{"oponente_id":1,"carta_id":1,"peso":20}])
            meta={"sha256":SHA,"opponent_identification":"extraidos_estruturalmente",
                  "independent_opponent_discovery":compact_opponent_evidence(candidates)}
            profile=analyse(folder,meta,folder/"gog_synthetic.iso")
            self.assertEqual(len(profile["cards"]),722)
            self.assertEqual(len(profile["opponents"]),39)
            self.assertTrue(profile["supported_features"]["opponents"])
            self.assertFalse(profile["supported_features"]["drops"])
            self.assertFalse(profile["supported_features"]["ranks"])
            self.assertEqual(profile["drops"],[])
            self.assertEqual(profile["decks"],[])
            self.assertEqual(profile["verified"]["oponentes"],"extraidos_estruturalmente")
            self.assertEqual(report_level(profile),"parcial_revisar")
            self.assertTrue(supported_for_runtime(profile)["oponentes"])
            self.assertFalse(supported_for_runtime(profile)["drops_brutos"])
            self.assertFalse(supported_for_runtime(profile)["rank"])
            self.assertFalse(supported_for_runtime(profile)["pontuacao"])

    def test_revision_and_no_cross_mod_publish(self):
        self.assertGreaterEqual(SCAN_PARSER_REVISION,18)
        source=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf8")
        self.assertIn("discover_independent_opponents(",source)
        self.assertIn("oponentes_candidatos_nao_verificados.json",source)
        self.assertNotIn("drops=found_opponents",source)


if __name__=="__main__":
    unittest.main()
