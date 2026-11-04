"""Regression tests for RANK comparisons without real emulator claims."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_rank_duel_verification import compare_rank_observations
from dueltrace_rank_export import build_rank_evidence_report
from scanner_multiiso import X15_SHA

CLASSIC = "a" * 64


def observation(sha=CLASSIC, score=85, rank="A-POW", predicted=85,
                predicted_rank="A-POW", victory="lp", duel="duel-000001"):
    return {
        "rom_sha256": sha, "duel_id": duel,
        "source": "manual_game_observation",
        "observed_points": score, "observed_rank": rank,
        "victory_type": victory, "opponent_id": 1, "card_id": 1,
        "rank_snapshot": {
            "projected_score": predicted, "projected_rank": predicted_rank,
            "comparison_status": "projection_not_final",
            "counters": {"private_path": "C:/secret"},
        },
    }


class RankDuelVerificationTests(unittest.TestCase):
    def test_same_score_different_iso_labels_without_changing_points(self):
        classic = compare_rank_observations(CLASSIC, [observation()])
        x15 = compare_rank_observations(X15_SHA, [
            observation(X15_SHA, rank="S-POW", predicted_rank="S-POW")
        ])
        self.assertEqual(classic["matches"], 1)
        self.assertEqual(x15["matches"], 1)
        self.assertEqual(classic["cases"][0]["projected_score"], 85)
        self.assertEqual(x15["cases"][0]["projected_score"], 85)
        self.assertEqual(classic["cases"][0]["projected_rank"], "A-POW")
        self.assertEqual(x15["cases"][0]["projected_rank"], "S-POW")
        for report in (classic, x15):
            self.assertFalse(report["runtime_verified"])
            self.assertFalse(report["binding_unlocked"])
            self.assertFalse(report["rank_routine_confirmed"])

    def test_score_disagreement_can_keep_same_letter(self):
        report = compare_rank_observations(CLASSIC, [
            observation(score=86, predicted=85)
        ])
        self.assertEqual(report["mismatches"], 1)
        self.assertEqual(report["cases"][0]["status"], "score_mismatch")
        self.assertEqual(report["cases"][0]["score_delta"], 1)

    def test_rank_only_with_unknown_observed_points(self):
        row = observation()
        row["observed_points"] = None
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["rank_only_matches"], 1)
        row["observed_rank"] = "B-POW"
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["rank_only_mismatches"], 1)

    def test_missing_or_invalid_prediction_never_counts_as_match(self):
        row = observation()
        row["rank_snapshot"] = None
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["missing_prediction"], 1)
        row["rank_snapshot"] = {"projected_score": 85, "projected_rank": "Z-POW"}
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["invalid"], 1)

    def test_deckout_is_not_compared_to_lp_win_prediction(self):
        row = observation(victory="deckout")
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["not_lp_win"], 1)
        self.assertEqual(compare_rank_observations(CLASSIC, [row])["fully_comparable"], 0)

    def test_observed_score_and_label_conflict_is_not_training_evidence(self):
        row = observation(score=95, rank="A-POW")
        report = compare_rank_observations(CLASSIC, [row])
        self.assertEqual(report["cases"][0]["status"], "observed_result_conflict")
        self.assertEqual(report["matches"], 0)

    def test_cross_iso_observations_ignored_and_duplicates_flagged(self):
        rows = [observation(), observation(), observation(X15_SHA)]
        result = compare_rank_observations(CLASSIC, rows)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["cases"][1]["status"], "duplicate_duel")

    def test_invalid_input_rejected_and_details_sanitized(self):
        for sha in (None, "abc", "G" * 64):
            with self.assertRaises(ValueError):
                compare_rank_observations(sha, [])
        with self.assertRaises(ValueError):
            compare_rank_observations(CLASSIC, {})
        record = observation()
        record["source_path"] = "C:/private-location"
        report = compare_rank_observations(CLASSIC, [record])
        self.assertNotIn("private-location", str(report))
        self.assertNotIn("C:/secret", str(report))

    def test_export_adds_comparison_without_private_data(self):
        record = observation()
        profile = {
            "rom_sha256": CLASSIC, "exe_sha256": "b" * 64,
            "wa_sha256": "c" * 64,
            "rank_points": {"available": False},
            "rank_mips_evidence": {"available": False},
        }
        exported = build_rank_evidence_report(profile, [record], [], {})
        self.assertEqual(exported["rank_comparison"]["matches"], 1)
        self.assertEqual(exported["rank_comparison"]["fully_comparable"], 1)
        self.assertFalse(exported["rank_comparison"]["rank_routine_confirmed"])
        self.assertNotIn("C:/secret", str(exported))


if __name__ == "__main__":
    unittest.main()
