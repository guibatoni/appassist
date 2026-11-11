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
    _PID_HAND_ADDRESS_CACHE, _PID_PENDING_HANDS, _PID_SCAN_PROGRESS,
    _PID_CONFIRMED_READ_FAILURES, _LAST_FAILED_SCAN,
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
    def setUp(self):
        for cache in (_PID_HAND_ADDRESS_CACHE,_PID_PENDING_HANDS,
                      _PID_SCAN_PROGRESS,_PID_CONFIRMED_READ_FAILURES,
                      _LAST_FAILED_SCAN):
            cache.clear()
            self.addCleanup(cache.clear)

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
        result=read_hand_from_epsxe(kernel=kernel,pids=[1234],
                                    monotonic=lambda:100)
        self.assertFalse(result["ready"])
        self.assertIn("jogue uma carta",result["status"])
        self.assertIsNone(result["hand_ids"])
        # The player's next turn replaces one card.
        updated=[34,100,200,15,701]
        kernel.payload=fake_hand(updated)
        next_result=read_hand_from_epsxe(kernel=kernel,pids=[1234],
                                         monotonic=lambda:101)
        self.assertTrue(next_result["ready"],next_result)
        self.assertEqual(next_result["hand_ids"],updated)
        self.assertEqual(next_result["pid"],1234)
        self.assertEqual(kernel.address,HAND_ADDRESS)
        self.assertEqual(kernel.closed,[99,99])
        self.assertFalse(kernel.opened[0][1])

    def test_failure_does_not_retain_stale_hand(self):
        bad=bytearray(fake_hand([1,2,3,4,5]))
        struct.pack_into("<I",bad,12,99)
        for kernel in (FakeKernel(bytes(bad)),FakeKernel(b"bad",ok=False)):
            result=read_hand_from_epsxe(kernel=kernel,pids=[1234])
            self.assertFalse(result["ready"])
            self.assertIsNone(result["hand_ids"])
            self.assertEqual(kernel.closed,[99])

    def test_process_preference_is_not_silently_replaced(self):
        result=read_hand_from_epsxe(
            preferred_pid=4321,kernel=FakeKernel(fake_hand([1,2,3,4,5])),
            pids=[1234])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["hand_ids"])
        self.assertIsNone(result["pid"])

    def test_second_snapshot_changed_during_read_is_discarded(self):
        kernel=FakeKernel(fake_hand([1,2,3,4,5]))
        first=fake_hand([1,2,3,4,5])
        changed=fake_hand([1,2,6,4,5])
        samples=iter((first,changed))
        def read_different(_handle,_addr,buffer,_size,nread):
            blob=next(samples)
            ctypes.memmove(buffer,blob,len(blob))
            ctypes.cast(nread,ctypes.POINTER(ctypes.c_size_t)).contents.value=len(blob)
            return True
        kernel.ReadProcessMemory.side_effect=read_different
        result=read_hand_from_epsxe(kernel=kernel,pids=[1234])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["hand_ids"])
        self.assertIn("não localizada",result["status"])
        self.assertEqual(kernel.ReadProcessMemory.call_count,2)
        self.assertEqual(kernel.closed,[99])

    def test_process_disappearance_invalidates_all_cached_ram(self):
        kernel=FakeKernel(fake_hand([1,2,3,4,5]))
        read_hand_from_epsxe(kernel=kernel,pids=[567],monotonic=lambda:100)
        kernel.payload=fake_hand([1,2,3,4,6])
        self.assertTrue(read_hand_from_epsxe(
            kernel=kernel,pids=[567],monotonic=lambda:101)["ready"])
        self.assertIn(567,_PID_HAND_ADDRESS_CACHE)
        lost=read_hand_from_epsxe(kernel=kernel,pids=[])
        self.assertFalse(lost["ready"])
        self.assertIsNone(lost["hand_ids"])
        self.assertEqual(_PID_HAND_ADDRESS_CACHE,{})
        self.assertEqual(_PID_PENDING_HANDS,{})

    def test_process_ambiguity_does_not_guess(self):
        result=read_hand_from_epsxe(kernel=FakeKernel(fake_hand([1]*5)),
                                    pids=[10,11])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["pid"])
        kernel=FakeKernel(fake_hand([1]*5))
        result=read_hand_from_epsxe(kernel=kernel,
                                    preferred_pid=11,pids=[10,11],
                                    monotonic=lambda:100)
        self.assertFalse(result["ready"])
        kernel.payload=fake_hand([1,1,1,1,2])
        next_result=read_hand_from_epsxe(kernel=kernel,
                                         preferred_pid=11,pids=[10,11],
                                         monotonic=lambda:101)
        self.assertTrue(next_result["ready"])
        self.assertEqual(next_result["hand_ids"],[1,1,1,1,2])


@unittest.skipUnless(sys.platform=="win32","Requer sessão gráfica Windows")
class HomeWindowSmokeTests(unittest.TestCase):
    def test_home_renders_five_cards_and_refreshes_fusion_results(self):
        import tempfile
        import tkinter as tk
        from auto_mods import ModCatalog
        from dueltrace_desktop import DueltraceDesktop
        with tempfile.TemporaryDirectory() as td:
            try:
                app=DueltraceDesktop(catalog=ModCatalog(Path(td)))
            except tk.TclError as exc:
                if "display" in str(exc).lower():
                    self.skipTest(str(exc))
                raise
            try:
                app.withdraw()
                app.update_idletasks()
                self.assertEqual(app.active_page,"inicio")
                self.assertEqual(len(app.home_hand_tiles),5)
                app._home_cards={
                    1:{"id":1,"name":"Material A","atk":100,"def":200},
                    2:{"id":2,"name":"Material B","atk":300,"def":400},
                    3:{"id":3,"name":"Material C","atk":500,"def":600},
                    5:{"id":5,"name":"Material E","atk":800,"def":900},
                    10:{"id":10,"name":"Resultado","atk":2500,"def":1000},
                }
                app._home_fusions=build_fusion_index([
                    {"a":1,"b":2,"result":10,
                     "validation":"extraida_sete_bancos_consistentes"},
                ])
                app._render_live_hand({
                    "ready":True,"hand_ids":[1,2,3,5,3],"pid":1234,
                    "status":"Mão lida ao vivo",
                })
                app.update_idletasks()
                self.assertEqual(len(app.home_fusion_tree.get_children()),1)
                first=app.home_fusion_tree.item(
                    app.home_fusion_tree.get_children()[0])["values"]
                self.assertEqual(first[0],"1 + 2")
                self.assertEqual(first[-1],"ISO ×7")
                app._render_live_hand({
                    "ready":False,"hand_ids":None,"pid":None,
                    "status":"ePSXe desconectado",
                })
                self.assertEqual(len(app.home_fusion_tree.get_children()),0)
                self.assertTrue(all(tile.card is None for tile in app.home_hand_tiles))
            finally:
                app.destroy()


if __name__=="__main__":
    unittest.main()
