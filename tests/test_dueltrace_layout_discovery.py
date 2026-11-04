"""Testes sintéticos de descoberta por bytes, mesmo após renomeações arbitrárias.

Nenhuma ISO comercial é necessária ou incluída.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from dueltrace_layout_discovery import (
    FIRST_TABLE, RANK_STRIDE, KNOWN_WA_SIZE,
    discover_disc_layout, candidate_files_for_decoder,
)


class SparseDisc:
    def __init__(self, files, signatures=None, tables=None):
        self.files = files
        self.signatures = signatures or {}
        self.tables = tables or {}
        self.read_calls = []
        self.get_calls = []

    def get(self, name, limit_bytes=None):
        self.get_calls.append((name,limit_bytes))
        return self.signatures.get(name,b"\0"*32)[:limit_bytes]

    def read(self, lba, length):
        self.read_calls.append((lba, length))
        self.assert_read_is_bounded(length)
        for name,(base,size) in sorted(self.files.items(),
                                       key=lambda item:-item[1][0]):
            start=(lba-base)*2048
            if 0<=start<size:
                data=bytearray(length)
                for offset,payload in self.tables.get(name,{}).items():
                    left=max(offset,start)
                    right=min(offset+len(payload),start+length)
                    if left<right:
                        data[left-start:right-start]=payload[
                            left-offset:right-offset]
                return bytes(data)
        raise ValueError("LBA não encontrado")

    @staticmethod
    def assert_read_is_bounded(length):
        if not 0<=length<=4096:
            raise AssertionError("Sondagem leu além de 4KB")


def weights():
    return struct.pack("<722H",2048,*([0]*721))


class UniversalLayoutDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.exe="GOG_VNT.223"
        self.container="GOSD/GOG_SD1.23"
        self.video="GOSD/GO_SD2.23"
        # O arquivo de recursos foi RENOMEADO e seu tamanho difere do WA.
        self.disc=SparseDisc(
            files={
                self.exe:(100,1_902_032),
                self.container:(1000,24_000_000),
                self.video:(50_000,35_430_400),
            },
            signatures={self.exe:b"PS-X EXE" + bytes(24)},
            tables={self.container:{
                FIRST_TABLE+RANK_STRIDE:weights(),
                FIRST_TABLE+2*RANK_STRIDE:weights(),
            }},
        )

    def test_renamed_and_resized_container_is_candidate_by_internal_arrays(self):
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertFalse(report["validated"])
        self.assertEqual(report["inspectedFiles"],3)
        self.assertEqual(report["resourceProbes"],2)
        self.assertEqual(report["executables"][0]["name"],self.exe)
        self.assertTrue(report["executables"][0]["psxHeader"])
        self.assertEqual(candidate_files_for_decoder(report,role="executavel"),
                         [self.exe])
        resources=report["resources"]
        self.assertEqual(resources[0]["name"],self.container)
        self.assertEqual(resources[0]["dropArrayMatches"],2)
        self.assertIn("matrizes_2048_no_layout_antigo",
                      resources[0]["signals"])
        self.assertNotEqual(resources[0]["size"],KNOWN_WA_SIZE)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),
                         [self.container])
        self.assertFalse(resources[0]["validated"])
        self.assertTrue(all(n<=4096 for _,n in self.disc.read_calls))
        self.assertTrue(all(n==32 for _,n in self.disc.get_calls))

    def test_one_table_or_size_alone_never_validates_resource(self):
        self.disc.tables[self.container]={
            FIRST_TABLE+RANK_STRIDE:weights(),
        }
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertEqual(report["resources"][0]["dropArrayMatches"],1)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])
        self.disc.tables[self.container]={}
        self.disc.files[self.container]=(1000,KNOWN_WA_SIZE)
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertIn("tamanho_wa_conhecido",
                      report["resources"][0]["signals"])
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])

    def test_ambiguous_structurally_matching_containers_are_not_chosen(self):
        other="RANDOM.ABC"
        self.disc.files[other]=(80_000,26_000_000)
        self.disc.tables[other]=dict(self.disc.tables[self.container])
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])
        self.assertEqual(len([x for x in report["resources"]
                              if x["dropArrayMatches"]>=2]),2)

    def test_random_large_video_with_no_signals_cannot_be_selected(self):
        self.disc.tables={}
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])
        video=next(r for r in report["resources"] if r["name"]==self.video)
        self.assertEqual(video["dropArrayMatches"],0)
        self.assertFalse(video["validated"])

    def test_content_based_executable_not_naming_dependent(self):
        report=discover_disc_layout(self.disc,boot_target="")
        exe=report["executables"][0]
        self.assertEqual(exe["name"],"GOG_VNT.223")
        self.assertIn("cabecalho_ps_x_exe",exe["signals"])
        self.assertFalse(exe["validated"])

    def test_invalid_role_and_probe_limits(self):
        with self.assertRaises(ValueError):
            candidate_files_for_decoder({},role="fusoes")
        data=discover_disc_layout(self.disc,max_files=2,max_resource_probes=1)
        self.assertEqual(data["inspectedFiles"],2)
        self.assertLessEqual(data["resourceProbes"],1)
        self.assertLessEqual(len(self.disc.read_calls),2+6)


if __name__=="__main__":
    unittest.main()
