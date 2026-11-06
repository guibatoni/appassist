"""Read-only PSX opponent-ID RAM probe: isolated synthetic tests."""
from __future__ import annotations

import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_live_opponent import (
    OPPONENT_OFFSET,LP_BASE_OFFSET,DRAW_HISTORY_OFFSET,
    DRAW_SAMPLE_SIZE,probe_live_opponent,_valid_psx_sample,
    _select_region_candidates, MEMORY_BASIC_INFORMATION, MIN_REQUIRED_SPAN,
    MAX_LIVE_READ_BYTES,
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

    def test_native_reader_can_accept_full_proven_hand_bytes(self):
        from dueltrace_live_hand import HAND_BYTES
        self.assertEqual(HAND_BYTES,140)
        self.assertGreaterEqual(MAX_LIVE_READ_BYTES,HAND_BYTES)

    def test_working_five_card_hand_overrides_unverified_draw_format(self):
        # GOG field evidence: the existing DUELTRACE hand is working,
        # but the assumed draw-history layout did not validate in ePSXe.
        base, old = memory_snapshot(oid=1,lp1=9000,lp2=9000,
                                    invalid_history=True)
        hand=bytearray(140)
        for slot,card in enumerate((449,145,447,629,468)):
            struct.pack_into("<H",hand,slot*28,card)
            struct.pack_into("<I",hand,slot*28+12,slot)
        raw=bytes(hand)
        from dueltrace_live_hand import HAND_ADDRESS
        from dueltrace_live_opponent import HAND_OFFSET
        self.assertEqual(base+HAND_OFFSET,HAND_ADDRESS)
        def read(addr,size):
            if (addr,size)==(HAND_ADDRESS,140):
                return raw
            return old(addr,size)
        stats={}
        sample=_valid_psx_sample(read,base,stats)
        self.assertEqual(sample["runtimeOpponentId"],1)
        self.assertEqual(sample["validationMethod"],"known_hand_anchor")
        self.assertEqual(stats.get("validatedHandAnchors"),1)
        probe=probe_live_opponent(read_at=read,candidate_bases=[base])
        self.assertTrue(probe["ready"])
        self.assertEqual(probe["validationMethod"],"known_hand_anchor")
        self.assertFalse(probe["romIdentityVerified"])
        self.assertFalse(probe["mayActivateDrops"])

    def test_known_hand_anchor_rejects_unverified_hand_layout(self):
        base,old=memory_snapshot(invalid_history=True)
        invalid=bytes(140)
        from dueltrace_live_hand import HAND_ADDRESS
        def read(addr,size):
            return invalid if (addr,size)==(HAND_ADDRESS,140) else old(addr,size)
        sample=_valid_psx_sample(read,base)
        self.assertIsNone(sample)
        self.assertFalse(probe_live_opponent(
            read_at=read,candidate_bases=[base])["ready"])

    def test_known_hand_does_not_override_invalid_lp_or_opponent_id(self):
        from dueltrace_live_hand import HAND_ADDRESS
        for kwargs in ({"oid":255},{"lp1":0},{"lp2":0}):
            base,old=memory_snapshot(invalid_history=True,**kwargs)
            raw=bytearray(140)
            for slot in range(5):
                struct.pack_into("<H",raw,slot*28,slot+1)
                struct.pack_into("<I",raw,slot*28+12,slot)
            def read(addr,size):
                return bytes(raw) if (addr,size)==(HAND_ADDRESS,140) else old(addr,size)
            self.assertIsNone(_valid_psx_sample(read,base))

    def test_find_high_win64_ram_base_even_after_large_low_mapping(self):
        high = 0x1422E800000
        low, read_low = memory_snapshot(oid=14, lp1=9000, lp2=9000)
        def read_high(address, size):
            return read_low(address - (high-low), size)
        bases = _select_region_candidates([
            (0x200000, 0x5000000),
            (high, 0x200000),
        ],hint=0xB15000,max_candidates=8)
        self.assertIn(high, bases)
        self.assertEqual(bases[0],0xB15000)
        result=probe_live_opponent(read_at=read_high,candidate_bases=[high])
        self.assertTrue(result["ready"])
        self.assertEqual(result["runtimeOpponentId"],14)
        self.assertEqual(result["playerLP"],9000)
        self.assertFalse(result["opponentNameVerified"])

    def test_support_partially_partitioned_psx_region(self):
        high=0x14400000000
        candidates=_select_region_candidates([
            (high,MIN_REQUIRED_SPAN+0x1000),
        ],hint=0xB15000)
        self.assertIn(high,candidates)

    def test_rejection_stages_distinguish_history_lp_and_opponent(self):
        base, read=memory_snapshot(invalid_history=True)
        stats={}
        self.assertIsNone(_valid_psx_sample(read,base,stats))
        self.assertEqual(stats.get("implausibleDrawHistory"),1)
        self.assertEqual(stats.get("implausibleLifePoints",0),0)
        base,read=memory_snapshot(lp1=0)
        stats={}
        self.assertIsNone(_valid_psx_sample(read,base,stats))
        self.assertEqual(stats.get("implausibleLifePoints"),1)
        base,read=memory_snapshot(oid=255)
        stats={}
        self.assertIsNone(_valid_psx_sample(read,base,stats))
        self.assertEqual(stats.get("opponentIdOutOfRange"),1)

    def test_virtualquery_struct_matches_current_python_bitness(self):
        import ctypes
        fields={field[0] for field in MEMORY_BASIC_INFORMATION._fields_}
        self.assertEqual("PartitionId" in fields,
                         ctypes.sizeof(ctypes.c_void_p)==8)
        self.assertIn("RegionSize",fields)

    def test_reject_unbounded_candidates(self):
        r=probe_live_opponent(read_at=lambda a,n:None,
                              candidate_bases=list(range(200)))
        self.assertEqual(r["status"],"too_many_candidates")
        self.assertFalse(r["ready"])


if __name__=="__main__":
    unittest.main()
