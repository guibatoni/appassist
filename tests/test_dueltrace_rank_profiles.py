"""RANK só é reutilizado por SHA conhecido, sem inventar dados do SLUS."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_profiles import rank_profile_for_image
from scanner_multiiso import X15_SHA


class RankProfileTests(unittest.TestCase):
    def test_known_x15_has_model_with_source_and_points(self):
        report=rank_profile_for_image(X15_SHA)
        self.assertTrue(report["available"])
        self.assertEqual(report["status"],"modelo_validado_para_sha_exato")
        self.assertIn("SLUS_014.11",report["source"])
        self.assertEqual(report["base_points"],50)
        self.assertEqual(report["lp_victory_bonus"],2)
        self.assertEqual(len(report["rules"]),10)
        self.assertEqual(report["rules"]["turns"][0],{"below":5,"points":12})
        self.assertFalse(report["final_rank"])

    def test_unknown_or_lookalike_mod_gets_no_scoring(self):
        for sha in ("a"*64,X15_SHA[:-1]+"a",None,"Remaster X15",""):
            if sha==X15_SHA:
                continue
            with self.subTest(sha=sha):
                report=rank_profile_for_image(sha)
                self.assertFalse(report["available"])
                self.assertEqual(report["rules"],{})
                self.assertIsNone(report["base_points"])
                self.assertIn("mod",report["note"].lower())


if __name__=="__main__":
    unittest.main()
