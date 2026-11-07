"""Regression for source-bound, reward-only discovery across 40-block mods."""
from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_alpha_reward_pools import (
    discover_alpha_reward_pools, BLOCK_BYTES, GROUP_STRIDE,
)


def table(seed, masked=False):
    weights = [0]*722
    for idx,value in enumerate((512,512,1024)):
        weights[(seed + idx*13) % 722] = value
    if masked:
        weights = [2512 + 8*w for w in weights]
    return struct.pack("<722H",*weights) + bytes(16)


def record(seed, masked=False):
    data = b"".join(
        table(seed+j*37, masked and j>0) for j in range(4))
    assert len(data) == GROUP_STRIDE * 4
    return data + bytes(200) + b"\xff"*104


def fixture(*, masked=False):
    sentinel = record(5,False)
    assert len(sentinel)==BLOCK_BYTES
    payload = sentinel + b"".join(
        record(i*7 + 16,masked) for i in range(39))
    return sentinel,payload


class AlphaRewardPoolsTests(unittest.TestCase):
    def test_rising_style_masked_drops_after_plain_sentinel(self):
        unused,payload=fixture(masked=True)
        with patch("dueltrace_alpha_reward_pools.RETAIL_UNUSED_BLOCK_SHA256",
                   hashlib.sha256(unused).hexdigest()):
            r=discover_alpha_reward_pools(b"\x00"*2048+payload)
        self.assertTrue(r["available"])
        self.assertEqual(r["opponentBlocks"],39)
        self.assertEqual(r["dropMatrices"],117)
        self.assertEqual(r["rowCount"],39*3*3)
        self.assertEqual(r["base"],2048+BLOCK_BYTES)
        self.assertEqual(r["encoding"],"x15_masked")
        self.assertEqual(set(x["opponent_id"] for x in r["rows"]),set(range(1,40)))
        self.assertEqual(set(x["group"] for x in r["rows"]),
                         {"S/A POW","B/C/D POW/TEC","S/A TEC"})
        self.assertFalse(r["opponentIdentityVerified"])
        self.assertFalse(r["rankGroupLabelsVerified"])
        self.assertFalse(r["mayActivateDrops"])
        self.assertFalse(r["verifiedInGame"])
        # Original unused block weights may not appear in the extracted catalog.
        self.assertNotIn(5,[x["card_id"] for x in r["rows"] if
                            x["opponent_id"]==1 and x["group"]=="S/A POW"])

    def test_enhance_style_plain_40_blocks_selects_latter_39(self):
        unused,payload=fixture(masked=False)
        with patch("dueltrace_alpha_reward_pools.RETAIL_UNUSED_BLOCK_SHA256",
                   hashlib.sha256(unused).hexdigest()):
            r=discover_alpha_reward_pools(b"\x00"*(2048*4)+payload)
        self.assertEqual(r["status"],"structural_39_reward_tables")
        self.assertEqual(r["base"],2048*4+BLOCK_BYTES)
        self.assertEqual(r["encoding"],"plain")
        self.assertEqual(r["rowCount"],351)

    def test_second_valid_sentinel_fails_closed(self):
        unused,payload=fixture()
        with patch("dueltrace_alpha_reward_pools.RETAIL_UNUSED_BLOCK_SHA256",
                   hashlib.sha256(unused).hexdigest()):
            r=discover_alpha_reward_pools(payload+b"\0"*2048+payload)
        self.assertFalse(r["available"])
        self.assertEqual(r["status"],"ambiguous_retail_sentinel_runs")

    def test_any_corrupt_reward_table_disables_alpha_catalog(self):
        unused,payload=fixture(masked=True)
        data=bytearray(payload)
        data[BLOCK_BYTES+GROUP_STRIDE+20:BLOCK_BYTES+GROUP_STRIDE+22]=b"\xff\xff"
        with patch("dueltrace_alpha_reward_pools.RETAIL_UNUSED_BLOCK_SHA256",
                   hashlib.sha256(unused).hexdigest()):
            r=discover_alpha_reward_pools(bytes(data))
        self.assertFalse(r["available"])

    def test_missing_sentinel_does_not_guess_39_block_window(self):
        _unused,payload=fixture()
        r=discover_alpha_reward_pools(b"\0"*BLOCK_BYTES + payload[BLOCK_BYTES:])
        self.assertFalse(r["available"])
        self.assertEqual(r["rowCount"],0)


if __name__=="__main__":
    unittest.main()
