"""Testes do diagnóstico de RAM: não confundir mudanças com fusões provadas."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from fusion_ram_probe import (
    WINDOWS, FusionMemoryProbe, decode_hand, differences
)


def hand_blob(ids):
    data=bytearray(140)
    for idx,cid in enumerate(ids):
        struct.pack_into("<H",data,idx*28,cid)
        struct.pack_into("<I",data,idx*28+12,idx)
    return bytes(data)


class FakeReader:
    def __init__(self, pid=1234):
        self.pid=pid
        self.regions={
            0xBFF484:hand_blob([300,10,120,525,722]),
            0xB483A2:bytes(32),
            0xB5B21E:bytes(32),
            0xB41891:bytes(32),
        }
        self.read_calls=[]
    def read(self,address,length):
        self.read_calls.append((address,length))
        return self.regions[address][:length]


class FusionRamProbeTests(unittest.TestCase):
    def test_hand_ids_are_validated_strictly(self):
        self.assertEqual(decode_hand(hand_blob([1,2,3,4,722])),[1,2,3,4,722])
        self.assertIsNone(decode_hand(b""))
        self.assertIsNone(decode_hand(bytes(140)))
        altered=bytearray(hand_blob([1,2,3,4,5]))
        struct.pack_into("<I",altered,12,9)
        self.assertIsNone(decode_hand(bytes(altered)))

    def test_before_after_logged_but_not_confirmed(self):
        with tempfile.TemporaryDirectory() as folder:
            sha="a"*64
            rd=FakeReader()
            probe=FusionMemoryProbe(lambda: rd,Path(folder))
            before=probe.capture_before(sha)
            self.assertEqual(before["hand_ids"],[300,10,120,525,722])
            # Isto é só uma mudança de RAM: não é comprovação de fusão.
            rd.regions[0xB483A2]=b"\x42"+bytes(31)
            rd.regions[0xBFF484]=hand_blob([300,10,120,526,722])
            report,path=probe.capture_after(sha,observed_result_id=638)
            self.assertTrue(path.is_file())
            loaded=json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["diff"]["exploratoria_a"]["changed_bytes"],1)
            self.assertEqual(loaded["user_observed_result_id"],638)
            self.assertFalse(loaded["fusion_event_verified"])
            self.assertFalse(loaded["fusion_catalog_changed"])
            self.assertFalse(loaded["emulator_iso_verified"])
            self.assertIn(sha,str(path))
            self.assertIsNone(probe.before)
            self.assertEqual(len(rd.read_calls),len(WINDOWS)*2)

    def test_no_event_without_before_or_matching_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            rd=FakeReader()
            probe=FusionMemoryProbe(lambda:rd,Path(folder))
            with self.assertRaises(RuntimeError):
                probe.capture_after("a"*64)
            probe.capture_before("a"*64)
            with self.assertRaises(RuntimeError):
                probe.capture_after("b"*64)
            with self.assertRaises(ValueError):
                probe.capture_after("a"*64,observed_result_id=999)
            with self.assertRaises(ValueError):
                probe.capture_after("../traversal")

    def test_changed_pid_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            rd=FakeReader()
            probe=FusionMemoryProbe(lambda:rd,Path(folder))
            probe.capture_before("a"*64)
            rd.pid=9999
            with self.assertRaisesRegex(RuntimeError,"processo"):
                probe.capture_after("a"*64)

    def test_unavailable_window_does_not_invent_diffs(self):
        with tempfile.TemporaryDirectory() as folder:
            rd=FakeReader()
            def broken_read(address,length):
                if address==0xB41891:
                    raise OSError("reading failed")
                return rd.regions[address][:length]
            rd.read=broken_read
            probe=FusionMemoryProbe(lambda:rd,Path(folder))
            probe.capture_before("a"*64)
            report,_=probe.capture_after("a"*64)
            self.assertEqual(report["diff"]["exploratoria_c"]["status"],"indisponivel")
            self.assertIsNone(report["diff"]["exploratoria_c"]["changed_bytes"])
            self.assertFalse(report["fusion_event_verified"])

    def test_fusion_probe_never_calls_any_write_api(self):
        class ReadOnlyReader(FakeReader):
            def write(self,*args,**kwargs):
                raise AssertionError("Nenhuma escrita na RAM permitida")
        with tempfile.TemporaryDirectory() as folder:
            rd=ReadOnlyReader()
            probe=FusionMemoryProbe(lambda:rd,Path(folder))
            probe.capture_before("a"*64)
            probe.capture_after("a"*64)
            self.assertEqual(len(rd.read_calls),len(WINDOWS)*2)


if __name__=="__main__":
    unittest.main()
