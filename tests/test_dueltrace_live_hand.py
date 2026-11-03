"""Regressões da mão ao vivo do Início, sem depender de ePSXe real."""
from __future__ import annotations

import ctypes
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_live_hand import (
    HAND_ADDRESS,HAND_BYTES,build_fusion_index,
    read_hand_from_epsxe,suggest_hand_pairs,
)


def fake_hand(ids):
    raw=bytearray(140)
    for n,cid in enumerate(ids):
        struct.pack_into("<H",raw,n*28,cid)
        struct.pack_into("<I",raw,n*28+12,n)
    return bytes(raw)


class FakeKernel:
    def __init__(self, payload, ok=True):
        self.payload=payload
        self.ok=ok
        self.opened=[]
        self.closed=[]
        self.OpenProcess=Mock(side_effect=self._open)
        self.ReadProcessMemory=Mock(side_effect=self._read)
        self.CloseHandle=Mock(side_effect=self._close)

    def _open(self,rights,inherit,pid):
        self.opened.append((rights,inherit,pid))
        return 99

    def _read(self,handle,address,buffer,size,nread):
        self.address=address.value
        if not self.ok:
            return False
        ctypes.memmove(buffer,self.payload,len(self.payload))
        ctypes.cast(nread,ctypes.POINTER(ctypes.c_size_t)).contents.value=len(self.payload)
        return True

    def _close(self,handle):
        self.closed.append(handle)
        return True


class HandFusionTests(unittest.TestCase):
    def test_five_slots_only_and_rank_results_by_attack(self):
        recipes=[
            {"a":1,"b":2,"result":300,"validation":"extraida_sete_bancos_consistentes"},
            {"a":2,"b":1,"result":300,"validation":"extraida_sete_bancos_consistentes"},
            {"a":1,"b":3,"result":301,"validation":"observada_manualmente_no_jogo"},
            {"a":7,"b":8,"result":302},
            {"a":0,"b":2,"result":99},
        ]
        cards={300:{"name":"Fusion A","atk":2200},
               301:{"name":"Fusion B","atk":3000}}
        idx=build_fusion_index(recipes)
        self.assertEqual(len(idx[(1,2)]),1)
        rows=suggest_hand_pairs([1,2,3,4,5],idx,cards)
        self.assertEqual([x["result"] for x in rows],[301,300])
        self.assertEqual((rows[0]["slot_a"],rows[0]["slot_b"]),(1,3))
        self.assertEqual(rows[0]["validation"],"observada_manualmente_no_jogo")

    def test_duplicate_cards_are_distinct_slots(self):
        idx=build_fusion_index([{"a":4,"b":4,"result":10}])
        rows=suggest_hand_pairs([4,4,4,2,1],idx,{10:{"atk":100}})
        self.assertEqual(len(rows),3)
        self.assertEqual([(x["slot_a"],x["slot_b"]) for x in rows],
                         [(1,2),(1,3),(2,3)])

    def test_invalid_hand_shows_no_fusions(self):
        idx=build_fusion_index([{"a":1,"b":2,"result":3}])
        for sample in (None,[],[1,2,3,4],[0,1,2,3,4],[1,2,3,4,723]):
            self.assertEqual(suggest_hand_pairs(sample,idx,{}),[])

    def test_ram_reads_only_validated_140_bytes(self):
        hand=[34,100,200,15,700]
        kernel=FakeKernel(fake_hand(hand))
        result=read_hand_from_epsxe(kernel=kernel,pids=[1234])
        self.assertTrue(result["ready"])
        self.assertEqual(result["hand_ids"],hand)
        self.assertEqual(result["pid"],1234)
        self.assertEqual(kernel.address,HAND_ADDRESS)
        self.assertEqual(kernel.closed,[99])
        self.assertFalse(kernel.opened[0][1])

    def test_failure_does_not_retain_stale_hand(self):
        bad=bytearray(fake_hand([1,2,3,4,5]))
        struct.pack_into("<I",bad,12,99)
        for kernel in (FakeKernel(bytes(bad)),FakeKernel(b"bad",ok=False)):
            result=read_hand_from_epsxe(kernel=kernel,pids=[1234])
            self.assertFalse(result["ready"])
            self.assertIsNone(result["hand_ids"])
            self.assertEqual(kernel.closed,[99])

    def test_process_ambiguity_does_not_guess(self):
        result=read_hand_from_epsxe(kernel=FakeKernel(fake_hand([1]*5)),
                                    pids=[10,11])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["pid"])
        result=read_hand_from_epsxe(kernel=FakeKernel(fake_hand([1]*5)),
                                    preferred_pid=11,pids=[10,11])
        self.assertTrue(result["ready"])


if __name__=="__main__":
    unittest.main()
