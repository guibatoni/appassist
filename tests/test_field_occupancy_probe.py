"""Testes do detector exploratório de ocupação: não valida slots da mesa."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from field_occupancy_probe import analyze_occupancy, CHUNK_SIZE
from field_ram_probe import SEARCH_START, SEARCH_SIZE, HAND_ADDR, FieldMemoryProbe


def fake_hand(ids):
    result=bytearray(140)
    for slot,card_id in enumerate(ids):
        struct.pack_into("<H",result,slot*28,card_id)
        struct.pack_into("<I",result,slot*28+12,slot)
    return bytes(result)


class ReadOnlyFake:
    def __init__(self):
        self.pid=4321
        self.hand=fake_hand([291,159,16,635,192])
        self.chunks={
            a:bytearray(CHUNK_SIZE)
            for a in range(SEARCH_START,SEARCH_START+SEARCH_SIZE,CHUNK_SIZE)
        }
        self.reads=0

    def read(self,address,size):
        self.reads+=1
        if address==HAND_ADDR and size==140:
            return self.hand
        if size==CHUNK_SIZE and address in self.chunks:
            return bytes(self.chunks[address])
        raise OSError("fora da região")

    def write(self,*args,**kwargs):
        raise AssertionError("RAM deve ser somente leitura")

    def set_byte(self,address,value):
        start=address & ~(CHUNK_SIZE-1)
        self.chunks[start][address-start]=value


class OccupancyProbeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name)
        self.reader=ReadOnlyFake()
        self.sha="a"*64
        self.probe=FieldMemoryProbe(lambda:self.reader,self.home)
        self.addr=0xBFF505
        self.volatile=0xBFF550
        self.selection_id=0xBFF510

    def test_strong_reversible_candidate_but_not_verified(self):
        self.probe.capture_before(self.sha,291)
        self.reader.set_byte(self.addr,1)
        # Esse ID é apenas um histórico, que nao volta ao valor inicial.
        self.reader.set_byte(self.selection_id,291)
        self.probe.capture_after(self.sha,user_slot=1)
        self.probe.capture_occupied_control(self.sha)
        self.reader.set_byte(self.addr,0)
        report,path=self.probe.capture_removed(self.sha)
        self.assertTrue(path.is_file())
        self.assertTrue(report["after_occupied_control"])
        a=report["occupancy_analysis"]
        self.assertEqual(a["reversible_total"],1)
        self.assertEqual(a["matched_total"],1)
        self.assertEqual(a["candidates"][0]["address"],f"0x{self.addr:08X}")
        self.assertTrue(a["candidates"][0]["returns_to_baseline"])
        self.assertTrue(a["candidates"][0]["near_hypothetical_record_for_reported_slot"])
        self.assertFalse(a["occupancy_verified"])
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertFalse(report["fusion_catalog_changed"])
        self.assertEqual(report["hypothetical_slot_probe"]["removed"][0]["u16_le"],291)
        self.probe.capture_vacant_control(self.sha)
        self.assertFalse(self.probe.report["occupancy_analysis"]["occupancy_verified"])
        report_json=path.read_text(encoding="utf-8")
        self.assertNotIn('"hex"',report_json)
        self.assertNotIn('"chunks"',report_json)

    def test_volatile_occupied_or_empty_control_is_filtered(self):
        addr=self.volatile
        before={SEARCH_START:bytes(CHUNK_SIZE)}
        # usar bloco com os endereços, sem alterar a mão conhecida
        base=addr & ~(CHUNK_SIZE-1)
        before[base]=bytes(CHUNK_SIZE)
        occ=bytearray(CHUNK_SIZE);occ[addr-base]=1
        occupied={base:bytes(occ)}
        removed={base:bytes(CHUNK_SIZE)}
        occ_guard={base:bytes(CHUNK_SIZE)}  # não fica constante em OCUPADA
        vacant_guard={base:bytes(CHUNK_SIZE)}
        a=analyze_occupancy(before,occupied,removed,observed_slot=2,
                            occupied_control=occ_guard,vacant_control=vacant_guard)
        self.assertEqual(a["matched_total"],0)
        self.assertEqual(a["discarded_due_to_unstable_controls"],1)
        b=analyze_occupancy(before,occupied,removed,observed_slot=2,
                            occupied_control=occupied,vacant_control=vacant_guard)
        self.assertEqual(b["reversible_total"],1)
        self.assertTrue(b["occupied_control_recorded"])
        self.assertTrue(b["vacant_control_recorded"])

    def test_phase_preparation_change_is_downranked(self):
        base=self.addr & ~(CHUNK_SIZE-1)
        a=bytes(CHUNK_SIZE)
        b=bytearray(CHUNK_SIZE);b[self.addr-base]=1
        a_chunks={base:a};b_chunks={base:bytes(b)}
        result=analyze_occupancy(
            a_chunks,b_chunks,a_chunks,observed_slot=1,prepared=b_chunks)
        self.assertEqual(result["matched_total"],1)
        self.assertEqual(result["potentially_preparation_related"],1)
        self.assertTrue(result["candidates"][0]["already_changed_during_preparation"])

    def test_hand_bytes_excluded_even_if_reversible(self):
        base=HAND_ADDR & ~(CHUNK_SIZE-1)
        offset=HAND_ADDR-base
        a=bytes(CHUNK_SIZE)
        b=bytearray(CHUNK_SIZE);b[offset]=1
        result=analyze_occupancy(
            {base:a},{base:bytes(b)},{base:a},observed_slot=1)
        self.assertEqual(result["matched_total"],0)

    def test_capture_order_control_and_pid_safety(self):
        with self.assertRaises(RuntimeError):
            self.probe.capture_occupied_control(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_vacant_control(self.sha)
        self.probe.capture_before(self.sha,291)
        self.probe.capture_after(self.sha,user_slot=1)
        self.reader.pid=4322
        with self.assertRaisesRegex(RuntimeError,"PID"):
            self.probe.capture_occupied_control(self.sha)
        self.reader.pid=4321
        self.probe.capture_removed(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_occupied_control(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_removed(self.sha)
        self.probe.capture_vacant_control(self.sha)

    def test_missing_removed_does_not_invent_occupancy(self):
        zero={SEARCH_START:bytes(CHUNK_SIZE)}
        report=analyze_occupancy(zero,zero,None,observed_slot=1)
        self.assertEqual(report["status"],"AGUARDANDO_REMOCAO")
        self.assertFalse(report["occupancy_verified"])
        self.assertFalse(report["field_slot_verified"])
        self.assertEqual(report["candidates"],[])
        with self.assertRaises(ValueError):
            analyze_occupancy(zero,zero,zero,observed_slot=0)


if __name__=="__main__":
    unittest.main()
