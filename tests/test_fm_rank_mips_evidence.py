"""Teste de leitura estrutural MIPS PS-X EXE, sem executar ROM comercial."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from fm_rank_mips_evidence import inspect_mips_rank_routines


def fake_slus(*, with_pattern=True):
    words=[0]*128
    if with_pattern:
        sample=[
            0x3c088000,  # lui t0, 0x8000
            0x25080120,  # addiu t0,t0,0x120
            0x85090000,  # lh t1,0(t0)
            0x950a0004,  # lhu t2,4(t0)
            0x012a582b,  # sltu t3,t1,t2
            0x11600003,  # beq t3,zero,+3
            0x00094880,  # sll t1,t1,2
            0x012a4821,  # addu t1,t1,t2
            0x152b0002,  # bne t1,t3,+2
            0x25080004,  # addiu t0,t0,4
            0x850a0004,  # lh t2,4(t0)
        ]
        words[16:16+len(sample)]=sample
    length=len(words)*4
    data=bytearray(0x800+length)
    data[:8]=b"PS-X EXE"
    struct.pack_into("<III",data,0x10,0x80010000,0x80010000,length)
    for i,w in enumerate(words):
        struct.pack_into("<I",data,0x800+i*4,w)
    return bytes(data)


class MipsEvidenceTests(unittest.TestCase):
    def test_offsets_and_candidates_from_valid_exe(self):
        output=inspect_mips_rank_routines(fake_slus())
        self.assertTrue(output["available"])
        self.assertEqual(output["status"],"mips_patterns_found")
        self.assertTrue(output["candidates"])
        self.assertTrue(output["candidates"][0]["pc"].startswith("0x8001"))
        self.assertFalse(output["execution_confirmed"])
        self.assertFalse(output["rank_routine_confirmed"])
        self.assertGreaterEqual(output["candidates"][0]["features"]["halfword_loads"],2)

    def test_unknown_or_corrupted_header_is_not_verified(self):
        for blob in (b"",b"NOT EXE",fake_slus().replace(b"PS-X EXE",b"FALSIFIC")):
            report=inspect_mips_rank_routines(blob)
            self.assertFalse(report["available"])
            self.assertEqual(report["candidates"],[])

    def test_plain_executable_does_not_invent_rank(self):
        output=inspect_mips_rank_routines(fake_slus(with_pattern=False))
        self.assertTrue(output["available"])
        self.assertEqual(output["candidate_count"],0)
        self.assertFalse(output["rank_routine_confirmed"])

    def test_bad_load_length_or_entry_rejected(self):
        blob=bytearray(fake_slus())
        struct.pack_into("<I",blob,0x18,0x81000000)
        self.assertEqual(inspect_mips_rank_routines(bytes(blob))["status"],
                         "invalid_exe_mapping")
        blob=bytearray(fake_slus())
        struct.pack_into("<I",blob,0x10,0x800FFFFF)
        self.assertEqual(inspect_mips_rank_routines(bytes(blob))["status"],
                         "invalid_entry_point")


if __name__ == "__main__":
    unittest.main()
