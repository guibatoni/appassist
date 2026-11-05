"""Regressões para mods com recursos renomeados e imports parciais.

Não usa imagens comerciais. Dados sem confirmação de identidade nunca
viram drops ou RANKs verificados automaticamente.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_resource_selection import inspect_resource_candidates
from scanner_multiiso import process,SCAN_PARSER_REVISION
from importador_perfis import analyse


class ResourceDisc:
    def __init__(self,resources):
        self.resources=dict(resources)
        self.files={name:(30+i*100,len(data))
                    for i,(name,data) in enumerate(resources.items())}
        self.calls=[]
    def get(self,name,limit_bytes=None):
        self.calls.append(name)
        data=self.resources[name]
        return data if limit_bytes is None else data[:limit_bytes]


def decode_synthetic(raw):
    if raw.startswith(b"FULL"):
        return {"verificacao":[{"matrix":i} for i in range(117)],
                "drops":[{"card_id":1}]}, "117 full tables"
    return None,"invalid"


class ResourceSelectionTests(unittest.TestCase):
    def select(self,files,prefer=()):
        disc=ResourceDisc(files)
        return disc,inspect_resource_candidates(
            disc,list(files),decode_tables=decode_synthetic,
            preferred_names=prefer)

    def test_single_renamed_full_matrix_resource_is_selected_by_contents(self):
        disc,result=self.select({"DATA/MOD.PAK":b"FULL with matrices",
                                 "DATA/VDO.BIN":b"video unrecognized"})
        self.assertEqual(result["source"],"DATA/MOD.PAK")
        self.assertEqual(result["selected_bytes"],b"FULL with matrices")
        self.assertEqual(result["method"],"117_matrizes_compativeis")
        self.assertFalse(result["validatedIdentity"])
        self.assertFalse(result["dropsVerified"])
        self.assertEqual(result["candidates"][0]["state"],
                         "matrizes_117_plausiveis")
        self.assertEqual(len(disc.calls),3)

    def test_two_distinct_full_matrix_resources_are_never_assigned(self):
        _,out=self.select({"DATA/ONE.DAT":b"FULL 111",
                           "DATA/TWO.DAT":b"FULL 222"})
        self.assertEqual(out["state"],"matrizes_ambiguas")
        self.assertIsNone(out["source"])
        self.assertEqual(out["selected_bytes"],b"")

    def test_two_identical_resource_copies_are_same_candidate(self):
        _,out=self.select({"DATA/A.MRG":b"FULL SAME",
                           "DATA/B.MRG":b"FULL SAME"},
                          prefer=("DATA/B.MRG",))
        self.assertEqual(out["source"],"DATA/B.MRG")
        self.assertEqual(out["method"],"117_matrizes_compativeis")

    def test_unique_relocated_layout_chooses_renamed_container_by_content(self):
        disc=ResourceDisc({
            "GOG/MOVED.DAT":b"RELOC defined weights",
            "GOG/VIDEO.DAT":b"opaque movie"}
        )
        def discovery(data):
            if data.startswith(b"RELOC"):
                return {"state":"layout_candidato_unico",
                        "selected":{"opponentBase":123456,
                                    "opponentStep":6144,"rankStride":1460}}
            return {"state":"nao_encontrado","selected":None}
        out=inspect_resource_candidates(
            disc,list(disc.files),decode_tables=decode_synthetic,
            discover_relocated=discovery)
        self.assertEqual(out["source"],"GOG/MOVED.DAT")
        self.assertEqual(out["method"],"117_matrizes_compativeis")
        self.assertEqual(out["selectedLayout"]["opponentBase"],123456)
        self.assertFalse(out["dropsVerified"])
        self.assertEqual(out["candidates"][0]["state"],
                         "matrizes_117_realocadas_plausiveis")

    def test_single_unnamed_fallback_is_not_considered_verified(self):
        _,out=self.select({"GOSD/UNKNOWN.1":b"unknown mod payload"})
        self.assertEqual(out["source"],"GOSD/UNKNOWN.1")
        self.assertEqual(out["state"],"recurso_candidato_nao_validado")
        self.assertFalse(out["validatedIdentity"])
        self.assertFalse(out["dropsVerified"])

    def test_ambiguous_unknown_resources_fail_closed(self):
        _,out=self.select({"A.PAK":b"alpha","B.PAK":b"beta"})
        self.assertIsNone(out["source"])
        self.assertEqual(out["state"],"recursos_ambiguos_ou_incompativeis")

    def test_preferred_named_file_only_fallback_when_no_structural_match(self):
        _,out=self.select({"DATA/WA_MRG.MRG":b"unknown WA",
                           "DATA/MOVIE.DAT":b"movie contents"},
                          prefer=("DATA/WA_MRG.MRG",))
        self.assertEqual(out["source"],"DATA/WA_MRG.MRG")
        self.assertEqual(out["method"],"nome_convencional_sem_matrizes")
        self.assertFalse(out["dropsVerified"])

    def test_truncated_candidates_and_capacity_limit_do_not_promote(self):
        disc=ResourceDisc({"TRUNCATED.PAK":b"FULL payload"})
        disc.files["TRUNCATED.PAK"]=(20,2500)
        data=inspect_resource_candidates(disc,["TRUNCATED.PAK"],
                                         decode_tables=decode_synthetic)
        self.assertEqual(data["candidates"][0]["state"],"leitura_incompleta")
        self.assertIsNone(data["source"])
        too_many={f"X{i}.PAK":b"FULL" for i in range(7)}
        _,result=self.select(too_many)
        self.assertTrue(result["limitReached"])
        self.assertIsNone(result["source"])

    def test_mutation_during_second_read_prevents_selection(self):
        disc=ResourceDisc({"ONE.PAK":b"FULL initial"})
        original=disc.get
        count={"n":0}
        def mutated(name,limit_bytes=None):
            count["n"]+=1
            return b"FULL changed" if count["n"]>=2 else original(name,limit_bytes)
        disc.get=mutated
        out=inspect_resource_candidates(disc,["ONE.PAK"],decode_tables=decode_synthetic)
        self.assertEqual(out["state"],"recurso_alterado_durante_leitura")
        self.assertIsNone(out["source"])


class PartialScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.iso=self.root/"unknown.iso"
        self.iso.write_bytes(b"synthetic placeholder")
        self.output=self.root/"out"
        self.output.mkdir()

    def scan(self,files,*,decoder=None):
        class FakeDisc:
            sector=2048
            geometry="iso2048"
            def __init__(self,path):
                self.files=files
            def get(self,name,limit_bytes=None):
                return b"synthetic.exe"
            def close(self): pass
        fake_discovery={"executables":[],"resources":[],"validated":False}
        with patch("scanner_multiiso.Disc",FakeDisc),\
             patch("scanner_multiiso.inspect_system_cnf",
                   return_value={"boot_target":None}),\
             patch("scanner_multiiso.inspect_file_signatures",return_value=[]),\
             patch("scanner_multiiso.discover_disc_layout",
                   return_value=fake_discovery):
            if decoder is None:
                return process(self.iso,self.output,digest="a"*64)
            with patch("scanner_multiiso.decode_names",return_value=decoder):
                return process(self.iso,self.output,digest="a"*64)

    def test_valid_exe_names_are_kept_when_no_wa_exists(self):
        cards=[{"id":i,"nome":f"Card {i}","atk":1000,"def":800,
                "tipo":3,"nivel":4,"atributo":1,"estrela_1":2,
                "estrela_2":5} for i in range(1,723)]
        opponents=[{"id":i,"nome":f"Opponent {i}"} for i in range(1,40)]
        result=self.scan({"DATA/SLUS_014.11":(50,2_000_000)},
                         decoder=(opponents,cards,"722/722"))
        self.assertIn("parcial:",result["status"])
        self.assertEqual(result["oponentes"],39)
        self.assertEqual(result["cartas"],722)
        self.assertEqual(result["wa_total_bytes"],0)
        self.assertIsNone(result["hash_wa"])
        self.assertFalse(result["wa_lido_integralmente"])
        self.assertEqual(result["wa_resource_selection"]["state"],"sem_recurso")
        extracted=Path(result["resultado_dir"])
        self.assertTrue((extracted/"cartas.csv").is_file())
        profile=analyse(extracted,result,self.iso)
        self.assertTrue(profile["supported_features"]["cards"])
        self.assertTrue(profile["supported_features"]["opponents"])
        self.assertFalse(profile["supported_features"]["drops"])
        self.assertFalse(profile["supported_features"]["art"])
        self.assertFalse(profile["supported_features"]["ranks"])

    def test_even_when_no_exe_and_no_wa_scan_keeps_inventory(self):
        result=self.scan({"README.TXT":(20,600)})
        self.assertIn("incerto:",result["status"])
        self.assertNotIn("problema",result)
        self.assertIsNone(result["executavel"])
        self.assertIsNone(result["hash_executavel"])
        self.assertEqual(result["wa_total_bytes"],0)
        self.assertTrue(result["executavel_status"].startswith("Nenhum executável"))
        self.assertEqual(result["scan_parser_revision"],SCAN_PARSER_REVISION)
        self.assertTrue((Path(result["resultado_dir"])/"relatorio.json").is_file())


if __name__=="__main__":
    unittest.main()
