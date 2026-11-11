"""Version-agnostic ePSXe Windows RAM regression tests, no real emulator.

These tests prove the memory signature discovery mechanism, NOT that every
individual ePSXe release has been tested in game. Incompatible layouts
must fail closed without invented hand, rank, ISO or opponent identity.
"""
from __future__ import annotations

import ctypes
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_epsxe_memory import (
    HAND_BYTES,HAND_OFFSET, MEMORY_BASIC_INFORMATION,
    discover_hand_addresses,choose_stable_hand,readable_regions,
    probe_region_hand_anchors,
)
from dueltrace_live_hand import (
    HAND_ADDRESS, is_epsxe_process_name, read_hand_from_epsxe,
    _PID_HAND_ADDRESS_CACHE, _LAST_FAILED_SCAN, _PID_SCAN_PROGRESS,
    _PID_PENDING_HANDS, _PID_CONFIRMED_READ_FAILURES,
)


def hand_blob(ids):
    raw=bytearray(HAND_BYTES)
    for i,cid in enumerate(ids):
        struct.pack_into("<H",raw,i*28,cid)
        struct.pack_into("<I",raw,i*28+12,i)
    return bytes(raw)


class MappedKernel:
    """Synthetic VirtualQueryEx and ReadProcessMemory (read-only)."""
    def __init__(self,base: int, data: bytes):
        self.base=base
        self.data=data
        self.read_addresses=[]
        self.opened=[]
        self.closed=[]
        self.OpenProcess=Mock(side_effect=self._open)
        self.ReadProcessMemory=Mock(side_effect=self._read)
        self.CloseHandle=Mock(side_effect=self._close)
        self.VirtualQueryEx=Mock(side_effect=self._query)

    def _open(self,mask,inherit,pid):
        self.opened.append((mask,inherit,pid))
        return 55

    def _close(self,handle):
        self.closed.append(handle)
        return True

    def _read(self,handle,address,buffer,size,nread):
        start=address.value
        self.read_addresses.append((start,size))
        rel=start-self.base
        if rel<0 or rel+size>len(self.data):
            return False
        ctypes.memmove(buffer,self.data[rel:rel+size],size)
        ctypes.cast(nread,ctypes.POINTER(ctypes.c_size_t)).contents.value=size
        return True

    def _query(self,handle,address,out,length):
        addr=address.value
        if addr < self.base:
            region_base=0x10000
            region_size=self.base-region_base
            state=0x10000
        elif addr < self.base+len(self.data):
            region_base=self.base
            region_size=len(self.data)
            state=0x1000
        else:
            return 0
        p=ctypes.cast(out,ctypes.POINTER(MEMORY_BASIC_INFORMATION))
        info=p.contents
        info.BaseAddress=region_base
        info.AllocationBase=region_base
        info.RegionSize=region_size
        info.Protect=0x04
        info.State=state
        info.Type=0x20000
        return ctypes.sizeof(MEMORY_BASIC_INFORMATION)


class EpsxeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        _PID_HAND_ADDRESS_CACHE.clear()
        _LAST_FAILED_SCAN.clear()
        _PID_SCAN_PROGRESS.clear()
        _PID_PENDING_HANDS.clear()
        _PID_CONFIRMED_READ_FAILURES.clear()
        self.addCleanup(_PID_PENDING_HANDS.clear)
        self.addCleanup(_PID_CONFIRMED_READ_FAILURES.clear)
        self.addCleanup(_PID_HAND_ADDRESS_CACHE.clear)
        self.addCleanup(_LAST_FAILED_SCAN.clear)
        self.addCleanup(_PID_SCAN_PROGRESS.clear)

    def test_known_ePSXe_filename_styles_without_accepting_other_emulators(self):
        for name in (
            "ePSXe.exe","EPSXE.EXE","ePSXe1.9.25.exe","ePSXe-2.0.5.exe",
            "ePSXe_205.exe","ePSXe 2.0.18.exe","epsxe-v2.0.18.exe",
            "ePSXe_x64.exe","ePSXe2.exe",
        ):
            with self.subTest(allowed=name):
                self.assertTrue(is_epsxe_process_name(name))
        for name in (
            "duckstation.exe","PCSX2.exe","epsxemalware.exe",
            "epsxe-evil.exe","C:/Games/ePSXe.exe","epsxe.exe.bat",
            "epsxe.dll","",None,"ePSXe\\evil.exe",
        ):
            with self.subTest(rejected=name):
                self.assertFalse(is_epsxe_process_name(name))

    def test_scanner_finds_hand_at_unaligned_unknown_module_base(self):
        # The PS1 RAM base is deliberately NOT 64KB-aligned (typical PE .data).
        for base in (0x5659A0,0x1580A020,0x12340A579A0):
            with self.subTest(base=hex(base)):
                hand_host=base+HAND_OFFSET
                region_start=hand_host-0x90000
                memory=bytearray(0x200000)
                cards=[449,145,447,629,468]
                offset=hand_host-region_start
                memory[offset:offset+HAND_BYTES]=hand_blob(cards)
                kernel=MappedKernel(region_start,bytes(memory))
                regions=readable_regions(kernel,55)
                self.assertEqual(regions,[(region_start,len(memory))])
                def reader(address,size):
                    rel=address-region_start
                    if rel<0 or rel+size>len(memory):
                        return None
                    return bytes(memory[rel:rel+size])
                found=discover_hand_addresses(reader,regions)
                self.assertEqual(found,[hand_host])
                self.assertEqual(
                    choose_stable_hand(reader,found)["hand_ids"],cards)
                self.assertNotEqual(hand_host,HAND_ADDRESS)

    def test_ePSXe_old_and_new_layouts_are_read_without_fixed_address(self):
        for pid,base in ((19025,0x5659A0),(2018,0x162A579A0)):
            with self.subTest(epsxe_pid=pid):
                _PID_HAND_ADDRESS_CACHE.clear()
                hand_host=base+HAND_OFFSET
                region=hand_host-0xA0000
                image=bytearray(0x200000)
                cards=[461,16,635,10,123]
                image[hand_host-region:hand_host-region+HAND_BYTES]=hand_blob(cards)
                kernel=MappedKernel(region,bytes(image))
                sample=read_hand_from_epsxe(kernel=kernel,pids=[pid],monotonic=lambda:100.0)
                self.assertFalse(sample["ready"])
                self.assertIsNone(sample["hand_ids"])
                self.assertNotIn(pid,_PID_HAND_ADDRESS_CACHE)
                self.assertIn(hand_host,_PID_PENDING_HANDS[pid])

                # A genuine hand change during a subsequent game turn proves
                # the address is active. Two immediate static reads never do.
                next_cards=[449,145,447,629,469]
                image[hand_host-region:hand_host-region+HAND_BYTES]=hand_blob(next_cards)
                kernel.data=bytes(image)
                observed=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                              monotonic=lambda:100.5)
                self.assertTrue(observed["ready"],observed)
                self.assertEqual(observed["hand_ids"],next_cards)
                self.assertEqual(observed["ramLayout"],"dynamic")
                self.assertEqual(_PID_HAND_ADDRESS_CACHE[pid],hand_host)
                self.assertEqual(kernel.closed,[55,55])
                self.assertFalse(kernel.opened[0][1])
                self.assertFalse(hasattr(kernel,"WriteProcessMemory"))

                # Now the proven mapping is read with only two 140-byte
                # samples; there is no need to scan process memory again.
                kernel.read_addresses.clear()
                before=kernel.VirtualQueryEx.call_count
                again=read_hand_from_epsxe(kernel=kernel,pids=[pid])
                self.assertEqual(again["hand_ids"],next_cards)
                self.assertEqual(kernel.VirtualQueryEx.call_count,before)
                self.assertEqual(kernel.read_addresses,[(hand_host,HAND_BYTES)]*2)

    def test_ambiguous_hand_signatures_fail_closed(self):
        base=0x500000
        data=bytearray(0x300000)
        hand=hand_blob([1,2,3,4,5])
        for start in (0x110000,0x190000):
            data[start:start+HAND_BYTES]=hand
        kernel=MappedKernel(base,bytes(data))
        result=read_hand_from_epsxe(kernel=kernel,pids=[445],
                                   candidate_addresses=[
                                       base+0x110000,base+0x190000])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["hand_ids"])
        self.assertIn("Múltiplos candidatos",result["status"])
        self.assertNotIn(445,_PID_HAND_ADDRESS_CACHE)

    def test_stale_mappings_never_expose_previous_hand(self):
        pid=21925
        base=0x500000
        hand_host=base+HAND_OFFSET
        memory=bytearray(0x200000)
        memory[HAND_OFFSET:HAND_OFFSET+HAND_BYTES]=hand_blob([1,2,3,4,5])
        kernel=MappedKernel(base,bytes(memory))
        first=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                   monotonic=lambda:100.0)
        self.assertFalse(first["ready"])
        memory[HAND_OFFSET:HAND_OFFSET+HAND_BYTES]=hand_blob([1,2,3,4,6])
        kernel.data=bytes(memory)
        second=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                    monotonic=lambda:100.5)
        self.assertTrue(second["ready"])
        self.assertEqual(second["hand_ids"],[1,2,3,4,6])
        kernel.data=bytes(len(memory))
        transient=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                      monotonic=lambda:101.0)
        self.assertFalse(transient["ready"])
        self.assertIsNone(transient["hand_ids"])
        lost=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                 monotonic=lambda:106.0)
        self.assertFalse(lost["ready"])
        self.assertIsNone(lost["hand_ids"])
        self.assertNotIn(pid,_PID_HAND_ADDRESS_CACHE)

    def test_resumable_scan_finds_hand_beyond_first_read_budget(self):
        size=0x280000
        region_start=0x600000
        memory=bytearray(size)
        hand_offset=0x1D2345
        hand=[449,145,447,629,468]
        memory[hand_offset:hand_offset+HAND_BYTES]=hand_blob(hand)
        reader=lambda address, count: (
            bytes(memory[address-region_start:address-region_start+count])
            if region_start<=address and address+count<=region_start+size
            else None)
        regions=[(region_start,size)]
        state=None
        attempts=0
        while True:
            page=discover_hand_addresses(
                reader,regions,budget=512*1024,
                cursor=state,report_progress=True)
            self.assertLessEqual(page["scanned_bytes"],512*1024)
            attempts+=1
            if page["addresses"]:
                self.assertEqual(page["addresses"],[region_start+hand_offset])
                self.assertEqual(
                    choose_stable_hand(reader,page["addresses"])["hand_ids"],hand)
                break
            self.assertFalse(page["completed"],"A busca reiniciou antes da região real")
            self.assertIsNotNone(page["cursor"])
            self.assertNotEqual(state,page["cursor"])
            state=page["cursor"]
            self.assertLess(attempts,12)
        self.assertGreater(attempts,2)

    def test_reader_continues_next_scan_instead_of_starting_over(self):
        from dueltrace_epsxe_memory import discover_hand_addresses as actual_scan
        pid=59025
        base=0x600000
        image=bytearray(0x280000)
        actual_offset=0x1D2345
        cards=[461,16,635,10,123]
        image[actual_offset:actual_offset+HAND_BYTES]=hand_blob(cards)
        kernel=MappedKernel(base,bytes(image))
        # Bound this test's page to 1 MiB to reproduce the previous
        # problem without allocating or reading 50+ MiB in CI.
        def page(reader,regions,**kw):
            return actual_scan(reader,regions,budget=1024*1024,**kw)
        with patch("dueltrace_live_hand.discover_hand_addresses",side_effect=page):
            first=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                       monotonic=lambda:100.0)
            self.assertFalse(first["ready"])
            self.assertIn("continua",first["status"])
            self.assertIn(pid,_PID_SCAN_PROGRESS)
            checkpoint=_PID_SCAN_PROGRESS[pid][1]
            self.assertGreater(checkpoint[1],0)
            kernel.read_addresses.clear()
            second=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                        monotonic=lambda:106.0)
            self.assertFalse(second["ready"],second)
            self.assertIsNone(second["hand_ids"])
            self.assertIn(base+actual_offset,_PID_PENDING_HANDS[pid])
            # The next real hand change, not two static reads, confirms RAM.
            updated=[461,16,635,10,124]
            image[actual_offset:actual_offset+HAND_BYTES]=hand_blob(updated)
            kernel.data=bytes(image)
            third=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                       monotonic=lambda:106.5)
        self.assertTrue(third["ready"],third)
        self.assertEqual(third["hand_ids"],updated)
        self.assertNotIn(pid,_PID_SCAN_PROGRESS)
        self.assertEqual(_PID_HAND_ADDRESS_CACHE[pid],base+actual_offset)
        # No rescan of region start: only probes, legacy and continuation.
        self.assertFalse(any(
            address==base and length>=1024*1024
            for address,length in kernel.read_addresses))

    def test_small_anchor_probes_find_playstation_ram_fast(self):
        base=0x700000
        mem=bytearray(0x200000)
        cards=[1,2,3,4,5]
        mem[HAND_OFFSET:HAND_OFFSET+HAND_BYTES]=hand_blob(cards)
        def reader(address,length):
            pos=address-base
            return bytes(mem[pos:pos+length]) if (
                0<=pos and pos+length<=len(mem)) else None
        matches=probe_region_hand_anchors(reader,[(base,len(mem))])
        self.assertEqual(matches,[base+HAND_OFFSET])
        self.assertEqual(choose_stable_hand(reader,matches)["hand_ids"],cards)

    def test_static_fake_hand_is_not_cached_and_live_hand_wins(self):
        pid=3432
        base=0x700000
        static_offset=0x150000
        live_offset=0x1B0000
        image=bytearray(0x300000)
        static=[16,33,77,145,449]
        live=[12,44,66,88,100]
        image[static_offset:static_offset+HAND_BYTES]=hand_blob(static)
        image[live_offset:live_offset+HAND_BYTES]=hand_blob(live)
        kernel=MappedKernel(base,bytes(image))
        early=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                  candidate_addresses=[base+static_offset,
                                                       base+live_offset],
                                  monotonic=lambda:100)
        self.assertFalse(early["ready"])
        self.assertIsNone(early["hand_ids"])
        self.assertIn(base+static_offset,_PID_PENDING_HANDS[pid])
        self.assertIn(base+live_offset,_PID_PENDING_HANDS[pid])
        self.assertNotIn(pid,_PID_HAND_ADDRESS_CACHE)

        # A static decoy can survive hundreds of valid reads. It must never
        # win over the copy that actually changes when the player draws.
        unchanged=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                       candidate_addresses=[],
                                       monotonic=lambda:105)
        self.assertFalse(unchanged["ready"])
        self.assertNotIn(pid,_PID_HAND_ADDRESS_CACHE)

        new_hand=[12,44,66,88,101]
        image[live_offset:live_offset+HAND_BYTES]=hand_blob(new_hand)
        kernel.data=bytes(image)
        proven=read_hand_from_epsxe(kernel=kernel,pids=[pid],
                                    candidate_addresses=[],monotonic=lambda:110)
        self.assertTrue(proven["ready"],proven)
        self.assertEqual(proven["hand_ids"],new_hand)
        self.assertEqual(_PID_HAND_ADDRESS_CACHE[pid],base+live_offset)

    def test_multiple_changing_copies_are_not_silently_selected(self):
        pid=3555
        base=0x600000
        memory=bytearray(0x300000)
        a,b=0x110000,0x1A0000
        for off in (a,b):
            memory[off:off+HAND_BYTES]=hand_blob([1,2,3,4,5])
        kernel=MappedKernel(base,bytes(memory))
        first=read_hand_from_epsxe(
            kernel=kernel,pids=[pid],
            candidate_addresses=[base+a,base+b],monotonic=lambda:100)
        self.assertFalse(first["ready"])
        for off in (a,b):
            memory[off:off+HAND_BYTES]=hand_blob([1,2,3,4,6])
        kernel.data=bytes(memory)
        second=read_hand_from_epsxe(
            kernel=kernel,pids=[pid],candidate_addresses=[],
            monotonic=lambda:101)
        self.assertFalse(second["ready"])
        self.assertIn("ambíguo",second["status"])
        self.assertNotIn(pid,_PID_HAND_ADDRESS_CACHE)

    def test_scan_bounds_reject_unlimited_read_and_spurious_data(self):
        reads=[]
        def reader(addr,length):
            reads.append(length)
            return bytes(length)
        regions=[(0x40000000,0x3000000)]
        result=discover_hand_addresses(reader,regions,budget=1024*1024)
        self.assertEqual(result,[])
        self.assertLessEqual(sum(reads),1024*1024)
        with self.assertRaises(ValueError):
            discover_hand_addresses(reader,regions,budget=10**15)
        self.assertEqual(choose_stable_hand(reader,list(range(130)))["status"],
                         "too_many_candidates")


if __name__=="__main__":
    unittest.main()
