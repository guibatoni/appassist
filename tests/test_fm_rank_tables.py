"""Verificações estruturais WA/RANK baseadas no relatório forense X15 real.

Somente amostras sintéticas, sem incluir bytes do jogo. O hash conhecido
da tabela reconstruída serve como prova reproduzível da interpretação Hh.
"""
import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
import fm_rank_tables as forensic
from dueltrace_rank_live import RULES
from dueltrace_rank_profiles import rank_profile_for_image
from scanner_multiiso import X15_SHA


def reference_table():
    return b"".join(
        struct.pack("<Hh",threshold,points)
        for ranges in RULES.values() for threshold,points in ranges
    )


def sample_wa(table=None):
    table = reference_table() if table is None else table
    n=(forensic.BLOCK_FIRST_SECTOR+forensic.BLOCK_COUNT*forensic.BLOCK_SECTORS)*forensic.SECTOR
    wa=bytearray(n)
    for i in range(forensic.BLOCK_COUNT):
        at=(forensic.BLOCK_FIRST_SECTOR+i*forensic.BLOCK_SECTORS)*forensic.SECTOR+forensic.POINT_TABLE_OFFSET
        wa[at:at+len(table)]=table
    return wa


class RankTableTests(unittest.TestCase):
    def test_reference_sha_reproduces_previous_real_iso_forensics(self):
        self.assertEqual(len(reference_table()),200)
        self.assertEqual(
            hashlib.sha256(reference_table()).hexdigest(),
            forensic.KNOWN_X15_TABLE_SHA256
        )

    def test_decodes_forty_identical_tables_but_no_fake_runtime_claims(self):
        report=forensic.extract_rank_table(bytes(sample_wa()),slus=b"SYNTHETIC",
                                          rom_sha256="b"*64,
                                          known_rom_sha256=X15_SHA)
        self.assertTrue(report["available"])
        self.assertFalse(report["runtime_verified"])
        self.assertEqual(report["table_count"],40)
        self.assertEqual(report["identical_copies"],40)
        self.assertEqual(report["first_offset"],7475*2048+0x16D0)
        self.assertEqual(report["rules"]["criterion_01"][0],{"below":5,"points":12})
        self.assertEqual(report["rules"]["criterion_07"][0],{"below":9,"points":15})
        self.assertIsNone(report["base_points"])
        output=rank_profile_for_image("b"*64,report)
        self.assertTrue(output["available"])
        self.assertFalse(output["runtime_verified"])
        self.assertIsNone(output["lp_victory_bonus"])

    def test_automatically_finds_relocated_rank_table_without_fixed_offset(self):
        # Um mod pode deslocar o banco WA sem alterar as regras do duelo.
        original=sample_wa()
        shifted=bytearray(len(original)+4096)
        moved=forensic.LEGACY_OFFSET+512
        for i in range(forensic.BLOCK_COUNT):
            old=forensic.LEGACY_OFFSET+i*forensic.STRIDE
            new=moved+i*forensic.STRIDE
            shifted[new:new+forensic.TABLE_SIZE]=original[old:old+forensic.TABLE_SIZE]
        report=forensic.extract_rank_table(bytes(shifted),slus=b"MOD",
                                           rom_sha256="c"*64,
                                           known_rom_sha256=X15_SHA)
        self.assertTrue(report["available"])
        self.assertEqual(report["first_offset"],moved)
        self.assertTrue(report["layout_moved"])
        self.assertEqual(report["method"],"automatic_stride_scan")
        self.assertFalse(report["binary_verified"])
        self.assertEqual(report["rules"]["criterion_07"][0]["points"],15)

    def test_rejects_two_independent_valid_scoring_tables(self):
        first=sample_wa()
        second_start=forensic.LEGACY_OFFSET+(forensic.BLOCK_COUNT+4)*forensic.STRIDE
        blob=bytearray(second_start+forensic.BLOCK_COUNT*forensic.STRIDE+
                       forensic.TABLE_SIZE+2048)
        blob[:len(first)]=first
        altered=bytearray(reference_table())
        struct.pack_into("<h",altered,2,7)
        for i in range(forensic.BLOCK_COUNT):
            pos=second_start+i*forensic.STRIDE
            blob[pos:pos+forensic.TABLE_SIZE]=altered
        report=forensic.extract_rank_table(bytes(blob),slus=b"MOD")
        self.assertFalse(report["available"])
        self.assertEqual(report["status"],"ambiguous_rank_tables")

    def test_first_anchor_not_equal_to_a_full_valid_table(self):
        wa=bytearray(sample_wa())
        for i in range(forensic.BLOCK_COUNT):
            pos=forensic.LEGACY_OFFSET+i*forensic.STRIDE
            # último limiar preservado, mas a segunda faixa é inválida.
            struct.pack_into("<H",wa,pos+4,1)
        report=forensic.extract_rank_table(bytes(wa),slus=b"MOD")
        self.assertFalse(report["available"])

    def test_mutated_valid_points_are_detected_without_copying_x15(self):
        table=bytearray(reference_table())
        struct.pack_into("<h",table,2,7)
        report=forensic.extract_rank_table(bytes(sample_wa(table)),slus=b"MOD",
                                          rom_sha256="b"*64,
                                          known_rom_sha256=X15_SHA)
        self.assertTrue(report["available"])
        self.assertNotEqual(report["table_sha256"],forensic.KNOWN_X15_TABLE_SHA256)
        self.assertEqual(report["rules"]["criterion_01"][0]["points"],7)
        self.assertFalse(report["criterion_names_verified"])

    def test_nonidentical_opponent_blocks_fail_closed(self):
        wa=sample_wa()
        offset=(forensic.BLOCK_FIRST_SECTOR+21*forensic.BLOCK_SECTORS)*2048
        wa[offset+forensic.POINT_TABLE_OFFSET+3]^=1
        report=forensic.extract_rank_table(bytes(wa),slus=b"MOD")
        self.assertFalse(report["available"])
        self.assertEqual(report["status"],"divergent_rank_tables")
        self.assertEqual(report["identical_copies"],39)

    def test_invalid_threshold_or_truncation_fails_closed(self):
        table=bytearray(reference_table())
        struct.pack_into("<H",table,4,1)
        report=forensic.extract_rank_table(bytes(sample_wa(table)))
        self.assertEqual(report["status"],"rank_table_unrecognized")
        self.assertFalse(report["available"])
        small=forensic.extract_rank_table(b"abc")
        self.assertFalse(small["available"])
        self.assertEqual(small["status"],"layout_unknown")

    def test_existing_iso_rejected_when_exe_digest_does_not_match(self):
        report=forensic.extract_rank_table(bytes(sample_wa()),slus=b"WRONG",
                                          rom_sha256=X15_SHA,
                                          known_rom_sha256=X15_SHA)
        self.assertFalse(report["runtime_verified"])
        self.assertTrue(report["known_x15_table_content"])
        self.assertFalse(rank_profile_for_image(X15_SHA,report)["runtime_verified"])

    def test_known_x15_requires_matching_iso_exe_and_fingerprint(self):
        fake_exe=b"FINGERPRINT-TEST"
        with patch.object(forensic,"KNOWN_X15_SLUS_SHA256",
                          hashlib.sha256(fake_exe).hexdigest()):
            report=forensic.extract_rank_table(bytes(sample_wa()),slus=fake_exe,
                                              rom_sha256=X15_SHA,
                                              known_rom_sha256=X15_SHA)
        self.assertTrue(report["runtime_verified"])
        self.assertTrue(report["criterion_names_verified"])
        self.assertEqual(report["rules"]["turns"][0],{"below":5,"points":12})
        self.assertEqual(rank_profile_for_image(X15_SHA,report)["base_points"],50)

    def test_no_rank_when_forensic_report_has_failure(self):
        report={"status":"divergent_rank_tables","available":False}
        output=rank_profile_for_image(X15_SHA,report)
        self.assertFalse(output["available"])
        self.assertEqual(output["rules"],{})


if __name__=="__main__":
    unittest.main()
