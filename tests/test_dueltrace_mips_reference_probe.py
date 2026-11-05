"""MIPS PS-X EXE sintético: LUI + ORI/ADDIU/LW contra offsets de tabelas.

Sem ROM comercial, hardware e modelos. Match estático não valida ID/RANK.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_mips_reference_probe import inspect_mips_table_references
from dueltrace_mod_diagnostic import diagnose_layout
from ia_local import minimal_evidence

LOAD=0x80010000
LENGTH=0x13000
TABLE_OFFSET=0x2800
TABLE_ADDR=LOAD+TABLE_OFFSET-0x800
HIGH=(TABLE_ADDR>>16)&0xFFFF
LOW=TABLE_ADDR&0xFFFF

def ins_lui(rt,imm):
    return (0x0F<<26)|(rt<<16)|(imm&0xFFFF)

def ins_ori(rt,rs,imm):
    return (0x0D<<26)|(rs<<21)|(rt<<16)|(imm&0xFFFF)

def ins_addiu(rt,rs,imm):
    return (0x09<<26)|(rs<<21)|(rt<<16)|(imm&0xFFFF)

def ins_lw(rt,rs,imm):
    return (0x23<<26)|(rs<<21)|(rt<<16)|(imm&0xFFFF)

def exe_at(instructions, *,load=LOAD,entry=LOAD):
    blob=bytearray(0x800+LENGTH)
    blob[:8]=b"PS-X EXE"
    struct.pack_into("<I",blob,0x10,entry)
    struct.pack_into("<I",blob,0x18,load)
    struct.pack_into("<I",blob,0x1C,LENGTH)
    for idx,word in enumerate(instructions):
        struct.pack_into("<I",blob,0x800+idx*4,word)
    return bytes(blob)


class MipsTableReferenceTests(unittest.TestCase):
    def test_lui_ori_matches_candidate_table_in_same_exe(self):
        exe=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        result=inspect_mips_table_references(exe,[TABLE_OFFSET])
        self.assertEqual(result["state"],"referencias_mips_candidatas")
        self.assertFalse(result["validated"])
        self.assertFalse(result["executionConfirmed"])
        self.assertEqual(len(result["references"]),1)
        row=result["references"][0]
        self.assertEqual(row["tableFileOffset"],TABLE_OFFSET)
        self.assertEqual(row["deltaBytes"],0)
        self.assertEqual(row["matchType"],"lui_ori")
        self.assertEqual(row["fileOffset"],0x800)
        self.assertEqual(row["pc"],"0x80010000")
        self.assertEqual(row["targetAddress"],f"0x{TABLE_ADDR:08X}")
        self.assertEqual(len(result["exeSha256"]),64)

    def test_addiu_signed_low_half_and_memory_access(self):
        # Ao atravessar 0x8000, ADDIU acrescenta um deslocamento NEGATIVO.
        off=0xA800
        target=LOAD+off-0x800
        self.assertEqual(target&0xFFFF,0xA000)
        high=((target+0x8000)>>16)&0xFFFF
        low=target&0xFFFF
        result=inspect_mips_table_references(
            exe_at([ins_lui(9,high),ins_addiu(9,9,low)]),[off])
        self.assertEqual(result["references"][0]["matchType"],"lui_addiu")
        loadref=inspect_mips_table_references(
            exe_at([ins_lui(9,high),ins_lw(10,9,low)]),[off])
        self.assertEqual(loadref["references"][0]["matchType"],"lui_load")

    def test_kseg1_ram_alias_and_small_delta_are_evidence_only(self):
        alias=TABLE_ADDR|0x20000000
        words=[ins_lui(11,alias>>16),ins_ori(11,11,(alias+8)&0xFFFF)]
        result=inspect_mips_table_references(exe_at(words),[TABLE_OFFSET])
        self.assertEqual(result["references"][0]["deltaBytes"],8)
        self.assertFalse(result["references"][0]["validated"])

    def test_branch_separates_instructions_and_prevents_false_positive(self):
        exe=exe_at([ins_lui(8,HIGH),0x10000000,ins_ori(8,8,LOW)])
        result=inspect_mips_table_references(exe,[TABLE_OFFSET])
        self.assertEqual(result["references"],[])
        self.assertEqual(result["state"],"sem_evidencia")

    def test_wrong_address_or_random_header_never_confirms_pointer(self):
        result=inspect_mips_table_references(
            exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)]),[0x3800])
        self.assertEqual(result["references"],[])
        empty=inspect_mips_table_references(b"PS-X EXE"+b"\0"*5000,
                                           [TABLE_OFFSET])
        self.assertEqual(empty["state"],"psx_header_invalido")
        self.assertFalse(empty["validated"])

    def test_limits_and_invalid_offsets_fail_closed(self):
        exe=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        for offsets in ([0],[3],[0x7FE],[0xFFFFF],[TABLE_OFFSET]*9,[]):
            with self.subTest(offsets=offsets):
                result=inspect_mips_table_references(exe,offsets)
                if offsets==[]:
                    self.assertEqual(result["state"],"sem_evidencia")
                else:
                    self.assertEqual(result["state"],"alvos_invalidos")
        limited=inspect_mips_table_references(exe,[TABLE_OFFSET],max_scan_bytes=4)
        self.assertEqual(limited["references"],[])
        self.assertEqual(limited["scanBytes"],4)
        self.assertFalse(limited["executionConfirmed"])

    def test_capstone_is_optional(self):
        exe=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        with patch.dict(sys.modules,{"capstone":None}):
            result=inspect_mips_table_references(exe,[TABLE_OFFSET])
        self.assertEqual(result["references"][0]["matchType"],"lui_ori")
        self.assertFalse(result["capstoneAvailable"])
        # O Capstone só enriquece as instruções, sem mudar o match binário.
        auto=inspect_mips_table_references(exe,[TABLE_OFFSET])
        self.assertEqual([r["matchType"] for r in auto["references"]],
                         [r["matchType"] for r in result["references"]])

    def test_diagnostic_and_ollama_receive_only_bounded_unverified_evidence(self):
        exe=exe_at([ins_lui(8,HIGH),ins_ori(8,8,LOW)])
        mips=inspect_mips_table_references(exe,[TABLE_OFFSET])
        report={
            "arquivos_discos":[{"nome":"DATA/MOD.EXE","tamanho":len(exe),"lba":23}],
            "status":"incerto",
            "name_pointer_discovery":{
                "state":"tabela_candidata_localizada",
                "candidates":[{"pointerBase":TABLE_OFFSET,
                               "cardNamesTerminated":722,
                               "opponentNamesTerminated":39}]},
            "mips_name_pointer_evidence":mips,
        }
        diagnostic=diagnose_layout(report,{})
        evidence=diagnostic["mipsNameTableEvidence"]
        self.assertFalse(evidence["verified"])
        self.assertFalse(evidence["executionConfirmed"])
        self.assertEqual(len(evidence["nameCandidates"]),1)
        self.assertEqual(evidence["mipsReferences"][0]["tableFileOffset"],
                         TABLE_OFFSET)
        llm=minimal_evidence({
            "file":"example.iso","hash_rom":"a"*64,
            "inventory":{},"features":{},"scan_diagnostic":diagnostic
        })
        summarized=llm["scan_diagnostic"]["mipsNameTableEvidence"]
        self.assertFalse(summarized["verified"])
        self.assertEqual(len(summarized["references"]),1)
        self.assertNotIn("disassembly",summarized["references"][0])

    def test_scanner_integration_is_read_only_and_revision_is_new(self):
        source=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertIn('info["mips_name_pointer_evidence"]=',source)
        self.assertIn('inspect_mips_table_references(',source)
        self.assertIn("SCAN_PARSER_REVISION=11",source)


if __name__=="__main__":
    unittest.main()
