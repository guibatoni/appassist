"""Regression for conservative, read-only Live Diagnostics interpretation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_live_forensics import summarize_live_report


def row(sample, hand, opponent_id, lp_p, lp_o, rank_ready=False):
    return {"sample": sample, "atUTC": "2026-11-06T22:00:00+00:00",
            "data": {
                "hand": {"ready": True, "ids": hand},
                "opponent": {"ready": True,
                             "status": "runtime_id_candidate",
                             "candidateId": opponent_id,
                             "lpPlayer": lp_p, "lpOpponent": lp_o},
                "rank": {"ready": rank_ready,
                         "state": "provisional" if rank_ready else "unavailable"},
            }}


class ForensicConsistencyTests(unittest.TestCase):
    def test_stable_candidate_amid_changing_hands_and_legacy_lp_fields(self):
        report = {"schema": 1, "events": [
            row(1,[447,311,447,81,196],5,10758,5376),
            row(2,[58,95,61,450,105],5,11050,8737),
            row(3,[196,449,61,55,95],5,6939,3615),
        ]}
        review = summarize_live_report(report)
        self.assertTrue(review["available"])
        self.assertEqual(review["eventCountExamined"],3)
        self.assertEqual(review["distinctHands"],3)
        self.assertEqual(review["distinctLegacyLpPairs"],3)
        self.assertEqual(review["candidateIds"],[5])
        self.assertEqual(review["candidateObservedInEvents"],3)
        self.assertTrue(review["candidateStableDespiteHandAndLpFieldChanges"])
        self.assertEqual(review["status"],"stable_candidate_requires_independent_proof")
        self.assertFalse(review["opponentIdentityVerified"])
        self.assertFalse(review["legacyLpSemanticsVerified"])
        self.assertFalse(review["dropMappingVerified"])
        self.assertFalse(review["fusionRecipesVerified"])
        self.assertNotIn("447",str(review))  # never export raw hand
        self.assertNotIn("10758",str(review))

    def test_changed_id_disables_stability_conclusion(self):
        report = {"schema": 1, "events": [
            row(1,[447,311,447,81,196],5,10758,5376),
            row(2,[58,95,61,450,105],5,11050,8737),
            row(3,[196,449,61,55,95],6,6939,3615,rank_ready=True),
        ]}
        review = summarize_live_report(report)
        self.assertEqual(review["candidateIds"],[5,6])
        self.assertFalse(review["candidateStableDespiteHandAndLpFieldChanges"])
        self.assertEqual(review["rankSnapshotEvents"],1)
        self.assertFalse(review["opponentIdentityVerified"])

    def test_stable_id_without_independent_variation_is_not_claimed(self):
        report = {"schema": 1, "events": [
            row(1,[447,311,447,81,196],5,10758,5376),
            row(2,[447,311,447,81,196],5,10758,5376),
            row(3,[447,311,447,81,196],5,10758,5376),
        ]}
        review = summarize_live_report(report)
        self.assertFalse(review["candidateStableDespiteHandAndLpFieldChanges"])
        self.assertFalse(review["opponentIdentityVerified"])

    def test_invalid_and_unexpected_fields_do_not_leak(self):
        malformed = {"schema": 1, "events": [
            {"data": {"hand": {"ready": True, "ids": [True, 1, 2, 3, 4]},
                      "opponent": {"ready": True, "candidateId": True,
                                   "lpPlayer": -4, "lpOpponent": "secret"},
                      "rank": {"ready": False}}},
            {"unexpected":"secret"},
        ], "rawMemory": "PRIVATE"}
        result = summarize_live_report(malformed)
        self.assertEqual(result["eventCountExamined"],1)
        self.assertEqual(result["candidateIds"],[])
        self.assertEqual(result["distinctHands"],0)
        self.assertEqual(result["distinctLegacyLpPairs"],0)
        self.assertNotIn("secret",str(result))
        self.assertNotIn("PRIVATE",str(result))
        self.assertFalse(result["opponentIdentityVerified"])
        self.assertFalse(summarize_live_report(None)["available"])
        self.assertFalse(summarize_live_report({"schema":1,"events":[{}]*361})["available"])


if __name__=="__main__":
    unittest.main()
