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
    discover_independent_opponents, compact_opponent_evidence,
    explain_opponent_blocker)
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

    def test_alternative_terminator_with_proven_physical_boundaries(self):
        result=probe(relocated_opponents(terminator=0xfe))
        self.assertEqual(result["state"],"layout_terminador_alternativo_estrutural")
        self.assertEqual(result["candidateOpponentCount"],39)
        self.assertEqual(len(result["selected"]["opponents"]),39)
        self.assertEqual(result["selected"]["opponents"][0]["nome"],"OPP01")
        self.assertEqual(result["selected"]["opponents"][-1]["nome"],"OPP39")
        self.assertEqual(result["selected"]["evidence"],
                         "marcador_alternativo_e_38_fronteiras_fisicas")
        boundary=result["boundaryTerminatorEvidence"]
        self.assertEqual(boundary["candidateCount"],1)
        self.assertEqual(boundary["candidates"][0]["terminator"],"0xFE")
        self.assertEqual(boundary["candidates"][0]["verifiedBoundaries"],38)
        self.assertFalse(result["inGameVerified"])
        self.assertFalse(result["dropsVerified"])
        self.assertFalse(result["rankVerified"])

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

    def test_unmapped_drop_groups_never_enter_public_catalogue(self):
        from test_dueltrace_independent_cards import make_known_layout
        original=make_known_layout()
        opponents,cards,_=decode_names(original)
        self.assertEqual(len(cards),722)
        self.assertEqual(len(opponents),39)
        checks=[]; drops=[]
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
            profile=analyse(folder,{
                "sha256":SHA,
                "drop_group_mapping_status":"grupos_nao_identificados",
            },folder/"unknown_groups.iso")
            self.assertTrue(profile["supported_features"]["cards"])
            self.assertTrue(profile["supported_features"]["opponents"])
            self.assertFalse(profile["supported_features"]["drops"])
            self.assertFalse(profile["supported_features"]["ranks"])
            self.assertEqual(profile["drop_group_labels"],[])
            self.assertEqual(profile["drops"],[])
            self.assertEqual(profile["drops_provenance"]["candidate_table_count"],117)

    def test_strict_boundary_evidence_is_structural_only(self):
        report=probe(relocated_opponents(terminator=0xfe))
        reason=explain_opponent_blocker(report)
        self.assertEqual(reason["code"],"nomes_estruturais")
        compact=compact_opponent_evidence(report)
        self.assertEqual(compact["reasonCode"],"nomes_estruturais")
        self.assertEqual(compact["candidateOpponentCount"],39)
        self.assertEqual(compact["boundaryTerminatorEvidence"]["candidateCount"],1)
        self.assertNotIn("OPP01",str(compact))
        self.assertFalse(compact["inGameVerified"])

    def test_ambiguous_table_reason_never_chooses_arbitrary_index(self):
        report=probe(relocated_opponents(starts=(0x360,0x3b0)))
        reason=explain_opponent_blocker(report)
        self.assertEqual(reason["code"],"multiplos_blocos")
        self.assertIsNone(report["selected"])

    def test_quarantined_full_names_not_exposed_in_compact_report(self):
        report=probe(relocated_opponents())
        self.assertGreaterEqual(len(report["quarantinedRecords"]),1)
        self.assertEqual(len(report["quarantinedRecords"][0]["records"]),39)
        self.assertIn("OPP01",str(report["quarantinedRecords"]))
        compact=compact_opponent_evidence(report)
        self.assertNotIn("quarantinedRecords",compact)
        self.assertNotIn("OPP01",str(compact))
        self.assertEqual(compact["reasonCode"],"nomes_estruturais")

    def test_failure_reasons_include_missing_isolation_and_duplicates(self):
        samples=[
            ({"state":"tabelas_parciais_nao_verificadas",
              "candidates":[{"recognized":39,"readablePrefixes":39,
                              "distinctPointers":39,"distinctNames":39,
                              "isolated":False}]},
              "bloco_nao_isolado"),
            ({"state":"tabelas_parciais_nao_verificadas",
              "candidates":[{"recognized":35,"readablePrefixes":39,
                              "distinctPointers":35,"distinctNames":35,
                              "isolated":True}]},
              "ponteiros_repetidos"),
            ({"state":"tabelas_parciais_nao_verificadas",
              "candidates":[{"recognized":39,"readablePrefixes":39,
                              "distinctPointers":39,"distinctNames":28,
                              "isolated":True}]},
              "nomes_repetidos")
        ]
        for source, expected in samples:
            with self.subTest(reason=expected):
                self.assertEqual(explain_opponent_blocker(source)["code"],expected)

    def test_public_ui_shows_reason_without_raw_evidence_or_rom(self):
        ui=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf8")
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf8")
        mods=ui.split("function Mods(",1)[1].split("function CardDropSourcesPanel(",1)[0]
        self.assertNotIn("Motivo: {mod.opponentDiagnosticReason}",mods)
        self.assertIn('"opponentDiagnosticReason"',bridge)
        self.assertNotIn("quarantinedRecords",ui)
        self.assertNotIn("get_mod_scan_diagnostic",ui.split("function Mods(",1)[1].split(
            "function CardDropSourcesPanel(",1)[0])

    def test_nonzero_data_after_fe_blocks_structural_promotion(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        first=struct.unpack_from("<H",exe,SLUS_PTR_BASE+0x360*2)[0]
        pos=SLUS_TEXT_BASE+first
        marker=exe.index(0xfe,pos,pos+32)
        exe[marker+1]=1
        result=probe(bytes(exe))
        self.assertIsNone(result["selected"])
        self.assertEqual(result["state"],"hipotese_terminador_alternativo")
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],0)

    def test_mixed_control_bytes_never_select_opponent_ids(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        first=struct.unpack_from("<H",exe,SLUS_PTR_BASE+0x360*2)[0]
        pos=SLUS_TEXT_BASE+first
        marker=exe.index(0xfe,pos,pos+32)
        exe[marker]=0xfd
        result=probe(bytes(exe))
        self.assertIsNone(result["selected"])
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],0)

    def test_ambiguous_terminated_physical_blocks_are_rejected(self):
        result=probe(relocated_opponents(starts=(0x360,0x3b0),terminator=0xfe))
        self.assertEqual(result["state"],"layouts_completos_ambiguos")
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],2)
        self.assertIsNone(result["selected"])

    def test_out_of_order_pointers_keep_original_id_to_name_mapping(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        a=SLUS_PTR_BASE+0x360*2
        first,second=struct.unpack_from("<HH",exe,a)
        struct.pack_into("<HH",exe,a,second,first)
        result=probe(bytes(exe))
        self.assertEqual(result["state"],"layout_terminador_alternativo_estrutural")
        selected=result["selected"]
        self.assertEqual(len(selected["opponents"]),39)
        self.assertEqual(selected["opponents"][0],{"id":1,"nome":"OPP02"})
        self.assertEqual(selected["opponents"][1],{"id":2,"nome":"OPP01"})
        self.assertEqual(selected["opponents"][-1],{"id":39,"nome":"OPP39"})
        table=result["boundaryTerminatorEvidence"]
        self.assertEqual(table["candidateCount"],1)
        self.assertTrue(table["candidates"][0]["physicalOrderRemapped"])
        self.assertGreater(table["candidates"][0]["ordinalPointerInversions"],0)
        self.assertFalse(result["inGameVerified"])
        self.assertFalse(result["dropsVerified"])

    def test_all_39_unique_pointers_can_be_reversed_without_relabeling(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        base=SLUS_PTR_BASE+0x360*2
        values=struct.unpack_from("<"+"H"*39,exe,base)
        struct.pack_into("<"+"H"*39,exe,base,*reversed(values))
        result=probe(bytes(exe))
        self.assertEqual(result["state"],"layout_terminador_alternativo_estrutural")
        selected=result["selected"]
        self.assertEqual(selected["opponents"][0]["nome"],"OPP39")
        self.assertEqual(selected["opponents"][-1]["nome"],"OPP01")
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidates"][0]
                         ["ordinalPointerInversions"],38)
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidates"][0]
                         ["verifiedBoundaries"],38)
        self.assertFalse(result["inGameVerified"])

    def test_duplicate_physical_pointers_do_not_select_ids(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        a=SLUS_PTR_BASE+0x360*2
        struct.pack_into("<H",exe,a+2,struct.unpack_from("<H",exe,a)[0])
        result=probe(bytes(exe))
        self.assertIsNone(result["selected"])
        self.assertEqual(result["boundaryTerminatorEvidence"]["candidateCount"],0)
        compact=compact_opponent_evidence(result)
        self.assertIn(compact["forensicEvidence"]["windows"][0]
                      ["boundaryDecision"],
                      ("dados_apos_marcador", "ponteiro_intercalado"))
        self.assertEqual(compact["forensicEvidence"]["windows"][0]
                         ["pointerAliasCount"],1)
        self.assertFalse(compact["mayActivate"] if "mayActivate" in compact else False)

    def test_alternative_terminator_in_profile_preserves_drop_and_rank_gate(self):
        exe=relocated_opponents(terminator=0xfe)
        candidates=probe(exe)
        opponents=candidates["selected"]["opponents"]
        _,cards,_=decode_names(exe)
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            write_rows(folder/"cartas.csv",cards)
            write_rows(folder/"oponentes.csv",opponents)
            fake_drops=[]
            checks=[]
            for oid in range(1,40):
                for group in ("GRUPO_1","GRUPO_2","GRUPO_3"):
                    checks.append({"oponente_id":oid,"rank":group,"peso_total":2048})
                    fake_drops.append({"oponente_id":oid,"rank":group,
                                       "carta_id":1,"peso":2048})
            write_rows(folder/"validacao_pesos.csv",checks)
            write_rows(folder/"drops_por_oponente.csv",fake_drops)
            meta={"sha256":SHA,"opponent_identification":"extraidos_estruturalmente",
                  "independent_opponent_discovery":compact_opponent_evidence(candidates)}
            profile=analyse(folder,meta,folder/"gog_synthetic.iso")
            self.assertEqual(len(profile["opponents"]),39)
            self.assertEqual(profile["verified"]["oponentes"],"extraidos_estruturalmente")
            self.assertTrue(profile["supported_features"]["opponents"])
            self.assertFalse(profile["supported_features"]["drops"])
            self.assertFalse(profile["supported_features"]["ranks"])
            self.assertFalse(profile["supported_features"]["scoring"])
            self.assertEqual(profile["drops"],[])

    def test_revision_and_no_cross_mod_publish(self):
        self.assertGreaterEqual(SCAN_PARSER_REVISION,18)
        source=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf8")
        self.assertIn("discover_independent_opponents(",source)
        self.assertIn("oponentes_candidatos_nao_verificados.json",source)
        self.assertNotIn("drops=found_opponents",source)


if __name__=="__main__":
    unittest.main()
