"""PS-X EXE ISO9660 end-of-sector zero-padding regressions (synthetic).

A missing, nonzero or overlapping extent must never be accepted.
The actual game image is intentionally not committed to the repository.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from dueltrace_exe_sector_padding import load_executable_sector_padding
from dueltrace_layout_discovery import inspect_psx_executable_header
from scanner_multiiso import SCAN_PARSER_REVISION


class FakeDisc:
    def __init__(self, *, extra=560, dirty=False, overlap=False, malformed=False):
        size = 0x800 + 0x1000
        data = bytearray(size)
        data[:8] = b"PS-X EXE"
        struct.pack_into("<I", data, 0x10, 0x80010000)
        struct.pack_into("<I", data, 0x18, 0x80010000)
        struct.pack_into("<I", data, 0x1C, 0x1000 + (0x1000 if malformed else 0))
        if dirty:
            data[-1] = 0x7E
        self.payload = bytes(data)
        self.length = size - extra
        self.files = {"BOOT.EXE": (20, self.length)}
        if overlap:
            self.files["ANOTHER.DAT"] = (22, 1600)

    def get(self, name):
        assert name == "BOOT.EXE"
        return self.payload[:self.length]

    def read(self, lba, size):
        assert lba == 20
        return self.payload[:size]


class PaddingTests(unittest.TestCase):
    def test_only_real_zero_bytes_in_existing_final_sector_are_recovered(self):
        disc = FakeDisc()
        partial = disc.get("BOOT.EXE")
        self.assertFalse(inspect_psx_executable_header(
            partial[:2048], len(partial))["headerCoherent"])
        result, info = load_executable_sector_padding(disc, "BOOT.EXE")
        self.assertEqual(result, disc.payload)
        self.assertEqual(len(result) - len(partial), 560)
        self.assertEqual(info["state"], "padding_zero_verificado")
        self.assertEqual(info["paddingBytes"], 560)
        self.assertTrue(info["headerCoherent"])
        self.assertTrue(inspect_psx_executable_header(
            result[:2048], len(result))["headerCoherent"])

    def test_nonzero_bytes_never_recovered_as_padding(self):
        disc = FakeDisc(dirty=True)
        result, info = load_executable_sector_padding(disc, "BOOT.EXE")
        self.assertEqual(result, disc.get("BOOT.EXE"))
        self.assertEqual(info["state"], "padding_nao_nulo_ou_incoerente")
        self.assertFalse(info["headerCoherent"])

    def test_overlap_with_another_entry_is_rejected(self):
        disc = FakeDisc(overlap=True)
        result, info = load_executable_sector_padding(disc, "BOOT.EXE")
        self.assertEqual(result, disc.get("BOOT.EXE"))
        self.assertEqual(info["state"], "extents_sobrepostos")

    def test_declared_length_beyond_final_sector_is_not_guessed(self):
        disc = FakeDisc(malformed=True)
        result, info = load_executable_sector_padding(disc, "BOOT.EXE")
        self.assertEqual(result, disc.get("BOOT.EXE"))
        self.assertEqual(info["state"], "declaracao_incompativel")

    def test_exact_normal_executables_are_not_changed(self):
        disc = FakeDisc(extra=0)
        original = disc.get("BOOT.EXE")
        result, info = load_executable_sector_padding(disc, "BOOT.EXE")
        self.assertEqual(result, original)
        self.assertEqual(info["state"], "nao_necessario")
        self.assertGreaterEqual(SCAN_PARSER_REVISION, 28)


if __name__ == "__main__":
    unittest.main()
