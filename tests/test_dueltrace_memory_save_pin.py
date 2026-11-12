"""v0.17.3 regression: per-ISO PS1 save-slot preference survives restarts.

The confirmed user's reference is block 4, sequence initially 3.
The sequence is a version counter; a save can advance it without moving
the selected block or changing the save identity.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from dueltrace_memory_cards import MemoryCardStore, SIZE, BLOCK
from dueltrace_save_integrity import TABLES, STATE_SIZE, _mask_words, crc_xmodem

SHA_A="a"*64
SHA_B="b"*64


def frame_checksum(data,at):
    c=0
    for x in data[at:at+127]:
        c^=x
    data[at+127]=c


def one_save(ids,*,sequence=3,duelist=123):
    img=bytearray(SIZE)
    img[:2]=b"MC"
    frame_checksum(img,0)
    start=128
    img[start:start+4]=b"\x51\x00\x00\x00"
    img[start+4:start+8]=BLOCK.to_bytes(4,"little")
    img[start+8:start+10]=b"\xff\xff"
    save_name=b"BASLUS-01411-YUGIOH"
    img[start+10:start+10+len(save_name)]=save_name
    frame_checksum(img,start)
    img[BLOCK:BLOCK+3]=b"SC\x11"
    state=bytearray(STATE_SIZE)
    struct.pack_into("<40H",state,0,*ids)
    struct.pack_into("<i",state,0x334,duelist)
    struct.pack_into("<I",state,0x404,sequence)
    for start,length,at,count,crc_at in TABLES:
        crc=crc_xmodem(state[start:start+length])
        struct.pack_into("<HH",state,crc_at,crc,crc)
        for idx,word in enumerate(_mask_words(crc,count)):
            struct.pack_into("<I",state,at-4*idx,word)
    img[BLOCK+0x200:BLOCK+0x200+STATE_SIZE]=state
    img[BLOCK+0x880:BLOCK+0x880+STATE_SIZE]=state
    return bytes(img)


def card_with_two_saves(*,sequence=3,duelist=123):
    first=one_save(list(range(1,41)),sequence=2,duelist=55)
    fourth=one_save(list(range(41,81)),sequence=sequence,duelist=duelist)
    image=bytearray(first)
    image[4*128:5*128]=fourth[128:256]
    image[4*BLOCK:5*BLOCK]=fourth[BLOCK:2*BLOCK]
    return bytes(image)


class MemoryCardPinnedSlotTests(unittest.TestCase):
    def test_pins_block_four_per_mod_and_ignores_sequence_increment(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            original=folder/"epsxe000.mcr"
            original.write_bytes(card_with_two_saves(sequence=3))
            store=MemoryCardStore(folder/"appdata")
            self.assertTrue(store.select(SHA_A,original)["selected"])
            self.assertEqual(store.read(SHA_A)["deckIds"],[])
            store.select_save(SHA_A,4)
            result=store.read(SHA_A)
            self.assertEqual(result["selectedBlock"],4)
            self.assertTrue(result["savePinned"])
            self.assertEqual(result["deckIds"],list(range(41,81)))
            self.assertEqual(result["saves"][1]["saveSequence"],3)
            # New object = app restarted; re-selecting the card is also safe.
            restarted=MemoryCardStore(folder/"appdata")
            self.assertEqual(restarted.read(SHA_A)["selectedBlock"],4)
            restarted.select(SHA_A,original)
            self.assertEqual(restarted.read(SHA_A)["selectedBlock"],4)
            # Game saves again, updates sequence and cards, keeps slot+identity.
            original.write_bytes(card_with_two_saves(sequence=4))
            latest=restarted.read(SHA_A)
            self.assertEqual(latest["selectedBlock"],4)
            self.assertEqual(latest["saves"][1]["saveSequence"],4)
            self.assertEqual(latest["deckIds"],list(range(41,81)))
            self.assertEqual(original.stat().st_size,SIZE)

    def test_another_mod_does_not_inherit_block_four(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.select(SHA_A,card)
            store.select_save(SHA_A,4)
            store.select(SHA_B,card)
            self.assertIsNone(store.read(SHA_B)["selectedBlock"])
            self.assertEqual(store.read(SHA_B)["deckIds"],[])
            self.assertEqual(store.read(SHA_A)["selectedBlock"],4)

    def test_does_not_silently_switch_to_wrong_save_if_block_four_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.select(SHA_A,card)
            store.select_save(SHA_A,4)
            # Another playthrough uses the SAME physical block 4.
            card.write_bytes(card_with_two_saves(sequence=2,duelist=987))
            wrong=store.read(SHA_A)
            self.assertEqual(wrong["deckIds"],[])
            self.assertIn("não corresponde",wrong["status"])
            # Reselect should not erase a pin on the same card while unavailable.
            store.select(SHA_A,card)
            self.assertEqual(store.read(SHA_A)["deckIds"],[])
            card.write_bytes(card_with_two_saves(sequence=5,duelist=123))
            correct=store.read(SHA_A)
            self.assertEqual(correct["selectedBlock"],4)
            self.assertEqual(correct["deckIds"],list(range(41,81)))

    def test_upgrade_from_v0172_block_only_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.binding_file.parent.mkdir(parents=True)
            store.binding_file.write_text(
                json.dumps({"schema":1,"links":{SHA_A:{
                    "path":str(card.resolve()),"selectedBlock":4}}}),
                encoding="utf-8")
            self.assertEqual(store.read(SHA_A)["selectedBlock"],4)
            store.select(SHA_A,card)
            binding=store._binding_data()["links"][SHA_A]
            self.assertEqual(binding["selectedBlock"],4)
            self.assertEqual(binding["selectedDuelistCode"],123)
            self.assertTrue(binding["selectedSaveName"].endswith("YUGIOH"))

    def test_choose_other_slot_explicitly_overrides_preference(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.select(SHA_A,card)
            store.select_save(SHA_A,4)
            store.select_save(SHA_A,1)
            self.assertEqual(store.read(SHA_A)["selectedBlock"],1)
            self.assertEqual(store.read(SHA_A)["deckIds"],list(range(1,41)))


    def test_each_block_is_labeled_by_its_explicit_mod_link(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            card=folder/"epsxe000.mcr"
            raw=card_with_two_saves(sequence=3)
            card.write_bytes(raw)
            root=folder/"userdata"
            store=MemoryCardStore(root)
            store.select(SHA_A,card,mod_name="RISING OF WICKED GODS")
            store.select_save(SHA_A,4,mod_name="RISING OF WICKED GODS")
            first=store.read(SHA_A,mod_name="RISING OF WICKED GODS")
            self.assertEqual(first["selectedBlock"],4)
            self.assertIn("RISING OF WICKED GODS",first["saveDisplayName"])
            self.assertIn("seq. 3",first["saveDisplayName"])
            self.assertEqual(first["saves"][0]["association"],"unassigned")
            self.assertEqual(first["saves"][1]["association"],"linked_current_mod")
            # Every auto-snapshot is associated to the linked slot only.
            snapshots=store._saved(SHA_A)
            self.assertEqual(len(snapshots),1)
            self.assertIn("Bloco 4",snapshots[0]["name"])
            self.assertEqual(card.read_bytes(),raw)
            other=MemoryCardStore(root)
            self.assertEqual(other.read(SHA_A)["selectedBlock"],4)
            self.assertIn("RISING OF WICKED GODS",other.read(SHA_A)["saveDisplayName"])

    def test_same_card_with_another_mod_is_not_mislabeled(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.select(SHA_A,card,mod_name="RISING OF WICKED GODS")
            store.select_save(SHA_A,4,mod_name="RISING OF WICKED GODS")
            store.select(SHA_B,card,mod_name="Remaster X15")
            second=store.read(SHA_B,mod_name="Remaster X15")
            block_four=next(s for s in second["saves"] if s["block"]==4)
            self.assertEqual(block_four["association"],"linked_other_mod")
            self.assertIn("RISING OF WICKED GODS",block_four["displayName"])
            self.assertNotIn("Remaster X15",block_four["displayName"])
            store.select_save(SHA_B,1,mod_name="Remaster X15")
            assert store.read(SHA_A)["selectedBlock"]==4
            second=store.read(SHA_B,mod_name="Remaster X15")
            self.assertIn("Remaster X15",second["saveDisplayName"])
            self.assertEqual(second["saves"][1]["association"],"linked_other_mod")
            self.assertEqual(len(store._saved(SHA_B)),1)

    def test_old_auto_snapshots_from_other_blocks_are_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);card=folder/"epsxe000.mcr"
            card.write_bytes(card_with_two_saves())
            store=MemoryCardStore(folder/"userdata")
            store.select(SHA_A,card,mod_name="RISING")
            store.select_save(SHA_A,4,mod_name="RISING")
            store.read(SHA_A)  # Create the valid current snapshot first.
            snapshot_dir=store.home/"deck_snapshots"/SHA_A
            legacy=snapshot_dir/"auto-old-bug.json"
            legacy.write_text(json.dumps({
                "schema":1,"rom_sha256":SHA_A,"id":"auto-old-bug",
                "name":"Wrong old auto deck","source":"memory_card",
                "cards":list(range(1,41)),
                "saveName":"BASLUS-01411-YUGIOH",
                "saveIntegrityVerified":True
            }),encoding="utf8")
            names=[row["name"] for row in store.read(SHA_A)["saved"]]
            self.assertNotIn("Wrong old auto deck",names)
            self.assertTrue(any("Bloco 4" in name for name in names))


if __name__=="__main__":
    unittest.main()
