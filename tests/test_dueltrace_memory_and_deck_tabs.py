"""v0.17: deck pools, PS1 memory-card binding, snapshots and fusion regressions."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_memory_cards import MemoryCardStore, parse_memory_card, SIZE, BLOCK
from dueltrace_deck_library import opponent_deck_view, fusion_pairs_for_deck
from dueltrace_web_security import ProtectedDesktopApi

SHA="a"*64
OTHER="b"*64


def frame_checksum(data,at):
    val=0
    for n in range(127):
        val ^= data[at+n]
    data[at+127]=val


def memory_bytes(ids=None,save_name=b"BASLUS-01411-YUGIOH"):
    image=bytearray(SIZE)
    image[:2]=b"MC"
    frame_checksum(image,0)
    offset=128
    image[offset:offset+4]=b"\x51\x00\x00\x00"
    image[offset+4:offset+8]=(8192).to_bytes(4,"little")
    image[offset+8:offset+10]=b"\xff\xff"
    image[offset+10:offset+10+len(save_name)]=save_name
    frame_checksum(image,offset)
    image[BLOCK:BLOCK+3]=b"SC\x11"
    ids=ids if ids is not None else list(range(1,41))
    for i,cid in enumerate(ids):
        image[BLOCK+0x200+i*2:BLOCK+0x202+i*2]=cid.to_bytes(2,"little")
    return bytes(image)


class MemoryCardTests(unittest.TestCase):
    def test_realistic_ps1_header_40_cards(self):
        data=parse_memory_card(memory_bytes())
        self.assertEqual(data["detectedSaveCount"],1)
        self.assertEqual(data["saves"][0]["deckIds"],list(range(1,41)))
        self.assertFalse(data["gameIntegrityVerified"])

    def test_invalid_directory_checksum_rejected_without_guessing(self):
        blob=bytearray(memory_bytes())
        blob[128+8]=0
        self.assertEqual(parse_memory_card(bytes(blob))["detectedSaveCount"],0)

    def test_invalid_save_or_40_card_range_rejected(self):
        self.assertEqual(parse_memory_card(memory_bytes([1]*39+[723]))["detectedSaveCount"],0)
        blob=bytearray(memory_bytes());blob[BLOCK:BLOCK+2]=b"ZZ"
        self.assertEqual(parse_memory_card(bytes(blob))["detectedSaveCount"],0)
        with self.assertRaises(ValueError):
            parse_memory_card(memory_bytes()[:-1])
        with self.assertRaises(ValueError):
            parse_memory_card(b"not a memory card")

    def test_select_reopen_autobackup_and_deck_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/"epsxe000.mcr"
            original=memory_bytes()
            source.write_bytes(original)
            store=MemoryCardStore(root/"DUELTRACE_DATA")
            selected=store.select(SHA,source)
            self.assertTrue(selected["selected"])
            one=store.read(SHA)
            self.assertEqual(one["deckIds"],list(range(1,41)))
            self.assertTrue(one["linked"])
            self.assertGreater(len(one["saved"]),0)
            initial=one["backupFingerprint"]
            self.assertEqual(source.read_bytes(),original)
            another=store.read(OTHER)
            self.assertFalse(another["linked"])
            ids=list(range(2,42))
            source.write_bytes(memory_bytes(ids))
            two=store.read(SHA)
            self.assertEqual(two["deckIds"],ids)
            self.assertNotEqual(two["backupFingerprint"],initial)
            snapshots=list((root/"DUELTRACE_DATA"/"memory_card_backups"/SHA).glob("*.mcr"))
            self.assertEqual(len(snapshots),2)
            self.assertGreaterEqual(len(two["saved"]),2)
            self.assertEqual(snapshots[0].stat().st_size,131072)

    def test_save_named_deck_without_touching_emulator(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            card=root/"memcard1.mcd"
            raw=memory_bytes()
            card.write_bytes(raw)
            store=MemoryCardStore(root/"userdata")
            store.select(SHA,card)
            saved=store.save_snapshot(SHA,"Deck de farm")
            self.assertTrue(saved["saved"])
            self.assertIn("Deck de farm",[x["name"] for x in store.read(SHA)["saved"]])
            self.assertEqual(card.read_bytes(),raw)
            with self.assertRaises(ValueError):
                store.save_snapshot(SHA,"")

    def test_other_game_is_not_interpreted_as_yugioh(self):
        self.assertFalse(parse_memory_card(memory_bytes(save_name=b"BASLUS-99999-OTHER"))["saves"])

    def test_bad_selection_keeps_prior_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            good=root/"good.mcr";good.write_bytes(memory_bytes())
            bad=root/"bad.mcr";bad.write_bytes(b"wrong")
            store=MemoryCardStore(root/"app")
            store.select(SHA,good)
            with self.assertRaises(ValueError):
                store.select(SHA,bad)
            self.assertEqual(store.read(SHA)["deckCount"] if "deckCount" in store.read(SHA) else len(store.read(SHA)["deckIds"]),40)


class OpponentDeckTests(unittest.TestCase):
    def profile(self):
        return {"verified":{"oponentes":"verificado"},
                "opponents":[{"id":1,"name":"Simon"},{"id":2,"name":"Jono"}],
                "decks":[{"opponent_id":1,"card_id":1,"weight":1024},
                         {"opponent_id":1,"card_id":2,"weight":1024}]}

    def test_weights_are_probabilities_not_fixed_deck(self):
        row=opponent_deck_view(self.profile(),1,cards={1:{"name":"Dragão"},2:{"name":"Fada"}})
        self.assertTrue(row["available"])
        self.assertEqual(row["totalWeight"],2048)
        self.assertFalse(row["fixed"])
        self.assertEqual(row["cards"][0]["chancePercent"],50)
        self.assertIn("não deck fixo",row["status"])

    def test_unverified_opponent_identity_is_never_promoted(self):
        p=self.profile();p["verified"]["oponentes"]="extraidos_estruturalmente"
        self.assertFalse(opponent_deck_view(p,1,cards={})["available"])
        with self.assertRaises(ValueError):
            opponent_deck_view(p,40,cards={})

    def test_empty_decks_are_explicit(self):
        self.assertFalse(opponent_deck_view(self.profile(),2,cards={})["available"])

    def test_fusion_requires_both_materials_and_sufficient_copies(self):
        ids=[1]+[2]*39
        recipes=[{"a":1,"b":2,"result":3},{"a":1,"b":1,"result":4},
                 {"a":2,"b":2,"result":5}]
        data=fusion_pairs_for_deck(ids,recipes,{3:{"name":"Resultado"}})
        self.assertEqual(data["total"],2)
        self.assertEqual({r["result"] for r in data["rows"]},{3,5})

    def test_conflicting_pairs_are_quarantined(self):
        ids=[1,2]+[3]*38
        recipes=[{"a":1,"b":2,"result":5},{"a":2,"b":1,"result":6}]
        data=fusion_pairs_for_deck(ids,recipes,{})
        self.assertEqual(data["total"],0)
        self.assertEqual(data["conflictsOmitted"],1)


class ClientContractTests(unittest.TestCase):
    def test_nav_and_file_picker_are_available(self):
        sidebar=(ROOT/"web/components/shell/sidebar.tsx").read_text("utf8")
        main=(ROOT/"web/components/desktop/desktop-page.tsx").read_text("utf8")
        picker=(ROOT/"scanner/dueltrace_web_desktop.py").read_text("utf8")
        self.assertIn('href: "/oponentes"',sidebar)
        self.assertIn('href: "/decks"',sidebar)
        self.assertIn("Selecionar Memory Card",main)
        self.assertIn('kind=="memory_card"',picker)
        self.assertIn('page==="decks"',main)
        self.assertIn('page==="oponentes"',main)

    def test_native_api_requires_token(self):
        backend=Mock()
        api=ProtectedDesktopApi(backend,"x"*64)
        with self.assertRaises(PermissionError):
            api.select_memory_card("wrong")
        with self.assertRaises(PermissionError):
            api.get_deck_library("wrong")
        with self.assertRaises(PermissionError):
            api.get_opponent_deck("wrong",1)
        api.get_deck_library("x"*64)
        backend.get_deck_library.assert_called_once_with("")


if __name__=="__main__":
    unittest.main()
