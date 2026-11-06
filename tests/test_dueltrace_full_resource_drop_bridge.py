"""Whole-resource drop probe must never guess a physical opponent window."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_full_resource_drop_bridge import use_unique_weight_family


def family(*, base=0x2421800, state="unique_structural_candidate",
           candidate_count=1, ambiguous=False, codec="plain_deck_masked_drops"):
    return {
        "state":state,"candidateCount":candidate_count,
        "ambiguous39BlockWindows":ambiguous,
        "selected":{
            "base":base,"opponentStep":0x1800,"matrixStride":0x5b4,
            "encoding":codec,"opponentBlocks":39,"matrixCount":156,
            "deckMatrices":39,"unlabeledDistributionMatrices":117,
        },
    }


def decoder(base,step,stride):
    assert step==0x1800 and stride==0x5b4
    return ({
        "verificacao":[{"peso_total":2048} for _ in range(117)],
        "drops":[{"carta_id":7,"peso":2}],
    }, "117 structurally parsed")


class FullResourceBridgeTests(unittest.TestCase):
    def test_rising_style_distant_unique_structural_family_allowed(self):
        result=use_unique_weight_family(family(),decoder)
        self.assertEqual(result["state"],"unique_156_matrices_full_resource")
        self.assertEqual(result["selected"]["opponentBase"],0x2421800)
        self.assertEqual(result["selected"]["encoding"],"plain_deck_masked_drops")
        self.assertFalse(result["inGameVerified"])
        self.assertFalse(result["rankLabelsVerified"])
        self.assertFalse(result["opponentIdsVerified"])
        self.assertFalse(result["mayActivateDrops"])

    def test_enhance_style_40_block_two_windows_are_ambiguous(self):
        self.assertIsNone(use_unique_weight_family(
            family(base=0xE99800,candidate_count=2,ambiguous=True),decoder))
        self.assertIsNone(use_unique_weight_family(
            family(state="single_family_unmapped_windows",ambiguous=True),decoder))

    def test_decoder_must_confirm_all_117_normalized_matrices(self):
        self.assertIsNone(use_unique_weight_family(
            family(),lambda b,s,r:({"verificacao":[{"peso_total":2048}]*116,
                                    "drops":[{"carta_id":1}]}, "short")))
        self.assertIsNone(use_unique_weight_family(
            family(),lambda b,s,r:({"verificacao":[{"peso_total":5000}]*117,
                                    "drops":[{"carta_id":1}]}, "wrong")))
        self.assertIsNone(use_unique_weight_family(
            family(codec="unknown_format"),decoder))
        self.assertIsNone(use_unique_weight_family(
            family(base=-1),decoder))

    def test_decoder_errors_never_activate(self):
        def broken(*args):
            raise ValueError("unsupported")
        self.assertIsNone(use_unique_weight_family(family(),broken))


if __name__=="__main__":
    unittest.main()
