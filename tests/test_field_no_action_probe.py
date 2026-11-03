"""Regressões do protocolo SEM AÇÃO, evitando simular cancelamento impossível."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from field_ram_probe import FieldMemoryProbe, HAND_ADDR, SEARCH_START, SEARCH_SIZE, CHUNK_SIZE
from field_cancel_probe import FOCUS_CHUNK


def hand_bytes(ids):
    import struct
    result=bytearray(140)
    for i,card in enumerate(ids):
        struct.pack_into("<H",result,i*28,card)
        struct.pack_into("<I",result,i*28+12,i)
    return bytes(result)


class FakeReader:
    def __init__(self,with_focus=True):
        self.pid=707
        self.hand=hand_bytes([291,65,10,547,192])
        self.chunks={
            base:bytearray(CHUNK_SIZE)
            for base in range(SEARCH_START,SEARCH_START+SEARCH_SIZE,CHUNK_SIZE)
        }
        if with_focus:self.chunks[FOCUS_CHUNK]=bytearray(CHUNK_SIZE)
        self.reads=[]
    def read(self,addr,size):
        self.reads.append((addr,size))
        if addr==HAND_ADDR and size==140:return self.hand
        if size==CHUNK_SIZE and addr in self.chunks:return bytes(self.chunks[addr])
        raise OSError("indisponivel")
    def write(self,*args,**kwargs):
        raise AssertionError("Nunca escrever na RAM")
    def byte(self,addr,value):
        self.chunks[addr & ~(CHUNK_SIZE-1)][addr%CHUNK_SIZE]=value


class NoActionControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader=FakeReader()
        self.sha="f"*64
        self.probe=FieldMemoryProbe(
            lambda:self.reader,Path(self.temp.name),focused=True)

    def test_no_action_does_not_require_faceup_preparation_or_cancellation(self):
        before=self.probe.capture_before(self.sha,291,user_slot=1)
        self.assertEqual(before["readable_chunks"],25)
        report,path=self.probe.capture_no_action(self.sha,user_slot=1)
        self.assertTrue(path.is_file())
        self.assertIn("SEM_ACAO",path.name)
        self.assertEqual(report["type"],"CONTROLE_SEM_ACAO_CAMPO_RAM")
        self.assertIsNone(report["after_preparation"])
        self.assertIsNone(report["after_summon"])
        self.assertFalse(report["observed_by_user"]["card_placed_on_board"])
        self.assertTrue(report["hand_analysis"]["hand_ids_unchanged"])
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertFalse(report["fusion_catalog_changed"])
        self.assertIsNone(report["duel_field_card_ids"])
        diff=report["no_action_analysis"]
        self.assertEqual(diff["before_to_no_action"]["changed_bytes"],0)
        self.assertEqual(diff["focus_before_to_no_action"]["changed_bytes"],0)
        self.assertEqual(diff["watched_changed_values"],[])
        saved=path.read_text(encoding="utf-8")
        self.assertNotIn('"chunks"',saved)
        self.assertNotIn('"hex"',saved)
        self.assertEqual(json.loads(saved)["type"],"CONTROLE_SEM_ACAO_CAMPO_RAM")
        with self.assertRaisesRegex(RuntimeError,"SEM AÇÃO"):
            self.probe.capture_after(self.sha,user_slot=1)
        with self.assertRaisesRegex(RuntimeError,"SEM AÇÃO"):
            self.probe.capture_prepared(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_no_action(self.sha)
        # Novas capturas reais nao ficam bloqueadas depois de reiniciar.
        self.probe.capture_before(self.sha,291,user_slot=1)
        self.probe.capture_prepared(self.sha,face_state="faceup")
        real,_=self.probe.capture_after(self.sha,user_slot=1)
        self.assertEqual(real["type"],"DIAGNOSTICO_CAMPO_RAM")

    def test_no_action_detects_memory_volatility_without_labeling_field(self):
        self.probe.capture_before(self.sha,291,user_slot=2)
        self.reader.byte(0xC39234,1)  # mudanca sem nenhuma invocacao
        self.reader.byte(0xBFF6B3,255)
        report,_=self.probe.capture_no_action(self.sha,user_slot=2)
        d=report["no_action_analysis"]
        self.assertEqual(d["before_to_no_action"]["changed_bytes"],2)
        self.assertEqual(d["focus_before_to_no_action"]["changed_bytes"],1)
        self.assertEqual(len(d["watched_changed_values"]),2)
        self.assertFalse(d["occupancy_verified"])
        self.assertTrue(all(not x["field_slot_verified"] for x in d["watched_changed_values"]))
        self.assertFalse(report["hypothetical_slot_probe"]["field_slot_verified"])

    def test_requires_before_unchanged_session_slot_and_no_prepared(self):
        with self.assertRaisesRegex(RuntimeError,"ANTES"):
            self.probe.capture_no_action(self.sha,user_slot=1)
        self.probe.capture_before(self.sha,291,user_slot=1)
        with self.assertRaisesRegex(ValueError,"slot mudou"):
            self.probe.capture_no_action(self.sha,user_slot=2)
        self.reader.pid=708
        with self.assertRaisesRegex(RuntimeError,"PID"):
            self.probe.capture_no_action(self.sha,user_slot=1)
        self.reader.pid=707
        self.probe.capture_prepared(self.sha)
        with self.assertRaisesRegex(RuntimeError,"PREPARADA"):
            self.probe.capture_no_action(self.sha,user_slot=1)

    def test_focus_unreadable_is_null_and_1mib_nonfocus_remains_optional(self):
        r=FakeReader(with_focus=False)
        p=FieldMemoryProbe(lambda:r,Path(self.temp.name),focused=True)
        initial=p.capture_before(self.sha,291,user_slot=2)
        self.assertEqual(initial["readable_chunks"],24)
        self.assertEqual(len(initial["unreadable_chunks"]),1)
        report,_=p.capture_no_action(self.sha,user_slot=2)
        self.assertIsNone(next(x["u8"] for x in report["targeted_ram_monitor"]["after_no_action"]["watch_values"]
                             if x["address"]=="0x00C39234") if "after_no_action" in report["targeted_ram_monitor"] else
                          next(x["u8"] for x in report["targeted_ram_monitor"]["no_action"]["watch_values"]
                               if x["address"]=="0x00C39234"))
        self.assertEqual(report["no_action_analysis"]["focus_before_to_no_action"]["compared_bytes"],0)
        basic=FieldMemoryProbe(lambda:r,Path(self.temp.name),focused=False)
        basic.capture_before(self.sha,291,user_slot=2)
        report,_=basic.capture_no_action(self.sha,user_slot=2)
        self.assertIsNone(report["targeted_ram_monitor"])
        self.assertIsNone(report["scan"]["focused_extra_chunk"])


if __name__=="__main__":
    unittest.main()
