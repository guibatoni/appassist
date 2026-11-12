"""Reciprocal card fusion hints for material/result, source-bound and capped."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from auto_mods import ModCatalog
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi


class CardFusionPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sha = "a" * 64
        self.other = "b" * 64
        self.bridge = DueltraceWebBridge(catalog=ModCatalog(Path(self.tmp.name)))
        self.profile = {
            "rom_sha256": self.sha,
            "supported_features": {"cards": True, "fusions": True},
            "cards": [
                {"id": i, "name": f"Carta {i}", "atk": i * 100,
                 "def": i * 50, "category": "Monstros"}
                for i in range(1, 723)
            ],
        }
        self.recipes = [
            {"a": 1, "b": i, "result": i + 20}
            for i in range(2, 11)
        ] + [
            {"a": i, "b": i + 10, "result": 1}
            for i in range(2, 11)
        ] + [
            {"a": 2, "b": 1, "result": 22},  # duplicate of first entry
            {"a": False, "b": 2, "result": 1},  # malformed input
            {"a": 3, "b": 4, "result": 5},  # irrelevant for selected card
        ]
        self.active = {"sha256": self.sha}

    def query(self, card_id=1, *, sha=None, provisional=False):
        with (patch.object(self.bridge, "_active",
                           return_value=({"sha256": sha or self.sha},
                                         {}, self.profile)),
              patch.object(self.bridge, "_combined_fusion_recipes",
                           return_value=(self.recipes, provisional))):
            return self.bridge.get_card_fusion_paths(card_id)

    def test_both_directions_return_only_five_and_real_source_ids(self):
        result = self.query(provisional=True)
        self.assertTrue(result["available"])
        self.assertTrue(result["provisional"])
        self.assertEqual(result["romSha"], self.sha)
        self.assertEqual(result["cardId"], 1)
        self.assertEqual(result["materialTotal"], 9)
        self.assertEqual(result["resultTotal"], 9)
        self.assertEqual(len(result["materialRows"]), 5)
        self.assertEqual(len(result["resultRows"]), 5)
        self.assertEqual(result["materialRows"][0]["resultId"], 30)
        self.assertEqual(result["materialRows"][0]["partnerId"], 10)
        self.assertEqual(result["materialRows"][0]["atk"], 3000)
        self.assertEqual(result["materialRows"][0]["def"], 1500)
        self.assertEqual(result["resultRows"][0]["materialAId"], 2)
        self.assertEqual(result["resultRows"][0]["materialBId"], 12)
        self.assertEqual(result["resultRows"][0]["materialAName"], "Carta 2")

    def test_current_iso_sha_must_match_profile(self):
        result = self.query(sha=self.other)
        self.assertFalse(result["available"])
        self.assertEqual(result["romSha"], self.other)
        self.assertEqual(result["materialRows"], [])
        self.assertEqual(result["resultRows"], [])
        self.assertEqual(result["materialTotal"], 0)

    def test_inputs_are_checked_and_no_other_source_is_accepted(self):
        for value in (0, -1, 723, 1.2, "1", True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.bridge.get_card_fusion_paths(value)
        empty = self.bridge.get_card_fusion_paths(2)
        self.assertFalse(empty["available"])

    def test_access_to_fusion_paths_requires_session_secret(self):
        protected = ProtectedDesktopApi(self.bridge, "s" * 64)
        with self.assertRaises(PermissionError):
            protected.get_card_fusion_paths("bad", 1)
        with (patch.object(self.bridge, "_active",
                           return_value=(self.active, {}, self.profile)),
              patch.object(self.bridge, "_combined_fusion_recipes",
                           return_value=(self.recipes, False))):
            result = protected.get_card_fusion_paths("s" * 64, 1)
        self.assertEqual(result["materialTotal"], 9)


if __name__ == "__main__":
    unittest.main()
