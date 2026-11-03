"""Regressões do catálogo Drops com 117 tabelas sintéticas e sem ISOs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_drops import get_drop_catalog
from scanner_multiiso import X15_SHA


def fake_profile(sha="a"*64, groups=None):
    if groups is None:
        groups=["TABELA_1_RANK_DESCONHECIDO","TABELA_2_RANK_DESCONHECIDO",
                "TABELA_3_RANK_DESCONHECIDO"]
    drops=[]
    for oid in range(1,40):
        for index,group in enumerate(groups):
            # Cada tabela possui uma carta distinta com peso total 2048.
            drops.append({"opponent_id":oid,"group":group,
                          "card_id":index+1,"weight":2048,
                          "source_offset":0xE9B000+(oid-1)*0x1800+(index+1)*0x5B4})
    return {
        "rom_sha256":sha,
        "verified":{"tabelas_drops":"verificado","oponentes":"verificado",
                    "nomes_dos_ranks":"verificado" if sha==X15_SHA else "não_identificado"},
        "supported_features":{"drops":True},
        "drop_group_labels":groups,
        "opponents":[{"id":i,"name":f"Oponente {i}"} for i in range(1,40)],
        "cards":[{"id":i,"name":f"Carta {i}","atk":i*100,"def":i*50}
                 for i in range(1,4)],
        "drops":drops,
        "rank_points":{"available":False,"rules":{}},
    }


class DropCatalogTests(unittest.TestCase):
    def test_validated_117_tables_and_fair_probabilities(self):
        p=fake_profile()
        result=get_drop_catalog(p)
        self.assertTrue(result["available"])
        self.assertEqual(result["total"],117)
        self.assertEqual(len(result["opponents"]),39)
        self.assertEqual(len(result["groups"]),3)
        self.assertFalse(result["rankLabelsVerified"])
        self.assertEqual(result["rows"][0]["weight"],2048)
        self.assertEqual(result["rows"][0]["chancePercent"],100.0)
        self.assertEqual(result["rows"][0]["sourceOffset"],"0xE9B5B4")

    def test_paginate_and_filter_without_mixing_opponents(self):
        p=fake_profile()
        r=get_drop_catalog(p,opponent_id=3,group=p["drop_group_labels"][1])
        self.assertTrue(r["available"])
        self.assertEqual(r["total"],1)
        self.assertEqual(r["rows"][0]["opponentId"],3)
        self.assertEqual(r["rows"][0]["cardName"],"Carta 2")
        self.assertEqual(get_drop_catalog(p,query="Carta 3")["total"],39)
        self.assertEqual(get_drop_catalog(p,query="2")["total"],39)
        self.assertEqual(len(get_drop_catalog(p,offset=100,limit=10)["rows"]),10)

    def test_correct_known_rank_labels_only_for_matching_sha(self):
        p=fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"])
        self.assertTrue(get_drop_catalog(p)["rankLabelsVerified"])
        p["rom_sha256"]="a"*64
        self.assertFalse(get_drop_catalog(p)["rankLabelsVerified"])

    def test_modified_weight_and_duplicate_do_not_show_false_probs(self):
        p=fake_profile()
        p["drops"][0]["weight"]=2047
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["drops"].append(dict(p["drops"][0]))
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["drops"].pop()
        self.assertFalse(get_drop_catalog(p)["available"])

    def test_malicious_or_bad_filter_rejected(self):
        p=fake_profile()
        for oid in (-1,40,1.2,True):
            with self.subTest(oid=oid), self.assertRaises(ValueError):
                get_drop_catalog(p,opponent_id=oid)
        for kw in ({"offset":-1},{"limit":0},{"query":"x"*101},
                   {"group":"UNKNOWN"},{"limit":True}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                get_drop_catalog(p,**kw)

    def test_unverified_profile_never_displays_drops(self):
        p=fake_profile()
        p["supported_features"]["drops"]=False
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["verified"]["tabelas_drops"]="pendente"
        self.assertFalse(get_drop_catalog(p)["available"])
        self.assertFalse(get_drop_catalog(None)["available"])


if __name__=="__main__":
    unittest.main()
