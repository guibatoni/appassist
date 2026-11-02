"""Testes do monitor temporal com leitor simulado, sem ePSXe e sem escrita."""
from __future__ import annotations
import csv
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from fusion_ram_probe import WINDOWS, FusionMemoryProbe
from ram_temporal import (
    TemporalRamRecorder, MAX_SAMPLES, MIN_INTERVAL_MS, MAX_INTERVAL_MS,
)


def hand_blob(ids):
    data=bytearray(140)
    for index,cid in enumerate(ids):
        struct.pack_into("<H",data,index*28,cid)
        struct.pack_into("<I",data,index*28+12,index)
    return bytes(data)


class Reader:
    def __init__(self):
        self.pid=123
        self.regions={addr:bytes(size) for addr,size in WINDOWS.values()}
        self.regions[0xBFF484]=hand_blob([16,10,200,45,461])
        self.calls=[]
    def read(self,addr,n):
        self.calls.append((addr,n))
        return self.regions[addr]
    def write(self,*args,**kwargs):
        raise AssertionError("Proibido escrever na memória")


class Clock:
    def __init__(self):
        self.t=10.0
    def __call__(self):
        return self.t
    def advance(self,delta):
        self.t+=delta


class TemporalRamTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rd=Reader()
        self.clock=Clock()
        self.probe=FusionMemoryProbe(lambda:self.rd,Path(self.tmp.name))
        self.rec=TemporalRamRecorder(self.probe,monotonic=self.clock)
        self.sha="A"*64

    def test_timeline_with_markers_and_safe_exports(self):
        initial=self.rec.start(self.sha,interval_ms=250,duration_seconds=45)
        self.assertEqual(initial["hand_ids"],[16,10,200,45,461])
        self.clock.advance(0.25)
        self.rd.regions[0xBFF484]=hand_blob([69,10,200,45,461])
        changed=self.rec.sample()
        self.assertIn("mao_conhecida",changed["changed_windows"])
        self.assertEqual(changed["elapsed_ms"],250)
        self.clock.advance(0.05)
        self.rec.mark("fusao")
        self.clock.advance(0.2)
        self.rec.sample()
        report,jpath,cpath=self.rec.stop()
        self.assertEqual(report["sample_count"],3)
        self.assertEqual(report["transitions_with_changed_bytes"],1)
        self.assertEqual(report["markers"][0]["elapsed_ms"],300)
        self.assertTrue(report["markers"][0]["annotation_only"])
        self.assertFalse(report["fusion_event_verified"])
        self.assertFalse(report["fusion_catalog_changed"])
        self.assertFalse(report["emulator_iso_verified"])
        self.assertIsNone(report["duel_field_card_ids"])
        self.assertFalse(report["duel_field_ram_verified"])
        self.assertEqual(report["rom_sha256_selected_manually"],"a"*64)
        self.assertTrue(jpath.is_file())
        self.assertTrue(cpath.is_file())
        loaded=json.loads(jpath.read_text(encoding="utf-8"))
        self.assertEqual(loaded["samples"][1]["changes"]["mao_conhecida"]["changed_bytes"],1)
        with cpath.open(newline="",encoding="utf-8-sig") as fp:
            rows=list(csv.reader(fp))
        self.assertEqual(len(rows),4)
        self.assertEqual(len(self.rd.calls),len(WINDOWS)*3)

    def test_invalid_interval_duration_and_label(self):
        for interval in (0,199,1001,True):
            with self.assertRaises(ValueError):
                self.rec.start(self.sha,interval_ms=interval)
        for duration in (0,91,True):
            with self.assertRaises(ValueError):
                self.rec.start(self.sha,duration_seconds=duration)
        self.rec.start(self.sha)
        with self.assertRaises(RuntimeError):
            self.rec.start(self.sha)
        with self.assertRaises(ValueError):
            self.rec.mark("resultado_automatico")
        with self.assertRaises(ValueError):
            self.rec.stop(reason="arbitrario")

    def test_pid_change_is_rejected(self):
        self.rec.start(self.sha)
        self.rd.pid=456
        with self.assertRaisesRegex(RuntimeError,"PID"):
            self.rec.sample()
        report,_,_=self.rec.stop(reason="erro")
        self.assertEqual(report["end_reason"],"erro")
        self.assertEqual(report["sample_count"],1)

    def test_no_hand_no_start(self):
        self.rd.regions[0xBFF484]=bytes(140)
        with self.assertRaises(RuntimeError):
            self.rec.start(self.sha)
        self.assertFalse(self.rec.active)

    def test_bounded_sampling_and_clock(self):
        self.rec.start(self.sha,interval_ms=200,duration_seconds=1)
        self.clock.advance(1.1)
        state=self.rec.sample()
        self.assertTrue(state["finished_by_duration"])
        self.assertFalse(state["finished_by_limit"])
        report,_,_=self.rec.stop(reason="duracao")
        self.assertEqual(report["end_reason"],"duracao")
        self.assertLessEqual(report["sample_count"],MAX_SAMPLES)

    def test_no_session_stop(self):
        with self.assertRaises(RuntimeError):
            self.rec.stop()
        with self.assertRaises(RuntimeError):
            self.rec.mark("fusao")
        with self.assertRaises(RuntimeError):
            self.rec.sample()


if __name__=="__main__":
    unittest.main()
