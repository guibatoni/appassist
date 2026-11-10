"""Regressões do contador provisório de RANK, com RAM totalmente sintética."""
from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from scanner_multiiso import X15_SHA
from dueltrace_rank_live import (
    CANDIDATE_RANK_ADDRESS, RECORD_BYTES, decode_rank_record,
    model_available, project_lp_win_rank, read_rank_candidate,
)


def make_record(*, lp=8000, turns=1, spells=0, fusions=0, cards_used=0):
    raw=bytearray(RECORD_BYTES)
    raw[1]=turns
    raw[5]=spells
    raw[8]=fusions
    raw[20:22]=lp.to_bytes(2,"little",signed=True)
    raw[24:25]=cards_used.to_bytes(1,"little",signed=True)
    return bytes(raw)


class FakeKernel:
    def __init__(self, payloads, *, permit=True):
        self.payloads=iter(payloads)
        self.closed=[]
        self.addresses=[]
        self.OpenProcess=Mock(return_value=789 if permit else None)
        self.ReadProcessMemory=Mock(side_effect=self._read)
        self.CloseHandle=Mock(side_effect=lambda handle:self.closed.append(handle) or True)

    def _read(self,handle,address,buffer,size,nread):
        blob=next(self.payloads)
        self.addresses.append((address.value,size))
        ctypes.memmove(buffer,blob,len(blob))
        ctypes.cast(nread,ctypes.POINTER(ctypes.c_size_t)).contents.value=len(blob)
        return True


class RankRulesTests(unittest.TestCase):
    def test_explicit_model_is_only_exact_remaster_sha(self):
        self.assertTrue(model_available(X15_SHA))
        self.assertTrue(model_available(X15_SHA.upper()))
        self.assertFalse(model_available("a"*64))
        self.assertFalse(model_available("Remaster 1.2.1 X15"))
        self.assertFalse(model_available(None))

    def test_counters_and_projection_not_final(self):
        counters=decode_rank_record(make_record(lp=8000,turns=1))
        self.assertIsNotNone(counters)
        self.assertEqual(counters["turns"],1)
        self.assertEqual(counters["remaining_lp"],8000)
        rank=project_lp_win_rank(counters)
        self.assertFalse(rank["final"])
        self.assertEqual(rank["breakdown"]["turns"],12)
        self.assertEqual(rank["breakdown"]["remaining_lp"],6)
        self.assertEqual(rank["score"],50+2+sum(rank["breakdown"].values()))
        self.assertEqual(rank["category"],"Z-POW")

    def test_rank_band_cutoffs(self):
        # Usamos valores derivados de contadores, não o score hardcoded.
        base=decode_rank_record(make_record())
        self.assertIsNotNone(base)
        lower={**base,"turns":60,"spells":15,"fusions":30,
               "traps":8,"defense_wins":20,"face_down":50,"equips":20,
               "cards_used":40,"remaining_lp":500}
        result=project_lp_win_rank(lower)
        self.assertLess(result["score"],50)
        self.assertEqual(result["category"],"S-TEC")

    def test_invalid_snapshot_or_lp_does_not_generate_score(self):
        self.assertIsNone(decode_rank_record(b""))
        self.assertIsNone(decode_rank_record(bytes(31)))
        self.assertIsNone(decode_rank_record(make_record(lp=-1)))
        self.assertIsNone(decode_rank_record(make_record(turns=120)))
        with self.assertRaises(ValueError):
            project_lp_win_rank({"turns":5})
        with self.assertRaises(ValueError):
            project_lp_win_rank({**decode_rank_record(make_record()),"turns":-1})

    def test_reads_same_32_bytes_twice_and_closes_handle(self):
        blob=make_record(lp=7000,turns=4,fusions=3)
        kernel=FakeKernel([blob,blob])
        result=read_rank_candidate(kernel=kernel,pids=[4321])
        self.assertTrue(result["ready"])
        self.assertEqual(result["pid"],4321)
        self.assertEqual(result["counters"]["fusions"],3)
        self.assertEqual(kernel.addresses,[(CANDIDATE_RANK_ADDRESS,RECORD_BYTES)]*2)
        self.assertEqual(kernel.closed,[789])

    def test_x15_candidate_is_relocated_only_after_validated_hand_address(self):
        from dueltrace_live_hand import HAND_ADDRESS, _PID_HAND_ADDRESS_CACHE
        pid=21918
        relocated=0x112345678
        _PID_HAND_ADDRESS_CACHE[pid]=relocated
        try:
            blob=make_record(lp=8000,turns=2)
            kernel=FakeKernel([blob,blob])
            sample=read_rank_candidate(kernel=kernel,pids=[pid])
            self.assertTrue(sample["ready"])
            expected=CANDIDATE_RANK_ADDRESS+(relocated-HAND_ADDRESS)
            self.assertEqual(kernel.addresses,[(expected,RECORD_BYTES)]*2)
        finally:
            _PID_HAND_ADDRESS_CACHE.pop(pid,None)

    def test_custom_mod_reader_uses_its_own_host_address_not_ps1_virtual(self):
        from dueltrace_rank_live import read_rank_from_verified_binding
        binding={
            "record_address":0xBA1000,"record_length":32,
            "criterion_offsets":{
                "criterion_01":{"type":"u8","offset":1},
                "criterion_02":{"type":"u16le","offset":20},
            },
        }
        blob=make_record(lp=6500,turns=3)
        kernel=FakeKernel([blob,blob])
        output=read_rank_from_verified_binding(binding,kernel=kernel,pids=[4321])
        self.assertTrue(output["ready"])
        self.assertEqual(output["counters"]["criterion_01"],3)
        self.assertEqual(output["counters"]["criterion_02"],6500)
        self.assertEqual(kernel.addresses,[(0xBA1000,32)]*2)
        self.assertEqual(kernel.closed,[789])

    def test_custom_mod_reader_rejects_bad_address_before_memory_access(self):
        from dueltrace_rank_live import read_rank_from_verified_binding
        kernel=FakeKernel([])
        with self.assertRaises(ValueError):
            read_rank_from_verified_binding(
                {"record_address":0,"record_length":32},kernel=kernel,pids=[4321])
        kernel.OpenProcess.assert_not_called()

    def test_transition_is_rejected_and_no_stale_memory(self):
        kernel=FakeKernel([make_record(turns=2),make_record(turns=3)])
        result=read_rank_candidate(kernel=kernel,pids=[4321])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["counters"])
        self.assertEqual(kernel.closed,[789])

    def test_no_guess_when_multiple_emulators_or_wrong_pid(self):
        kernel=FakeKernel([])
        result=read_rank_candidate(kernel=kernel,pids=[1,2])
        self.assertFalse(result["ready"])
        result=read_rank_candidate(kernel=kernel,preferred_pid=5,pids=[1])
        self.assertFalse(result["ready"])
        self.assertFalse(kernel.OpenProcess.called)


if __name__=="__main__":
    unittest.main()
