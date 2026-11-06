"""Read-only PSX opponent-ID RAM probe: isolated synthetic tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_live_opponent import (
    OPPONENT_OFFSET,LP_BASE_OFFSET,DRAW_HISTORY_OFFSET,
    DRAW_SAMPLE_SIZE,probe_live_opponent,_valid_psx_sample,
)


def memory_snapshot(oid=11, lp1=8000,lp2=8000, *, invalid_history=False):
    base=0xB15000
    duel=bytearray(0x30)
    duel[4:6]=lp1.to_bytes(2,"little")
    duel[0x24:0x26]=lp2.to_bytes(2,"little")
    duel[0x0A:0x0F]=bytes([0,1,2,3,4])
    history=bytearray(DRAW_SAMPLE_SIZE)
    if not invalid_history:
        for idx in range(8):
            history[idx*6:idx*6+2]=(idx+1).to_bytes(2,"little")
            history[idx*6+2]=idx
            history[idx*6+3]=idx
    values={
        (base+OPPONENT_OFFSET,1):bytes([oid]),
        (base+LP_BASE_OFFSET,0x30):bytes(duel),
        (base+DRAW_HISTORY_OFFSET,DRAW_SAMPLE_SIZE):bytes(history),
    }
    return base,lambda addr,size:values.get((addr,size))


class RuntimeOpponentTests(unittest.TestCase):
    def test_original_psx_memory_id_is_provisional_even_when_stable(self):
        base,read=memory_snapshot(oid=11)
        result=probe_live_opponent(read_at=read,candidate_bases=[base])
        self.assertTrue(result["ready"])
        self.assertEqual(result["runtimeOpponentId"],11)
        self.assertEqual(result["playerLP"],8000)
        self.assertEqual(result["opponentLP"],8000)
        self.assertTrue(result["mappingValidatedByIndependentFields"])
        self.assertFalse(result["runtimeIdVerifiedForMod"])
        self.assertFalse(result["opponentNameVerified"])
        self.assertFalse(result["romIdentityVerified"])
        self.assertFalse(result["mayActivateDrops"])
        self.assertFalse(result["mayActivateRank"])
        self.assertNotIn("base",result)

    def test_reject_menus_invalid_lp_missing_draws_and_large_ids(self):
        for kwargs in [
            {"oid":255},{"lp1":0},{"lp2":0},
            {"invalid_history":True},
        ]:
            with self.subTest(case=kwargs):
                base,read=memory_snapshot(**kwargs)
                r=probe_live_opponent(read_at=read,candidate_bases=[base])
                self.assertFalse(r["ready"])
                self.assertIsNone(r["runtimeOpponentId"])

    def test_ambiguous_duplicate_memory_mappings_fail_closed(self):
        a,read=memory_snapshot()
        b=a+0x1000000
        def both(addr,size):
            if b <= addr < b+0x200000:
                return read(addr-(b-a),size)
            return read(addr,size)
        r=probe_live_opponent(read_at=both,candidate_bases=[a,b])
        self.assertFalse(r["ready"])
        self.assertEqual(r["status"],"ambiguous_ram_mapping")

    def test_runtime_memory_reads_must_not_be_partial(self):
        base,read=memory_snapshot()
        def incomplete(addr,size):
            data=read(addr,size)
            return data[:-1] if data else None
        self.assertIsNone(_valid_psx_sample(incomplete,base))
        bad=probe_live_opponent(read_at=incomplete,candidate_bases=[base])
        self.assertFalse(bad["ready"])

    def test_reject_unbounded_candidates(self):
        r=probe_live_opponent(read_at=lambda a,n:None,
                              candidate_bases=list(range(200)))
        self.assertEqual(r["status"],"too_many_candidates")
        self.assertFalse(r["ready"])


if __name__=="__main__":
    unittest.main()
