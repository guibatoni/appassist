"""Live deck must come from confirmed RAM, not a random save or hand buffer."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_live_deck import parse_live_deck,derive_host_deck_address,DECK_BYTES
from dueltrace_epsxe_memory import HAND_OFFSET
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_memory_cards import MemoryCardStore

SHA="a"*64
OTHER="b"*64


class LiveDeckTests(unittest.TestCase):
    def test_known_ps1_offset_derived_only_from_confirmed_hand_anchor(self):
        self.assertEqual(
            derive_host_deck_address(0xB00000+HAND_OFFSET),
            0xB00000+0x1D0200)
        for invalid in (None,0,-1,"0xBFF484",True):
            self.assertIsNone(derive_host_deck_address(invalid))

    def test_cards_validate_full_80_byte_deck(self):
        ids=list(range(1,41))
        raw=b"".join(x.to_bytes(2,"little") for x in ids)
        self.assertEqual(len(raw),DECK_BYTES)
        self.assertEqual(parse_live_deck(raw),ids)
        self.assertIsNone(parse_live_deck(raw[:-1]))
        self.assertIsNone(parse_live_deck(b"\x00"*80))
        self.assertIsNone(parse_live_deck(None))
        corrupted=bytearray(raw);corrupted[0:2]=(723).to_bytes(2,"little")
        self.assertIsNone(parse_live_deck(bytes(corrupted)))

    def test_bridge_does_not_trust_unlaunched_or_wrong_iso_process(self):
        bridge=object.__new__(DueltraceWebBridge)
        bridge._launched_rom_sha=SHA
        bridge._process=Mock(pid=1234,poll=Mock(return_value=None))
        fake={"ready":True,"deckIds":list(range(1,41)),"pid":1234}
        with patch("dueltrace_live_deck.read_live_deck",return_value=fake) as read:
            self.assertIsNone(bridge._get_confirmed_live_deck(OTHER))
            read.assert_not_called()
            self.assertEqual(bridge._get_confirmed_live_deck(SHA),fake)
            read.assert_called_once_with(1234)
        bridge._process.poll.return_value=1
        with patch("dueltrace_live_deck.read_live_deck") as read:
            self.assertIsNone(bridge._get_confirmed_live_deck(SHA))
            read.assert_not_called()

    def test_save_verified_live_snapshot_without_touching_memory_card(self):
        with tempfile.TemporaryDirectory() as temp:
            store=MemoryCardStore(Path(temp)/"data")
            ids=list(range(1,41))
            result=store.save_live_snapshot(SHA,"Deck RAM",ids)
            self.assertTrue(result["saved"])
            found=store.read(SHA)["saved"]
            self.assertEqual(len(found),1)
            self.assertEqual(found[0]["ids"],ids)
            self.assertEqual(found[0]["source"],"live_ram")
            self.assertFalse(store.read(OTHER)["saved"])

    def test_bridge_only_marks_live_verified_if_real_ram_data_available(self):
        src=(ROOT/"scanner/dueltrace_web_bridge.py").read_text("utf8")
        self.assertIn("self._get_confirmed_live_deck(sha)",src)
        self.assertIn("live is not None",src)
        self.assertIn("activeInEmulatorVerified",src)
        self.assertIn("save_live_snapshot(",src)


if __name__=="__main__":
    unittest.main()
