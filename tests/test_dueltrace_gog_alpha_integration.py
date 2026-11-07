"""Regression: source-bound GOG-style 40-record scan in Alpha Windows UI.

No real game bytes or emulator required. The physical ISO's full SHA check
and its indexed renamed resource are simulated under a private test folder.
"""
from __future__ import annotations
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from auto_mods import ModCatalog, atomic_json
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_iso_layout_hints import recover_scan_resource

BLOCK=0x1800
STRIDE=0x5B4

def weight(seed):
    words=[0]*722
    for i,v in enumerate((128,896,1024)):
        words[(seed+i*15)%722]=v
    return struct.pack("<722H",*words)+bytes(16)

def record(seed):
    return b"".join(weight(seed+i*7) for i in range(4))+bytes(200)+b"\xff"*104


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.sha="a"*64
        self.source=self.home/"GOG MOD 2.2.iso"
        self.source.write_bytes(b"temporary synthetic ISO container"*100)
        self.first=2048*4
        self.wa=b"\0"*self.first+b"".join(record(i*7+4) for i in range(40))
        self.wa_name="G0SD/GOG_SD1.23"
        self.family={
            "schema":1,"state":"single_family_unmapped_windows",
            "candidateCount":2,"scanComplete":True,
            "clusters":[{"firstBlockOffset":self.first,
                         "consecutiveBlockCount":40,
                         "possible39BlockWindows":2,
                         "opponentStep":BLOCK,
                         "matrixStride":STRIDE,
                         "encoding":"plain","runCapReached":False}],
        }
        self.scan_dir=self.home/"analises"/"synthetic"
        self.scan_dir.mkdir(parents=True)
        atomic_json(self.scan_dir/"relatorio.json",{
            "sha256":self.sha,"mod_family_evidence":self.family,
            "wa_resource_selection":{"source":self.wa_name},
        })
        self.profile={
            "rom_sha256":self.sha,"scan_result_dir":str(self.scan_dir),
            "verified":{"cartas":"verificado","oponentes":"extraidos_estruturalmente",
                        "tabelas_drops":"pendente"},
            "supported_features":{"cards":True,"opponents":True,
                                  "drops":False,"fusions":False},
            "cards":[{"id":i,"name":f"Card {i}"} for i in range(1,723)],
            "opponents":[{"id":i,"name":f"Opponent {i}"} for i in range(1,40)],
            "fusion_recipes":[],
        }
        folder=self.home/"profiles"/self.sha[:16]
        folder.mkdir(parents=True)
        self.profile_file=folder/"profile.json"
        atomic_json(self.profile_file,self.profile)
        self.entry={"sha256":self.sha,"source_path":str(self.source),
                    "profile_path":str(self.profile_file),
                    "file_name":"GOG MOD 2.2.iso"}
        self.catalog=ModCatalog(self.home)
        atomic_json(self.catalog.registry_file,{"entries":[self.entry]})
        atomic_json(self.catalog.active_file,{"sha256":self.sha})
        self.bridge=DueltraceWebBridge(self.catalog,ram_reader=lambda **kwargs:{"ready":False})

    def test_renamed_source_bound_40_block_works_for_drops_and_fusions(self):
        wa=self.wa
        name=self.wa_name
        class MockDisc:
            def __init__(self,p):
                self.files={name:(1,len(wa))}
            def get(self,p,limit_bytes=None):
                if p!=name:raise KeyError(p)
                return wa[:limit_bytes] if limit_bytes else wa
            def close(self):pass
        report={
            "valid_banks":7,"matching_banks":7,"divergent_banks":False,
            "candidates":[{"a":1,"b":2,"result":3}],
        }
        with patch("scanner_multiiso.sha256",return_value=self.sha),\
             patch("scanner_multiiso.Disc",MockDisc),\
             patch("extrator_fusoes.analyze_fusion_banks",return_value=report) as fusion:
            candidate=self.bridge.get_alpha_discovery(self.sha)
            self.assertTrue(candidate["available"])
            self.assertEqual(candidate["dropCandidates"],39*3*3)
            self.assertEqual(candidate["fusionCandidates"],1)
            self.assertEqual(candidate["candidateMode"],
                             "40_block_retail_mapping_hypothesis")
            self.assertFalse(candidate["mayActivateDrops"])
            page=self.bridge.get_drops(opponent_id=1,rank="S-POW")
            self.assertTrue(page["available"])
            self.assertTrue(page["provisional"])
            self.assertEqual(page["total"],3)
            self.assertTrue(all(r["opponentId"]==1 for r in page["rows"]))
            self.assertFalse(page["opponentMappingVerified"])
            library=self.bridge.get_fusions()
            self.assertEqual(library["total"],1)
            self.assertTrue(library["provisional"])
        fusion.assert_called_once()
        self.assertEqual(fusion.call_args.kwargs["resource_name"],name)
        unchanged=self.catalog.profile_for(self.entry)
        self.assertFalse(unchanged["supported_features"]["drops"])
        self.assertFalse(unchanged["supported_features"]["fusions"])
        self.assertEqual(unchanged["verified"]["tabelas_drops"],"pendente")

    def test_scan_hints_rejected_for_foreign_sha_and_ambiguous_resource(self):
        self.assertIsNotNone(recover_scan_resource(
            self.home,self.profile,self.sha,{self.wa_name:(1,len(self.wa))}))
        self.assertIsNone(recover_scan_resource(
            self.home,self.profile,"b"*64,{self.wa_name:(1,len(self.wa))}))
        self.assertIsNone(recover_scan_resource(
            self.home,self.profile,self.sha,{"OTHER.MRG":(1,len(self.wa))}))
        meta={"sha256":self.sha,
              "mod_family_audit":{"resourcesScanned":[
                  {"resource":"A.MRG","weightFamily":self.family},
                  {"resource":"B.MRG","weightFamily":self.family},
              ]}}
        atomic_json(self.scan_dir/"relatorio.json",meta)
        self.assertIsNone(recover_scan_resource(
            self.home,self.profile,self.sha,{"A.MRG":(1,len(self.wa)),
                                             "B.MRG":(2,len(self.wa))}))


if __name__=="__main__":
    unittest.main()
