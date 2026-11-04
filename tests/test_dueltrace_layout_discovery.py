"""Testes sintéticos de descoberta por bytes, mesmo após renomeações arbitrárias.

Nenhuma ISO comercial é necessária ou incluída.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from dueltrace_layout_discovery import (
    FIRST_TABLE, RANK_STRIDE, KNOWN_WA_SIZE, RESOURCE_ADAPTERS,
    DropLayoutAdapter, inspect_psx_executable_header,
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


def executable_header(*, entry=0x80010000, load=0x80010000, length=0x100000):
    header=bytearray(32)
    header[:8]=b"PS-X EXE"
    # The GP word at 0x14 is independent of both load and payload length.
    struct.pack_into("<IIII",header,0x10,entry,0x80098760,load,length)
    return bytes(header)


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
            signatures={self.exe:executable_header()},
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
        self.assertTrue(report["executables"][0]["executableHeader"]["headerCoherent"])
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
        self.assertEqual(resources[0]["layoutProbes"][0]["adapter"],"fm_wa_722_v1")

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

    def test_psx_signature_alone_is_diagnostic_and_not_a_decoder_candidate(self):
        self.disc.signatures[self.exe]=b"PS-X EXE"+bytes(24)
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertTrue(report["executables"][0]["psxHeader"])
        self.assertFalse(report["executables"][0]["executableHeader"]["headerCoherent"])
        self.assertEqual(candidate_files_for_decoder(report,role="executavel"),[])

    def test_psx_headers_keep_all_coherent_candidates_without_choosing_one(self):
        other="RENAMED.BIN"
        self.disc.files[other]=(80_000,0x120000)
        self.disc.signatures[other]=executable_header()
        report=discover_disc_layout(self.disc,boot_target=self.exe)
        self.assertCountEqual(candidate_files_for_decoder(report,role="executavel"),
                              [self.exe,other])
        self.assertFalse(report["validated"])

    def test_truncated_reads_never_count_as_matching_matrices(self):
        self.disc.read=lambda lba,length: bytes(length-1)
        report=discover_disc_layout(self.disc)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])
        self.assertTrue(all(r["probeState"]=="falha_leitura" for r in report["resources"]))

    def test_two_matches_followed_by_read_failure_remain_diagnostic(self):
        read=self.disc.read
        failed_lba=self.disc.files[self.container][0]+(FIRST_TABLE+3*RANK_STRIDE)//2048
        def fail_last(lba,length):
            if lba==failed_lba:
                raise OSError("synthetic truncated sector")
            return read(lba,length)
        self.disc.read=fail_last
        report=discover_disc_layout(self.disc)
        row=next(r for r in report["resources"] if r["name"]==self.container)
        self.assertEqual(row["dropArrayMatches"],2)
        self.assertEqual(row["probeState"],"falha_leitura")
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])

    def test_invalid_iso_index_lba_is_skipped_without_read(self):
        self.disc.files={"BROKEN.DAT":(-1,KNOWN_WA_SIZE)}
        report=discover_disc_layout(self.disc)
        self.assertEqual(report["resources"],[])
        self.assertEqual(self.disc.get_calls,[])
        self.assertEqual(self.disc.read_calls,[])

    def test_multiple_adapter_matches_in_one_container_remain_ambiguous(self):
        duplicate=DropLayoutAdapter("synthetic_other",RESOURCE_ADAPTERS[0].table_offsets)
        with patch("dueltrace_layout_discovery.RESOURCE_ADAPTERS",
                   RESOURCE_ADAPTERS+(duplicate,)):
            report=discover_disc_layout(self.disc)
        row=next(r for r in report["resources"] if r["name"]==self.container)
        self.assertEqual(len(row["layoutProbes"]),2)
        self.assertEqual(candidate_files_for_decoder(report,role="recursos"),[])

    def test_adapter_budget_is_global_even_with_several_registered_layouts(self):
        duplicate=DropLayoutAdapter("synthetic_other",RESOURCE_ADAPTERS[0].table_offsets)
        with patch("dueltrace_layout_discovery.RESOURCE_ADAPTERS",
                   RESOURCE_ADAPTERS+(duplicate,)):
            report=discover_disc_layout(self.disc,max_resource_probes=1)
        self.assertEqual(report["resourceProbes"],1)
        self.assertTrue(report["probeLimitReached"])
        self.assertEqual(len(self.disc.read_calls),3)

    def test_adapter_rejects_duplicate_and_negative_offsets_without_read(self):
        for offsets in ((0,0,0),(-1,20,40)):
            result=DropLayoutAdapter("synthetic_invalid",offsets).probe(self.disc,self.container)
            self.assertEqual(result["state"],"adaptador_invalido")
            self.assertEqual(result["matchingTables"],0)
        self.assertEqual(self.disc.read_calls,[])


class PsxExecutableHeaderTests(unittest.TestCase):
    def test_correct_pc_gp_load_and_size_offsets(self):
        result=inspect_psx_executable_header(executable_header(entry=0x80010008),0x120000)
        self.assertTrue(result["headerCoherent"])
        self.assertEqual(result["loadAddress"],0x80010000)
        self.assertEqual(result["payloadSize"],0x100000)
        self.assertEqual(result["entryFileOffset"],0x808)
        self.assertFalse(result["validated"])

    def test_uncached_and_physical_ram_aliases_are_supported(self):
        for load,entry in ((0xA0010000,0xA0010004),(0x10000,0x10004),
                           (0x80010000,0xA0010004)):
            result=inspect_psx_executable_header(executable_header(load=load,entry=entry),0x120000)
            self.assertTrue(result["headerCoherent"])
            self.assertEqual(result["entryFileOffset"],0x804)

    def test_rejects_truncation_zero_and_oversized_payloads(self):
        cases=((b"PS-X EXE",0x120000),
               (executable_header(),0x100),
               (executable_header(),0x100000),
               (executable_header(length=0),0x120000),
               (executable_header(length=0x100003),0x120000),
               (executable_header(length=0x300000),0x400000))
        for header,size in cases:
            with self.subTest(size=size,header=header):
                self.assertFalse(inspect_psx_executable_header(header,size)["headerCoherent"])

    def test_rejects_entry_outside_payload_unaligned_and_ram_overflow(self):
        cases=(dict(entry=0x80110000),dict(entry=0x80010002),
               dict(load=0x80010002),dict(load=0x80180000,entry=0x80180000),
               dict(load=0xBFC00000,entry=0xBFC00000),
               dict(load=0xC0010000,entry=0xC0010000))
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                self.assertFalse(inspect_psx_executable_header(
                    executable_header(**kwargs),0x120000)["headerCoherent"])


if __name__=="__main__":
    unittest.main()
