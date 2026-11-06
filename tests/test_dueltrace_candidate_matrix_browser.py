"""Read-only matrix browsing against a synthetic 40-block ISO resource."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_candidate_matrix_browser import browse_candidate_matrices
from dueltrace_mod_family_probe import discover_weight_families

BASE, STEP, STRIDE, CARD_COUNT = 0x2000, 0x1800, 0x5B4, 722


def fixture():
    data = bytearray(BASE + 40 * STEP)
    for b in range(40):
        start = BASE + b * STEP
        for g in range(4):
            v = [0] * CARD_COUNT
            a = (b * 19 + g * 37) % CARD_COUNT
            v[a] = 100
            v[(a + 210) % CARD_COUNT] = 300
            v[(a + 410) % CARD_COUNT] = 1648
            struct.pack_into("<722H", data, start + g * STRIDE, *v)
        data[start + 4 * STRIDE:start + 4 * STRIDE + 200] = b"\xA5" * 200
        data[start + 4 * STRIDE + 200:start + STEP] = b"\xFF" * 104
    blob = bytes(data)
    fam = discover_weight_families(blob, layout_hypotheses=((STEP,STRIDE),))
    assert fam["state"] == "single_family_unmapped_windows", fam
    return blob, fam, [{"id":i,"name":f"Own ROM card {i}",
                        "atk":i * 2, "def":i * 3,"type":"Monster"}
                       for i in range(1, 723)]


class CandidateBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob, cls.family, cls.cards = fixture()

    def browse(self, block=0, group=1, **kw):
        return browse_candidate_matrices(
            self.blob,self.family,self.cards,
            physical_block_index=block,matrix_group=group,**kw)

    def test_can_read_all_physical_blocks_without_assigning_an_opponent(self):
        for block in (0,11,39):
            result = self.browse(block, 1)
            self.assertTrue(result["available"])
            self.assertEqual(result["blockCount"],40)
            self.assertEqual(result["physicalBlockIndex"],block)
            self.assertEqual(result["totalWeight"],2048)
            self.assertEqual(result["nonzeroCards"],3)
            self.assertEqual(result["total"],3)
            self.assertEqual(result["matrixKind"],"unlabeled_reward_distribution_candidate")
            self.assertFalse(result["opponentIdsVerified"])
            self.assertFalse(result["rankGroupLabelsVerified"])
            self.assertFalse(result["mayActivateDrops"])
            self.assertFalse(result["mayActivateRank"])
            self.assertNotIn("rom",str(result).casefold())

    def test_query_by_id_or_name_and_use_own_catalog_attributes(self):
        result = self.browse(0,1,query="38")
        self.assertEqual(result["total"],1)
        row = result["rows"][0]
        self.assertEqual(row["id"],38)
        self.assertEqual(row["weight"],100)
        self.assertEqual(row["weightDenominator"],2048)
        self.assertEqual(row["atk"],76)
        self.assertEqual(row["def"],114)
        self.assertAlmostEqual(row["chancePercent"],4.8828,places=4)
        self.assertEqual(self.browse(0,1,query="Own ROM card 38")["total"],1)
        self.assertEqual(self.browse(0,1,query="NOPE")["total"],0)

    def test_deck_matrix_remains_unverified(self):
        r=self.browse(0,0)
        self.assertEqual(r["matrixKind"],"deck_candidate")
        self.assertFalse(r["opponentIdsVerified"])

    def test_pagination_and_sorting(self):
        r=self.browse(0,1,offset=0,limit=2)
        self.assertEqual(r["rows"][0]["weight"],1648)
        self.assertEqual(r["rows"][1]["weight"],300)
        self.assertEqual(self.browse(0,1,offset=2,limit=2)["rows"][0]["weight"],100)

    def test_reject_malformed_layout_input_and_never_promote(self):
        self.assertFalse(self.browse(40,1)["available"])
        self.assertEqual(self.browse(0,4)["status"],"invalid_request")
        changed=dict(self.family,scanComplete=False)
        r=browse_candidate_matrices(self.blob,changed,self.cards,
                                     physical_block_index=0)
        self.assertFalse(r["available"])
        self.assertFalse(r["mayActivateDrops"])
        wrong=dict(self.family,clusters=self.family["clusters"]*2)
        r=browse_candidate_matrices(self.blob,wrong,self.cards,
                                     physical_block_index=0)
        self.assertFalse(r["available"])
        short=self.blob[:BASE+4*STEP]
        r=browse_candidate_matrices(short,self.family,self.cards,
                                     physical_block_index=0)
        self.assertFalse(r["available"])
        bad_cards=[{"id":1,"name":"Same"}]*722
        r=browse_candidate_matrices(self.blob,self.family,bad_cards,
                                     physical_block_index=0)
        self.assertFalse(r["available"])


if __name__=="__main__":
    unittest.main()
