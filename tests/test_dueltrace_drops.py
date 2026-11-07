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
        "verified":{"tabelas_drops":"verificado","oponentes":"verificado","cartas":"verificado",
                    "nomes_dos_ranks":"verificado" if sha==X15_SHA else "não_identificado"},
        "supported_features":{"drops":True,"cards":True},
        "drop_group_labels":groups,
        "opponents":[{"id":i,"name":f"Oponente {i}"} for i in range(1,40)],
        "cards":[{"id":i,"name":f"Carta {i}","atk":(i%51)*100,"def":(i%51)*50}
                 for i in range(1,723)],
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

    def test_card_references_and_iso_provenance_cannot_be_silently_replaced(self):
        p=fake_profile()
        p["cards"].pop()
        p["drops"][0]["card_id"]=722  # In the format range but absent from this catalogue.
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["cards"].append(dict(p["cards"][0]))
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["drops_provenance"]={"rom_sha256":"b"*64}
        self.assertFalse(get_drop_catalog(p)["available"])
        p["drops_provenance"]["rom_sha256"]=p["rom_sha256"]
        self.assertTrue(get_drop_catalog(p)["available"])

    def test_complete_verified_catalogue_is_required_even_for_unreferenced_cards(self):
        p=fake_profile()
        self.assertTrue(get_drop_catalog(p)["available"])  # Legacy complete profile, no new provenance field.
        p["cards"].pop()  # Card 722 has no drop row, but the catalogue is incomplete.
        self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["cards"]=p["cards"][:1]
        for row in p["drops"]:
            row["card_id"]=1
        self.assertFalse(get_drop_catalog(p)["available"])
        for verification in (None,"pendente",False):
            p=fake_profile()
            if verification is None:
                del p["verified"]["cartas"]
            else:
                p["verified"]["cartas"]=verification
            self.assertFalse(get_drop_catalog(p)["available"])
        p=fake_profile()
        p["supported_features"]["cards"]=False
        self.assertFalse(get_drop_catalog(p)["available"])

    def test_card_sources_use_exact_id_and_return_all_117_rows(self):
        from dueltrace_drops import get_card_drop_sources
        p=fake_profile()
        for record in p["drops"]:
            record["card_id"]=1
        p["cards"][11]["name"]="Carta 1 falsa com ID 12"
        result=get_card_drop_sources(p,1)
        self.assertTrue(result["available"])
        self.assertEqual(result["total"],117)
        self.assertEqual(len(result["rows"]),117)
        self.assertTrue(all(r["cardId"]==1 for r in result["rows"]))
        self.assertEqual(result["romSha"],p["rom_sha256"])
        self.assertEqual(get_card_drop_sources(p,12)["total"],0)

    def test_card_sources_do_not_promote_unverified_or_foreign_iso(self):
        from dueltrace_drops import get_card_drop_sources
        p=fake_profile()
        self.assertEqual(get_card_drop_sources(p,2)["total"],39)
        p["drops_provenance"]={"rom_sha256":"b"*64}
        self.assertFalse(get_card_drop_sources(p,2)["available"])
        p=fake_profile()
        p["supported_features"]["drops"]=False
        self.assertFalse(get_card_drop_sources(p,2)["available"])
        for bad in (-1,0,723,True,1.2,"2"):
            with self.subTest(card_id=bad),self.assertRaises(ValueError):
                get_card_drop_sources(p,bad)

    def test_malicious_or_bad_filter_rejected(self):
        p=fake_profile()
        for oid in (-1,40,1.2,True):
            with self.subTest(oid=oid), self.assertRaises(ValueError):
                get_drop_catalog(p,opponent_id=oid)
        for kw in ({"offset":-1},{"limit":0},{"query":"x"*101},
                   {"group":"UNKNOWN"},{"limit":True}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                get_drop_catalog(p,**kw)

    def test_alpha_reward_catalogue_is_separate_from_verified_profiles(self):
        p=fake_profile()
        p["supported_features"]["drops"]=False
        p["verified"]["tabelas_drops"]="pendente"
        p["verified"]["oponentes"]="pendente"
        self.assertFalse(get_drop_catalog(p)["available"])
        p["alpha_discovery"]={
            "state":"retail_sentinel_39_reward_records",
            "source":"local_iso_sha256_matched",
            "rom_sha256":p["rom_sha256"],
        }
        candidate=get_drop_catalog(p,opponent_id=1,rank="S-POW")
        self.assertTrue(candidate["available"])
        self.assertTrue(candidate["provisional"])
        self.assertEqual(candidate["rows"][0]["opponentId"],1)
        self.assertFalse(candidate["opponentMappingVerified"])
        self.assertFalse(candidate["rankLabelsVerified"])
        self.assertFalse(candidate["mayActivateDrops"])
        from dueltrace_drops import get_card_drop_sources
        sources=get_card_drop_sources(p,1)
        self.assertTrue(sources["available"])
        self.assertTrue(sources["provisional"])
        p["alpha_discovery"]["rom_sha256"]="f"*64
        self.assertFalse(get_drop_catalog(p)["available"])
        p["alpha_discovery"]["rom_sha256"]=p["rom_sha256"]
        p["verified"]["cartas"]="pendente"
        self.assertFalse(get_drop_catalog(p)["available"])

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
