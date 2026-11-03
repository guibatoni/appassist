"""Prova de consistência entre os três bancos WA sem suposições sobre RANK."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_rank_drop_solver import solve_rank_drop_labels
from dueltrace_drop_rank_evidence import rank_drop_report
from test_dueltrace_drops import fake_profile


def by_opp(groups):
    return {oid:{g:{i+1} for i,g in enumerate(groups)} for oid in range(1,40)}


def observation(sha,oid,cid,label,duel):
    return {"rom_sha256":sha, "opponent_id":oid, "card_id":cid,
            "observed_rank":label,"duel_id":duel}


class RankDropSolverTests(unittest.TestCase):
    def setUp(self):
        self.groups=["G1","G2","G3"]
        self.wa=by_opp(self.groups)
        self.sha="a"*64

    def test_two_discriminating_opponents_corrob_one_rank_not_others(self):
        obs=[observation(self.sha,1,2,"Z-POW","duel-001"),
             observation(self.sha,2,2,"Z-POW","duel-002")]
        r=solve_rank_drop_labels(self.groups,self.wa,obs,self.sha)
        self.assertEqual(r["consistentAssignments"],2)
        self.assertEqual(r["possibleGroups"]["Z-POW"],["G2"])
        self.assertEqual(r["supportedMappings"]["Z-POW"]["group"],"G2")
        self.assertNotIn("S-POW",r["supportedMappings"])
        self.assertFalse(r["executionVerified"])

    def test_all_three_labels_unique_bijection_requires_distinct_evidence(self):
        obs=[]
        for label,cid in (("Z-POW",3),("S-POW",1),("S-TEC",2)):
            for oid in (4,8):
                obs.append(observation(self.sha,oid,cid,label,
                                       f"duel-{label}-{oid}"))
        r=solve_rank_drop_labels(self.groups,self.wa,obs,self.sha)
        self.assertEqual(r["consistentAssignments"],1)
        self.assertEqual({name:row["group"] for name,row in r["supportedMappings"].items()},
                         {"Z-POW":"G3","S-POW":"G1","S-TEC":"G2"})
        self.assertFalse(r["executionVerified"])

    def test_no_bijection_for_two_ranks_pointing_same_bank(self):
        obs=[observation(self.sha,1,1,"Z-POW","duel-Z001"),
             observation(self.sha,2,1,"Z-POW","duel-Z002"),
             observation(self.sha,1,1,"S-POW","duel-S001"),
             observation(self.sha,2,1,"S-POW","duel-S002")]
        r=solve_rank_drop_labels(self.groups,self.wa,obs,self.sha)
        self.assertEqual(r["consistentAssignments"],0)
        self.assertEqual(r["supportedMappings"],{})
        self.assertEqual(r["status"],"inconsistent")

    def test_shared_drop_does_not_create_false_assignment(self):
        self.wa[1]["G2"].add(1)
        self.wa[2]["G2"].add(1)
        obs=[observation(self.sha,1,1,"Z-POW","duel-A100"),
             observation(self.sha,2,1,"Z-POW","duel-B200")]
        r=solve_rank_drop_labels(self.groups,self.wa,obs,self.sha)
        self.assertEqual(r["possibleGroups"]["Z-POW"],["G1","G2"])
        self.assertEqual(r["supportedMappings"],{})
        self.assertEqual(r["ambiguousDrops"],2)

    def test_different_rom_and_duplicate_duels_never_confuse_mapping(self):
        obs=[observation("b"*64,1,3,"Z-POW","duel-A100"),
             observation(self.sha,1,1,"Z-POW","duel-A100"),
             observation(self.sha,2,2,"Z-POW","duel-B200"),
             observation(self.sha,1,2,"Z-POW","duel-A100")]
        r=solve_rank_drop_labels(self.groups,self.wa,obs,self.sha)
        self.assertEqual(r["distinctDuels"],2)
        self.assertEqual(r["status"],"inconsistent")
        self.assertFalse(r["supportedMappings"])

    def test_integrated_catalog_exposes_remaining_hypotheses(self):
        p=fake_profile()
        obs=[observation(p["rom_sha256"],1,1,"S-POW","duel-A100"),
             observation(p["rom_sha256"],2,1,"A-POW","duel-B200")]
        r=rank_drop_report(p,obs)
        self.assertEqual(r["assignmentCount"],2)
        self.assertEqual(r["mappingConsistency"],"corroborated")
        self.assertEqual(len(r["mappingHypotheses"]),2)
        self.assertEqual(r["suspectedMappings"]["S/A POW"]["group"],p["drop_group_labels"][0])


if __name__=="__main__":
    unittest.main()
