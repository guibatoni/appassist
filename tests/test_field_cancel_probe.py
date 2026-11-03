"""Testes sintéticos do controle negativo CANCELADA e do monitor direcionado."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from field_ram_probe import FieldMemoryProbe, SEARCH_START, SEARCH_SIZE, CHUNK_SIZE, HAND_ADDR
from field_cancel_probe import (
    FOCUS_CHUNK, FOCUS_FROM, FOCUS_TO, focus_watch_values,
    focus_phase_differences, cancelled_preparation_analysis,
)


def make_hand(ids):
    b=bytearray(140)
    for i,v in enumerate(ids):
        struct.pack_into("<H",b,28*i,v)
        struct.pack_into("<I",b,28*i+12,i)
    return bytes(b)


class FakeReadOnly:
    def __init__(self,focused_region=True):
        self.pid=9494
        self.hand=make_hand([291,159,16,635,192])
        self.chunks={
            a:bytearray(CHUNK_SIZE)
            for a in range(SEARCH_START, SEARCH_START+SEARCH_SIZE, CHUNK_SIZE)
        }
        if focused_region:
            self.chunks[FOCUS_CHUNK]=bytearray(CHUNK_SIZE)
        self.calls=[]

    def read(self,address,size):
        self.calls.append((address,size))
        if address==HAND_ADDR and size==140:
            return self.hand
        if size==CHUNK_SIZE and address in self.chunks:
            return bytes(self.chunks[address])
        raise OSError("unreadable")

    def write(self,*args):
        raise AssertionError("RAM somente leitura")

    def put_u8(self,address,value):
        start=address & ~(CHUNK_SIZE-1)
        self.chunks[start][address-start]=value

    def put_u16(self,address,value):
        self.put_u8(address,value&255)
        self.put_u8(address+1,value>>8)


class CancelledProbeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.reader=FakeReadOnly()
        self.probe=FieldMemoryProbe(
            lambda:self.reader,self.root,expanded=False,focused=True)
        self.sha="b"*64

    def test_negative_control_has_3_phases_and_cannot_become_summon(self):
        before=self.probe.capture_before(self.sha,291,user_slot=2)
        self.assertEqual(before["readable_chunks"],25)
        self.assertEqual(before["unreadable_chunks"],[])
        self.assertEqual(
            sum(a==FOCUS_CHUNK and b==CHUNK_SIZE for a,b in self.reader.calls),1)
        # Preparacao mostra ID no registro candidato da segunda posicao.
        self.reader.put_u16(0xBFF52C,291)
        self.reader.put_u8(0xBFF6B3,255)
        self.reader.put_u8(0xC3920C,1)
        pre=self.probe.capture_prepared(self.sha,face_state="faceup")
        self.assertEqual(pre["phase"],"PREPARADA_INFORMADA_PELO_USUARIO")
        # Cancela sem setar. O ID fica no buffer, enquanto flags retornam.
        self.reader.put_u8(0xBFF6B3,0)
        self.reader.put_u8(0xC3920C,0)
        report,path=self.probe.capture_cancelled(self.sha,user_slot=2)
        self.assertTrue(path.is_file())
        self.assertIn("CANCELADA",path.name)
        self.assertEqual(report["type"],"CONTROLE_CANCELAMENTO_CAMPO_RAM")
        self.assertIsNone(report["after_summon"])
        self.assertTrue(report["observed_by_user"]["cancellation_confirmed_visually"])
        self.assertFalse(report["observed_by_user"]["card_placed_on_board"])
        self.assertEqual(report["before"]["hand_ids"],[291,159,16,635,192])
        self.assertTrue(report["hand_analysis"]["hand_unchanged_after_cancel"])
        diff=report["negative_control_analysis"]
        self.assertGreaterEqual(diff["prepared_changes"],3)
        self.assertGreaterEqual(diff["restored_after_cancel"],2)
        self.assertGreaterEqual(diff["persisted_after_cancel"],1)
        self.assertFalse(diff["field_slot_verified"])
        self.assertFalse(diff["occupancy_verified"])
        self.assertEqual(report["scan"]["focused_extra_chunk"],"0x00C39000")
        self.assertEqual(report["targeted_ram_monitor"]["prepared"]["watch_values"][
            next(i for i,x in enumerate(focus_watch_values({}))
                 if x["address"]=="0x00C3920C")]["u8"],1)
        self.assertEqual(report["targeted_ram_monitor"]["cancelled"]["watch_values"][
            next(i for i,x in enumerate(focus_watch_values({}))
                 if x["address"]=="0x00C3920C")]["u8"],0)
        self.assertEqual(report["hypothetical_slot_probe"]["cancelled"][1]["u16_le"],291)
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertIsNone(report["duel_field_card_ids"])
        self.assertFalse(report["fusion_catalog_changed"])
        saved=path.read_text(encoding="utf-8")
        self.assertNotIn('"chunks":',saved)
        self.assertNotIn('"hex":',saved)
        self.assertNotIn('"after_summon": {',saved)
        self.assertEqual(json.loads(saved)["type"],report["type"])
        with self.assertRaisesRegex(RuntimeError,"cancelada|cancelado"):
            self.probe.capture_after(self.sha,user_slot=2)
        with self.assertRaises(RuntimeError):
            self.probe.capture_cancelled(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_prepared(self.sha)
        self.probe.capture_before(self.sha,291,user_slot=2)
        self.probe.capture_prepared(self.sha)
        normal,_=self.probe.capture_after(self.sha,user_slot=2)
        self.assertEqual(normal["type"],"DIAGNOSTICO_CAMPO_RAM")

    def test_cancelled_require_prepared_and_same_pid_and_slot(self):
        with self.assertRaisesRegex(RuntimeError,"ANTES"):
            self.probe.capture_cancelled(self.sha,user_slot=1)
        with self.assertRaises(ValueError):
            self.probe.capture_before(self.sha,291,user_slot=6)
        self.probe.capture_before(self.sha,291,user_slot=1)
        with self.assertRaisesRegex(RuntimeError,"PREPARADA"):
            self.probe.capture_cancelled(self.sha,user_slot=1)
        self.probe.capture_prepared(self.sha)
        with self.assertRaises(ValueError):
            self.probe.capture_cancelled(self.sha,user_slot=2)
        self.reader.pid=9090
        with self.assertRaisesRegex(RuntimeError,"PID"):
            self.probe.capture_cancelled(self.sha,user_slot=1)
        self.reader.pid=9494
        report,_=self.probe.capture_cancelled(self.sha,user_slot=1)
        self.assertEqual(report["observed_by_user"]["slot_position_1_to_5"],1)

    def test_cancelled_cannot_happen_after_summon(self):
        self.probe.capture_before(self.sha,291,user_slot=1)
        self.probe.capture_prepared(self.sha)
        self.probe.capture_after(self.sha,user_slot=1)
        with self.assertRaisesRegex(RuntimeError,"NA MESA"):
            self.probe.capture_cancelled(self.sha,user_slot=1)

    def test_focus_capture_normal_report_and_unchanged_versions(self):
        self.probe.capture_before(self.sha,291,user_slot=1)
        self.reader.put_u8(0xC3920C,1)
        self.probe.capture_prepared(self.sha)
        report,path=self.probe.capture_after(self.sha,user_slot=1)
        self.assertEqual(report["schema"],2)
        self.assertTrue(path.is_file())
        self.assertTrue(report["scan"]["focused_enabled"])
        self.assertEqual(report["scan"]["size_bytes"],SEARCH_SIZE)
        self.assertTrue(report["targeted_ram_monitor"]["prepared"]["watch_values"])
        self.probe.capture_occupied_control(self.sha)
        self.reader.put_u8(0xC3920C,0)
        r,_=self.probe.capture_removed(self.sha)
        self.assertEqual(r["targeted_ram_monitor"]["removed"]["watch_values"][
            next(i for i,x in enumerate(focus_watch_values({}))
                 if x["address"]=="0x00C3920C")]["u8"],0)
        self.assertEqual(r["targeted_ram_monitor"]["focus_set_to_removed"][
            "changed_bytes"],1)
        r,_=self.probe.capture_vacant_control(self.sha)
        self.assertIsNotNone(r["targeted_ram_monitor"]["vacant_control"])
        self.assertFalse(r["duel_field_ram_verified"])

    def test_unreadable_focus_returns_null_not_false_card(self):
        other=FakeReadOnly(focused_region=False)
        p=FieldMemoryProbe(lambda:other,self.root,focused=True)
        b=p.capture_before(self.sha,291,user_slot=1)
        self.assertEqual(b["readable_chunks"],24)
        self.assertEqual(len(b["unreadable_chunks"]),1)
        p.capture_prepared(self.sha)
        report,path=p.capture_cancelled(self.sha)
        self.assertIsNone(report["targeted_ram_monitor"]["before"]["watch_values"][
            next(i for i,x in enumerate(focus_watch_values({}))
                 if x["address"]=="0x00C3920C")]["u8"])
        self.assertEqual(report["negative_control_analysis"][
            "focus_before_to_prepared"]["compared_bytes"],0)
        self.assertTrue(path.is_file())

    def test_negative_control_categories_are_observational_only(self):
        addr=0xC3920C
        index=addr-FOCUS_CHUNK
        def make(value):
            block=bytearray(CHUNK_SIZE)
            block[index]=value
            return {FOCUS_CHUNK:bytes(block)}
        result=cancelled_preparation_analysis(make(0),make(1),make(2))
        self.assertEqual(result["different_after_cancel"],1)
        self.assertEqual(result["restored_after_cancel"],0)
        self.assertFalse(result["field_slot_verified"])
        self.assertEqual(result["focus_prepared_to_cancelled"]["changed_bytes"],1)
        with self.assertRaises(ValueError):
            FieldMemoryProbe(lambda:self.reader,self.root,focused=1)


if __name__=="__main__":
    unittest.main()
