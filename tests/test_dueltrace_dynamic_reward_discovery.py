"""Alpha 40-block discovery without hardcoded unused-record SHA.

Synthetic records only; not distributed game content.
"""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_dynamic_reward_discovery import discover_dynamic_reward_pools


BLOCK=0x1800
STRIDE=0x5B4

def _matrix(seed):
    words=[0]*722
    for i,v in enumerate((333,715,1000)):
        words[(seed+19*i)%722]=v
    return struct.pack("<722H",*words)+bytes(16)

def _record(seed):
    return b"".join(_matrix(seed+7*j) for j in range(4))+bytes(200)+b"\xff"*104

def _family(first,*,blocks=40,ambiguous=False):
    one={"firstBlockOffset":first,"consecutiveBlockCount":blocks,
         "possible39BlockWindows":2 if blocks==40 else max(0,blocks-38),
         "runCapReached":False,"opponentStep":BLOCK,
         "matrixStride":STRIDE,"encoding":"plain"}
    return {"state":"single_family_unmapped_windows","scanComplete":True,
            "candidateCount":2,"clusters":[one]+([dict(one,firstBlockOffset=first+BLOCK*50)] if ambiguous else [])}

class DynamicRewardTests(unittest.TestCase):
    def test_gog_style_40_blocks_recover_117_reward_tables(self):
        first=2048*4
        blob=b"\0"*first+b"".join(_record(23+j*7) for j in range(40))
        r=discover_dynamic_reward_pools(blob,_family(first))
        self.assertTrue(r["available"])
        self.assertEqual(r["status"],"provisional_40_block_retail_convention")
        self.assertEqual(r["candidateMode"],"40_block_retail_mapping_hypothesis")
        self.assertEqual(r["base"],first+BLOCK)
        self.assertEqual(r["dropMatrices"],117)
        self.assertEqual(r["rowCount"],39*3*3)
        self.assertFalse(r["opponentIdentityVerified"])
        self.assertFalse(r["rankGroupLabelsVerified"])
        self.assertFalse(r["verifiedInGame"])
        self.assertFalse(r["mayActivateDrops"])
        self.assertFalse(r["mayActivateRank"])
        # The first card of record zero's reward table must never be included.
        self.assertEqual(r["rows"][0]["opponent_id"],1)
        self.assertEqual(r["rows"][0]["group"],"S/A POW")
        self.assertEqual(r["rows"][0]["source_offset"],
                         first+BLOCK+STRIDE+((23+7+7)%722)*2)
        self.assertTrue(all(x["group"]!="DECK" for x in r["rows"]))

    def test_scanner_json_hints_alone_cannot_fabricate_drops(self):
        first=4096
        blob=b"\0"*(first+40*BLOCK)
        r=discover_dynamic_reward_pools(blob,_family(first))
        self.assertFalse(r["available"])
        self.assertEqual(r["rowCount"],0)
        self.assertFalse(r["mayActivateDrops"])

    def test_41_consecutive_blocks_fail_closed(self):
        first=4096
        blob=b"\0"*first+b"".join(_record(11+i*7) for i in range(41))
        r=discover_dynamic_reward_pools(blob,_family(first))
        self.assertFalse(r["available"])
        self.assertIn("40_block",r["status"])

    def test_two_distinct_valid_runs_are_ambiguous(self):
        first=4096
        one=b"".join(_record(i*13) for i in range(40))
        second=first+BLOCK*50
        blob=b"\0"*first+one+b"\0"*(second-first-len(one))+one
        r=discover_dynamic_reward_pools(blob,_family(first,ambiguous=True))
        self.assertFalse(r["available"])
        self.assertEqual(r["status"],"ambiguous_40_block_runs")

    def test_39_only_or_broken_matrix_does_not_assume_extra_record(self):
        first=4096
        blob=b"\0"*first+b"".join(_record(i) for i in range(39))
        self.assertFalse(discover_dynamic_reward_pools(blob,_family(first,blocks=39))["available"])
        broken=bytearray(blob+_record(40))
        broken[first+BLOCK+STRIDE:first+BLOCK+STRIDE+2]=b"\xff\xff"
        self.assertFalse(discover_dynamic_reward_pools(bytes(broken),_family(first))["available"])


if __name__=="__main__":
    unittest.main()
