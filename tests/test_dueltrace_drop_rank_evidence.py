"""Validação de banco de drops, filtro e correspondência com resultados reais."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_library_sort import validate_sort,sort_key,matches_type
from dueltrace_drop_rank_evidence import rank_drop_report
from test_dueltrace_drops import fake_profile
from scanner_multiiso import X15_SHA


def entry(profile,opp,group,card,weight=2048):
    return {"opponent_id":opp,"group":group,"card_id":card,
            "weight":weight,"source_offset":0xE9B000+opp*0x1800}


def observed(profile,opp,card,rank,duel):
    return {"rom_sha256":profile["rom_sha256"],"opponent_id":opp,
            "card_id":card,"observed_rank":rank,"duel_id":duel}


class DropRankEvidenceTests(unittest.TestCase):
    def test_unknown_mod_infers_only_from_exclusive_drops_multiple_opponents(self):
        p=fake_profile()
        obs=[observed(p,1,1,"S-POW","duel_a001"),
             observed(p,2,1,"A-POW","duel_b002")]
        r=rank_drop_report(p,obs)
        self.assertEqual(r["status"],"manual_corroboration")
        self.assertEqual(r["rankMappings"]["A-POW"]["status"],"layout_original_presumido")
        self.assertEqual(
            r["suspectedMappings"]["S/A POW"]["group"],
            "TABELA_1_RANK_DESCONHECIDO")
        self.assertEqual(r["usable"],2)
        self.assertIn("registros fornecidos",r["note"])

    def test_single_opponent_is_not_enough_and_duplicate_duel_ignored(self):
        p=fake_profile()
        r=rank_drop_report(p,[observed(p,1,1,"S-POW","duel_a001"),
                              observed(p,1,1,"S-POW","duel_a001")])
        self.assertEqual(r["observations"],1)
        self.assertEqual(r["suspectedMappings"],{})

    def test_shared_card_group_is_ambiguous_not_mapped(self):
        p=fake_profile()
        for oid in range(1,40):
            first=next(x for x in p["drops"] if x["opponent_id"]==oid and
                       x["group"]==p["drop_group_labels"][0])
            second=next(x for x in p["drops"] if x["opponent_id"]==oid and
                        x["group"]==p["drop_group_labels"][1])
            first["weight"]=1024
            second["weight"]=1024
            p["drops"].append(entry(p,oid,p["drop_group_labels"][0],2,1024))
            p["drops"].append(entry(p,oid,p["drop_group_labels"][1],1,1024))
        obs=[observed(p,1,1,"S-POW","duel_a001"),
             observed(p,2,1,"S-POW","duel_b002")]
        r=rank_drop_report(p,obs)
        self.assertEqual(r["ambiguous"],2)
        self.assertEqual(r["suspectedMappings"],{})

    def test_impossible_reward_flagged_for_known_sha(self):
        p=fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"])
        r=rank_drop_report(p,[observed(p,1,2,"Z-POW","duel_a001")])
        self.assertEqual(r["status"],"mismatch")
        self.assertEqual(r["inconsistent"],1)
        self.assertEqual(r["rankMappings"]["Z-POW"]["group"],"Z-POW")
        self.assertEqual(r["mappingConsistency"],"inconsistent_known_mapping")

    def test_known_x15_sha_remains_unique_without_manual_observations(self):
        p=fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"])
        result=rank_drop_report(p,[])
        self.assertEqual(result["assignmentCount"],1)
        self.assertEqual(result["possibleGroups"]["Z-POW"],["Z-POW"])
        self.assertEqual(result["mappingConsistency"],"identidade_sha_conhecida")

    def test_actual_lp_scores_compare_but_never_claim_mips_proof(self):
        p=fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"])
        first=observed(p,1,1,"Z-POW","duel_a001")
        second=observed(p,2,1,"Z-POW","duel_b002")
        for row in (first,second):
            row.update({
                "victory_type":"lp","observed_points":95,
                "rank_snapshot":{"projected_score":95,"projected_rank":"Z-POW"},
            })
        report=rank_drop_report(p,[first,second])
        self.assertEqual(report["scoreComparisons"]["exact"],2)
        self.assertEqual(report["scoreComparisons"]["status"],"duelos_coerentes_sem_prova_mips")
        second["observed_points"]=90
        report=rank_drop_report(p,[first,second])
        self.assertEqual(report["scoreComparisons"]["different"],1)
        self.assertEqual(report["scoreComparisons"]["status"],"divergencia_modelo")
        second["victory_type"]="deckout"
        report=rank_drop_report(p,[first,second])
        self.assertEqual(report["scoreComparisons"]["compared"],1)

    def test_bad_profile_or_cross_sha_is_never_mapped(self):
        p=fake_profile()
        different=observed(p,1,1,"Z-POW","duel_a001")
        different["rom_sha256"]="e"*64
        r=rank_drop_report(p,[different])
        self.assertEqual(r["observations"],0)
        p["drops"].pop()
        self.assertEqual(rank_drop_report(p,[])["status"],"unavailable")

    def test_sort_and_exact_type_before_pagination(self):
        from dueltrace_drops import get_drop_catalog
        p=fake_profile()
        p["cards"][0].update({"name":"Zebra","atk":500,"def":100,"type_label":"Dragão","category":"Monstros"})
        p["cards"][1].update({"name":"Abelha","atk":300,"def":800,"type_label":"Fada","category":"Monstros"})
        p["cards"][2].update({"name":"Lua","atk":100,"def":300,"type_label":"Fada","category":"Monstros"})
        sorted_atk=get_drop_catalog(p,sort="atk",limit=1)
        self.assertEqual(sorted_atk["rows"][0]["cardId"],1)
        sorted_def=get_drop_catalog(p,sort="def",limit=1)
        self.assertEqual(sorted_def["rows"][0]["cardId"],2)
        alphabetical=get_drop_catalog(p,sort="name",limit=1)
        self.assertEqual(alphabetical["rows"][0]["cardId"],2)
        typed=get_drop_catalog(p,card_type="Fada",sort="atk",limit=10)
        self.assertTrue(typed["available"])
        self.assertEqual(typed["total"],78)
        self.assertTrue(all(x["cardType"]=="Fada" for x in typed["rows"]))
        self.assertIn("Fada",typed["cardTypes"])
        with self.assertRaises(ValueError):
            get_drop_catalog(p,sort="__proto__")
        with self.assertRaises(ValueError):
            get_drop_catalog(p,card_type="\x00script")


if __name__=="__main__":
    unittest.main()
