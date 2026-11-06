"""Synthetic tests for unique FD length-metadata opponent name runs.

The fixture is algorithmic and contains no original game resources.
All data must remain structural until verified in a real game session.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
sys.path.insert(0, str(ROOT / "tests"))

from scanner_multiiso import (
    SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS,
    SCAN_PARSER_REVISION, decode_names)
from test_dueltrace_card_opponent_discovery import synthetic_executable, CODES
from dueltrace_inline_fd_names import probe_inline_fd_names
from dueltrace_independent_opponents import (
    discover_independent_opponents, compact_opponent_evidence)

FIRST = 0x329
SHA = "a" * 64


def synthetic_fd_names(*, broken_index=None, second_run=False):
    exe = bytearray(synthetic_executable(shift=0))
    last = SLUS_TEXT_BASE + 0xC000
    if len(exe) < last:
        exe.extend(b"\x00" * (last - len(exe)))
    for start in ((FIRST, 0xB000), (0x390, 0xB400)) if second_run else (
            (FIRST, 0xB000),):
        base_index, text_offset = start
        for ordinal in range(39):
            name = "TEST%04d" % (ordinal + 1)
            glyph_bytes = bytes(CODES[ch] for ch in name)
            pointer = text_offset + ordinal * 24
            position = SLUS_TEXT_BASE + pointer
            suffix_value = 0x3200 + len(glyph_bytes)
            raw = glyph_bytes + b"\xFD" + struct.pack("<H", suffix_value) + b"\xFF"
            if broken_index == ordinal and base_index == FIRST:
                raw = glyph_bytes + b"\xFD" + struct.pack("<H", suffix_value + 1) + b"\xFF"
            exe[position:position + len(raw)] = raw
            struct.pack_into("<H", exe, SLUS_PTR_BASE + 2 * (base_index + ordinal),
                             pointer)
    return bytes(exe)


def discover(exe):
    return discover_independent_opponents(
        exe, pointer_base=SLUS_PTR_BASE, text_base=SLUS_TEXT_BASE,
        glyph_base=SLUS_GLYPHS, rom_sha256=SHA)


class InlineFdTests(unittest.TestCase):
    def test_39_unique_prefix_fd_field_ff_accepts_only_structural_names(self):
        exe = synthetic_fd_names()
        direct = probe_inline_fd_names(
            exe, pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE, glyph_base=SLUS_GLYPHS)
        self.assertEqual(direct["candidateCount"], 1)
        self.assertEqual(direct["selected"]["startIndex"], FIRST)
        self.assertEqual(direct["candidates"][0]["sharedFieldBase"], 0x3200)
        old_opps, cards, _ = decode_names(exe)
        self.assertEqual(old_opps, [])
        self.assertEqual(len(cards), 722)
        discovered = discover(exe)
        self.assertEqual(discovered["state"], "layout_fd_inline_unico_estrutural")
        self.assertEqual(discovered["selected"]["opponents"][0]["nome"], "TEST0001")
        self.assertEqual(discovered["selected"]["opponents"][-1]["nome"], "TEST0039")
        self.assertEqual(discovered["candidateOpponentCount"], 39)
        self.assertFalse(discovered["inGameVerified"])
        self.assertFalse(discovered["rankVerified"])
        self.assertFalse(discovered["dropsVerified"])
        compact = compact_opponent_evidence(discovered)
        self.assertEqual(compact["reasonCode"], "nomes_estruturais")
        self.assertNotIn("TEST", str(compact))
        self.assertEqual(compact["inlineFdEvidence"]["candidateCount"], 1)

    def test_mismatch_in_one_field_does_not_publish_any_opponents(self):
        exe = synthetic_fd_names(broken_index=12)
        direct = probe_inline_fd_names(
            exe, pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE, glyph_base=SLUS_GLYPHS)
        self.assertEqual(direct["candidateCount"], 0)
        self.assertIsNone(direct["selected"])
        self.assertIsNone(discover(exe)["selected"])

    def test_two_full_runs_are_ambiguous_and_are_not_selected(self):
        exe = synthetic_fd_names(second_run=True)
        direct = probe_inline_fd_names(
            exe, pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE, glyph_base=SLUS_GLYPHS)
        self.assertEqual(direct["candidateCount"], 2)
        self.assertEqual(direct["state"], "layouts_fd_inline_ambiguos")
        self.assertIsNone(direct["selected"])
        self.assertIsNone(discover(exe)["selected"])

    def test_garbage_executable_cannot_become_a_name_catalogue(self):
        direct = probe_inline_fd_names(
            b"\xFF" * 4096, pointer_base=0, text_base=0, glyph_base=0)
        self.assertIsNone(direct["selected"])
        self.assertFalse(direct["inGameVerified"])
        self.assertGreaterEqual(SCAN_PARSER_REVISION, 28)


if __name__ == "__main__":
    unittest.main()
