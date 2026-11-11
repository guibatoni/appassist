"""Regressões: RANK do duelo não é a mesma coisa que banco de drops WA."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_system import (
    X15_RANKS, CLASSIC_RANKS, CLASSIC_POOLS, CLASSIC_DROP_FILTERS,
    drop_filter_ranks, pool_index_for_drop_filter, pool_index_for_rank,
    classic_rank_for_verified_score, x15_rank_for_verified_score,
)
from dueltrace_rank_system import rank_label_for_existing_score
from dueltrace_drops import get_drop_catalog
from dueltrace_rank_drop_solver import solve_rank_drop_labels
from test_dueltrace_drops import fake_profile
from scanner_multiiso import X15_SHA


class RankSystemTests(unittest.TestCase):
    def test_classic_ten_rank_order_is_exact(self):
        self.assertEqual(CLASSIC_RANKS,(
            "S-POW","A-POW","B-POW","C-POW","D-POW",
            "D-TEC","C-TEC","B-TEC","A-TEC","S-TEC",
        ))
        self.assertEqual(CLASSIC_POOLS,("S/A POW","B/C/D POW/TEC","S/A TEC"))
        self.assertEqual([pool_index_for_rank("a"*64,r) for r in CLASSIC_RANKS],
                         [0,0,1,1,1,1,1,1,2,2])
        self.assertEqual([pool_index_for_rank(X15_SHA,r) for r in X15_RANKS],
                         [0,1,2])

    def test_legacy_unknown_group_names_display_standard_without_rescan(self):
        p=fake_profile()
        result=get_drop_catalog(p)
        self.assertEqual(result["rankSystem"],"classic")
        self.assertEqual(result["rankOptions"],list(CLASSIC_DROP_FILTERS))
        self.assertEqual([x["label"] for x in result["groupOptions"]],list(CLASSIC_POOLS))
        self.assertEqual([x["groupLabel"] for x in result["rows"][:3]],["S/A POW","B/C/D POW/TEC","S/A TEC"])
        self.assertFalse(result["rankLabelsVerified"])
        self.assertIn("deve ser conferido em duelo",result["status"])

    def test_original_rank_filter_uses_exact_WA_bank_not_fabricated_ten_tables(self):
        p=fake_profile()
        pool_rank_sets={
            0:("S-POW","A-POW"),
            1:("B-POW","C-POW","D-POW","D-TEC","C-TEC","B-TEC"),
            2:("A-TEC","S-TEC"),
        }
        for pool,rank_list in pool_rank_sets.items():
            for rank in rank_list:
                with self.subTest(rank=rank):
                    result=get_drop_catalog(p,rank=rank)
                    self.assertTrue(result["available"])
                    self.assertEqual(result["total"],39)
                    self.assertEqual(result["rankSelected"],rank)
                    self.assertTrue(all(row["group"]==p["drop_group_labels"][pool]
                                        for row in result["rows"]))
                    self.assertTrue(all(rank in row["eligibleRanks"]
                                        for row in result["rows"]))
                    self.assertEqual(result["rows"][0]["groupLabel"],CLASSIC_POOLS[pool])
        self.assertEqual(get_drop_catalog(p)["total"],117)

    def test_bcd_pow_tec_are_two_dropdown_choices_for_one_real_drop_pool(self):
        sha="a"*64
        p=fake_profile(sha)
        expected=("S-POW","A-POW","BCD-POW","BCD-TEC","A-TEC","S-TEC")
        self.assertEqual(CLASSIC_DROP_FILTERS,expected)
        self.assertEqual(drop_filter_ranks(sha),expected)
        self.assertEqual(drop_filter_ranks(X15_SHA),X15_RANKS)
        original_scores=("B-POW","C-POW","D-POW",
                         "D-TEC","C-TEC","B-TEC")
        self.assertTrue(all(x in CLASSIC_RANKS for x in original_scores))
        self.assertTrue(all(x not in expected for x in original_scores))
        for choice in ("BCD-POW","BCD-TEC"):
            with self.subTest(choice=choice):
                self.assertEqual(pool_index_for_drop_filter(sha,choice),1)
                data=get_drop_catalog(p,rank=choice)
                self.assertEqual(data["rankOptions"],list(expected))
                self.assertEqual(data["rankSelected"],choice)
                self.assertTrue(data["available"])
                self.assertEqual(data["total"],39)
                self.assertTrue(all(
                    r["group"]==p["drop_group_labels"][1] for r in data["rows"]))
                self.assertEqual(data["rows"][0]["groupLabel"],"B/C/D POW/TEC")
                self.assertEqual(data["rows"][0]["eligibleRanks"],
                                 list(original_scores))
        # They are separate menu choices, NOT new physical tables/probabilities.
        self.assertEqual(
            get_drop_catalog(p,rank="BCD-POW")["rows"],
            get_drop_catalog(p,rank="BCD-TEC")["rows"])
        # Old programmatic requests remain valid; the underlying score engine
        # still computes all ten actual ranks individually.
        for rank in original_scores:
            self.assertEqual(pool_index_for_drop_filter(sha,rank),1)
            self.assertEqual(get_drop_catalog(p,rank=rank)["total"],39)
        with self.assertRaises(ValueError):
            get_drop_catalog(p,rank="BCD-RANK")
        with self.assertRaises(ValueError):
            get_drop_catalog(fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"]),
                             rank="BCD-POW")
        with self.assertRaises(ValueError):
            pool_index_for_drop_filter(X15_SHA,"BCD-TEC")

    def test_x15_only_its_three_ranks_and_original_scores_not_reused(self):
        p=fake_profile(X15_SHA,["Z-POW","S-POW","S-TEC"])
        result=get_drop_catalog(p)
        self.assertEqual(result["rankSystem"],"x15")
        self.assertEqual(result["rankOptions"],list(X15_RANKS))
        self.assertTrue(result["rankLabelsVerified"])
        self.assertEqual(get_drop_catalog(p,rank="Z-POW")["total"],39)
        self.assertEqual(get_drop_catalog(p,rank="S-TEC")["rows"][0]["group"],"S-TEC")
        with self.assertRaises(ValueError):
            get_drop_catalog(p,rank="A-POW")
        with self.assertRaises(ValueError):
            get_drop_catalog(fake_profile(),rank="Z-POW")
        with self.assertRaises(ValueError):
            get_drop_catalog(fake_profile(),rank="S-POW",group="TABELA_2_RANK_DESCONHECIDO")

    def test_malformed_rank_observation_does_not_crash_solver(self):
        sha="a"*64
        groups=list(CLASSIC_POOLS)
        wa={1:{pool:set() for pool in groups}}
        report=solve_rank_drop_labels(
            groups,wa,[{
                "rom_sha256":sha,"duel_id":"duel-a0001",
                "opponent_id":1,"card_id":9,"observed_rank":["S-POW"],
            }],sha,labels=groups,
            rank_to_label={"S-POW":"S/A POW"})
        self.assertEqual(report["distinctDuels"],0)
        self.assertFalse(report["executionVerified"])

    def test_only_rank_letter_changes_for_same_existing_points(self):
        # O cálculo numérico continua sendo o do motor atual.
        for score,classic,x15 in (
            (95,"S-POW","Z-POW"),
            (85,"A-POW","S-POW"),
            (68,"C-POW","S-POW"),
            (50,"D-POW","S-POW"),
            (49,"D-TEC","S-TEC"),
            (0,"S-TEC","S-TEC"),
            (101,"S-POW","Z-POW"),
            (-12,"S-TEC","S-TEC"),
        ):
            with self.subTest(score=score):
                self.assertEqual(rank_label_for_existing_score("a"*64,score),classic)
                self.assertEqual(rank_label_for_existing_score(X15_SHA,score),x15)
        for wrong in (None,True,False,85.5,"85",10**9):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValueError):
                    rank_label_for_existing_score(X15_SHA,wrong)

    def test_score_labels_only_for_independently_observed_result(self):
        for score,label in (
            (99,"S-POW"),(90,"S-POW"),(89,"A-POW"),(80,"A-POW"),
            (79,"B-POW"),(70,"B-POW"),(69,"C-POW"),(60,"C-POW"),
            (59,"D-POW"),(50,"D-POW"),(49,"D-TEC"),(40,"D-TEC"),
            (39,"C-TEC"),(30,"C-TEC"),(29,"B-TEC"),(20,"B-TEC"),
            (19,"A-TEC"),(10,"A-TEC"),(9,"S-TEC"),(0,"S-TEC"),
        ):
            self.assertEqual(classic_rank_for_verified_score(score),label)
        for invalid in (100,-1,1000,55.5,"90"):
            with self.assertRaises(ValueError):
                classic_rank_for_verified_score(invalid)
        self.assertEqual(x15_rank_for_verified_score(95),"Z-POW")
        self.assertEqual(x15_rank_for_verified_score(94),"S-POW")
        self.assertEqual(x15_rank_for_verified_score(49),"S-TEC")

    def test_solver_understands_two_original_ranks_sharing_one_pool(self):
        sha="a"*64
        groups=list(CLASSIC_POOLS)
        wa={i:{groups[0]:{1},groups[1]:{2},groups[2]:{3}} for i in range(1,40)}
        obs=[{"rom_sha256":sha,"duel_id":"duel-classic-a1","opponent_id":1,
              "card_id":1,"observed_rank":"S-POW"},
             {"rom_sha256":sha,"duel_id":"duel-classic-b2","opponent_id":2,
              "card_id":1,"observed_rank":"A-POW"}]
        rank_to_pool={r:groups[pool_index_for_rank(sha,r)] for r in CLASSIC_RANKS}
        result=solve_rank_drop_labels(groups,wa,obs,sha,
                                      labels=groups,rank_to_label=rank_to_pool)
        self.assertEqual(result["consistentAssignments"],2)
        self.assertEqual(result["supportedMappings"][groups[0]]["group"],groups[0])
        self.assertFalse(result["executionVerified"])


if __name__=="__main__":
    unittest.main()
