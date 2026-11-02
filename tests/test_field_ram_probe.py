"""Testes sintéticos da procura restrita da carta invocada no campo do ePSXe."""
from __future__ import annotations
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from field_ram_probe import (
    CHUNK_SIZE, HAND_ADDR, SEARCH_START, SEARCH_SIZE, FieldMemoryProbe,
    find_new_id_candidates
)

def make_hand(ids):
    b=bytearray(140)
    for i,c in enumerate(ids):
        struct.pack_into("<H",b,i*28,c)
        struct.pack_into("<I",b,i*28+12,i)
    return bytes(b)

class FakeReader:
    def __init__(self):
        self.pid=1234
        self.hand=make_hand([159,291,16,635,192])
        self.chunks={a:bytearray(CHUNK_SIZE) for a in range(
            SEARCH_START,SEARCH_START+SEARCH_SIZE,CHUNK_SIZE)}
        self.calls=[]
    def read(self,address,size):
        self.calls.append((address,size))
        if address==HAND_ADDR and size==140:
            return self.hand
        if size==CHUNK_SIZE and address in self.chunks:
            return bytes(self.chunks[address])
        raise OSError("invalid region")
    def write(self,*args):
        raise AssertionError("Never write RAM")

class FieldRamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader=FakeReader()
        self.probe=FieldMemoryProbe(lambda:self.reader,Path(self.temp.name))
        self.sha="a"*64
        self.addr=SEARCH_START+14*CHUNK_SIZE+0x50
        self.chunk=self.addr&~(CHUNK_SIZE-1)
        self.offset=self.addr-self.chunk

    def test_before_summon_removed_find_candidate_never_confirm_field(self):
        before=self.probe.capture_before(self.sha,291)
        self.assertEqual(before["hand_ids"],[159,291,16,635,192])
        self.assertEqual(before["readable_chunks"],SEARCH_SIZE//CHUNK_SIZE)
        self.reader.hand=make_hand([159,16,635,192,10])
        self.reader.chunks[self.chunk][self.offset:self.offset+2]=struct.pack("<H",291)
        report,path=self.probe.capture_after(self.sha)
        self.assertTrue(path.is_file())
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertIsNone(report["duel_field_card_ids"])
        self.assertFalse(report["fusion_catalog_changed"])
        self.assertFalse(report["emulator_iso_verified"])
        candidates=report["analysis"]["candidates"]
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]["address"],f"0x{self.addr:08X}")
        self.assertEqual(candidates[0]["after_u16"],291)
        self.assertIsNone(candidates[0]["disappeared_after_removal"])
        self.reader.chunks[self.chunk][self.offset:self.offset+2]=b"\x00\x00"
        report2,path2=self.probe.capture_removed(self.sha)
        self.assertEqual(path,path2)
        self.assertTrue(report2["analysis"]["candidates"][0]["disappeared_after_removal"])
        saved=json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(saved["analysis"]["candidates"][0]["disappeared_after_removal"])
        self.assertNotIn('"hex"',path.read_text(encoding="utf-8"))
        self.assertEqual(len(self.reader.calls),3*(1+SEARCH_SIZE//CHUNK_SIZE))

    def test_unmodified_hand_is_accepted_at_set(self):
        with self.assertRaises(ValueError):
            self.probe.capture_before(self.sha,0)
        with self.assertRaises(ValueError):
            self.probe.capture_before(self.sha,722)
        self.probe.capture_before(self.sha,291)
        report,path=self.probe.capture_after(self.sha)
        self.assertTrue(path.is_file())
        self.assertEqual(report["schema"],2)
        self.assertTrue(report["hand_state_at_set"]["target_still_visible_in_hand_ram"])
        self.assertTrue(report["hand_state_at_set"]["hand_ids_identical_to_before"])
        self.assertFalse(report["duel_field_ram_verified"])

    def test_prepared_set_before_hand_refresh_and_removed(self):
        self.probe.capture_before(self.sha,291)
        # Jogador escolhe FaceDown e Guardian Star; mão ainda está estática.
        self.reader.chunks[self.chunk][self.offset-1]=12
        prepared=self.probe.capture_prepared(self.sha,face_state="facedown")
        self.assertEqual(prepared["phase"],"PREPARADA_INFORMADA_PELO_USUARIO")
        self.assertGreater(prepared["changes_since_before"]["changed_bytes"],0)
        # Carta agora visível no slot 3; RAM da mão ainda lista o ID 291.
        self.reader.chunks[self.chunk][self.offset:self.offset+2]=struct.pack("<H",291)
        report,path=self.probe.capture_after(self.sha,face_state="facedown",user_slot=3)
        self.assertEqual(report["observed_by_user"]["slot_position_1_to_5"],3)
        self.assertEqual(report["observed_by_user"]["face_state"],"facedown")
        self.assertTrue(report["hand_state_at_set"]["target_still_visible_in_hand_ram"])
        self.assertEqual(report["after_summon"]["hand_ids"],[159,291,16,635,192])
        self.assertEqual(report["analysis"]["candidate_count_total"],1)
        self.assertIsNotNone(report["phase_differences"]["before_to_preparation"])
        self.assertGreater(report["phase_differences"]["reference_to_set"]["changed_bytes"],0)
        # Somente no turno seguinte a RAM da mão finalmente é atualizada.
        self.reader.hand=make_hand([159,16,635,192,10])
        report,path2=self.probe.capture_hand_refresh(self.sha)
        self.assertEqual(path,path2)
        self.assertTrue(report["hand_refresh_analysis"]["target_count_decreased"])
        self.assertIsNotNone(report["phase_differences"]["set_to_hand_refresh"])
        # Depois a carta é removida do campo.
        self.reader.chunks[self.chunk][self.offset:self.offset+2]=b"\x00\x00"
        report,path3=self.probe.capture_removed(self.sha)
        self.assertEqual(path3,path)
        self.assertTrue(report["analysis"]["candidates"][0]["disappeared_after_removal"])
        self.assertIsNotNone(report["phase_differences"]["set_to_removed"])
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertFalse(report["fusion_catalog_changed"])
        saved=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["after_hand_refresh"]["hand_ids"],[159,16,635,192,10])
        self.assertNotIn('"hex"',path.read_text(encoding="utf-8"))

    def test_falsely_assuming_id_is_field_is_blocked(self):
        self.probe.capture_before(self.sha,291)
        # Nenhum byte RAM mudou, mas o usuário afirma que colocou a carta.
        # O relatório não inventa uma posição nem aprova uma leitura.
        report,path=self.probe.capture_after(self.sha,face_state="faceup",user_slot=1)
        self.assertEqual(report["analysis"]["candidate_count_total"],0)
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertIsNone(report["duel_field_card_ids"])
        self.assertTrue(report["hand_state_at_set"]["target_still_visible_in_hand_ram"])
        self.assertEqual(report["phase_differences"]["before_to_set"]["changed_bytes"],0)
        with self.assertRaises(RuntimeError):
            self.probe.capture_prepared(self.sha)
        with self.assertRaises(ValueError):
            self.probe.capture_after(self.sha,user_slot=6)

    def test_same_pid_sha_must_remain(self):
        self.probe.capture_before(self.sha,291)
        self.reader.hand=make_hand([159,16,635,192,10])
        self.reader.pid=9876
        with self.assertRaisesRegex(RuntimeError,"PID"):
            self.probe.capture_after(self.sha)
        self.reader.pid=1234
        with self.assertRaisesRegex(RuntimeError,"ISO"):
            self.probe.capture_after("b"*64)

    def test_no_field_data_without_full_observation(self):
        self.assertIsNone(self.probe.before)
        with self.assertRaises(RuntimeError):
            self.probe.capture_after(self.sha)
        with self.assertRaises(RuntimeError):
            self.probe.capture_removed(self.sha)

    def test_do_not_assume_hand_is_field(self):
        before={SEARCH_START:bytes(CHUNK_SIZE)}
        after={SEARCH_START:bytes(CHUNK_SIZE)}
        # O ID aparecer na mão não é evidência de carta na mesa.
        haddr=HAND_ADDR&~(CHUNK_SIZE-1)
        i=HAND_ADDR-haddr
        before[haddr]=bytes(CHUNK_SIZE)
        b=bytearray(CHUNK_SIZE)
        b[i:i+2]=struct.pack("<H",291)
        after[haddr]=bytes(b)
        r=find_new_id_candidates(before,after,291)
        self.assertEqual(r["candidate_count_total"],0)
        self.assertFalse(r["field_address_verified"])

    def test_chunk_read_failures_are_not_copied_as_candidates(self):
        class Failing(FakeReader):
            def read(self,address,size):
                if size==CHUNK_SIZE and address==SEARCH_START:
                    raise OSError("unreadable")
                return super().read(address,size)
        reader=Failing()
        probe=FieldMemoryProbe(lambda:reader,Path(self.temp.name))
        before=probe.capture_before(self.sha,291)
        self.assertEqual(len(before["unreadable_chunks"]),1)
        reader.hand=make_hand([159,16,635,192,10])
        report,_=probe.capture_after(self.sha)
        self.assertEqual(report["analysis"]["chunks_compared"],23)
        self.assertEqual(report["analysis"]["candidate_count_total"],0)

if __name__=="__main__":
    unittest.main()
