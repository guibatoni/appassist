"""Evidence-only regression tests for alternative 39-opponent windows."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_mod_family_probe import discover_weight_families
from dueltrace_window_observation import correlate_observed_duels

BASE = 0x2000
STEP = 0x1800
STRIDE = 0x5B4
CARD_COUNT = 722


def fixture():
    data = bytearray(BASE + 40 * STEP)
    for opponent in range(40):
        offset = BASE + opponent * STEP
        for group in range(4):
            cards = [0] * CARD_COUNT
            a = (opponent * 19 + group * 37) % CARD_COUNT
            cards[a] += 100
            cards[(a + 210) % CARD_COUNT] += 300
            cards[(a + 410) % CARD_COUNT] += 1648
            struct.pack_into("<722H", data, offset + group * STRIDE, *cards)
        data[offset + 4 * STRIDE:offset + 4 * STRIDE + 200] = b"\xA5" * 200
        data[offset + 4 * STRIDE + 200:offset + STEP] = b"\xff" * 104
    blob = bytes(data)
    family = discover_weight_families(
        blob, layout_hypotheses=((STEP, STRIDE),))
    assert family["state"] == "single_family_unmapped_windows", family["state"]
    assert family["candidateCount"] == 2
    return blob, family


def observed(*, slot=1, reward=38, rank="S-POW", played=None):
    return {"source": "manual_game_observation",
            "opponent_slot": slot,
            "reward_card_id": reward,
            "observed_rank": rank,
            "played_card_ids": [1] if played is None else played}


class WindowEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob, cls.family = fixture()

    def test_no_observations_do_not_select_window(self):
        report = correlate_observed_duels(self.blob, self.family, [])
        self.assertEqual(report["status"], "awaiting_independent_duels")
        self.assertEqual(report["windowCount"], 2)
        self.assertIsNone(report["candidateWindowHint"])
        self.assertFalse(report["mayActivateDrops"])

    def test_one_observation_only_suggests_first_window(self):
        # The first 39-window's first opponent has card 1 in deck and
        # card 38 in the first unlabeled reward distribution.
        report = correlate_observed_duels(
            self.blob, self.family, [observed()])
        self.assertEqual(report["status"], "single_window_suggested_not_verified")
        self.assertEqual(report["candidateWindowHint"], 0)
        self.assertEqual(report["compatibleWindowCount"], 1)
        self.assertEqual(report["windows"][1]["deckContradictions"], 1)
        self.assertTrue(report["windows"][0]["compatibleUnderHypothesis"])
        self.assertFalse(report["inGameVerified"])
        self.assertFalse(report["rankGroupsVerified"])
        self.assertFalse(report["opponentIdsVerified"])
        self.assertFalse(report["mayActivateDrops"])
        self.assertFalse(report["mayActivateRank"])
        self.assertNotIn("reward_card_id", str(report))
        self.assertNotIn("played_card_ids", str(report))

    def test_second_window_can_be_suggested_without_promotion(self):
        # Physical block 1 is the first opponent under window B.
        report = correlate_observed_duels(
            self.blob, self.family, [observed(reward=57, played=[20])])
        self.assertEqual(report["status"], "single_window_suggested_not_verified")
        self.assertEqual(report["candidateWindowHint"], 1)
        self.assertFalse(report["mayActivateDrops"])

    def test_missing_reward_in_all_groups_reports_conflict(self):
        report = correlate_observed_duels(
            self.blob, self.family, [observed(reward=700, played=[])])
        self.assertEqual(report["status"], "observations_conflict_with_all_windows")
        self.assertEqual(report["compatibleWindowCount"], 0)
        self.assertIsNone(report["candidateWindowHint"])

    def test_repeated_rank_does_not_force_unverified_group_label(self):
        # Each observation is only a possibility. Never assert exact RANK.
        report = correlate_observed_duels(self.blob, self.family, [
            observed(slot=1, reward=38, played=[]),
            observed(slot=2, reward=57, played=[]),
        ])
        self.assertFalse(report["rankGroupsVerified"])
        self.assertFalse(report["mayActivateRank"])
        for row in report["windows"]:
            self.assertTrue(all(
                group in (1, 2, 3)
                for ids in row["candidateGroupsPerObservedRank"].values()
                for group in ids))

    def test_bad_user_supplied_observations_are_rejected(self):
        bad = [
            {"source": "manual_game_observation", "opponent_slot": True,
             "reward_card_id": 38, "observed_rank": "S-POW"},
            observed(slot=40), observed(reward=0),
            observed(rank="S POW"), observed(played=[1, 1]),
            observed(played=list(range(1, 30))),
            {**observed(), "source": "unverified_foreign_iso"},
        ]
        for item in bad:
            with self.subTest(item=item):
                report = correlate_observed_duels(self.blob, self.family, [item])
                self.assertEqual(report["status"], "invalid_observation")
                self.assertEqual(report["windows"], [])

    def test_reject_stale_or_truncated_family_input(self):
        altered = dict(self.family, scanComplete=False)
        self.assertEqual(correlate_observed_duels(
            self.blob, altered, [observed()])["status"], "invalid_input")
        altered = dict(self.family, clusters=[dict(
            self.family["clusters"][0], opponentStep=0)])
        self.assertEqual(correlate_observed_duels(
            self.blob, altered, [observed()])["status"], "unusable_family_layout")
        self.assertEqual(correlate_observed_duels(
            b"bad", self.family, [observed()])["status"], "unusable_family_layout")


if __name__ == "__main__":
    unittest.main()
